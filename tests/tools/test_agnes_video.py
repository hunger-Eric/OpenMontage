from __future__ import annotations

from tools.base_tool import ToolStatus
from tools.video import agnes_video as module
from tools.video.agnes_video import AgnesVideo


class _Response:
    def __init__(self, payload=None, content=b""):
        self._payload = payload or {}
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_agnes_video_creates_polls_downloads_and_preserves_receipt(monkeypatch, tmp_path):
    calls = []
    states = iter([
        {"id": "task-1", "status": "in_progress"},
        {"id": "task-1", "status": "completed", "url": "https://cdn.example/video.mp4"},
    ])
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setenv("AGNES_API_BASE_URL", "https://apihub.agnes-ai.com/v1")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module.requests, "post", lambda url, **kwargs: calls.append(("post", url, kwargs)) or _Response({"id": "task-1", "task_id": "task-1", "video_id": "video-1", "status": "queued"}))

    def fake_get(url, **kwargs):
        calls.append(("get", url, kwargs))
        if url == "https://cdn.example/video.mp4":
            return _Response(content=b"video-bytes")
        return _Response(next(states))

    monkeypatch.setattr(module.requests, "get", fake_get)
    monkeypatch.setattr(module, "probe_output", lambda _path: {"duration_seconds": 5.0, "video_width": 648, "video_height": 1152})

    output = tmp_path / "agnes.mp4"
    result = AgnesVideo().execute({
        "prompt": "A mint hair clip on cream tissue paper",
        "output_path": str(output),
        "aspect_ratio": "9:16",
        "duration": 5,
        "poll_interval_seconds": 1,
    })

    assert result.success
    assert result.data["task_id"] == "task-1"
    assert result.data["fallback_used"] is False
    assert result.data["video_id"] == "video-1"
    assert result.data["seconds_requested"] == 5
    assert output.read_bytes() == b"video-bytes"
    create_payload = calls[0][2]["json"]
    assert create_payload == {
        "model": "agnes-video-2.5-flash",
        "prompt": "A mint hair clip on cream tissue paper",
        "seconds": "5",
        "mode": "text",
        "size": "720P",
        "aspect_ratio": "9:16",
        "n": 1,
    }
    poll_call = next(call for call in calls if call[0] == "get" and call[1].endswith("/agnesapi"))
    assert poll_call[2]["params"] == {"video_id": "video-1", "model_name": "agnes-video-2.5-flash"}


def test_agnes_video_image_mode_uses_selector_compatible_url(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    captured = {}
    monkeypatch.setattr(module.requests, "post", lambda _url, **kwargs: captured.update(kwargs["json"]) or _Response({"id": "task-2", "video_id": "video-2"}))
    monkeypatch.setattr(module.requests, "get", lambda url, **_kwargs: _Response(content=b"video") if url.startswith("https://cdn") else _Response({"status": "completed", "url": "https://cdn.example/v.mp4"}))
    monkeypatch.setattr(module, "probe_output", lambda _path: {"duration_seconds": 5.0, "video_width": 1152, "video_height": 648})

    result = AgnesVideo().execute({
        "prompt": "Subtle camera movement",
        "output_path": str(tmp_path / "image.mp4"),
        "operation": "image_to_video",
        "image_url": "https://example.com/reference.jpg",
        "poll_interval_seconds": 1,
    })

    assert result.success
    assert captured["images"] == ["https://example.com/reference.jpg"]
    assert captured["mode"] == "reference"


def test_agnes_video_maps_81_legacy_frames_to_four_seconds(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    captured = {}
    monkeypatch.setattr(module.requests, "post", lambda _url, **kwargs: captured.update(kwargs["json"]) or _Response({"id": "task-3", "video_id": "video-3"}))
    monkeypatch.setattr(module.requests, "get", lambda url, **_kwargs: _Response(content=b"video") if url.startswith("https://cdn") else _Response({"status": "completed", "url": "https://cdn.example/frame.mp4"}))
    monkeypatch.setattr(module, "probe_output", lambda _path: {"duration_seconds": 4.0, "video_width": 1280, "video_height": 704})

    result = AgnesVideo().execute({
        "prompt": "Product motion",
        "output_path": str(tmp_path / "frames.mp4"),
        "num_frames": 81,
        "frame_rate": 24,
    })

    assert result.success
    assert captured["seconds"] == "4"


def test_agnes_video_is_unavailable_without_key(monkeypatch):
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert AgnesVideo().get_status() == ToolStatus.UNAVAILABLE
