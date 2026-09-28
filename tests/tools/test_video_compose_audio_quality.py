"""Regression tests for delivery-blocking narration/music quality checks."""

from pathlib import Path
import subprocess

import yaml

from tools.video.video_compose import VideoCompose


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio-fixture")
    return str(path)


def test_audio_asset_review_rejects_inaudible_music(tmp_path, monkeypatch):
    narration = _touch(tmp_path / "assets" / "audio" / "narration.wav")
    music = _touch(tmp_path / "assets" / "music" / "background.mp3")
    manifest = {
        "version": "1.0",
        "assets": [
            {"id": "voice", "type": "narration", "path": narration},
            {"id": "bed", "type": "music", "path": music},
        ],
    }
    edit = {
        "audio": {
            "narration": {"segments": [{"asset_id": "voice", "start_seconds": 0}]},
            "music": {"asset_id": "bed", "volume": 0.075},
        }
    }

    monkeypatch.setattr(
        VideoCompose,
        "_measure_integrated_loudness",
        staticmethod(lambda path: -16.0 if "narration" in str(path) else -19.0),
    )

    review = VideoCompose()._review_audio_assets(
        asset_manifest=manifest,
        edit_decisions=edit,
        output_path=tmp_path / "renders" / "final.mp4",
    )

    assert review["music_present"] is True
    assert review["music_audible"] is False
    assert review["music_to_narration_lu"] > 20
    assert any("effectively inaudible" in issue for issue in review["issues"])


def test_audio_asset_review_rejects_large_narration_slowdown(tmp_path, monkeypatch):
    narration = _touch(tmp_path / "assets" / "audio" / "narration.wav")
    manifest = {
        "version": "1.0",
        "assets": [
            {
                "id": "voice",
                "type": "narration",
                "path": narration,
                "voice_performance": {
                    "provider_settings": {"atempo": 0.78},
                },
            }
        ],
    }
    edit = {
        "audio": {
            "narration": {"segments": [{"asset_id": "voice", "start_seconds": 0}]},
        }
    }
    monkeypatch.setattr(
        VideoCompose,
        "_measure_integrated_loudness",
        staticmethod(lambda _path: -16.0),
    )

    review = VideoCompose()._review_audio_assets(
        asset_manifest=manifest,
        edit_decisions=edit,
        output_path=tmp_path / "renders" / "final.mp4",
    )

    assert review["narration_tempo_ratio"] == 0.78
    assert review["narration_pace_acceptable"] is False
    assert any("narration tempo distortion" in issue.lower() for issue in review["issues"])


def test_final_review_blocks_delivery_when_audio_balance_fails(tmp_path, monkeypatch):
    output = tmp_path / "renders" / "final.mp4"
    output.parent.mkdir(parents=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(output),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    narration = _touch(tmp_path / "assets" / "audio" / "narration.wav")
    music = _touch(tmp_path / "assets" / "music" / "background.mp3")
    manifest = {
        "version": "1.0",
        "assets": [
            {"id": "voice", "type": "narration", "path": narration},
            {"id": "bed", "type": "music", "path": music},
        ],
    }
    edit = {
        "version": "1.0",
        "render_runtime": "hyperframes",
        "renderer_family": "animation-first",
        "cuts": [{"id": "c1", "source": "x", "in_seconds": 0, "out_seconds": 2}],
        "audio": {
            "narration": {"segments": [{"asset_id": "voice", "start_seconds": 0}]},
            "music": {"asset_id": "bed", "volume": 0.075},
        },
    }
    monkeypatch.setattr(
        VideoCompose,
        "_measure_integrated_loudness",
        staticmethod(lambda path: -16.0 if "narration" in str(path) else -19.0),
    )

    review = VideoCompose()._run_final_review(
        output,
        edit_decisions=edit,
        asset_manifest=manifest,
    )

    assert review["status"] == "revise"
    assert review["recommended_action"] == "re_render"
    assert review["checks"]["audio_spotcheck"]["music_audible"] is False


def test_animated_explainer_routes_final_render_through_video_compose():
    root = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load(
        (root / "pipeline_defs" / "animated-explainer.yaml").read_text(encoding="utf-8")
    )
    compose = next(stage for stage in manifest["stages"] if stage["name"] == "compose")

    assert "video_compose" in compose["tools_available"]
    assert "hyperframes_compose" not in compose["tools_available"], (
        "The low-level HyperFrames renderer bypasses final_review and must not be "
        "a pipeline-facing delivery tool. video_compose delegates to it internally."
    )


def test_review_operation_can_gate_a_repaired_existing_render(tmp_path, monkeypatch):
    output = tmp_path / "final.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(output),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    narration = _touch(tmp_path / "narration.wav")
    music = _touch(tmp_path / "music.mp3")
    monkeypatch.setattr(
        VideoCompose,
        "_measure_integrated_loudness",
        staticmethod(lambda path: -16.0 if "narration" in str(path) else -19.0),
    )

    result = VideoCompose().execute(
        {
            "operation": "review",
            "input_path": str(output),
            "edit_decisions": {
                "version": "1.0",
                "render_runtime": "hyperframes",
                "renderer_family": "animation-first",
                "cuts": [{"id": "c", "source": "x", "in_seconds": 0, "out_seconds": 1}],
                "audio": {
                    "narration": {"segments": [{"asset_id": "voice", "start_seconds": 0}]},
                    "music": {"asset_id": "bed", "volume": 0.075},
                },
            },
            "asset_manifest": {
                "version": "1.0",
                "assets": [
                    {"id": "voice", "type": "narration", "path": narration},
                    {"id": "bed", "type": "music", "path": music},
                ],
            },
        }
    )

    assert result.success is False
    assert result.data["final_review_status"] == "revise"
