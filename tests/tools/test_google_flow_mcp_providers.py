from __future__ import annotations

from pathlib import Path

from tools._google_flow_mcp import provider as provider_module
from tools.audio import google_flow_mcp_music as music_module
from tools.audio.google_flow_mcp_music import GoogleFlowMCPMusic
from tools.base_tool import ToolStatus
from tools.video import google_flow_mcp_video as video_module
from tools.video.google_flow_mcp_video import GoogleFlowMCPVideo


class _SnapshotClient:
    def __init__(self, snapshots):
        self.snapshots = iter(snapshots)
        self.calls = 0

    def call_tool(self, name, arguments, timeout_seconds=None):
        assert name == "flow_snapshot"
        self.calls += 1
        return next(self.snapshots)


def _receipt(output_path: Path, media_type: str) -> dict:
    return {
        "opened": {"opened": True},
        "approval": {"confirmed": True},
        "wait": {"assetUrl": "https://example.invalid/asset", "jobId": "job-1"},
        "download": {
            "localPath": str(output_path),
            "mediaType": media_type,
            "sha256": "a" * 64,
        },
    }


def test_wait_for_text_input_tolerates_delayed_flow_composer(monkeypatch):
    client = _SnapshotClient(
        [
            {"interactables": []},
            {
                "interactables": [
                    {
                        "ref": "el_39",
                        "tag": "TEXTAREA",
                        "role": "textbox",
                        "visible": True,
                        "disabled": False,
                    }
                ]
            },
        ]
    )
    monkeypatch.setattr(provider_module.time, "sleep", lambda _: None)

    assert provider_module.wait_for_text_input(client, music=False) == "el_39"
    assert client.calls == 2


def test_google_flow_video_requires_explicit_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    result = GoogleFlowMCPVideo().execute(
        {
            "prompt": "mist over mountains",
            "output_path": str(tmp_path / "shot.mp4"),
            "project_url": "https://labs.google/fx/tools/flow/project/example",
            "confirm_paid_generation": False,
            "max_budget_credits": 10,
        }
    )
    assert not result.success
    assert result.data["error_code"] == "approval_required"


def test_google_flow_music_requires_explicit_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(music_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    result = GoogleFlowMCPMusic().execute(
        {
            "prompt": "epic orchestral score",
            "output_path": str(tmp_path / "score.m4a"),
            "confirm_paid_generation": False,
            "max_budget_credits": 10,
        }
    )
    assert not result.success
    assert result.data["error_code"] == "approval_required"


def test_google_flow_providers_refuse_to_overwrite(monkeypatch, tmp_path):
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(music_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    video_path = tmp_path / "shot.mp4"
    music_path = tmp_path / "score.m4a"
    video_path.write_bytes(b"user-video")
    music_path.write_bytes(b"user-audio")

    video_result = GoogleFlowMCPVideo().execute(
        {
            "prompt": "mist over mountains",
            "output_path": str(video_path),
            "project_url": "https://labs.google/fx/tools/flow/project/example",
            "confirm_paid_generation": True,
            "max_budget_credits": 10,
        }
    )
    music_result = GoogleFlowMCPMusic().execute(
        {
            "prompt": "epic orchestral score",
            "output_path": str(music_path),
            "confirm_paid_generation": True,
            "max_budget_credits": 10,
        }
    )
    assert not video_result.success and video_result.data["error_code"] == "output_exists"
    assert not music_result.success and music_result.data["error_code"] == "output_exists"
    assert video_path.read_bytes() == b"user-video"
    assert music_path.read_bytes() == b"user-audio"


def test_google_flow_video_returns_mcp_and_probe_receipts(monkeypatch, tmp_path):
    output_path = tmp_path / "shot.mp4"
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(
        video_module,
        "run_generation",
        lambda **kwargs: _receipt(output_path, "video"),
    )
    monkeypatch.setattr(
        video_module,
        "probe_media",
        lambda path, expected: {
            "duration_seconds": 6.0,
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "file_size_bytes": 1024,
        },
    )
    result = GoogleFlowMCPVideo().execute(
        {
            "prompt": "mist over mountains",
            "output_path": str(output_path),
            "project_url": "https://labs.google/fx/tools/flow/project/example",
            "confirm_paid_generation": True,
            "max_budget_credits": 10,
        }
    )
    assert result.success
    assert result.data["transport"] == "mcp_stdio_browser"
    assert result.data["codec"] == "h264"
    assert result.data["fallback_used"] is False


def test_google_flow_music_returns_mcp_and_probe_receipts(monkeypatch, tmp_path):
    output_path = tmp_path / "score.m4a"
    monkeypatch.setattr(music_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(
        music_module,
        "run_generation",
        lambda **kwargs: _receipt(output_path, "audio"),
    )
    monkeypatch.setattr(
        music_module,
        "probe_media",
        lambda path, expected: {
            "duration_seconds": 60.0,
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "aac",
            "sample_rate": "48000",
            "channels": 2,
            "file_size_bytes": 2048,
        },
    )
    result = GoogleFlowMCPMusic().execute(
        {
            "prompt": "epic orchestral score",
            "output_path": str(output_path),
            "confirm_paid_generation": True,
            "max_budget_credits": 10,
        }
    )
    assert result.success
    assert result.data["transport"] == "mcp_stdio_browser"
    assert result.data["codec"] == "aac"
    assert result.data["fallback_used"] is False


def test_provider_contracts_are_discoverable():
    video = GoogleFlowMCPVideo()
    music = GoogleFlowMCPMusic()
    assert video.capability == "video_generation"
    assert music.capability == "music_generation"
    assert video.provider == music.provider == "google_flow"
    assert video.get_status() == ToolStatus.AVAILABLE
    assert music.get_status() == ToolStatus.AVAILABLE
    assert video.is_operation_available("text_to_video")
    assert not video.is_operation_available("video_edit")
