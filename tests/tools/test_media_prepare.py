from __future__ import annotations
import hashlib
import json
import shutil
import subprocess

import pytest
from PIL import Image

from tools.enhancement import media_prepare
from tools.enhancement.media_prepare import MediaPrepare
from tools.tool_registry import ToolRegistry


def inputs(tmp_path, **overrides):
    source = tmp_path / "original.png"
    if not source.exists():
        Image.new("RGB", (80, 120), (120, 120, 120)).save(source)
    return {"input_path": str(source), "output_path": str(tmp_path / "prepared.png"),
            "media_type": "image", "width": 160, "height": 90,
            "confirm_processing": True, "plan_revision": "approved-plan-test", **overrides}


def test_tool_is_discoverable_and_not_automatic():
    registry = ToolRegistry()
    assert registry.register_module(media_prepare) == ["media_prepare"]
    assert registry.get("media_prepare").supports["automatic_on_upload"] is False


def test_plain_upload_does_not_run_processing(tmp_path, monkeypatch):
    tool = MediaPrepare()
    monkeypatch.setattr(tool, "run_command", lambda *a, **k: pytest.fail("unauthorized processing"))
    result = tool.execute(inputs(tmp_path, confirm_processing=False))
    assert not result.success and result.data["error_code"] == "processing_not_authorized"
    assert not (tmp_path / "prepared.png").exists()


@pytest.mark.parametrize("case", ["original", "existing_output", "nan", "odd_video"])
def test_invalid_request_preserves_files_and_never_runs(tmp_path, monkeypatch, case):
    args = inputs(tmp_path)
    if case == "original": args["output_path"] = args["input_path"]
    if case == "existing_output": (tmp_path / "prepared.png").write_bytes(b"keep")
    if case == "nan": args["brightness"] = float("nan")
    if case == "odd_video": args.update(media_type="video", width=159, output_path=str(tmp_path / "prepared.mp4"))
    source = (tmp_path / "original.png").read_bytes()
    tool = MediaPrepare()
    monkeypatch.setattr(tool, "run_command", lambda *a, **k: pytest.fail("invalid request executed"))
    assert not tool.execute(args).success
    assert (tmp_path / "original.png").read_bytes() == source
    if case == "existing_output": assert (tmp_path / "prepared.png").read_bytes() == b"keep"


def test_hdr_is_not_silently_converted(tmp_path, monkeypatch):
    tool = MediaPrepare()
    monkeypatch.setattr(tool, "_probe", lambda path: {"streams": [{"codec_type": "video", "color_transfer": "smpte2084"}]})
    monkeypatch.setattr(tool, "run_command", lambda *a, **k: pytest.fail("implicit HDR conversion"))
    result = tool.execute(inputs(tmp_path))
    assert not result.success and "HDR" in result.error
    assert not (tmp_path / "prepared.png").exists()


def test_failed_encoder_leaves_original_and_no_partial_delivery(tmp_path, monkeypatch):
    tool = MediaPrepare()
    args = inputs(tmp_path)
    source = (tmp_path / "original.png").read_bytes()
    monkeypatch.setattr(tool, "_probe", lambda path: {"streams": [{"codec_type": "video"}]})
    def fail(command, **kwargs):
        from pathlib import Path
        Path(command[-1]).write_bytes(b"partial output")
        raise RuntimeError("encoder failed")
    monkeypatch.setattr(tool, "run_command", fail)
    assert not tool.execute(args).success
    assert (tmp_path / "original.png").read_bytes() == source
    assert not (tmp_path / "prepared.png").exists()
    assert not (tmp_path / "prepared.png.prepare.json").exists()
    assert not list(tmp_path.glob(".prepare-*"))


real_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="real FFmpeg required")


@real_ffmpeg
def test_image_contain_preserves_geometry_and_source(tmp_path):
    args = inputs(tmp_path)
    original_hash = hashlib.sha256((tmp_path / "original.png").read_bytes()).hexdigest()
    result = MediaPrepare().execute(args)
    assert result.success, result.error
    image = Image.open(tmp_path / "prepared.png").convert("RGB")
    assert image.size == (160, 90)
    assert image.getpixel((0, 45)) == (0, 0, 0)
    assert image.getpixel((80, 45))[0] > 100
    assert image.getpixel((49, 45)) == (0, 0, 0) and image.getpixel((50, 45))[0] > 100
    receipt = json.loads((tmp_path / "prepared.png.prepare.json").read_text(encoding="utf-8"))
    assert receipt["source_sha256"] == original_hash and receipt["original_preserved"]
    assert hashlib.sha256((tmp_path / "original.png").read_bytes()).hexdigest() == original_hash
    assert receipt["parameters"]["plan_revision"] == "approved-plan-test"


@real_ffmpeg
def test_explicit_cover_and_color_are_executed(tmp_path):
    result = MediaPrepare().execute(inputs(tmp_path, fit_mode="cover", brightness=0.1))
    assert result.success, result.error
    image = Image.open(tmp_path / "prepared.png").convert("RGB")
    assert image.size == (160, 90)
    assert image.getpixel((0, 45))[0] > 130  # filled and brighter, no contain border


@real_ffmpeg
def test_video_normalizes_dimensions_fps_and_keeps_audio(tmp_path):
    source = tmp_path / "original.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i", "color=c=red:s=128x96:r=10:d=0.8",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=0.8", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source)], check=True)
    args = inputs(tmp_path, input_path=str(source), output_path=str(tmp_path / "prepared.mp4"), media_type="video", fps=20)
    result = MediaPrepare().execute(args)
    assert result.success, result.error
    after = result.data["after"]
    video = next(s for s in after["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (160, 90)
    assert video["avg_frame_rate"] == "20/1"
    assert any(s["codec_type"] == "audio" for s in after["streams"])
    assert abs(float(after["format"]["duration"]) - float(result.data["before"]["format"]["duration"])) < 0.15
