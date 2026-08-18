"""Grok text-to-speech through the user's OAuth-backed grok-cli."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolCommandError,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class GrokCliTTS(BaseTool):
    """Expose ``grok-cli tts`` as an OpenMontage speech provider."""

    name = "grok_cli_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "grok"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["cmd:grok-cli"]
    install_instructions = (
        "Install grok-cli and authenticate it with an OAuth auth file. "
        "Set GROK_CLI_AUTH_FILE only when the file is not at ~/.grok-cli/auth.json."
    )
    agent_skills = ["grok-cli-tts"]
    capabilities = ["text_to_speech", "voice_selection", "multilingual"]
    supports = {
        "multilingual": True,
        "native_audio": True,
        "oauth_subscription": True,
        "voice_selection": True,
        "output_mp3": True,
        "output_wav": True,
    }
    best_for = [
        "narration using an existing Grok subscription",
        "multilingual speech through a local OAuth CLI",
    ]
    not_good_for = ["offline generation", "USD cost estimation for subscription quota"]
    fallback_tools: list[str] = []

    input_schema = {
        "type": "object",
        "required": ["text", "output_path"],
        "properties": {
            "text": {"type": "string"},
            "voice_id": {"type": "string", "default": "ara"},
            "language_code": {"type": "string", "default": "zh"},
            "output_format": {"type": "string", "default": "mp3"},
            "format": {"type": "string", "default": "mp3"},
            "sample_rate": {"type": "integer", "minimum": 8000},
            "bit_rate": {"type": "integer", "minimum": 8000},
            "optimize_streaming_latency": {"type": "integer", "minimum": 0},
            "text_normalization": {"type": "string"},
            "apply_text_normalization": {"type": "string"},
            "model": {"type": "string"},
            "timeout_seconds": {"type": "integer", "minimum": 30, "default": 120},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "text",
        "voice_id",
        "language_code",
        "output_format",
        "model",
    ]
    side_effects = [
        "consumes the user's Grok subscription quota",
        "writes an audio file to output_path",
    ]
    user_visible_verification = [
        "Listen for intelligibility, pronunciation, pacing, and voice suitability"
    ]

    @staticmethod
    def _auth_file_path() -> Path:
        configured = os.environ.get("GROK_CLI_AUTH_FILE")
        if configured:
            return Path(configured).expanduser().resolve()
        return (Path.home() / ".grok-cli" / "auth.json").resolve()

    def get_status(self) -> ToolStatus:
        if shutil.which("grok-cli") is None:
            return ToolStatus.UNAVAILABLE
        if not self._auth_file_path().is_file():
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """The CLI exposes subscription quota, not a trustworthy USD unit price."""
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(int(inputs.get("timeout_seconds", 120)))

    @staticmethod
    def _output_format(inputs: dict[str, Any]) -> str:
        requested = str(inputs.get("output_format") or inputs.get("format") or "mp3").lower()
        if requested.startswith("mp3"):
            return "mp3"
        if requested.startswith("wav") or requested in {"pcm", "riff"}:
            return "wav"
        raise ValueError("Grok CLI TTS output_format must be MP3 or WAV")

    def _build_command(self, inputs: dict[str, Any]) -> list[str]:
        output_path = Path(str(inputs["output_path"]))
        command = [
            "grok-cli",
            "tts",
            "--json",
            "--auth-file",
            str(self._auth_file_path()),
            "--text",
            str(inputs["text"]),
            "--voice-id",
            str(inputs.get("voice_id") or inputs.get("voice") or "ara"),
            "--language",
            str(inputs.get("language_code") or inputs.get("language") or "zh"),
            "--output",
            str(output_path),
            "--output-format",
            self._output_format(inputs),
        ]

        optional_flags = (
            ("sample_rate", "--sample-rate"),
            ("bit_rate", "--bit-rate"),
            ("optimize_streaming_latency", "--optimize-streaming-latency"),
        )
        for key, flag in optional_flags:
            if inputs.get(key) is not None:
                command.extend([flag, str(inputs[key])])

        text_normalization = inputs.get("text_normalization")
        if text_normalization is None:
            text_normalization = inputs.get("apply_text_normalization")
        if text_normalization is not None:
            command.extend(["--text-normalization", str(text_normalization)])
        if inputs.get("model"):
            command.extend(["--model", str(inputs["model"])])
        command.extend(["--timeout", str(int(inputs.get("timeout_seconds", 120)))])
        return command

    @staticmethod
    def _parse_envelope(raw: str | None) -> dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            raise ValueError("grok-cli returned no JSON output")
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("grok-cli returned malformed JSON output") from None
            value = json.loads(text[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("grok-cli returned a non-object JSON envelope")
        return value

    def _run_json(self, command: list[str], *, timeout: int) -> dict[str, Any]:
        try:
            completed = self.run_command(command, timeout=timeout)
            return self._parse_envelope(completed.stdout)
        except ToolCommandError as exc:
            raw = exc.output or exc.stderr or exc.detail
            try:
                return self._parse_envelope(raw)
            except (ValueError, json.JSONDecodeError):
                raise RuntimeError(str(exc)) from exc

    @staticmethod
    def _failure_result(envelope: dict[str, Any]) -> ToolResult:
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = str(error.get("code") or "grok_cli_failed")
        message = str(error.get("message") or "grok-cli TTS failed")
        recovery_action = str(error.get("recovery_action") or "none")
        return ToolResult(
            success=False,
            error=f"{code}: {message}",
            data={
                "provider": "grok",
                "transport": "grok-cli",
                "error_code": code,
                "recovery_action": recovery_action,
                "fallback_used": False,
            },
        )

    def _refresh_auth(self, *, timeout: int) -> bool:
        command = [
            "grok-cli",
            "refresh",
            "--json",
            "--auth-file",
            str(self._auth_file_path()),
        ]
        envelope = self._run_json(command, timeout=min(max(timeout, 30), 300))
        return bool(envelope.get("ok"))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from tools.analysis.audio_probe import probe_duration

        started = time.time()
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="grok-cli or its explicit OAuth auth file is unavailable. "
                + self.install_instructions,
                data={"provider": "grok", "transport": "grok-cli", "fallback_used": False},
            )

        try:
            output_path = Path(str(inputs["output_path"]))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            command = self._build_command(inputs)
        except (KeyError, TypeError, ValueError) as exc:
            return ToolResult(success=False, error=str(exc), data={"fallback_used": False})

        timeout_seconds = int(inputs.get("timeout_seconds", 120))
        auth_recovery: str | None = None
        try:
            envelope = self._run_json(command, timeout=timeout_seconds + 30)
            if not envelope.get("ok"):
                error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
                recovery_action = str(error.get("recovery_action") or "none")
                if recovery_action == "refresh_then_retry":
                    if not self._refresh_auth(timeout=timeout_seconds):
                        return self._failure_result(envelope)
                    auth_recovery = recovery_action
                    envelope = self._run_json(command, timeout=timeout_seconds + 30)
                if not envelope.get("ok"):
                    return self._failure_result(envelope)

            data = envelope.get("data")
            if not isinstance(data, dict):
                return ToolResult(success=False, error="grok-cli success envelope missing data")
            if not data.get("file_path"):
                return ToolResult(success=False, error="grok-cli TTS output missing data.file_path")
            if not output_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"grok-cli reported success but did not write output_path: {output_path}",
                )
            audio_duration = probe_duration(output_path)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Grok CLI TTS failed: {exc}",
                data={"provider": "grok", "transport": "grok-cli", "fallback_used": False},
            )

        output_format = self._output_format(inputs)
        provider_output_format = data.get("output_format")
        if isinstance(provider_output_format, dict):
            reported_codec = provider_output_format.get("codec")
        else:
            reported_codec = provider_output_format
        result_data = {
            "provider": "grok",
            "transport": "grok-cli",
            "model": data.get("model") or inputs.get("model"),
            "voice_id": data.get("voice_id") or inputs.get("voice_id") or inputs.get("voice") or "ara",
            "language_code": data.get("language") or inputs.get("language_code") or "zh",
            "text": inputs["text"],
            "text_length": len(str(inputs["text"])),
            "media_tag": data.get("media_tag"),
            "format": output_format,
            "output_format": str(reported_codec or output_format).lower(),
            "provider_output_format": provider_output_format,
            "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
            "output": str(output_path),
            "output_path": str(output_path),
            "billing_mode": "subscription_quota",
            "cost_tracking": "subscription_quota_unpriced",
            "fallback_used": False,
        }
        if auth_recovery:
            result_data["auth_recovery"] = auth_recovery

        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
            model=str(result_data["model"]) if result_data["model"] else None,
        )
