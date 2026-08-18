"""Contract tests for the OAuth-backed Grok CLI TTS provider."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from tools.base_tool import ToolCommandError, ToolStatus


def _provider_class():
    try:
        module = importlib.import_module("tools.audio.grok_cli_tts")
    except ModuleNotFoundError:
        pytest.fail("tools.audio.grok_cli_tts is not implemented")
    return module.GrokCliTTS


def _success_envelope(output_path: Path) -> str:
    return json.dumps(
        {
            "ok": True,
            "command": "tts",
            "data": {
                "file_path": str(output_path),
                "media_tag": "tts-asset-123",
                "output_format": {"codec": "mp3"},
                "voice_id": "ara",
                "language": "zh",
            },
        }
    )


def test_chinese_text_is_passed_unchanged_and_cli_writes_project_asset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliTTS = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "projects" / "demo" / "assets" / "audio" / "sample.mp3"
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        commands.append(list(command))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-mp3")
        return subprocess.CompletedProcess(
            command, 0, stdout=_success_envelope(output_path), stderr=""
        )

    monkeypatch.setattr(GrokCliTTS, "run_command", lambda self, command, **kwargs: fake_run(command, **kwargs))
    monkeypatch.setattr("tools.analysis.audio_probe.probe_duration", lambda path: 2.5)

    result = GrokCliTTS().execute(
        {
            "text": "这段旁白必须原样传递。",
            "voice_id": "ara",
            "language_code": "zh",
            "output_format": "mp3_44100_128",
            "output_path": str(output_path),
        }
    )

    assert result.success is True
    assert result.artifacts == [str(output_path)]
    assert result.data["text"] == "这段旁白必须原样传递。"
    assert result.data["billing_mode"] == "subscription_quota"
    assert result.data["output_format"] == "mp3"
    assert result.data["provider_output_format"] == {"codec": "mp3"}
    assert result.data["audio_duration_seconds"] == 2.5
    assert commands == [
        [
            "grok-cli",
            "tts",
            "--json",
            "--auth-file",
            str(auth_file),
            "--text",
            "这段旁白必须原样传递。",
            "--voice-id",
            "ara",
            "--language",
            "zh",
            "--output",
            str(output_path),
            "--output-format",
            "mp3",
            "--timeout",
            "120",
        ]
    ]


def test_optional_cli_controls_are_mapped_mechanically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliTTS = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "speech.wav"
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        commands.append(list(command))
        output_path.write_bytes(b"fake-wav")
        return subprocess.CompletedProcess(
            command, 0, stdout=_success_envelope(output_path), stderr=""
        )

    monkeypatch.setattr(GrokCliTTS, "run_command", lambda self, command, **kwargs: fake_run(command, **kwargs))
    monkeypatch.setattr("tools.analysis.audio_probe.probe_duration", lambda path: None)

    result = GrokCliTTS().execute(
        {
            "text": "Exact text",
            "voice_id": "eve",
            "language_code": "en",
            "output_format": "wav",
            "sample_rate": 44100,
            "bit_rate": 128000,
            "optimize_streaming_latency": 2,
            "text_normalization": "auto",
            "model": "grok-tts",
            "timeout_seconds": 180,
            "output_path": str(output_path),
        }
    )

    assert result.success is True
    assert commands[0][-12:] == [
        "--sample-rate", "44100",
        "--bit-rate", "128000",
        "--optimize-streaming-latency", "2",
        "--text-normalization", "auto",
        "--model", "grok-tts",
        "--timeout", "180",
    ]


def test_refresh_then_retry_is_the_only_automatic_auth_recovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliTTS = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "retry.mp3"
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    calls: list[list[str]] = []
    expired = json.dumps(
        {
            "ok": False,
            "command": "tts",
            "error": {
                "code": "auth_expired",
                "message": "token expired",
                "recovery_action": "refresh_then_retry",
            },
        }
    )

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        if len(calls) == 1:
            raise ToolCommandError(1, command, output=expired, detail=expired)
        if command[1] == "refresh":
            return subprocess.CompletedProcess(command, 0, stdout='{"ok":true}', stderr="")
        output_path.write_bytes(b"fake-mp3")
        return subprocess.CompletedProcess(
            command, 0, stdout=_success_envelope(output_path), stderr=""
        )

    monkeypatch.setattr(GrokCliTTS, "run_command", lambda self, command, **kwargs: fake_run(command, **kwargs))
    monkeypatch.setattr("tools.analysis.audio_probe.probe_duration", lambda path: 1.0)

    result = GrokCliTTS().execute(
        {"text": "原文", "output_path": str(output_path)}
    )

    assert result.success is True
    assert result.data["auth_recovery"] == "refresh_then_retry"
    assert [command[1] for command in calls] == ["tts", "refresh", "tts"]


@pytest.mark.parametrize(
    ("code", "recovery_action"),
    [
        ("auth_relogin_required", "login_then_retry"),
        ("quota_exhausted", "stop_quota"),
    ],
)
def test_terminal_errors_stop_without_login_or_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    code: str,
    recovery_action: str,
) -> None:
    GrokCliTTS = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    calls: list[list[str]] = []
    failure = json.dumps(
        {
            "ok": False,
            "command": "tts",
            "error": {
                "code": code,
                "message": "terminal error",
                "recovery_action": recovery_action,
            },
        }
    )

    def fail(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        raise ToolCommandError(1, command, output=failure, detail=failure)

    monkeypatch.setattr(GrokCliTTS, "run_command", lambda self, command, **kwargs: fail(command, **kwargs))

    result = GrokCliTTS().execute(
        {"text": "原文", "output_path": str(tmp_path / "never.mp3")}
    )

    assert result.success is False
    assert result.data["error_code"] == code
    assert result.data["recovery_action"] == recovery_action
    assert result.data["fallback_used"] is False
    assert [command[1] for command in calls] == ["tts"]


def test_status_requires_binary_and_explicit_auth_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliTTS = _provider_class()
    auth_file = tmp_path / "auth.json"
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    monkeypatch.setattr("shutil.which", lambda name: "C:/bin/grok-cli.exe")

    provider = GrokCliTTS()
    assert provider.agent_skills == ["grok-cli-tts"]
    assert provider.get_status() == ToolStatus.UNAVAILABLE

    auth_file.write_text("{}", encoding="utf-8")
    assert provider.get_status() == ToolStatus.AVAILABLE
