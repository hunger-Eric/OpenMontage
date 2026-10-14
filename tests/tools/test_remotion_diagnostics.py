"""Tests for Remotion render debuggability in video_compose (issue #217).

Two creator-facing gaps:
  1. A failed `npx remotion render` surfaced only "returned non-zero exit
     status 1"; the useful Remotion diagnostics in stderr were dropped.
  2. There was no pass-through for Remotion's `--timeout`, so a slow headless
     browser setup failed opaquely with no way to raise the limit.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    return VideoCompose()


def test_render_failure_surfaces_remotion_stderr_tail(tool, tmp_path, monkeypatch):
    stderr = "some npm noise\nError: Delayed render timed out\nRemotion actual cause here"

    def fake_run_command(cmd, *a, **k):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, output="", stderr=stderr)

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert result.success is False
    assert "exit 1" in result.error
    assert "Remotion actual cause here" in result.error


def test_timeout_expired_gives_actionable_message(tool, tmp_path, monkeypatch):
    def fake_run_command(cmd, *a, **k):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=600)

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert result.success is False
    assert "timed out" in result.error.lower()
    assert "remotion_timeout_ms" in result.error


def test_remotion_timeout_ms_is_passed_through(tool, tmp_path, monkeypatch):
    seen = {}

    def fake_run_command(cmd, *a, **k):
        seen["cmd"] = cmd
        seen["timeout"] = k.get("timeout")
        return None  # output file intentionally absent

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    tool._remotion_render(
        {
            "composition_data": {"cuts": []},
            "output_path": str(tmp_path / "out.mp4"),
            "remotion_timeout_ms": 120000,
        }
    )

    assert "--timeout=120000" in seen["cmd"]
    # subprocess timeout widened past the 120s render budget so run_command
    # does not kill Remotion before its own timeout fires.
    assert seen["timeout"] >= 180


def test_high_level_render_forwards_timeout_to_remotion(tool, tmp_path, monkeypatch):
    # The gap in the first cut: execute(operation="render") -> _render() builds a
    # fresh remotion_inputs dict, so the option must be forwarded there, not only
    # on a direct _remotion_render() call.
    captured = {}
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *a, **k: None)
    monkeypatch.setattr(tool, "_needs_remotion", lambda *a, **k: True)

    def fake_remotion_render(inputs):
        captured.update(inputs)
        from tools.base_tool import ToolResult

        return ToolResult(success=True, data={}, artifacts=[])

    monkeypatch.setattr(tool, "_remotion_render", fake_remotion_render)
    monkeypatch.setattr(tool, "_run_final_review", lambda *a, **k: {})

    tool._render(
        {
            "edit_decisions": {
                "render_runtime": "remotion",
                "renderer_family": "explainer-data",
                "cuts": [{"id": "c1", "source": "a1", "in_seconds": 0, "out_seconds": 2}],
            },
            "asset_manifest": {"assets": [{"id": "a1", "path": "/tmp/a1.mp4"}]},
            "output_path": str(tmp_path / "out.mp4"),
            "remotion_timeout_ms": 120000,
        }
    )

    assert captured.get("remotion_timeout_ms") == 120000


def test_no_timeout_flag_when_not_requested(tool, tmp_path, monkeypatch):
    seen = {}

    def fake_run_command(cmd, *a, **k):
        seen["cmd"] = cmd
        seen["timeout"] = k.get("timeout")
        return None

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert not any(str(c).startswith("--timeout") for c in seen["cmd"])
    assert seen["timeout"] == 600


def _presenter_inputs(tmp_path):
    video = tmp_path / "assembled.mp4"
    video.write_bytes(b"assembled-source")
    transcript = tmp_path / "assembled.transcript.json"
    transcript.write_text(
        json.dumps({"word_timestamps": [
            {"word": "Good", "start": 0.0, "end": 0.3},
            {"word": "day", "start": 0.3, "end": 0.6},
        ]}),
        encoding="utf-8",
    )
    return {
        "edit_decisions": {
            "version": "1.0",
            "render_runtime": "remotion",
            "renderer_family": "presenter",
            "composition_mode": "templated",
            "cuts": [{"id": "main", "source": "assembled", "in_seconds": 0, "out_seconds": 0.6}],
            "subtitles": {"enabled": True, "source": "native-transcript"},
            "metadata": {"presenter_handoff": {
                "video_asset_id": "assembled",
                "caption_asset_id": "native-transcript",
                "overlays": [{
                    "id": "end-card",
                    "type": "text_card",
                    "position": "full_overlay",
                    "in_seconds": 0.5,
                    "out_seconds": 0.6,
                    "text": "Lingshun Express | shun-express.com",
                }],
            }},
        },
        "asset_manifest": {"assets": [
            {"id": "assembled", "type": "video", "path": str(video)},
            {"id": "native-transcript", "type": "subtitle", "path": str(transcript)},
        ]},
        "narration_transcript_path": str(transcript),
        "script_text": "Good day",
    }


def test_high_level_presenter_render_forwards_bound_talking_head_props(tool, tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *a, **k: None)
    monkeypatch.setattr(tool, "_needs_remotion", lambda *a, **k: True)

    def fake_remotion_render(inputs):
        captured.update(inputs["edit_decisions"])
        from tools.base_tool import ToolResult
        return ToolResult(success=True, data={}, artifacts=[])

    monkeypatch.setattr(tool, "_remotion_render", fake_remotion_render)
    inputs = _presenter_inputs(tmp_path)
    inputs["output_path"] = str(tmp_path / "out.mp4")

    result = tool._render(inputs)

    assert result.success is True
    assert captured["videoSrc"] == str((tmp_path / "assembled.mp4").resolve())
    assert captured["captions"] == [
        {"word": "Good", "startMs": 0, "endMs": 300},
        {"word": "day", "startMs": 300, "endMs": 600},
    ]
    assert captured["overlays"][0]["position"] == "full_overlay"
    assert captured["overlays"][0]["text"] == "Lingshun Express | shun-express.com"


def test_presenter_requires_remotion_without_silent_ffmpeg_fallback(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool, "_remotion_available", lambda: False)

    def forbidden(*args, **kwargs):
        raise AssertionError("presenter must never fall back to FFmpeg")

    monkeypatch.setattr(tool, "_compose", forbidden)
    inputs = _presenter_inputs(tmp_path)
    inputs["output_path"] = str(tmp_path / "out.mp4")
    result = tool._render(inputs)
    assert not result.success
    assert "Remotion" in result.error


def test_formal_presenter_preflight_rejects_mismatched_transcript_binding(tool, tmp_path, monkeypatch):
    inputs = _presenter_inputs(tmp_path)
    other = tmp_path / "other.transcript.json"
    other.write_text(json.dumps({"word_timestamps": []}), encoding="utf-8")
    inputs.update({"operation": "preflight", "narration_transcript_path": str(other)})

    result = tool.execute(inputs)

    assert result.success is False
    assert "caption asset must match narration_transcript_path" in result.error


def test_formal_presenter_preflight_rejects_missing_video_asset(tool, tmp_path):
    inputs = _presenter_inputs(tmp_path)
    inputs["asset_manifest"]["assets"] = inputs["asset_manifest"]["assets"][1:]
    inputs["operation"] = "preflight"

    result = tool.execute(inputs)

    assert result.success is False
    assert "video_asset_id must reference a video asset" in result.error


def test_formal_presenter_preflight_accepts_bound_handoff_before_session(tool, tmp_path, monkeypatch):
    inputs = _presenter_inputs(tmp_path)
    inputs["operation"] = "preflight"
    seen = {}

    def fake_session_preflight(received_tool, received_inputs):
        seen["tool"] = received_tool
        seen["inputs"] = received_inputs
        return {"input_sha256": "bound-inputs", "file_count": 2}

    monkeypatch.setattr("tools.video.composition_session.preflight", fake_session_preflight)

    result = tool.execute(inputs)

    assert result.success is True
    assert seen["tool"] is tool
    assert seen["inputs"]["edit_decisions"]["metadata"]["presenter_handoff"] == (
        inputs["edit_decisions"]["metadata"]["presenter_handoff"]
    )
    assert result.data["input_sha256"] == "bound-inputs"


@pytest.mark.parametrize("overlay", [
    {"type": "unsupported", "text": "hello"},
    {"type": "text_card", "text": "   "},
    {"type": "stat_card"},
    {"type": "comparison", "leftLabel": "only left"},
    {"type": "bar_chart", "chartData": []},
    {"type": "text_card", "text": "hello", "in_seconds": float("nan")},
    {"type": "text_card", "text": "hello", "out_seconds": float("inf")},
])
def test_presenter_rejects_invisible_or_invalid_overlays(tool, tmp_path, overlay):
    inputs = _presenter_inputs(tmp_path)
    inputs["edit_decisions"]["metadata"]["presenter_handoff"]["overlays"] = [
        {"in_seconds": 0, "out_seconds": 0.6, **overlay}
    ]
    with pytest.raises(ValueError, match="overlays"):
        tool._presenter_props_from_metadata(
            inputs["edit_decisions"], inputs["asset_manifest"], inputs["narration_transcript_path"]
        )
