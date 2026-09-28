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


class _UploadResponse(_Response):
    def __init__(self, text):
        super().__init__()
        self.text = text


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
    assert create_payload["width"] == 768
    assert create_payload["height"] == 1152
    assert create_payload["num_frames"] == 121
    assert create_payload["frame_rate"] == 24
    assert "seconds" not in create_payload
    assert "size" not in create_payload
    assert "aspect_ratio" not in create_payload
    poll_call = next(call for call in calls if call[0] == "get" and "/videos/task-1" in call[1])
    assert "params" not in poll_call[2]


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


def test_agnes_video_image_mode_uploads_local_reference_without_fal(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    local_image = tmp_path / "reference.jpg"
    local_image.write_bytes(b"image-bytes")
    uploaded = {}

    def fake_upload(path):
        uploaded["path"] = path
        return "https://litterbox.example/reference.jpg"

    monkeypatch.setattr(module, "upload_image_litterbox", fake_upload, raising=False)
    captured = {}
    monkeypatch.setattr(module.requests, "post", lambda _url, **kwargs: captured.update(kwargs["json"]) or _Response({"id": "task-local"}))
    monkeypatch.setattr(module.requests, "get", lambda url, **_kwargs: _Response(content=b"video") if url.startswith("https://cdn") else _Response({"status": "completed", "url": "https://cdn.example/local.mp4"}))
    monkeypatch.setattr(module, "probe_output", lambda _path: {"duration_seconds": 5.0, "video_width": 648, "video_height": 1152})

    result = AgnesVideo().execute({
        "prompt": "Subtle product movement",
        "output_path": str(tmp_path / "local-image.mp4"),
        "operation": "image_to_video",
        "reference_image_path": str(local_image),
        "aspect_ratio": "9:16",
        "poll_interval_seconds": 1,
    })

    assert result.success
    assert uploaded["path"] == str(local_image)
    assert captured["image"] == "https://litterbox.example/reference.jpg"
    assert captured["mode"] == "ti2vid"


def test_agnes_reference_upload_uses_ephemeral_litterbox_contract(monkeypatch, tmp_path):
    local_image = tmp_path / "reference.jpg"
    local_image.write_bytes(b"image-bytes")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _UploadResponse("https://litter.catbox.moe/reference.jpg\n")

    monkeypatch.setattr(module.requests, "post", fake_post)

    result = module.upload_image_litterbox(str(local_image))

    assert result == "https://litter.catbox.moe/reference.jpg"
    assert captured["url"] == module.LITTERBOX_UPLOAD_URL
    assert captured["data"] == {"reqtype": "fileupload", "time": "1h"}
    assert captured["files"]["fileToUpload"][0] == "reference.jpg"


def test_agnes_video_preserves_81_frame_request(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    captured = {}
    monkeypatch.setattr(module.requests, "post", lambda _url, **kwargs: captured.update(kwargs["json"]) or _Response({"id": "task-3"}))
    monkeypatch.setattr(module.requests, "get", lambda url, **_kwargs: _Response(content=b"video") if url.startswith("https://cdn") else _Response({"status": "completed", "url": "https://cdn.example/frame.mp4"}))
    monkeypatch.setattr(module, "probe_output", lambda _path: {"duration_seconds": 4.0, "video_width": 1280, "video_height": 704})

    result = AgnesVideo().execute({
        "prompt": "Product motion",
        "output_path": str(tmp_path / "frames.mp4"),
        "num_frames": 81,
        "frame_rate": 24,
    })

    assert result.success
    assert captured["model"] == "agnes-video-v2.0"
    assert captured["num_frames"] == 81
    assert captured["frame_rate"] == 24


def test_agnes_video_is_unavailable_without_key(monkeypatch):
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert AgnesVideo().get_status() == ToolStatus.UNAVAILABLE
