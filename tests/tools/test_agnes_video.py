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
        {"id": "task-1", "status": "completed", "video_url": "https://cdn.example/video.mp4"},
    ])
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setenv("AGNES_API_BASE_URL", "https://apihub.agnes-ai.com/v1")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module.requests, "post", lambda url, **kwargs: calls.append(("post", url, kwargs)) or _Response({"id": "task-1", "status": "queued"}))

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
    assert result.data["num_frames_requested"] == 121
    assert output.read_bytes() == b"video-bytes"
    create_payload = calls[0][2]["json"]
    assert create_payload["model"] == "agnes-video-v2.0"
    assert create_payload["width"] == 648
    assert create_payload["height"] == 1152


def test_agnes_video_image_mode_uses_selector_compatible_url(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    captured = {}
    monkeypatch.setattr(module.requests, "post", lambda _url, **kwargs: captured.update(kwargs["json"]) or _Response({"id": "task-2"}))
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
    assert captured["image"] == "https://example.com/reference.jpg"
    assert captured["mode"] == "ti2vid"


def test_agnes_video_encodes_local_reference_as_data_url(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    captured = {}
    monkeypatch.setattr(module.requests, "post", lambda _url, **kwargs: captured.update(kwargs["json"]) or _Response({"id": "task-local"}))
    monkeypatch.setattr(module.requests, "get", lambda url, **_kwargs: _Response(content=b"video") if url.startswith("https://cdn") else _Response({"status": "completed", "url": "https://cdn.example/local.mp4"}))
    monkeypatch.setattr(module, "probe_output", lambda _path: {"duration_seconds": 5.0, "video_width": 1152, "video_height": 648})
    reference = tmp_path / "reference.jpg"
    reference.write_bytes(b"jpeg-data")

    result = AgnesVideo().execute({
        "prompt": "Keep the product identity stable",
        "output_path": str(tmp_path / "local.mp4"),
        "operation": "image_to_video",
        "reference_image_path": str(reference),
        "poll_interval_seconds": 1,
    })

    assert result.success
    assert captured["image"].startswith("data:image/jpeg;base64,")
    assert captured["mode"] == "ti2vid"


def test_agnes_video_is_unavailable_without_key(monkeypatch):
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert AgnesVideo().get_status() == ToolStatus.UNAVAILABLE
