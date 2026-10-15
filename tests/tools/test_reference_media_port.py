from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tools.analysis.reference_media import ReferenceMedia, ported_media_command
from tools.analysis.video_analyzer import VideoAnalyzer
from tools.base_tool import ToolResult


@pytest.fixture
def clip(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is required")
    try:
        ported_media_command()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))
    path = tmp_path / "fixture.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=96x160:r=24:d=0.25",
        "-f", "lavfi", "-i", "color=blue:s=96x160:r=24:d=0.25", "-f", "lavfi", "-i", "color=green:s=96x160:r=24:d=0.5",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_local_port_does_not_resolve_hypit_or_require_its_installation(clip, tmp_path, monkeypatch):
    original = shutil.which
    def local_only(name):
        assert name != "hypit", "production adapter must not resolve an external Hypit command"
        return original(name)
    monkeypatch.setattr(shutil, "which", local_only)
    monkeypatch.setenv("HYPIT_ROOT", "does-not-exist-and-must-not-be-read")
    result = ReferenceMedia().execute({"operation": "probe", "input_path": str(clip), "receipt_path": str(tmp_path / "probe.json")})
    assert result.success, result.error
    assert result.data["native"]["duration"] == 1
    assert result.data["native"]["frameRate"] == 24
    assert result.data["source_sha256"] == hashlib.sha256(clip.read_bytes()).hexdigest()
    assert "_reference_media" in result.data["command"][3]
    assert result.data["interpretation_status"] == "not_performed_by_tool"


def test_upstream_change_algorithm_preserves_short_scene_candidates(clip):
    result = ReferenceMedia().execute({"operation": "boundaries", "input_path": str(clip)})
    assert result.success, result.error
    native = result.data["native"]
    assert native["sampleRate"] == 12 and native["threshold"] == .1
    assert [row["at"] for row in native["candidates"]] == [.25, .5]


def test_native_pagination_actual_frame_times_and_no_overwrite(clip, tmp_path):
    request = {"operation": "tiles", "input_path": str(clip), "output_path": str(tmp_path / "grids"),
               "options": {"every": .25, "columns": 2, "rows": 1, "cell": 96}}
    first = ReferenceMedia().execute(request)
    assert first.success, first.error
    grids = first.data["native"]["grids"]
    assert len(grids) == 2
    assert [t for grid in grids for t in grid["samples"]] == [0, .25, .5, .75]
    assert all(abs(f["at"] - f["requestedAt"]) <= 1 / 24 for grid in grids for f in grid["frames"])
    digests = [hashlib.sha256(Path(g["path"]).read_bytes()).hexdigest() for g in grids]
    again = ReferenceMedia().execute(request)
    assert not again.success
    assert digests == [hashlib.sha256(Path(g["path"]).read_bytes()).hexdigest() for g in grids]


def test_original_phrase_resolution_and_missing_word_times(clip, tmp_path):
    transcript = tmp_path / "words.json"
    transcript.write_text(json.dumps({"format": "hypit.transcript@1", "passages": [{"words": [
        {"text": "world", "start_seconds": .1, "end_seconds": .2},
        {"text": "world", "start_seconds": .7, "end_seconds": .8}, {"text": "untimed"}]}]}), encoding="utf8")
    request = {"operation": "tile", "input_path": str(clip), "output_path": str(tmp_path / "phrase.jpg"),
               "options": {"around": "world", "transcript": str(transcript), "every": .05, "cell": 96}}
    ambiguous = ReferenceMedia().execute(request)
    assert not ambiguous.success and "occurrence" in ambiguous.error
    request["options"].update(occurrence=2, padding=.05)
    selected = ReferenceMedia().execute(request)
    assert selected.success, selected.error
    assert selected.data["native"]["samples"][0] == .65
    assert any("words" in f for f in selected.data["native"]["frames"])
    request["output_path"] = str(tmp_path / "untimed.jpg")
    request["options"]["around"] = "untimed"
    missing = ReferenceMedia().execute(request)
    assert not missing.success and "missing boundary times" in missing.error


@pytest.mark.parametrize("operation", ["fetch", "prepare-fetch", "generate", "transcribe"])
def test_non_inspection_operations_are_not_part_of_the_port(operation, tmp_path):
    result = ReferenceMedia().execute({"operation": operation, "input_path": str(tmp_path / "absent")})
    assert not result.success and result.data["fallback_used"] is False


def test_standard_analyzer_uses_ported_source_and_leaves_reading_pending(clip, tmp_path, monkeypatch):
    from tools.analysis.scene_detect import SceneDetect
    from tools.analysis.frame_sampler import FrameSampler
    from tools.analysis.audio_energy import AudioEnergy
    for tool in [SceneDetect, FrameSampler, AudioEnergy]:
        monkeypatch.setattr(tool, "execute", lambda *_: ToolResult(success=False, error="supplementary measurement omitted"))
    result = VideoAnalyzer().execute({"source": str(clip), "output_dir": str(tmp_path / "analysis"),
                                     "reference_inspection": {"every": .25, "cell": 96}})
    assert result.success, result.error
    reading = result.data["reference_understanding"]
    assert reading["method"] == "hypit_source_port"
    assert reading["interpretation_status"] == "pending_agent_reading"
    assert Path(reading["evidence"]["tiles"]).is_file()
    assert not Path(reading["notes"]["ANALYSIS"]).exists(), "tool must not manufacture an interpretation"
    saved = (tmp_path / "analysis/video_analysis_brief.json").read_bytes()
    assert not VideoAnalyzer().execute({"source": str(clip), "output_dir": str(tmp_path / "analysis")}).success
    assert (tmp_path / "analysis/video_analysis_brief.json").read_bytes() == saved


def test_migration_provenance_covers_all_source_files_and_original_book():
    root = Path(__file__).resolve().parents[2]
    record = json.loads((root / "third_party/hypit/PROVENANCE.json").read_text(encoding="utf8"))
    assert record["package_version"] == "0.2.6"
    for item in record["source_files"]:
        assert hashlib.sha256((root / item["local"]).read_bytes()).hexdigest() == item["local_sha256"]
        if item["upstream"].endswith(("process.ts", "transcript.ts")):
            assert item["upstream_sha256"] == item["local_sha256"]
    for item in record["reference_book"]:
        assert hashlib.sha256((root / "third_party/hypit" / item["path"]).read_bytes()).hexdigest() == item["sha256"]
