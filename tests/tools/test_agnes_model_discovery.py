"""Account discovery, explicit model choice, versioned transport and recovery."""
import json

import pytest
import requests
from jsonschema import validate

from tools.video import agnes_video as module
from tools.video.agnes_video import AgnesVideo
from tools.video.video_selector import VideoSelector

FLASH = "agnes-video-2.5-flash"
STANDARD = "agnes-video-2.5"


class Response:
    def __init__(self, payload=None, content=b"", status=200):
        self.payload = payload
        self.content = content
        self.status_code = status
        self.text = ""

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setenv("AGNES_API_BASE_URL", "https://apihub.agnes-ai.com/v1")
    monkeypatch.setattr(module.shutil, "which", lambda _: "ffprobe")
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "probe_output", lambda _: {"duration_seconds": 4.48, "video_width": 1280, "video_height": 720})
    calls = []
    catalog = [FLASH, STANDARD]

    def get(url, **kwargs):
        calls.append(("get", url, kwargs))
        if url.endswith("/models"):
            return Response({"data": [{"id": m} for m in catalog]})
        if url.startswith("https://cdn"):
            assert "headers" not in kwargs
            return Response(content=b"video")
        return Response({"status": "completed", "url": "https://cdn.example/v.mp4"})

    def post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return Response({"task_id": "task-new", "video_id": "video-new", "status": "queued"})

    monkeypatch.setattr(module.requests, "get", get)
    monkeypatch.setattr(module.requests, "post", post)
    return calls, catalog


def inputs(tmp_path, **kwargs):
    return {"model": FLASH, "prompt": "A red ball rolls right", "duration": 4, "output_path": str(tmp_path / "test.mp4"), **kwargs}


def posts(api):
    return [call for call in api[0] if call[0] == "post"]


def test_discovery_is_read_only_and_does_not_claim_access(api):
    api[1].extend(["agnes-text", "agnes-video-future"])
    result = AgnesVideo().execute({"operation": "discover_models"})
    assert result.success
    assert result.data["selected_model"] is None
    assert [item["id"] for item in result.data["models"]] == [FLASH, STANDARD, "agnes-video-future"]
    assert all(item["access"] == "listed_unverified" for item in result.data["models"])
    assert result.data["models"][-1]["adapter_supported"] is False
    assert not posts(api)
    validate({"operation": "discover_models"}, AgnesVideo.input_schema)
    validate({"operation": "discover_models"}, VideoSelector.input_schema)


def test_selector_discovery_and_rank_expose_live_candidates(api, monkeypatch):
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [AgnesVideo()])
    result = selector.execute({"operation": "discover_models"})
    assert result.success
    ranked = selector.execute({"operation": "rank", "prompt": "ball"})
    assert ranked.success
    assert ranked.data["selected_model"] is None
    assert ranked.data["model_discovery"]["models"][0]["id"] == FLASH
    assert not posts(api)


def test_missing_choice_returns_catalog_without_submission(api, tmp_path):
    request = inputs(tmp_path)
    request.pop("model")
    result = AgnesVideo().execute(request)
    assert not result.success
    assert result.data["selection_required"]
    assert not posts(api)


@pytest.mark.parametrize("through_selector", [False, True])
def test_flash_end_to_end_transport_uses_selected_model(api, tmp_path, monkeypatch, through_selector):
    tool = AgnesVideo()
    if through_selector:
        selector = VideoSelector()
        monkeypatch.setattr(selector, "_providers", lambda provider=tool: [provider])
        tool = selector
    result = tool.execute(inputs(tmp_path))
    assert result.success
    payload = posts(api)[0][2]["json"]
    assert payload == {"model": FLASH, "prompt": "A red ball rolls right", "seconds": "4", "mode": "text", "size": "720P", "aspect_ratio": "16:9", "n": 1}
    assert api[0][0][1].endswith("/models")
    poll = next(c for c in api[0] if c[1].endswith("/agnesapi"))
    assert poll[2]["params"] == {"video_id": "video-new", "model_name": FLASH}
    receipt = json.loads((tmp_path / "test.agnes-task.json").read_text())
    assert receipt["model"] == FLASH
    assert result.model == FLASH
    assert result.data["effective_duration_seconds"] == 4


@pytest.mark.parametrize("extra", [
    {"duration": 13}, {"duration": 4.5}, {"size": "1080P"},
    {"num_frames": 121}, {"frame_rate": 24}, {"width": 1280},
    {"mode": "reference", "videos": [{"url": "https://example.com/v.mp4"}]},
    {"mode": "reference", "images": ["https://example.com/i.jpg"] * 6},
    {"mode": "text", "images": ["https://example.com/i.jpg"]},
    {"mode": "keyframe"}, {"n": 2}, {"aspect_ratio": "auto"},
])
def test_invalid_flash_inputs_never_submit(api, tmp_path, extra):
    result = AgnesVideo().execute(inputs(tmp_path, **extra))
    assert not result.success
    assert not posts(api)


@pytest.mark.parametrize("field", ["model", "model_name", "model_variant"])
def test_model_aliases_support_selected_flash(api, tmp_path, field):
    request = inputs(tmp_path)
    request.pop("model")
    request[field] = FLASH
    assert AgnesVideo().execute(request).success


def test_conflicting_aliases_do_not_query_or_submit(api, tmp_path):
    result = AgnesVideo().execute(inputs(tmp_path, model_name=STANDARD))
    assert not result.success
    assert not api[0]


def test_removed_model_does_not_submit(api, tmp_path):
    api[1].remove(FLASH)
    result = AgnesVideo().execute(inputs(tmp_path))
    assert not result.success
    assert "absent" in result.error
    assert not posts(api)


def test_discovery_failure_blocks_submission(api, monkeypatch, tmp_path):
    monkeypatch.setattr(module.requests, "get", lambda *a, **k: Response(status=401))
    result = AgnesVideo().execute(inputs(tmp_path))
    assert not result.success
    assert "discovery failed" in result.error
    assert not posts(api)


def test_paid_route_requires_authorization(api, tmp_path):
    result = AgnesVideo().execute(inputs(tmp_path, model=STANDARD))
    assert not result.success
    assert "paid-route authorization" in result.error
    assert not posts(api)


def test_authorized_standard_uses_its_resolution(api, tmp_path):
    result = AgnesVideo().execute(inputs(tmp_path, model=STANDARD, allow_paid_model=True, size="1080P"))
    assert result.success
    assert posts(api)[0][2]["json"]["model"] == STANDARD
    assert posts(api)[0][2]["json"]["size"] == "1080P"


def test_rejected_standard_never_falls_back_or_retries(api, tmp_path, monkeypatch):
    count = []

    def reject(url, **kwargs):
        count.append(kwargs["json"]["model"])
        return Response({"error": {"code": "model_not_found", "message": "No channel under group TokenPlan"}}, status=503)

    monkeypatch.setattr(module.requests, "post", reject)
    result = AgnesVideo().execute(inputs(tmp_path, model=STANDARD, allow_paid_model=True))
    assert not result.success
    assert "TokenPlan" in result.error
    assert count == [STANDARD]


@pytest.mark.parametrize("mode", ["keyframe", "reference"])
def test_local_reference_uses_correct_v25_field(api, tmp_path, monkeypatch, mode):
    reference = tmp_path / "ref.jpg"
    reference.write_bytes(b"reference")
    monkeypatch.setattr(module, "upload_image_litterbox", lambda _: "https://example.com/ref.jpg")
    result = AgnesVideo().execute(inputs(tmp_path, operation="image_to_video" if mode == "keyframe" else "reference_to_video", reference_image_path=str(reference)))
    assert result.success
    payload = posts(api)[0][2]["json"]
    assert payload["mode"] == mode
    assert payload["first_frame"] == "https://example.com/ref.jpg" if mode == "keyframe" else payload["images"] == ["https://example.com/ref.jpg"]
    assert "image" not in payload
    assert "extra_body" not in payload


def test_resume_uses_receipt_model_without_rediscovery_or_paid_call(api, tmp_path):
    receipt = tmp_path / "test.agnes-task.json"
    receipt.write_text(json.dumps({"model": STANDARD, "video_id": "video-existing", "task_id": "task-existing", "status": "pending"}))
    api[1].clear()
    request = inputs(tmp_path)
    request.pop("model")
    result = AgnesVideo().execute(request)
    assert result.success
    assert result.model == STANDARD
    assert not posts(api)
    assert not any(c[1].endswith("/models") for c in api[0])
    poll = next(c for c in api[0] if c[1].endswith("/agnesapi"))
    assert poll[2]["params"]["model_name"] == STANDARD


def test_conflicting_receipt_preserved_without_network(api, tmp_path):
    receipt = tmp_path / "test.agnes-task.json"
    original = json.dumps({"model": STANDARD, "video_id": "old", "status": "pending"})
    receipt.write_text(original)
    result = AgnesVideo().execute(inputs(tmp_path))
    assert not result.success
    assert not api[0]
    assert receipt.read_text() == original


def test_each_discovery_reads_current_catalog(api):
    tool = AgnesVideo()
    assert len(tool.discover_models().data["models"]) == 2
    api[1].remove(STANDARD)
    assert [m["id"] for m in tool.discover_models().data["models"]] == [FLASH]
    assert len(api[0]) == 2


@pytest.mark.parametrize("failure", ["timeout", "server_error", "missing_ids"])
def test_unknown_submission_outcome_prevents_second_submit(api, tmp_path, monkeypatch, failure):
    calls = []

    def ambiguous(url, **kwargs):
        calls.append(url)
        if failure == "timeout":
            raise requests.Timeout("response lost")
        if failure == "server_error":
            return Response({"error": {"message": "upstream failure"}}, status=500)
        return Response({"status": "queued"})

    monkeypatch.setattr(module.requests, "post", ambiguous)
    tool = AgnesVideo()
    assert not tool.execute(inputs(tmp_path)).success
    result = tool.execute(inputs(tmp_path))
    assert not result.success
    assert "outcome is unknown" in result.error
    assert len(calls) == 1


def test_resume_rejects_changed_flash_inputs_without_resubmit(api, tmp_path, monkeypatch):
    original_get = module.requests.get

    def interrupted_poll(url, **kwargs):
        if url.endswith("/agnesapi"):
            raise requests.Timeout("poll interrupted")
        return original_get(url, **kwargs)

    monkeypatch.setattr(module.requests, "get", interrupted_poll)
    tool = AgnesVideo()
    assert not tool.execute(inputs(tmp_path)).success
    result = tool.execute(inputs(tmp_path, duration=5))
    assert not result.success
    assert "different inputs" in result.error
    assert len(posts(api)) == 1


def test_unreadable_receipt_is_not_replaced(api, tmp_path):
    receipt = tmp_path / "test.agnes-task.json"
    receipt.write_text("broken json")
    result = AgnesVideo().execute(inputs(tmp_path))
    assert not result.success
    assert "Unreadable" in result.error
    assert not api[0]
    assert receipt.read_text() == "broken json"
