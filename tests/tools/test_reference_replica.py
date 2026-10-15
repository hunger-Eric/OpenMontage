"""Source bindings and timeline failures at registered production entries."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest
import jsonschema

from schemas.artifacts import validate_artifact
from tools.base_tool import ToolResult, ToolStatus
from tools.video.reference_contract import compile_timeline, sha256, verify_generation_reference
from tools.video.video_compose import VideoCompose
from tools.video.video_trimmer import VideoTrimmer
from tools.video.google_flow_mcp_video import GoogleFlowMCPVideo


@pytest.fixture
def replica(tmp_path):
    source = tmp_path / "reference.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=30:d=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    units = [{"id": f"u{i}", "source_start_frame": i * 30, "source_end_frame": (i + 1) * 30,
              "action": "Authored action", "composition": "Authored foreground and camera", "internal_cuts": [],
              "material": "generated_video"} for i in range(2)]
    proposal = {"version": "1.0", "concept_options": [{"id": "replica", "title": "replica", "hook": "source hook",
                "narrative_structure": "story", "visual_approach": "source", "target_duration_seconds": 2, "why_this_works": "source"}],
                "selected_concept": {"concept_id": "replica", "rationale": "explicit user copying intent"},
                "production_plan": {"pipeline": "cinematic", "stages": [], "render_runtime": "remotion"},
                "cost_estimate": {"total_estimated_usd": None, "line_items": [], "budget_verdict": "usage_unknown"},
                "approval": {"status": "pending"}, "metadata": {"reference_adaptation": {
                    "mode": "faithful_replica", "reference_evidence": {"source_path": str(source), "sha256": sha256(source)},
                    "replica": {"fps": 30, "total_frames": 60, "width": 160, "height": 90, "background_color": "black",
                                "units": units, "captions": [{"id": "cue", "unit_id": "u0", "start_frame": 0, "end_frame": 15,
                                "text": "KEEP", "style": {"left": 0, "top": 0, "width": 160, "height": 30, "fontSize": 20,
                                "fontFamily": "Arial", "fontWeight": 700, "color": "white", "strokeColor": "black", "strokeWidth": 1}}],
                                "audio": {"policy": "reuse_source", "authorized": True, "path": str(source),
                                          "sha256": sha256(source), "provenance": "same frozen source audio stream"}}}}}
    proposal_path = tmp_path / "proposal_packet.json"
    validate_artifact("proposal_packet", proposal)
    proposal_path.write_text(json.dumps(proposal), encoding="utf8")
    ref = {"proposal_path": str(proposal_path), "proposal_sha256": sha256(proposal_path)}
    review = {"status": "pass", "observations": "Actual synthetic fixture reviewed for test boundaries only",
              "checks": {key: "pass" for key in ("composition", "action", "timing", "embedded_text", "lip_sync")}}
    edit = {"version": "1.0", "render_runtime": "remotion", "renderer_family": "documentary-montage",
            "cuts": [{"id": f"c{i}", "source": "shot", "in_seconds": i, "out_seconds": i + 1} for i in range(2)],
            "metadata": {"reference_adaptation_ref": ref, "reference_timeline": {
                "segments": [{"unit_id": f"u{i}", "cut_id": f"c{i}", "media_sha256": sha256(source),
                              "fidelity_review": deepcopy(review)} for i in range(2)],
                "caption_dispositions": [{"cue_id": "cue", "handling": "overlay", "evidence": "no embedded caption",
                                          "media_sha256": sha256(source)}]}}}
    return {"proposal_packet": proposal, "edit_decisions": edit,
            "asset_manifest": {"version": "1.0", "assets": [{"id": "shot", "type": "video", "path": str(source),
                "scene_id": "u0", "source_tool": "local"}], "metadata": {"reference_adaptation_ref": ref}},
            "decision_log": {"version": "1.0", "project_id": "fixture", "decisions": []},
            "output_path": str(tmp_path / "preview.mp4")}


def test_registered_source_slice_and_provider_preparation_bind_exact_unit(replica, tmp_path):
    ref = replica["edit_decisions"]["metadata"]["reference_adaptation_ref"]
    inputs = {"operation": "reference_clip", "reference_adaptation_ref": ref, "reference_unit_id": "u1",
              "output_path": str(tmp_path / "u1.mp4")}
    result = VideoTrimmer().execute(inputs)
    assert result.success, result.error
    assert abs(result.data["duration_seconds"] - 1) < .06
    request = {"reference_adaptation_ref": ref, "reference_unit_id": "u1",
               "reference_receipt_path": result.data["reference_receipt_path"],
               "reference_paths": [result.data["path"]], "prompt": "Keep exact source camera", "model": "chosen"}
    prepared = GoogleFlowMCPVideo().prepare_video_request(request)
    assert prepared == request
    assert verify_generation_reference(prepared, [Path(result.data["path"])])["source_start_frame"] == 30
    assert not VideoTrimmer().execute(inputs).success  # no overwriting accepted derivatives
    wrong_unit = dict(request, reference_unit_id="u0")
    with pytest.raises(ValueError, match="receipt"):
        GoogleFlowMCPVideo().prepare_video_request(wrong_unit)
    with pytest.raises(ValueError, match="missing"):
        GoogleFlowMCPVideo().prepare_video_request(dict(request, reference_paths=[]))
    Path(result.data["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        GoogleFlowMCPVideo().prepare_video_request(request)


@pytest.mark.parametrize("mode", [None, "creative_adaptation"])
def test_adaptation_and_legacy_do_not_require_replica_fields(replica, mode):
    proposal = deepcopy(replica["proposal_packet"])
    proposal["metadata"]["reference_adaptation"] = {} if mode is None else {"mode": mode}
    validate_artifact("proposal_packet", proposal)
    assert compile_timeline(dict(replica, proposal_packet=proposal)) is None


@pytest.mark.parametrize("change", ["gap", "reorder", "duplicate_unit", "internal_cut", "audio_authorization", "caption_range"])
def test_plan_rejects_broken_source_clock(replica, change):
    proposal = deepcopy(replica["proposal_packet"])
    plan = proposal["metadata"]["reference_adaptation"]["replica"]
    if change == "gap": plan["units"][1]["source_start_frame"] = 31
    if change == "reorder": plan["units"].reverse()
    if change == "duplicate_unit": plan["units"][1]["id"] = "u0"
    if change == "internal_cut": plan["units"][0]["internal_cuts"] = [31]
    if change == "audio_authorization": plan["audio"]["authorized"] = False
    if change == "caption_range": plan["captions"][0]["end_frame"] = 61
    with pytest.raises((ValueError, jsonschema.ValidationError)):
        validate_artifact("proposal_packet", proposal)


def test_compile_executes_native_trim_clock_and_embedded_caption_layer(replica):
    props = compile_timeline(replica)
    assert props["total_frames"] == 60
    assert [(c["from"], c["duration"], c["trimBefore"]) for c in props["clips"]] == [(0, 30, 0), (30, 30, 30)]
    assert len(props["captions"]) == 1
    replica["edit_decisions"]["metadata"]["reference_timeline"]["caption_dispositions"][0]["handling"] = "embedded"
    assert compile_timeline(replica)["captions"] == []


def test_explicit_endpoint_hold_preserves_clock_without_whole_clip_stretch(replica):
    replica["edit_decisions"]["cuts"][1]["out_seconds"] = 1 + 29 / 30
    segment = replica["edit_decisions"]["metadata"]["reference_timeline"]["segments"][1]
    segment.update(end_hold_frames=1, time_transform_reason="One measured frame gap")
    clip = compile_timeline(replica)["clips"][1]
    assert clip["pictureFrames"] == 29 and clip["duration"] == 30 and clip["playbackRate"] == 1
    segment.pop("time_transform_reason")
    with pytest.raises(ValueError, match="End hold"):
        compile_timeline(replica)


def test_selector_preserves_binding_and_refuses_unimplemented_route(replica, monkeypatch):
    from tools.video.video_selector import VideoSelector
    from tools.video import google_flow_mcp_video as flow
    selector = VideoSelector()
    provider = GoogleFlowMCPVideo()
    ref = replica["edit_decisions"]["metadata"]["reference_adaptation_ref"]
    root = Path(replica["output_path"]).parent
    result = VideoTrimmer().execute({"operation": "reference_clip", "reference_adaptation_ref": ref,
        "reference_unit_id": "u0", "output_path": str(root / "selector-reference.mp4")})
    assert result.success, result.error
    request = {"operation": "reference_to_video", "preferred_tool": provider.name, "model": "chosen",
        "prompt": "exact authored content", "reference_adaptation_ref": ref, "reference_unit_id": "u0",
        "reference_receipt_path": result.data["reference_receipt_path"], "reference_paths": [result.data["path"]]}
    monkeypatch.setattr(flow, "provider_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(selector, "_providers", lambda: [provider])
    monkeypatch.setattr(selector, "_select_best_tool", lambda *args: (provider, None))
    received = []
    monkeypatch.setattr(provider, "execute", lambda inputs: received.append(inputs) or ToolResult(success=True))
    assert selector.execute(request).success
    assert all(received[0][key] == value for key, value in request.items())
    provider.supports = {**provider.supports, "source_timeline_binding": False}
    assert not selector.execute(request).success
    assert len(received) == 1


@pytest.mark.parametrize("change", ["proposal_sha", "source_sha", "media_sha", "cut_order", "nominal_duration", "out_of_range", "stretch", "missing_caption", "duplicate_caption", "stale_caption", "duplicate_subtitle", "audio_override", "false_pass"])
def test_official_compose_preflight_rejects_invalid_binding(replica, change, tmp_path):
    edit = replica["edit_decisions"]
    mapping = edit["metadata"]["reference_timeline"]
    if change == "proposal_sha": edit["metadata"]["reference_adaptation_ref"]["proposal_sha256"] = "0" * 64
    if change == "source_sha": Path(replica["asset_manifest"]["assets"][0]["path"]).write_bytes(b"changed")
    if change == "media_sha": mapping["segments"][0]["media_sha256"] = "0" * 64
    if change == "cut_order": edit["cuts"].reverse()
    if change == "nominal_duration": edit["cuts"][0]["out_seconds"] = 8
    if change == "out_of_range": edit["cuts"][1].update(in_seconds=2, out_seconds=3)
    if change == "stretch": edit["cuts"][0]["speed"] = 2
    if change == "missing_caption": mapping["caption_dispositions"] = []
    if change == "duplicate_caption": mapping["caption_dispositions"] *= 2
    if change == "stale_caption": mapping["caption_dispositions"][0]["media_sha256"] = "0" * 64
    if change == "duplicate_subtitle": edit["subtitles"] = {"enabled": True}
    if change == "audio_override": replica["audio_path"] = str(tmp_path / "other.wav")
    if change == "false_pass": mapping["segments"][0]["fidelity_review"]["checks"]["lip_sync"] = "unverified"
    result = VideoCompose().execute(dict(replica, operation="preflight"))
    assert not result.success, change


def test_technical_preview_does_not_finalize_unverified_fidelity(replica, monkeypatch, tmp_path):
    review = replica["edit_decisions"]["metadata"]["reference_timeline"]["segments"][0]["fidelity_review"]
    review.update(status="unverified")
    review["checks"]["lip_sync"] = "unverified"
    tool = VideoCompose()
    def render(inputs):
        Path(inputs["output_path"]).write_bytes(b"preview-fixture")
        return ToolResult(success=True, data={"final_review": {"status": "pass"}}, artifacts=[])
    monkeypatch.setattr(tool, "_render", render)
    monkeypatch.setattr(tool, "run_command", lambda *args, **kwargs: None)
    result = tool.execute(dict(replica, operation="preview"))
    assert result.success, result.error
    assert result.data["reference_fidelity"]["status"] == "unverified"
    finalize = tool.execute(dict(replica, operation="finalize", preview_receipt_path=result.data["preview_receipt_path"],
                                 output_path=str(tmp_path / "final.mp4")))
    assert not finalize.success and "fidelity" in finalize.error
    assert not (tmp_path / "final.mp4").exists()


def test_segment_pass_does_not_replace_whole_preview_reference_comparison(replica, monkeypatch, tmp_path):
    tool = VideoCompose()
    def render(inputs):
        Path(inputs["output_path"]).write_bytes(b"preview-fixture")
        return ToolResult(success=True, data={"final_review": {"status": "pass"}}, artifacts=[])
    monkeypatch.setattr(tool, "_render", render)
    monkeypatch.setattr(tool, "run_command", lambda *args, **kwargs: None)
    result = tool.execute(dict(replica, operation="preview"))
    assert result.success, result.error
    visual = tmp_path / "visual.json"
    visual.write_text(json.dumps({"owner": "current_codex_main_agent", "method": "continuous_watch",
        "verdict": "accept", "video_sha256": result.data["video_sha256"], "observations": "fixture visual review only"}))
    finalize = tool.execute(dict(replica, operation="finalize", preview_receipt_path=result.data["preview_receipt_path"],
        visual_review_path=str(visual), output_path=str(tmp_path / "final.mp4")))
    assert not finalize.success and "reference comparison" in finalize.error


def test_faithful_presenter_uses_source_layers_instead_of_old_transcript_handoff(replica):
    replica["edit_decisions"]["renderer_family"] = "presenter"
    result = VideoCompose().execute(dict(replica, operation="preflight"))
    assert result.success, result.error


@pytest.mark.parametrize("loss", ["attachment", "bytes"])
def test_final_bound_reference_loss_stops_before_credit_confirmation(replica, monkeypatch, tmp_path, loss):
    from tools._google_flow_mcp import provider, video_session
    ref = replica["edit_decisions"]["metadata"]["reference_adaptation_ref"]
    clip = VideoTrimmer().execute({"operation": "reference_clip", "reference_adaptation_ref": ref,
        "reference_unit_id": "u0", "output_path": str(tmp_path / "upload-reference.mp4")})
    assert clip.success, clip.error
    request = {"reference_adaptation_ref": ref, "reference_unit_id": "u0", "reference_receipt_path": clip.data["reference_receipt_path"]}
    path = Path(clip.data["path"])
    binding = verify_generation_reference(request, [path])
    calls = []
    class Client:
        def __init__(self, **kwargs): self.uploads = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def call_tool(self, name, arguments, **kwargs):
            calls.append(name)
            if name == "flow_upload":
                self.uploads += 1
                return {"uploaded": True, "verified": not (loss == "attachment" and self.uploads == 2)}
            if name == "flow_type":
                if loss == "bytes": path.write_bytes(b"changed while typing")
                return {"verified": True}
            return {}
    monkeypatch.setattr(provider, "GoogleFlowMCPClient", Client)
    monkeypatch.setattr(video_session, "resolve_video_project", lambda client, **kwargs: "https://flow.google.com/project/test")
    monkeypatch.setattr(video_session, "configure_video_settings", lambda *args, **kwargs: {"verified": True})
    monkeypatch.setattr(provider, "wait_for_text_input", lambda *args, **kwargs: "prompt")
    with pytest.raises(Exception, match="attached|changed"):
        provider.run_generation(url="https://flow.google.com/project/test", prompt="Keep source", output_path=tmp_path / "shot.mp4",
            expected_media_type="video", max_budget_credits=None, timeout_seconds=30, music=False, reference_paths=[path],
            video_settings={"model": "chosen", "duration": 8, "aspect_ratio": "16:9"}, reference_binding=binding)
    assert "flow_confirm_paid_generation" not in calls and "flow_click" not in calls
    attempt = json.loads((tmp_path / "shot.mp4.flow-attempt.json").read_text())
    assert attempt["generation_status"]["state"] == "not_started" and "generation_id" not in attempt


def test_unknown_flow_attempt_is_never_resent_even_with_new_binding(replica, monkeypatch, tmp_path):
    from tools.video import google_flow_mcp_video as flow
    output = tmp_path / "unknown.mp4"
    output.with_suffix(".mp4.flow-attempt.json").write_text(json.dumps({"generation_id": "original",
        "generation_status": {"state": "unknown"}}))
    monkeypatch.setattr(flow, "provider_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(flow, "run_generation", lambda **kwargs: pytest.fail("duplicate submit"))
    result = GoogleFlowMCPVideo().execute({"prompt": "replica", "output_path": str(output), "confirm_paid_generation": True,
        "reference_adaptation_ref": replica["edit_decisions"]["metadata"]["reference_adaptation_ref"]})
    assert not result.success and result.data["error_code"] == "existing_attempt"
