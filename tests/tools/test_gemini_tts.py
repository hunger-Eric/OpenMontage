"""Contract tests for Gemini generateContent TTS and its default routing."""

from __future__ import annotations

import base64
import io
import wave
from pathlib import Path
from typing import Any

from tools.audio.gemini_tts import GeminiTTS
from tools.audio.tts_selector import TTSSelector
from tools.base_tool import ToolResult, ToolStatus


class _Response:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _StubTTS:
    capability = "tts"
    best_for = ["test"]

    def __init__(self, name: str, provider: str, status: ToolStatus) -> None:
        self.name = name
        self.provider = provider
        self._status = status
        self.last_inputs: dict[str, Any] | None = None

    def get_status(self) -> ToolStatus:
        return self._status

    def get_info(self) -> dict[str, Any]:
        return {
            "agent_skills": [],
            "usage_location": "test",
            "best_for": self.best_for,
        }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        self.last_inputs = dict(inputs)
        return ToolResult(success=True, data={})


def test_gemini_tts_has_no_default_voice() -> None:
    properties = GeminiTTS.input_schema["properties"]

    assert GeminiTTS.input_schema["required"] == ["text", "voice", "output_path"]
    assert "default" not in properties["voice"]
    assert GeminiTTS().fallback_tools == []


def test_gemini_tts_accepts_google_api_key_as_the_single_google_credential(
    monkeypatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "shared-google-key")

    assert GeminiTTS()._resolve_credential() == "shared-google-key"
    assert GeminiTTS().get_status() == ToolStatus.AVAILABLE


def test_gemini_tts_reuses_video_project_private_credential_file(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    private_dir = tmp_path / ".ai-daily-automation"
    private_dir.mkdir()
    (private_dir / ".env").write_text(
        "GEMINI_API_KEY=shared-video-project-key\n", encoding="utf-8"
    )

    assert GeminiTTS()._resolve_credential() == "shared-video-project-key"
    assert GeminiTTS().get_status() == ToolStatus.AVAILABLE


def test_gemini_tts_requires_voice_before_network(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    called = False

    def fail_post(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal called
        called = True
        raise AssertionError("network must not run without a selected voice")

    monkeypatch.setattr("requests.post", fail_post)
    result = GeminiTTS().execute(
        {"text": "测试旁白", "output_path": str(tmp_path / "speech.wav")}
    )

    assert result.success is False
    assert result.data["error_code"] == "voice_required"
    assert called is False


def test_gemini_tts_sends_selected_voice_and_wraps_pcm_as_wav(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    pcm = b"\x01\x00\x02\x00" * 120
    captured: dict[str, Any] = {}

    def fake_post(url, **kwargs):  # noqa: ANN001
        captured["url"] = url
        captured.update(kwargs)
        return _Response(
            {
                "modelVersion": "gemini-3.1-flash-tts-preview",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/L16;codec=pcm;rate=24000",
                                        "data": base64.b64encode(pcm).decode("ascii"),
                                    }
                                }
                            ]
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    output = tmp_path / "speech.wav"
    result = GeminiTTS().execute(
        {
            "text": "测试旁白",
            "voice": "runtime-selected-voice",
            "language_code": "cmn-CN",
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert result.model == "gemini-3.1-flash-tts-preview"
    assert result.data["voice"] == "runtime-selected-voice"
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["json"]["generationConfig"]["speechConfig"]["voiceConfig"] == {
        "prebuiltVoiceConfig": {"voiceName": "runtime-selected-voice"}
    }
    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 24_000
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.readframes(audio.getnframes()) == pcm


def test_gemini_tts_accepts_provider_wav_response(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    pcm = b"\x03\x00\x04\x00" * 120
    wav_bytes = io.BytesIO()
    with wave.open(wav_bytes, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24_000)
        audio.writeframes(pcm)

    def fake_post(url, **kwargs):  # noqa: ANN001
        return _Response(
            {
                "modelVersion": "gemini-3.1-flash-tts-preview",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/wav",
                                        "data": base64.b64encode(
                                            wav_bytes.getvalue()
                                        ).decode("ascii"),
                                    }
                                }
                            ]
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    output = tmp_path / "speech.wav"
    result = GeminiTTS().execute(
        {
            "text": "测试旁白",
            "voice": "Kore",
            "language_code": "cmn-CN",
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert result.data["response"]["mime_types"] == ["audio/wav"]
    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 24_000
        assert audio.readframes(audio.getnframes()) == pcm


def test_gemini_tts_normalizes_parameterized_stereo_wav_response(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    stereo_frames = b"\x10\x00\x20\x00" * 4_800
    wav_bytes = io.BytesIO()
    with wave.open(wav_bytes, "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(48_000)
        audio.writeframes(stereo_frames)

    def fake_post(url, **kwargs):  # noqa: ANN001
        return _Response(
            {
                "modelVersion": "gemini-3.1-flash-tts-preview",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/wav;codec=pcm;rate=48000",
                                        "data": base64.b64encode(
                                            wav_bytes.getvalue()
                                        ).decode("ascii"),
                                    }
                                }
                            ]
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    output = tmp_path / "speech.wav"
    result = GeminiTTS().execute(
        {
            "text": "测试旁白",
            "voice": "Kore",
            "language_code": "cmn-CN",
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert result.data["response"]["mime_types"] == [
        "audio/wav;codec=pcm;rate=48000"
    ]
    assert result.data["response"]["normalized_audio_parts"] == 1
    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 24_000
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getnframes() > 0


def test_gemini_tts_accepts_pcm_when_audio_mime_is_omitted(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    pcm = b"\x05\x00\x06\x00" * 120

    def fake_post(url, **kwargs):  # noqa: ANN001
        return _Response(
            {
                "modelVersion": "gemini-3.1-flash-tts-preview",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "data": base64.b64encode(pcm).decode("ascii")
                                    }
                                }
                            ]
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    output = tmp_path / "speech.wav"
    result = GeminiTTS().execute(
        {
            "text": "测试旁白",
            "voice": "Kore",
            "language_code": "cmn-CN",
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert result.data["response"]["mime_types"] == [""]
    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 24_000
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.readframes(audio.getnframes()) == pcm


def test_gemini_tts_sniffs_wav_before_assuming_missing_mime_is_pcm(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    pcm = b"\x07\x00\x08\x00" * 120
    wav_bytes = io.BytesIO()
    with wave.open(wav_bytes, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24_000)
        audio.writeframes(pcm)

    def fake_post(url, **kwargs):  # noqa: ANN001
        return _Response(
            {
                "modelVersion": "gemini-3.1-flash-tts-preview",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "data": base64.b64encode(
                                            wav_bytes.getvalue()
                                        ).decode("ascii")
                                    }
                                }
                            ]
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    output = tmp_path / "speech.wav"
    result = GeminiTTS().execute(
        {
            "text": "测试旁白",
            "voice": "Kore",
            "language_code": "cmn-CN",
            "output_path": str(output),
        }
    )

    assert result.success is True
    with wave.open(str(output), "rb") as audio:
        assert audio.readframes(audio.getnframes()) == pcm


def test_tts_selector_defaults_to_gemini_without_fallback(monkeypatch) -> None:
    gemini = _StubTTS("gemini_tts", "gemini", ToolStatus.AVAILABLE)
    elevenlabs = _StubTTS("elevenlabs_tts", "elevenlabs", ToolStatus.AVAILABLE)
    selector = TTSSelector()
    selector._providers = lambda: [elevenlabs, gemini]  # type: ignore[method-assign]
    monkeypatch.setattr(
        "lib.scoring.rank_providers",
        lambda candidates, context: [],
    )

    result = selector.execute(
        {"text": "测试旁白", "voice": "runtime-selected-voice", "output_path": "x.wav"}
    )

    assert result.success is True
    assert gemini.last_inputs is not None
    assert elevenlabs.last_inputs is None
    assert TTSSelector.input_schema["properties"]["preferred_provider"]["default"] == "gemini"


def test_tts_selector_stops_when_default_gemini_is_unavailable(monkeypatch) -> None:
    gemini = _StubTTS("gemini_tts", "gemini", ToolStatus.UNAVAILABLE)
    elevenlabs = _StubTTS("elevenlabs_tts", "elevenlabs", ToolStatus.AVAILABLE)
    selector = TTSSelector()
    selector._providers = lambda: [elevenlabs, gemini]  # type: ignore[method-assign]
    monkeypatch.setattr("lib.scoring.rank_providers", lambda candidates, context: [])

    result = selector.execute(
        {"text": "测试旁白", "voice": "runtime-selected-voice", "output_path": "x.wav"}
    )

    assert result.success is False
    assert elevenlabs.last_inputs is None
