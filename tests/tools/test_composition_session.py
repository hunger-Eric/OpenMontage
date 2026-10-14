"""Acceptance reuse must not survive changed source, media or parameters."""
import json
from pathlib import Path

import pytest

from tools.base_tool import ToolResult
from tools.video.video_compose import VideoCompose


@pytest.fixture
def production(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source-video")
    return {
        "edit_decisions": {"version": "1.0", "render_runtime": "ffmpeg", "cuts": [
            {"id": "one", "source": "shot", "in_seconds": 0, "out_seconds": 2}]},
        "asset_manifest": {"version": "1.0", "assets": [{"id": "shot", "type": "video",
            "path": str(source), "source_tool": "local", "scene_id": "one"}]},
        "proposal_packet": {"version": "1.0", "concept_options": [
            {"id": str(i), "title": "test", "hook": "test", "narrative_structure": "story",
             "visual_approach": "test", "target_duration_seconds": 2, "why_this_works": "test"}
            for i in range(3)],
            "selected_concept": {"concept_id": "one", "rationale": "test"},
            "production_plan": {"pipeline": "animated-explainer", "stages": [], "render_runtime": "ffmpeg"},
            "cost_estimate": {"total_estimated_usd": 0, "line_items": [], "budget_verdict": "within_budget"},
            "approval": {"status": "approved"}},
        "decision_log": {"version": "1.0", "project_id": "test", "decisions": []},
        "output_path": str(tmp_path / "preview.mp4"),
    }


def accepted_preview(tool, production, monkeypatch):
    calls = []
    def render(inputs):
        calls.append("render")
        Path(inputs["output_path"]).write_bytes(b"reviewed-video")
        return ToolResult(success=True, data={"final_review": {"status": "pass", "checks": {}}}, artifacts=[])
    monkeypatch.setattr(tool, "_render", render)
    monkeypatch.setattr(tool, "run_command", lambda *a, **kw: calls.append("decode"))
    result = tool.execute(dict(production, operation="preview"))
    assert result.success, result.error
    review = Path(production["output_path"]).with_suffix(".visual.json")
    review.write_text(json.dumps({"owner": "current_codex_main_agent", "verdict": "accept",
        "method": "full_frame_sequence", "video_sha256": result.data["video_sha256"],
        "observations": [{"at_seconds": 1, "finding": "scene and narration match"}]}))
    return dict(production, operation="finalize", output_path=str(review.parent / "final.mp4"),
                preview_receipt_path=result.data["preview_receipt_path"], visual_review_path=str(review)), calls


def test_finalize_reuses_exact_bytes_without_render_or_review(production, monkeypatch):
    tool = VideoCompose()
    inputs, calls = accepted_preview(tool, production, monkeypatch)
    result = tool.execute(inputs)
    assert result.success, result.error
    assert calls == ["render", "decode"]
    assert Path(result.data["output"]).read_bytes() == b"reviewed-video"
    assert result.data["delivery_ready"]
    assert not tool.execute(inputs).success  # never overwrite historical output


@pytest.mark.parametrize("change", ["media", "timeline", "preview", "acceptance", "profile"])
def test_changed_evidence_blocks_reuse(production, monkeypatch, change):
    tool = VideoCompose()
    inputs, _ = accepted_preview(tool, production, monkeypatch)
    if change == "media":
        Path(production["asset_manifest"]["assets"][0]["path"]).write_bytes(b"different")
    elif change == "timeline":
        inputs["edit_decisions"]["cuts"][0]["out_seconds"] = 3
    elif change == "preview":
        Path(production["output_path"]).write_bytes(b"replaced-video")
    elif change == "acceptance":
        Path(inputs["visual_review_path"]).write_text('{}')
    else:
        inputs["profile"] = "tiktok"
    result = tool.execute(inputs)
    assert not result.success
    assert not Path(inputs["output_path"]).exists()


def test_missing_inputs_stop_before_renderer(production, monkeypatch):
    tool = VideoCompose()
    monkeypatch.setattr(tool, "_compose", lambda *_: pytest.fail("renderer reached"))
    Path(production["asset_manifest"]["assets"][0]["path"]).unlink()
    assert not tool.execute(dict(production, operation="render")).success


def test_schema_error_stops_before_renderer(production, monkeypatch):
    tool = VideoCompose()
    monkeypatch.setattr(tool, "_compose", lambda *_: pytest.fail("renderer reached"))
    production["edit_decisions"]["cuts"][0]["type"] = "legacy"
    assert not tool.execute(dict(production, operation="render")).success


def test_script_path_is_loaded_for_render(production, monkeypatch, tmp_path):
    tool = VideoCompose()
    script = tmp_path / "script.txt"
    script.write_text("真实旁白", encoding="utf8")
    def render(inputs):
        assert inputs["script_text"] == "真实旁白"
        return ToolResult(success=True)
    monkeypatch.setattr(tool, "_render", render)
    assert tool.execute(dict(production, operation="render", script_path=str(script))).success


@pytest.mark.parametrize("changed", ["module", "public", "props"])
def test_atelier_changes_invalidate_preview(production, monkeypatch, tmp_path, changed):
    entry = tmp_path / "index.tsx"
    entry.write_text("export {};", encoding="utf8")
    module = tmp_path / "Scene.tsx"
    module.write_text("export const Scene = 1;", encoding="utf8")
    public = tmp_path / "public"
    public.mkdir()
    media = public / "shot.mp4"
    media.write_bytes(b"static-media")
    props = tmp_path / "props.json"
    props.write_text('{}')
    production["edit_decisions"].update(composition_mode="atelier", bespoke={
        "entry": str(entry), "composition_id": "test", "art_direction": "original",
        "public_dir": str(public), "props_path": str(props)})
    tool = VideoCompose()
    inputs, _ = accepted_preview(tool, production, monkeypatch)
    target = {"module": module, "public": media, "props": props}[changed]
    target.write_bytes(b"changed")
    assert not tool.execute(inputs).success
    assert not Path(inputs["output_path"]).exists()


def test_failed_preview_never_writes_acceptance_receipt(production, monkeypatch):
    tool = VideoCompose()
    monkeypatch.setattr(tool, "_render", lambda *_: ToolResult(success=False, error="revise"))
    result = tool.execute(dict(production, operation="preview"))
    assert not result.success
    assert not Path(production["output_path"] + ".preview.json").exists()


def test_preview_reuses_inner_preflight_but_direct_render_remains_checked(production, monkeypatch):
    from tools.video import composition_session as session
    original = session.preflight
    calls = []
    def preflight(tool, inputs):
        calls.append("preflight")
        return original(tool, inputs)
    def render(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"reviewed-video")
        return ToolResult(success=True, data={"final_review": {"status": "pass"}})
    tool = VideoCompose()
    monkeypatch.setattr(session, "preflight", preflight)
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *args: None)
    monkeypatch.setattr(tool, "_render_via_ffmpeg", render)
    monkeypatch.setattr(tool, "run_command", lambda *a, **kw: None)
    assert tool.execute(dict(production, operation="preview")).success
    assert calls == ["preflight", "preflight"]  # before + after, not three
    Path(production["asset_manifest"]["assets"][0]["path"]).unlink()
    result = tool.execute(dict(production, operation="render", _validated_render=True))
    assert not result.success  # callers cannot smuggle a cached approval
    assert len(calls) == 3


def test_preview_detects_inputs_changed_during_render(production, monkeypatch):
    tool = VideoCompose()
    def render(inputs):
        Path(inputs["output_path"]).write_bytes(b"video")
        Path(inputs["asset_manifest"]["assets"][0]["path"]).write_bytes(b"changed-media")
        return ToolResult(success=True, data={"final_review": {"status": "pass"}})
    monkeypatch.setattr(tool, "_render", render)
    result = tool.execute(dict(production, operation="preview"))
    assert not result.success
    assert "changed while rendering" in result.error
    assert not Path(production["output_path"] + ".preview.json").exists()


def test_exception_cannot_leave_render_preflight_bypassed(production, monkeypatch):
    from tools.video import composition_session as session
    tool = VideoCompose()
    def crash(inputs):
        raise RuntimeError("render failed")
    monkeypatch.setattr(tool, "_render", crash)
    with pytest.raises(RuntimeError):
        session.preview(tool, production)
    Path(production["asset_manifest"]["assets"][0]["path"]).unlink()
    with pytest.raises(ValueError, match="missing or empty"):
        session.render_preflight(tool, production)
