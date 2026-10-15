from __future__ import annotations

import json

import pytest

from lib.config_model import OpenMontageConfig
from tools._google_flow_mcp import provider, video_session
from tools._google_flow_mcp.client import GoogleFlowMCPError
from tools.base_tool import ToolStatus
from tools.video import google_flow_mcp_video as video_module
from tools.video.video_selector import VideoSelector


class FlowUI:
    """Settings close after each choice, as on Flow's browser surface."""

    def __init__(self, **kwargs):
        self.project = False
        self.tools = False
        self.settings = False
        self.duration = 4
        self.aspect = "16:9"
        self.calls = []
        self.agent_collapsed = False
        self.close_only_collapses = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def snapshot(self):
        def item(ref, text, role="button", **extra):
            return dict(ref=ref, text=text, role=role, visible=True, disabled=False, **extra)
        if not self.project:
            return {"url": "https://flow.google.com/", "interactables": [item("new", "新建项目")]}
        items = [item("prompt", "", contentEditable=True)]
        items.append(item("tools-gallery", "apps_spark_2 工具", "link", tag="A"))
        if not self.tools:
            if self.agent_collapsed:
                items.append(item("agent-toggle", "智能体"))
            items += [item("agent-instructions", "article_spark", ariaLabel="智能体指令"),
                      item("expand-agent", "expand_content", ariaLabel="展开") if self.agent_collapsed
                      else item("close-agent", "close", ariaLabel="关闭")]
        else:
            items.append(item("settings", f"设置触发器 720p {self.duration} 秒 {self.aspect} x1"))
        if self.settings:
            items += [item("model", "Omni 1.1 Flash"), item("video", "视频", "radio"),
                      item("aspect", "9:16", "radio"), item("resolution", "720p", "radio"),
                      item("duration", "6 秒", "radio"), item("count", "x1", "radio")]
        items.append(item("submit", "Generate", type="submit"))
        return {"url": "https://flow.google.com/project/test", "interactables": items}

    def call_tool(self, name, arguments, timeout_seconds=None):
        self.calls.append((name, arguments))
        if name == "flow_snapshot":
            return self.snapshot()
        if name == "flow_type":
            return {"verified": True}
        if name == "flow_click":
            ref = arguments["ref"]
            if ref == "new": self.project = True
            elif ref == "expand-agent": self.agent_collapsed = False
            elif ref == "close-agent":
                if self.close_only_collapses: self.agent_collapsed = True
                else: self.tools = True
            elif ref == "agent-toggle": self.tools = True
            elif ref == "tools-gallery": pytest.fail("Tools gallery is not a video mode switch")
            elif ref == "settings": self.settings = True
            elif ref == "submit": return {"submissionAcknowledged": True, "generationId": "test-generation"}
            else:
                if ref == "aspect": self.aspect = "9:16"
                if ref == "duration": self.duration = 6
                self.settings = False
        if name == "flow_wait":
            return {"assetUrl": "https://example.invalid/shot.mp4", "jobId": "job-1"}
        if name == "flow_generation_status":
            assert arguments["generationId"] == "test-generation"
            return {"state": "succeeded", "assetUrl": "https://example.invalid/shot.mp4", "jobId": "job-1"}
        return {}


def test_homepage_and_agent_mode_resolve_and_verify_settings():
    client = FlowUI()
    project = video_session.resolve_video_project(client)
    settings = video_session.configure_video_settings(client, project, "Omni 1.1 Flash", 6, "9:16")
    assert settings == dict(model="Omni 1.1 Flash", duration=6, aspect_ratio="9:16",
                            resolution="720p", results=1, verified=True)
    assert client.project and client.tools and client.aspect == "9:16" and client.duration == 6
    assert sum(args.get("ref") == "settings" for _, args in client.calls) == 5
    assert any(args.get("ref") == "close-agent" for _, args in client.calls)


def test_video_reference_mode_does_not_require_unavailable_duration_control():
    client = FlowUI()
    client.project = client.tools = True
    original = client.snapshot
    def snapshot():
        result = original()
        result['interactables'] = [item for item in result['interactables'] if item['ref'] != 'duration']
        return result
    client.snapshot = snapshot
    settings = video_session.configure_video_settings(
        client, 'https://flow.google.com/project/test', 'Omni 1.1 Flash', 8, '9:16',
        inherit_video_duration=True,
    )
    assert settings['verified'] and settings['duration'] is None
    assert settings['duration_mode'] == 'source_video' and settings['requested_duration'] == 8
    assert client.duration == 4 and client.aspect == '9:16'
    assert not any(args.get('ref') == 'duration' for name, args in client.calls if name == 'flow_click')


def test_video_reference_cannot_attest_source_mode_with_ordinary_duration_controls():
    client = FlowUI()
    client.project = client.tools = True
    with pytest.raises(GoogleFlowMCPError, match='source_video mode'):
        video_session.configure_video_settings(client, 'https://flow.google.com/project/test',
            'Omni 1.1 Flash', 8, '9:16', inherit_video_duration=True)


@pytest.mark.parametrize("initial_mode", ["video", "agent_expanded", "agent_collapsed", "agent_close_collapses"])
def test_video_and_both_agent_panel_states_are_supported(initial_mode):
    client = FlowUI()
    client.project = True
    client.tools = initial_mode == "video"
    client.agent_collapsed = initial_mode == "agent_collapsed"
    client.close_only_collapses = initial_mode == "agent_close_collapses"
    video_session.configure_video_settings(client, "https://flow.google.com/project/test",
                                           "Omni 1.1 Flash", 6, "9:16")
    clicked = [args.get("ref") for name, args in client.calls if name == "flow_click"]
    assert "tools-gallery" not in clicked
    assert ("close-agent" in clicked) == (initial_mode in {"agent_expanded", "agent_close_collapses"})
    assert ("agent-toggle" in clicked) == (initial_mode in {"agent_collapsed", "agent_close_collapses"})
    assert client.aspect == "9:16" and client.duration == 6


def test_gallery_link_alone_never_triggers_navigation_or_payment(monkeypatch):
    client = FlowUI()
    client.snapshot = lambda: {"url": "https://flow.google.com/project/test", "interactables": [
        dict(ref="gallery", text="apps_spark_2 工具", tag="A", visible=True, disabled=False)]}
    def once(client, ready, message):
        snapshot = client.call_tool("flow_snapshot", {})
        if not ready(snapshot): raise GoogleFlowMCPError(message)
        return snapshot
    monkeypatch.setattr(video_session, "wait_snapshot", once)
    with pytest.raises(GoogleFlowMCPError, match="supported Agent panel"):
        video_session.configure_video_settings(client, "https://flow.google.com/project/test",
                                               "Omni 1.1 Flash", 6, "9:16")
    assert all(name == "flow_snapshot" for name, _ in client.calls)


def test_missing_model_stops_before_credit_confirmation(monkeypatch, tmp_path):
    client = FlowUI()
    monkeypatch.setattr(provider, "GoogleFlowMCPClient", lambda **kwargs: client)
    def once(client, ready, message):
        snapshot = client.call_tool("flow_snapshot", {})
        if not ready(snapshot): raise GoogleFlowMCPError(message)
        return snapshot
    monkeypatch.setattr(video_session, "wait_snapshot", once)
    with pytest.raises(GoogleFlowMCPError, match="unavailable"):
        provider.run_generation(url="https://flow.google.com/", prompt="a shot", output_path=tmp_path/"shot.mp4",
                                expected_media_type="video", max_budget_credits=10, timeout_seconds=60,
                                music=False, video_settings=dict(model="Unavailable model", duration=6, aspect_ratio="9:16"))
    assert not any(name in {"flow_type", "flow_confirm_paid_generation"} for name, _ in client.calls)


def test_unverified_reference_upload_stops_before_prompt_and_generation(monkeypatch, tmp_path):
    client = FlowUI()
    monkeypatch.setattr(provider, "GoogleFlowMCPClient", lambda **kw: client)
    reference = tmp_path / "product.jpg"
    reference.write_bytes(b"reference fixture")
    with pytest.raises(GoogleFlowMCPError, match="did not verify the reference upload"):
        provider.run_generation(url="https://flow.google.com/", prompt="product", output_path=tmp_path / "shot.mp4",
                                expected_media_type="video", max_budget_credits=None, timeout_seconds=60, music=False,
                                reference_paths=[reference], video_settings={"model": "Omni 1.1 Flash", "duration": 6, "aspect_ratio": "9:16"})
    assert any(name == "flow_upload" for name, _ in client.calls)
    assert not any(name in {"flow_type", "flow_confirm_paid_generation"} for name, _ in client.calls)


def test_generation_persists_identity_and_duplicate_claim_blocks_payment(monkeypatch, tmp_path):
    clients = []
    observed_states = []
    def client_factory(**kwargs):
        client = FlowUI()
        original_call = client.call_tool
        def call(name, arguments, **call_kwargs):
            if name in {"flow_open", "flow_type", "flow_confirm_paid_generation"} or (name == "flow_click" and arguments.get("requireGenerationAcknowledgement")):
                record = json.loads((tmp_path / "shot.mp4.flow-attempt.json").read_text())
                observed_states.append((name, record["generation_status"]["state"]))
            return original_call(name, arguments, **call_kwargs)
        client.call_tool = call
        clients.append(client)
        return client
    monkeypatch.setattr(provider, "GoogleFlowMCPClient", client_factory)
    kwargs = dict(url="https://flow.google.com/", prompt="a shot", output_path=tmp_path/"shot.mp4",
                  expected_media_type="video", max_budget_credits=10, timeout_seconds=60,
                  music=False, video_settings=dict(model="Omni 1.1 Flash", duration=6, aspect_ratio="9:16"))
    receipt = provider.run_generation(**kwargs)
    assert receipt["opened"]["url"] == "https://flow.google.com/project/test"
    record = json.loads((tmp_path/"shot.mp4.flow-attempt.json").read_text())
    assert record["wait"]["jobId"] == "job-1" and record["settings"]["verified"]
    assert observed_states == [("flow_open", "not_started"), ("flow_type", "not_started"),
                               ("flow_confirm_paid_generation", "not_started"), ("flow_click", "unknown")]
    with pytest.raises(GoogleFlowMCPError, match="already exists"):
        provider.run_generation(**kwargs)
    assert not any(name == "flow_confirm_paid_generation" for name, _ in clients[-1].calls)


def test_ack_timeout_keeps_preassigned_identity_and_reads_same_submission(monkeypatch, tmp_path):
    client = FlowUI()
    original = client.call_tool
    identities = []
    def call(name, arguments, **kwargs):
        if name == "flow_click" and arguments.get("requireGenerationAcknowledgement"):
            record = json.loads((tmp_path / "shot.mp4.flow-attempt.json").read_text())
            assert record["generation_id"] == arguments["generationId"]
            identities.append(arguments["generationId"])
            raise GoogleFlowMCPError("acknowledgement timeout")
        if name == "flow_generation_status" and identities:
            assert arguments["generationId"] == identities[0]
            return {"state": "queued", "jobId": "native-original-task", "source": "provider_operation"}
        return original(name, arguments, **kwargs)
    client.call_tool = call
    monkeypatch.setattr(provider, "GoogleFlowMCPClient", lambda **kwargs: client)
    with pytest.raises(GoogleFlowMCPError, match="acknowledgement timeout"):
        provider.run_generation(url="https://flow.google.com/", prompt="a shot", output_path=tmp_path/"shot.mp4",
                                expected_media_type="video", max_budget_credits=None, timeout_seconds=60,
                                music=False, video_settings=dict(model="Omni 1.1 Flash", duration=6, aspect_ratio="9:16"))
    record = json.loads((tmp_path/"shot.mp4.flow-attempt.json").read_text())
    assert record["job_id"] == "native-original-task"
    assert record["generation_status"]["state"] == "queued"
    assert record["acknowledgement_timeout"] is True and len(identities) == 1


def test_video_uses_local_model_homepage_budget_and_rejects_existing_attempt(monkeypatch, tmp_path):
    config = OpenMontageConfig.model_validate({"google_flow": {"model": "Omni 1.1 Flash"}})
    monkeypatch.setattr(video_module.OpenMontageConfig, "load", lambda: config)
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    seen = []
    def generate(**kwargs):
        seen.append(kwargs)
        return {"opened": {"url": "https://flow.google.com/project/test"}, "wait": {}, "download": {}}
    monkeypatch.setattr(video_module, "run_generation", generate)
    monkeypatch.setattr(video_module, "probe_media", lambda *args: {})
    inputs = dict(prompt="a shot", output_path=str(tmp_path/"shot.mp4"), confirm_paid_generation=True)
    result = video_module.GoogleFlowMCPVideo().execute(inputs)
    assert result.success and result.data["model"] == "Omni 1.1 Flash"
    assert seen[0]["max_budget_credits"] is None and seen[0]["video_settings"]["duration"] == 6
    assert result.data["project_url"] == "https://flow.google.com/project/test"
    assert video_module.GoogleFlowMCPVideo().dry_run(inputs)["requires_explicit_credit_approval"] is False
    result = video_module.GoogleFlowMCPVideo().execute({**inputs, "max_budget_credits": 25})
    assert result.success and seen[-1]["max_budget_credits"] == 25
    (tmp_path/"shot.mp4.flow-attempt.json").write_text('{"state":"submission_pending"}')
    result = video_module.GoogleFlowMCPVideo().execute(inputs)
    assert not result.success and result.data["error_code"] == "existing_attempt" and len(seen) == 2


def test_selector_resolves_configured_flow_model_without_generation(monkeypatch):
    config = OpenMontageConfig.model_validate({"providers": {"video_provider": "google_flow", "restrict_to_preferences": True},
                                             "google_flow": {"model": "Omni 1.1 Flash"}})
    monkeypatch.setattr(OpenMontageConfig, "load", lambda: config)
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(VideoSelector, "_providers", lambda self: [video_module.GoogleFlowMCPVideo()])
    result = VideoSelector().execute({"operation": "rank", "generation_mode": "text_to_video", "prompt": "a shot"})
    assert result.success and result.data["selected_tool"] == "google_flow_mcp_video"
    assert result.data["selected_model"] == "Omni 1.1 Flash"
    result = VideoSelector().execute({"operation": "rank", "generation_mode": "text_to_video", "model": "Omni 1.1 Flash"})
    assert result.data["selected_tool"] == "google_flow_mcp_video"


@pytest.mark.parametrize("duration,ratio", [(3,"16:9"), (6,"1:1")])
def test_invalid_settings_do_not_open_browser(monkeypatch, tmp_path, duration, ratio):
    monkeypatch.setattr(video_module, "provider_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(video_module, "run_generation", lambda **kwargs: pytest.fail("browser must not open"))
    result = video_module.GoogleFlowMCPVideo().execute(dict(prompt="a shot", output_path=str(tmp_path/"shot.mp4"),
                                                        confirm_paid_generation=True, duration=duration, aspect_ratio=ratio))
    assert not result.success and result.data["error_code"] == "invalid_video_settings"
