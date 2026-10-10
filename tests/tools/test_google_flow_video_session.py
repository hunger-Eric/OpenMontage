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
        if not self.tools:
            items.append(item("tools", "apps_spark_2 工具"))
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
            elif ref == "tools": self.tools = True
            elif ref == "settings": self.settings = True
            elif ref == "submit": return {"submissionAcknowledged": True}
            else:
                if ref == "aspect": self.aspect = "9:16"
                if ref == "duration": self.duration = 6
                self.settings = False
        if name == "flow_wait":
            return {"assetUrl": "https://example.invalid/shot.mp4", "jobId": "job-1"}
        return {}


def test_homepage_and_agent_mode_resolve_and_verify_settings():
    client = FlowUI()
    project = video_session.resolve_video_project(client)
    settings = video_session.configure_video_settings(client, project, "Omni 1.1 Flash", 6, "9:16")
    assert settings == dict(model="Omni 1.1 Flash", duration=6, aspect_ratio="9:16",
                            resolution="720p", results=1, verified=True)
    assert client.project and client.tools and client.aspect == "9:16" and client.duration == 6
    assert sum(args.get("ref") == "settings" for _, args in client.calls) == 5


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


def test_generation_persists_identity_and_duplicate_claim_blocks_payment(monkeypatch, tmp_path):
    clients = []
    def client_factory(**kwargs):
        client = FlowUI()
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
    with pytest.raises(GoogleFlowMCPError, match="already exists"):
        provider.run_generation(**kwargs)
    assert not any(name == "flow_confirm_paid_generation" for name, _ in clients[-1].calls)


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
    assert seen[0]["max_budget_credits"] == 10 and seen[0]["video_settings"]["duration"] == 6
    assert result.data["project_url"] == "https://flow.google.com/project/test"
    (tmp_path/"shot.mp4.flow-attempt.json").write_text('{"state":"submission_pending"}')
    result = video_module.GoogleFlowMCPVideo().execute(inputs)
    assert not result.success and result.data["error_code"] == "existing_attempt" and len(seen) == 1


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
