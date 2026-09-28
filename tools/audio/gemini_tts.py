"""Gemini generateContent text-to-speech provider.

This adapter accepts raw or containerized audio returned by Gemini, normalizes
it to 24 kHz mono PCM when needed, and wraps it as a local WAV artifact. Voice
selection remains a per-production model decision and is therefore
intentionally required with no project default.
"""

from __future__ import annotations

import base64
import io
import os
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class GeminiTTS(BaseTool):
    name = "gemini_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "gemini"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    MODEL = "gemini-3.1-flash-tts-preview"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    KEY_ENVS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    SAMPLE_RATE = 24_000

    dependencies = ["env:GEMINI_API_KEY|GOOGLE_API_KEY|~/.ai-daily-automation/.env"]
    install_instructions = (
        "Set GEMINI_API_KEY or GOOGLE_API_KEY, or keep GEMINI_API_KEY in the shared "
        "~/.ai-daily-automation/.env used by the video project. Do not duplicate the "
        "credential in project files or select a voice globally."
    )
    fallback_tools: list[str] = []
    agent_skills = ["text-to-speech"]
    capabilities = ["text_to_speech", "voice_selection", "multilingual"]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml": False,
    }
    best_for = [
        "Gemini natural narration through generateContent audio",
        "24 kHz PCM narration with per-production voice selection",
    ]
    not_good_for = ["voice cloning", "offline production", "SSML input"]

    input_schema = {
        "type": "object",
        "required": ["text", "voice", "output_path"],
        "properties": {
            "text": {"type": "string", "description": "Verbatim narration text"},
            "voice": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Gemini prebuilt voice selected for this production. "
                    "There is intentionally no default voice."
                ),
            },
            "language_code": {
                "type": "string",
                "default": "cmn-CN",
                "description": "BCP-47 language code passed to Gemini speechConfig",
            },
            "model": {
                "type": "string",
                "const": MODEL,
                "default": MODEL,
            },
            "output_path": {
                "type": "string",
                "description": "Absolute WAV output path",
            },
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    idempotency_key_fields = ["text", "voice", "language_code", "model"]
    side_effects = [
        "calls the Gemini generateContent API once",
        "writes a 24 kHz mono WAV file to output_path",
    ]
    user_visible_verification = ["Listen to the generated narration and verify the selected voice"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._resolve_credential() else ToolStatus.UNAVAILABLE

    @classmethod
    def _resolve_credential(cls) -> str:
        """Reuse the video project's single Google credential without copying it."""
        for name in cls.KEY_ENVS:
            value = os.environ.get(name, "").strip()
            if value:
                return value

        user_root = os.environ.get("USERPROFILE") or str(Path.home())
        private_env = Path(user_root) / ".ai-daily-automation" / ".env"
        try:
            lines = private_env.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""
        values: dict[str, str] = {}
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
        for name in cls.KEY_ENVS:
            if values.get(name):
                return values[name]
        return ""

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 120.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        credential = self._resolve_credential()
        if not credential:
            return ToolResult(
                success=False,
                error="Gemini TTS credential is unavailable. " + self.install_instructions,
                data={"error_code": "credential_unavailable", "fallback_used": False},
            )

        voice = str(inputs.get("voice") or "").strip()
        if not voice:
            return ToolResult(
                success=False,
                error="Gemini TTS requires a voice selected by the production plan.",
                data={"error_code": "voice_required", "fallback_used": False},
            )

        model = str(inputs.get("model") or self.MODEL)
        if model != self.MODEL:
            return ToolResult(
                success=False,
                error=f"Unsupported Gemini TTS model: {model}",
                data={"error_code": "model_invalid", "fallback_used": False},
            )

        output = Path(str(inputs.get("output_path") or ""))
        if output.suffix.lower() != ".wav":
            return ToolResult(
                success=False,
                error="Gemini TTS output_path must end in .wav.",
                data={"error_code": "output_format_invalid", "fallback_used": False},
            )
        if output.exists():
            return ToolResult(
                success=False,
                error="Gemini TTS output_path already exists; refusing to overwrite it.",
                data={"error_code": "output_exists", "fallback_used": False},
            )

        started = time.time()
        try:
            pcm, response_meta = self._request(
                text=str(inputs["text"]),
                voice=voice,
                language_code=str(inputs.get("language_code") or "cmn-CN"),
                credential=credential,
                model=model,
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            partial = output.with_name(f"{output.name}.partial")
            try:
                with wave.open(str(partial), "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(self.SAMPLE_RATE)
                    audio.writeframes(pcm)
                partial.replace(output)
            finally:
                if partial.exists():
                    partial.unlink()
        except Exception as exc:
            safe_error = str(exc).replace(credential, "[REDACTED]")
            return ToolResult(
                success=False,
                error=f"Gemini TTS failed: {safe_error}",
                data={"error_code": "provider_failed", "fallback_used": False},
            )

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "executor": "Gemini API generateContent TTS",
                "model": model,
                "voice": voice,
                "language_code": str(inputs.get("language_code") or "cmn-CN"),
                "output": str(output),
                "format": "wav",
                "raw_audio": {
                    "format": "pcm_s16le",
                    "sample_rate": self.SAMPLE_RATE,
                    "channels": 1,
                    "bytes": len(pcm),
                },
                "provider_request_count": 1,
                "retry_dispatched": False,
                "fallback_used": False,
                **response_meta,
            },
            artifacts=[str(output)],
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )

    def _request(
        self,
        *,
        text: str,
        voice: str,
        language_code: str,
        credential: str,
        model: str,
    ) -> tuple[bytes, dict[str, Any]]:
        import requests

        response = requests.post(
            f"{self.BASE_URL}/models/{model}:generateContent",
            headers={"content-type": "application/json", "x-goog-api-key": credential},
            json={
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "languageCode": language_code,
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": voice}
                        },
                    },
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        parts: list[dict[str, Any]] = []
        for candidate in candidates if isinstance(candidates, list) else []:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            candidate_parts = content.get("parts") if isinstance(content, dict) else None
            if isinstance(candidate_parts, list):
                parts.extend(part for part in candidate_parts if isinstance(part, dict))

        audio_parts: list[bytes] = []
        mime_types: list[str] = []
        normalized_audio_parts = 0
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            mime_type = str(inline.get("mimeType") or inline.get("mime_type") or "")
            data = inline.get("data")
            if not isinstance(data, str) or not data:
                continue
            decoded = base64.b64decode(data, validate=True)
            normalized = self._normalize_audio_part(decoded, mime_type)
            if normalized is None:
                continue
            pcm_part, converted = normalized
            audio_parts.append(pcm_part)
            mime_types.append(mime_type)
            normalized_audio_parts += int(converted)

        pcm = b"".join(audio_parts)
        if not pcm or len(pcm) % 2:
            raise ValueError("Gemini returned no valid 24 kHz PCM audio")
        return pcm, {
            "model_version": payload.get("modelVersion") if isinstance(payload, dict) else None,
            "response": {
                "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
                "part_count": len(parts),
                "audio_parts": len(audio_parts),
                "mime_types": mime_types,
                "normalized_audio_parts": normalized_audio_parts,
            },
        }

    @classmethod
    def _normalize_audio_part(
        cls, decoded: bytes, mime_type: str
    ) -> tuple[bytes, bool] | None:
        normalized_mime = mime_type.strip().lower()
        base_mime = normalized_mime.split(";", 1)[0].strip()

        looks_like_wav = (
            len(decoded) >= 12
            and decoded[:4] in {b"RIFF", b"RIFX", b"RF64"}
            and decoded[8:12] == b"WAVE"
        )
        if looks_like_wav:
            try:
                with wave.open(io.BytesIO(decoded), "rb") as audio:
                    if (
                        audio.getframerate() == cls.SAMPLE_RATE
                        and audio.getnchannels() == 1
                        and audio.getsampwidth() == 2
                    ):
                        return audio.readframes(audio.getnframes()), False
            except (EOFError, wave.Error):
                pass

        if base_mime in {"", "audio/l16", "audio/pcm", "audio/x-pcm"}:
            rate_match = re.search(r"(?:^|;)\s*rate=(\d+)", normalized_mime)
            source_rate = int(rate_match.group(1)) if rate_match else cls.SAMPLE_RATE
            if source_rate == cls.SAMPLE_RATE:
                return decoded, False
            return cls._transcode_audio(
                decoded,
                input_args=["-f", "s16le", "-ar", str(source_rate), "-ac", "1"],
            ), True

        if base_mime.startswith("audio/") or looks_like_wav:
            return cls._transcode_audio(decoded), True
        return None

    @classmethod
    def _transcode_audio(
        cls, decoded: bytes, *, input_args: list[str] | None = None
    ) -> bytes:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise ValueError(
                "Gemini returned audio that requires local conversion, but ffmpeg is unavailable"
            )
        command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
        command.extend(input_args or [])
        command.extend(
            [
                "-i",
                "pipe:0",
                "-vn",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(cls.SAMPLE_RATE),
                "-ac",
                "1",
                "pipe:1",
            ]
        )
        result = subprocess.run(
            command,
            input=decoded,
            capture_output=True,
            check=False,
            timeout=30,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            ),
        )
        if result.returncode != 0 or not result.stdout or len(result.stdout) % 2:
            raise ValueError("Gemini returned audio that ffmpeg could not normalize")
        return result.stdout
