"""Contract tests for the OAuth-backed Grok CLI video provider."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from tools.base_tool import ToolCommandError, ToolStatus


def _provider_class():
    """Load the production provider while keeping the initial RED a test failure."""
    try:
        module = importlib.import_module("tools.video.grok_cli_video")
    except ModuleNotFoundError:
        pytest.fail("tools.video.grok_cli_video is not implemented")
    return module.GrokCliVideo


class _DownloadResponse:
    content = b"fake-mp4-bytes"

    def raise_for_status(self) -> None:
        return None


def _success_envelope(prompt: str = "原样提示词") -> str:
    return json.dumps(
        {
            "ok": True,
            "command": "video",
            "data": {
                "video": "https://example.invalid/generated.mp4",
                "request_id": "request-123",
                "modality": "generation",
                "model": "grok-imagine-video",
                "prompt": prompt,
            },
        }
    )


def test_text_to_video_uses_explicit_oauth_file_and_writes_project_asset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliVideo = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "projects" / "demo" / "assets" / "video" / "shot-01.mp4"
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))

    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout=_success_envelope(), stderr="")

    monkeypatch.setattr(GrokCliVideo, "run_command", lambda self, command, **kwargs: fake_run(command, **kwargs))
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _DownloadResponse())
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda path: {"duration_seconds": 5.0, "width": 1280, "height": 720},
    )

    result = GrokCliVideo().execute(
        {
            "prompt": "原样提示词",
            "operation": "text_to_video",
            "duration": 5,
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "output_path": str(output_path),
        }
    )

    assert result.success is True
    assert output_path.read_bytes() == b"fake-mp4-bytes"
    assert result.artifacts == [str(output_path)]
    assert result.data["request_id"] == "request-123"
    assert result.data["output_path"] == str(output_path)
    assert result.data["billing_mode"] == "subscription_quota"
    assert commands == [
        [
            "grok-cli",
            "video",
            "--json",
            "--auth-file",
            str(auth_file),
            "--prompt",
            "原样提示词",
            "--duration",
            "5",
            "--aspect-ratio",
            "16:9",
            "--resolution",
            "720p",
            "--model",
            "grok-imagine-video",
            "--timeout",
            "900",
        ]
    ]


@pytest.mark.parametrize(
    ("operation", "inputs", "expected_tail"),
    [
        (
            "image_to_video",
            {"image_path": "C:/media/source.png"},
            ["--image", "C:/media/source.png"],
        ),
        (
            "reference_to_video",
            {
                "reference_image_paths": ["C:/media/a.png", "C:/media/b.png"],
                "reference_image_urls": ["https://example.invalid/c.png"],
            },
            [
                "--reference-image",
                "C:/media/a.png",
                "--reference-image",
                "C:/media/b.png",
                "--reference-image-url",
                "https://example.invalid/c.png",
            ],
        ),
    ],
)
def test_conditioning_inputs_map_to_public_cli_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    operation: str,
    inputs: dict[str, object],
    expected_tail: list[str],
) -> None:
    GrokCliVideo = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout=_success_envelope(), stderr="")

    monkeypatch.setattr(GrokCliVideo, "run_command", lambda self, command, **kwargs: fake_run(command, **kwargs))
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _DownloadResponse())
    monkeypatch.setattr("tools.video._shared.probe_output", lambda path: {})

    result = GrokCliVideo().execute(
        {
            "prompt": "原样提示词",
            "operation": operation,
            "output_path": str(tmp_path / f"{operation}.mp4"),
            **inputs,
        }
    )

    assert result.success is True
    conditioning_flags = {"--image", "--reference-image", "--reference-image-url"}
    actual_pairs = [
        item
        for index, item in enumerate(zip(commands[0], commands[0][1:]))
        if commands[0][index] in conditioning_flags
    ]
    assert actual_pairs == list(zip(expected_tail[::2], expected_tail[1::2]))


def test_refresh_then_retry_follows_structured_cli_recovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliVideo = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    calls: list[list[str]] = []
    expired = json.dumps(
        {
            "ok": False,
            "command": "video",
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
        return subprocess.CompletedProcess(command, 0, stdout=_success_envelope(), stderr="")

    monkeypatch.setattr(GrokCliVideo, "run_command", lambda self, command, **kwargs: fake_run(command, **kwargs))
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _DownloadResponse())
    monkeypatch.setattr("tools.video._shared.probe_output", lambda path: {})

    result = GrokCliVideo().execute(
        {"prompt": "原样提示词", "output_path": str(tmp_path / "retry.mp4")}
    )

    assert result.success is True
    assert result.data["auth_recovery"] == "refresh_then_retry"
    assert [command[1] for command in calls] == ["video", "refresh", "video"]


def test_quota_failure_stops_without_provider_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliVideo = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    quota_error = json.dumps(
        {
            "ok": False,
            "command": "video",
            "error": {
                "code": "quota_exhausted",
                "message": "subscription quota exhausted",
                "recovery_action": "stop_quota",
            },
        }
    )

    def fail(command, **kwargs):  # noqa: ANN001
        raise ToolCommandError(1, command, output=quota_error, detail=quota_error)

    monkeypatch.setattr(GrokCliVideo, "run_command", lambda self, command, **kwargs: fail(command, **kwargs))

    result = GrokCliVideo().execute(
        {"prompt": "原样提示词", "output_path": str(tmp_path / "never.mp4")}
    )

    assert result.success is False
    assert result.data["error_code"] == "quota_exhausted"
    assert result.data["recovery_action"] == "stop_quota"
    assert "subscription quota exhausted" in (result.error or "")
    assert result.data["fallback_used"] is False


def test_login_required_stops_without_launching_interactive_login(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliVideo = _provider_class()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    calls: list[list[str]] = []
    login_error = json.dumps(
        {
            "ok": False,
            "command": "video",
            "error": {
                "code": "auth_relogin_required",
                "message": "interactive login required",
                "recovery_action": "login_then_retry",
            },
        }
    )

    def fail(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        raise ToolCommandError(1, command, output=login_error, detail=login_error)

    monkeypatch.setattr(GrokCliVideo, "run_command", lambda self, command, **kwargs: fail(command, **kwargs))

    result = GrokCliVideo().execute(
        {"prompt": "原样提示词", "output_path": str(tmp_path / "never.mp4")}
    )

    assert result.success is False
    assert result.data["recovery_action"] == "login_then_retry"
    assert [command[1] for command in calls] == ["video"]


def test_status_requires_binary_and_explicit_auth_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    GrokCliVideo = _provider_class()
    auth_file = tmp_path / "auth.json"
    monkeypatch.setenv("GROK_CLI_AUTH_FILE", str(auth_file))
    monkeypatch.setattr("shutil.which", lambda name: "C:/bin/grok-cli.exe")

    assert GrokCliVideo().get_status() == ToolStatus.UNAVAILABLE

    auth_file.write_text("{}", encoding="utf-8")
    assert GrokCliVideo().get_status() == ToolStatus.AVAILABLE
