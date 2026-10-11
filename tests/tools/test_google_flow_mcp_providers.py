from __future__ import annotations

from pathlib import Path
import json

import pytest

from tools._google_flow_mcp import provider as provider_module
from tools.audio import google_flow_mcp_music as music_module
from tools.audio.google_flow_mcp_music import GoogleFlowMCPMusic
from tools.base_tool import ToolStatus
from tools.graphics import google_flow_mcp_image as image_module
from tools.graphics.google_flow_mcp_image import GoogleFlowMCPImage
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
        "uploads": [],
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
                        "tag": "DIV",
                        "contentEditable": True,
                        "text": "您希望创作什么？",
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


def test_video_prompt_selector_ignores_project_title_and_search():
    snapshot = {
        "interactables": [
            {"ref": "el_title", "tag": "INPUT", "ariaLabel": "可编辑文本", "visible": True, "disabled": False},
            {"ref": "el_search", "tag": "INPUT", "ariaLabel": "搜索", "visible": True, "disabled": False},
            {"ref": "el_prompt", "tag": "DIV", "contentEditable": True, "text": "您希望创作什么？", "visible": True, "disabled": False},
        ]
    }

    assert provider_module.select_text_input(snapshot, music=False) == "el_prompt"


def test_video_prompt_selector_accepts_unlabelled_visible_contenteditable():
    snapshot = {
        "interactables": [
            {"ref": "el_title", "tag": "INPUT", "ariaLabel": "可编辑文本", "visible": True, "disabled": False},
            {"ref": "el_search", "tag": "INPUT", "ariaLabel": "搜索", "visible": True, "disabled": False},
            {"ref": "el_prompt", "tag": "DIV", "contentEditable": True, "visible": True, "disabled": False},
        ]
    }

    assert provider_module.select_text_input(snapshot, music=False) == "el_prompt"


def test_generation_submit_selector_requires_visible_enabled_control():
    snapshot = {
        "interactables": [
            {"ref": "disabled", "tag": "BUTTON", "text": "开始生成", "visible": True, "disabled": True},
            {"ref": "hidden", "tag": "BUTTON", "text": "Generate", "visible": False, "disabled": False},
            {"ref": "submit", "tag": "BUTTON", "type": "submit", "visible": True, "disabled": False},
        ]
    }

    assert provider_module.select_generation_submit(snapshot) == "submit"


def test_generation_submit_ignores_create_prompt_and_result_actions():
    snapshot = {"interactables": [
        {"ref": "prompt", "tag": "DIV", "contentEditable": True,
         "text": "Create a ten-second original shot. No subtitles. Generation prompt.", "visible": True},
        {"ref": "card", "tag": "BUTTON", "text": "Create a ten-second original shot", "visible": True},
        {"ref": "new", "tag": "BUTTON", "text": "Create project", "visible": True},
        {"ref": "submit", "tag": "BUTTON", "type": "submit", "text": "arrow_forward",
         "ariaLabel": "开始生成", "visible": True},
    ]}
    assert provider_module.select_generation_submit(snapshot) == "submit"


def test_prompt_selector_ignores_previous_generation_prompt_card():
    snapshot = {"interactables": [
        {"ref": "card", "tag": "BUTTON", "text": "Create a video. Generation prompt.", "visible": True},
        {"ref": "title", "tag": "INPUT", "ariaLabel": "可编辑文本", "visible": True},
        {"ref": "editor", "tag": "DIV", "contentEditable": True, "visible": True},
    ]}
    assert provider_module.select_text_input(snapshot, music=False) == "editor"


def test_video_status_queries_same_generation_and_persists_progress(monkeypatch, tmp_path):
    states = iter([{"state": "queued"}, {"state": "running", "operations": [{"id": "job", "progress": 42}]},
                   {"state": "succeeded", "assetUrl": "https://example.invalid/shot.mp4"}])
    queries = []
    class Client:
        def call_tool(self, name, arguments, **kwargs):
            assert name == "flow_generation_status"
            queries.append(arguments)
            return next(states)
    monkeypatch.setattr(provider_module.time, "sleep", lambda _: None)
    attempt = tmp_path / "shot.mp4.flow-attempt.json"
    attempt.write_text('{"state":"submitted","submitted":{"generationId":"one"}}')
    result = provider_module.wait_for_video_generation(Client(), generation_id="one", timeout_seconds=10, attempt_path=attempt)
    assert result["done"]
    assert queries == [{"generationId": "one"}] * 3
    rows = [json.loads(line) for line in attempt.with_suffix(".status.jsonl").read_text().splitlines()]
    assert [row["state"] for row in rows] == ["queued", "running", "succeeded"]
    assert json.loads(attempt.read_text())["submitted"]["generationId"] == "one"


def test_video_provider_failure_stops_without_resubmission(monkeypatch, tmp_path):
    class Client:
        def call_tool(self, name, arguments, **kwargs):
            assert name == "flow_generation_status"
            return {"state": "failed", "source": "provider_operation", "operations": [{"id": "one", "errorCode": "7"}]}
    attempt = tmp_path / "shot.mp4.flow-attempt.json"
    attempt.write_text('{"state":"submitted"}')
    with pytest.raises(provider_module.GoogleFlowMCPError, match="terminal failure"):
        provider_module.wait_for_video_generation(Client(), generation_id="one", timeout_seconds=10, attempt_path=attempt)
    assert json.loads(attempt.read_text())["state"] == "provider_failed"


def test_video_status_timeout_preserves_unknown_instead_of_claiming_failure(monkeypatch, tmp_path):
    ticks = iter([0, 0, 2, 2])
    monkeypatch.setattr(provider_module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(provider_module.time, "sleep", lambda _: None)
    class Client:
        def call_tool(self, name, arguments, **kwargs):
            assert name == "flow_generation_status"
            return {"state": "unknown", "source": "no_bound_operation"}
    attempt = tmp_path / "shot.mp4.flow-attempt.json"
    attempt.write_text('{"state":"submitted"}')
    with pytest.raises(provider_module.GoogleFlowMCPError, match="observation deadline"):
        provider_module.wait_for_video_generation(Client(), generation_id="one", timeout_seconds=1, attempt_path=attempt)
    receipt = json.loads(attempt.read_text())
    assert receipt["state"] == "submitted" and receipt["generation_status"]["state"] == "unknown"


@pytest.mark.parametrize("budget", [None, 10])
@pytest.mark.parametrize("prompt", ["product\n  turntable", "Create " + "x" * 1838])
def test_run_generation_types_then_clicks_with_acknowledgement(monkeypatch, tmp_path, budget, prompt):
    calls = []
    typing_timeouts = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def call_tool(self, name, arguments, timeout_seconds=None):
            calls.append((name, arguments))
            if name == "flow_snapshot":
                if any(call_name == "flow_type" for call_name, _ in calls):
                    return {"interactables": [{"ref": "submit", "type": "submit", "visible": True, "disabled": False}]}
                return {"interactables": [{"ref": "prompt", "contentEditable": True, "visible": True, "disabled": False}]}
            if name == "flow_type":
                typing_timeouts.append(timeout_seconds)
                return {"verified": True}
            if name == "flow_click":
                return {"submissionAcknowledged": True, "generationId": "test-generation"}
            if name == "flow_generation_status":
                assert arguments["generationId"] == "test-generation"
                return {"state": "succeeded", "assetUrl": "https://example.invalid/video.mp4"}
            if name == "flow_wait":
                return {"assetUrl": "https://example.invalid/video.mp4"}
            return {"ok": True}

    monkeypatch.setattr(provider_module, "GoogleFlowMCPClient", FakeClient)
    receipt = provider_module.run_generation(
        url="https://flow.google.com/project/example",
        prompt=prompt,
        output_path=tmp_path / "shot.mp4",
        expected_media_type="video",
        max_budget_credits=budget,
        timeout_seconds=60,
        music=False,
    )

    names = [name for name, _ in calls]
    approval_args = next(arguments for name, arguments in calls if name == "flow_confirm_paid_generation")
    assert ("maxBudgetCredits" in approval_args) == (budget is not None)
    assert names.index("flow_type") < names.index("flow_confirm_paid_generation") < names.index("flow_click")
    typed_args = next(arguments for name, arguments in calls if name == "flow_type")
    clicked_args = next(arguments for name, arguments in calls if name == "flow_click")
    assert typed_args["submit"] is False
    assert typed_args["text"] == " ".join(prompt.split())
    if len(prompt) > 1800:
        # The actual production prompt took ~57s in a local browser alone;
        # retain headroom for MCP scheduling instead of a fixed 60s deadline.
        assert typing_timeouts[0] >= 90
    assert names.count("flow_click") == 1
    assert clicked_args["requireGenerationAcknowledgement"] is True
    assert receipt["submitted"]["submissionAcknowledged"] is True


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


def test_google_flow_image_requires_explicit_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(image_module, "provider_status", lambda **kwargs: ToolStatus.AVAILABLE)
    result = GoogleFlowMCPImage().execute(
        {
            "prompt": "weathered lighthouse robot",
            "output_path": str(tmp_path / "robot.png"),
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


def test_video_error_returns_persisted_generation_status(monkeypatch, tmp_path):
    output_path = tmp_path / "shot.mp4"
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    def failed_generation(**kwargs):
        record = output_path.with_suffix(".mp4.flow-attempt.json")
        record.write_text(json.dumps({"state": "provider_failed", "generation_status": {"state": "failed", "source": "provider_operation"}}))
        raise provider_module.GoogleFlowMCPError("provider terminal failure")
    monkeypatch.setattr(video_module, "run_generation", failed_generation)
    result = GoogleFlowMCPVideo().execute({"prompt": "a shot", "output_path": str(output_path), "confirm_paid_generation": True})
    assert not result.success
    assert result.data["generation_status"]["state"] == "failed"
    assert Path(result.data["attempt_record"]).exists()


def test_google_flow_video_passes_reference_ingredients(monkeypatch, tmp_path):
    output_path = tmp_path / "shot.mp4"
    reference_path = tmp_path / "robot.png"
    reference_path.write_bytes(b"reference")
    captured = {}
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)

    def fake_run_generation(**kwargs):
        captured.update(kwargs)
        receipt = _receipt(output_path, "video")
        receipt["uploads"] = [{"uploaded": True}]
        return receipt

    monkeypatch.setattr(video_module, "run_generation", fake_run_generation)
    monkeypatch.setattr(video_module, "probe_media", lambda path, expected: {"duration_seconds": 6.0})
    result = GoogleFlowMCPVideo().execute(
        {
            "prompt": "robot cleans the lens",
            "output_path": str(output_path),
            "project_url": "https://labs.google/fx/tools/flow/project/example",
            "reference_paths": [str(reference_path)],
            "confirm_paid_generation": True,
            "max_budget_credits": 10,
        }
    )
    assert result.success
    assert captured["reference_paths"] == [reference_path]
    assert result.data["reference_count"] == 1
    assert result.data["upload_receipts"] == [{"uploaded": True}]


def test_google_flow_image_returns_mcp_and_probe_receipts(monkeypatch, tmp_path):
    output_path = tmp_path / "robot.png"
    monkeypatch.setattr(image_module, "provider_status", lambda **kwargs: ToolStatus.AVAILABLE)
    monkeypatch.setattr(image_module, "run_generation", lambda **kwargs: _receipt(output_path, "image"))
    monkeypatch.setattr(
        image_module,
        "probe_image",
        lambda path: {
            "width": 1080,
            "height": 1920,
            "format_name": "PNG",
            "mode": "RGB",
            "file_size_bytes": 4096,
        },
    )
    result = GoogleFlowMCPImage().execute(
        {
            "prompt": "weathered lighthouse robot",
            "output_path": str(output_path),
            "project_url": "https://labs.google/fx/tools/flow/project/example",
            "confirm_paid_generation": True,
            "max_budget_credits": 10,
        }
    )
    assert result.success
    assert result.data["model"] == "Nano Banana 2"
    assert result.data["width"] == 1080
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
    image = GoogleFlowMCPImage()
    assert video.capability == "video_generation"
    assert music.capability == "music_generation"
    assert image.capability == "image_generation"
    assert video.provider == music.provider == image.provider == "google_flow"
    assert video.get_status() == ToolStatus.AVAILABLE
    assert music.get_status() == ToolStatus.AVAILABLE
    assert image.get_status() == ToolStatus.AVAILABLE
    assert video.is_operation_available("text_to_video")
    assert video.is_operation_available("references_to_video")
    assert image.is_operation_available("text_to_image")
    assert not video.is_operation_available("video_edit")
