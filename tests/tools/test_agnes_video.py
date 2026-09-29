from __future__ import annotations

import json

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
    assert create_payload["width"] == 648
    assert create_payload["height"] == 1152
    assert create_payload["num_frames"] == 121
    assert create_payload["frame_rate"] == 24
    assert "seconds" not in create_payload
    assert "size" not in create_payload
    assert "aspect_ratio" not in create_payload
    poll_call = next(call for call in calls if call[0] == "get" and "/videos/task-1" in call[1])
    assert "params" not in poll_call[2]
    receipt = json.loads(output.with_suffix(".agnes-task.json").read_text(encoding="utf-8"))
    assert receipt["task_id"] == "task-1"
    assert receipt["status"] == "completed"


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
    assert "width" not in captured
    assert "height" not in captured


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


def test_agnes_video_v20_schema_exposes_the_frame_duration_contract():
    schema = AgnesVideo.input_schema["properties"]
    conditions = AgnesVideo().get_info()["supports"]["usage_conditions"]

    assert schema["model"]["enum"] == ["agnes-video-v2.0"]
    assert schema["duration"]["default"] == 5
    assert schema["duration"]["maximum"] == 441
    assert "18.375 seconds" in schema["duration"]["description"]
    assert "Longer productions must be split" in AgnesVideo.input_schema["description"]
    assert "8n + 1" in schema["num_frames"]["description"]
    assert "num_frames / frame_rate" in schema["frame_rate"]["description"]
    assert schema["poll_interval_seconds"]["default"] == 5
    assert conditions["fixed_model"] == "agnes-video-v2.0"
    assert conditions["num_frames"] == {
        "minimum": 9,
        "maximum": 441,
        "rule": "8n + 1",
    }
    assert conditions["frame_rate_fps"]["default"] == 24
    assert conditions["duration_seconds"]["maximum_at_default_24_fps"] == 18.375
    assert conditions["duration_seconds"]["maximum_at_30_fps"] == 14.7
    assert "Split productions" in conditions["long_video_policy"]


def test_agnes_video_rejects_other_models_before_any_external_request(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    external_calls = []
    monkeypatch.setattr(
        module,
        "upload_image_litterbox",
        lambda *_args, **_kwargs: external_calls.append("upload"),
    )
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *_args, **_kwargs: external_calls.append("post"),
    )

    result = AgnesVideo().execute({
        "prompt": "Do not submit this task",
        "output_path": str(tmp_path / "rejected.mp4"),
        "operation": "image_to_video",
        "reference_image_path": str(tmp_path / "reference.jpg"),
        "model": "agnes-video-2.5",
    })

    assert result.success is False
    assert "fixed to agnes-video-v2.0" in result.error
    assert result.data["model"] == "agnes-video-v2.0"
    assert result.data["fallback_used"] is False
    assert external_calls == []


def test_agnes_video_maps_18_seconds_to_the_nearest_valid_frame_count(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    captured = {}
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda _url, **kwargs: captured.update(kwargs["json"])
        or _Response({"id": "task-18", "video_id": "video-18"}),
    )
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda url, **_kwargs: _Response(content=b"video")
        if url.startswith("https://cdn")
        else _Response({"status": "completed", "url": "https://cdn.example/18.mp4"}),
    )
    monkeypatch.setattr(
        module,
        "probe_output",
        lambda _path: {"duration_seconds": 18.0417, "video_width": 1152, "video_height": 648},
    )

    result = AgnesVideo().execute({
        "prompt": "Long landscape shot",
        "output_path": str(tmp_path / "eighteen.mp4"),
        "duration": 18,
        "aspect_ratio": "16:9",
        "poll_interval_seconds": 1,
    })

    assert result.success
    assert captured["num_frames"] == 433
    assert captured["frame_rate"] == 24
    assert captured["width"] == 1152
    assert captured["height"] == 648
    assert result.data["effective_duration_seconds"] == 433 / 24


def test_agnes_video_rejects_duration_beyond_the_frame_budget(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *_args, **_kwargs: calls.append(True))

    result = AgnesVideo().execute({
        "prompt": "Too long",
        "output_path": str(tmp_path / "too-long.mp4"),
        "duration": 18.376,
        "frame_rate": 24,
    })

    assert not result.success
    assert "18.375 seconds in one call at 24 FPS" in result.error
    assert "Split a longer production into planned shots" in result.error
    assert result.data["usage_conditions"]["num_frames"]["maximum"] == 441
    assert result.data["fallback_used"] is False
    assert calls == []


def test_agnes_video_polls_with_video_id_and_preserves_both_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setenv("AGNES_API_BASE_URL", "https://apihub.agnes-ai.com/v1")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    calls = []
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda _url, **_kwargs: _Response({"id": "task-new", "video_id": "video-new"}),
    )

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.startswith("https://cdn"):
            return _Response(content=b"video")
        return _Response({"status": "completed", "url": "https://cdn.example/new.mp4"})

    monkeypatch.setattr(module.requests, "get", fake_get)
    monkeypatch.setattr(
        module,
        "probe_output",
        lambda _path: {"duration_seconds": 5.0, "video_width": 1280, "video_height": 720},
    )

    result = AgnesVideo().execute({
        "prompt": "Landscape shot",
        "output_path": str(tmp_path / "video-id.mp4"),
        "duration": 5,
        "poll_interval_seconds": 1,
    })

    assert result.success
    poll_url, poll_kwargs = calls[0]
    assert poll_url == "https://apihub.agnes-ai.com/agnesapi"
    assert poll_kwargs["params"] == {
        "video_id": "video-new",
        "model_name": "agnes-video-v2.0",
    }
    assert result.data["task_id"] == "task-new"
    assert result.data["video_id"] == "video-new"


def test_agnes_video_persists_recovery_receipt_before_polling(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda _url, **_kwargs: _Response({
            "id": "task-recover",
            "video_id": "video-recover",
            "status": "queued",
            "seconds": "5.0",
            "size": "1280x720",
        }),
    )
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda _url, **_kwargs: (_ for _ in ()).throw(module.requests.Timeout("poll interrupted")),
    )
    output = tmp_path / "recover.mp4"

    result = AgnesVideo().execute({
        "prompt": "Recoverable shot",
        "output_path": str(output),
        "duration": 5,
    })

    assert not result.success
    receipt_path = output.with_suffix(".agnes-task.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == {
        "model": "agnes-video-v2.0",
        "task_id": "task-recover",
        "video_id": "video-recover",
        "status": "queued",
        "progress": None,
        "seconds": "5.0",
        "size": "1280x720",
    }
    assert result.data["task_receipt_path"] == str(receipt_path)


def test_agnes_video_poll_receipt_preserves_create_only_recovery_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffprobe")
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda _url, **_kwargs: _Response({
            "task_id": "task-preserve",
            "video_id": "video-preserve",
            "status": "queued",
            "seconds": "5.0",
            "size": "1152x648",
        }),
    )
    polls = iter([
        _Response({"status": "in_progress", "progress": 50}),
        module.requests.Timeout("after progress"),
    ])

    def fake_get(_url, **_kwargs):
        value = next(polls)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(module.requests, "get", fake_get)
    output = tmp_path / "preserve.mp4"

    result = AgnesVideo().execute({
        "prompt": "Preserve receipt",
        "output_path": str(output),
    })

    assert not result.success
    receipt = json.loads(output.with_suffix(".agnes-task.json").read_text(encoding="utf-8"))
    assert receipt["task_id"] == "task-preserve"
    assert receipt["video_id"] == "video-preserve"
    assert receipt["status"] == "in_progress"
    assert receipt["progress"] == 50
    assert receipt["seconds"] == "5.0"
    assert receipt["size"] == "1152x648"


def test_agnes_video_is_unavailable_without_key(monkeypatch):
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert AgnesVideo().get_status() == ToolStatus.UNAVAILABLE
