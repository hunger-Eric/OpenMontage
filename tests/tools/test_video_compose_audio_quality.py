"""Regression tests for delivery-blocking narration/music quality checks."""

from pathlib import Path
import json
import subprocess

import yaml

from schemas.artifacts import validate_artifact
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


def test_final_review_revises_when_proposal_music_is_missing(tmp_path):
    output = tmp_path / "final.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(output),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )

    review = VideoCompose()._run_final_review(
        output,
        edit_decisions={
            "version": "1.0",
            "render_runtime": "remotion",
            "renderer_family": "documentary-montage",
            "cuts": [],
        },
        proposal_packet={
            "production_plan": {
                "render_runtime": "remotion",
                "music_source": {"source_type": "bring_your_own"},
            }
        },
        asset_manifest={"version": "1.0", "assets": []},
    )

    assert review["status"] == "revise"
    assert review["checks"]["promise_preservation"]["delivery_promise_honored"] is False
    assert any("music" in issue.lower() for issue in review["issues_found"])


def test_final_review_requires_model_semantic_receipts_for_generated_motion(tmp_path):
    output = tmp_path / "semantic.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    proposal = {
        "production_plan": {
            "render_runtime": "remotion",
            "delivery_promise": {
                "promise_type": "motion_led",
                "motion_required": True,
                "tone_mode": "cinematic",
                "quality_floor": "presentable",
            },
        }
    }
    edit = {
        "version": "1.0",
        "render_runtime": "remotion",
        "renderer_family": "documentary-montage",
        "cuts": [{"id": "c1", "source": "clip", "in_seconds": 0, "out_seconds": 1}],
    }
    manifest = {
        "version": "1.1",
        "assets": [{
            "id": "clip", "type": "video", "path": "assets/video/clip.mp4",
            "source_tool": "video_selector", "scene_id": "s1",
            "provider": "agnes", "model": "agnes-video-v2.0",
        }],
    }

    review = VideoCompose()._run_final_review(
        output,
        edit_decisions=edit,
        proposal_packet=proposal,
        asset_manifest=manifest,
    )

    assert review["status"] == "revise"
    assert review["checks"]["semantic_alignment"]["complete"] is False
    assert any("semantic review" in issue.lower() for issue in review["issues_found"])
    assert validate_artifact("final_review", review) is None


def test_final_review_requires_decision_log_for_approved_semantic_deviation(tmp_path):
    output = tmp_path / "semantic-deviation.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    proposal = {
        "production_plan": {
            "render_runtime": "remotion",
            "delivery_promise": {
                "promise_type": "motion_led",
                "motion_required": True,
                "tone_mode": "cinematic",
                "quality_floor": "presentable",
            },
        }
    }
    edit = {
        "version": "1.0",
        "render_runtime": "remotion",
        "renderer_family": "documentary-montage",
        "cuts": [{"id": "c1", "source": "clip", "in_seconds": 0, "out_seconds": 1}],
    }
    manifest = {
        "version": "1.1",
        "assets": [{
            "id": "clip", "type": "video", "path": "assets/video/clip.mp4",
            "source_tool": "video_selector", "scene_id": "s1",
            "provider": "agnes", "model": "agnes-video-v2.0",
            "semantic_review": {
                "status": "approved_deviation",
                "executor_type": "model",
                "provider": "openai",
                "model": "gpt-5",
                "response_id": "resp-1",
                "requirements": [{
                    "kind": "action",
                    "requirement": "the creature's tail glows",
                    "status": "deviation",
                    "evidence": "the generated clip uses a glowing stone instead",
                }],
            },
        }],
    }

    review = VideoCompose()._run_final_review(
        output,
        edit_decisions=edit,
        proposal_packet=proposal,
        asset_manifest=manifest,
        decision_log={"version": "1.0", "project_id": "test", "decisions": []},
    )

    assert review["status"] == "revise"
    assert review["checks"]["semantic_alignment"]["complete"] is False
    assert any("decision log" in issue.lower() for issue in review["issues_found"])


def test_uniform_border_detector_finds_pillarbox_and_accepts_full_bleed(tmp_path):
    from PIL import Image

    pillar = Image.new("RGB", (100, 60), "black")
    for x in range(10, 90):
        for y in range(60):
            pillar.putpixel((x, y), (20 + x, 80, 160))
    pillar_path = tmp_path / "pillar.png"
    pillar.save(pillar_path)

    full = Image.new("RGB", (100, 60), (30, 100, 180))
    full_path = tmp_path / "full.png"
    full.save(full_path)

    assert VideoCompose._detect_uniform_borders(pillar_path)["pillarbox"] is True
    assert VideoCompose._detect_uniform_borders(full_path)["detected"] is False


def test_chinese_transcript_comparison_keeps_cjk_content(tmp_path):
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps(
            {
                "word_timestamps": [
                    {"word": "OPS 8.5 发布精心联语发行"},
                    {"word": "FFMPG 可以直接播放 OPS MP4"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    comparison = VideoCompose()._compare_transcript_to_script(
        transcript,
        "Opus 5.5 真正厉害的，是它会写代码。浏览器负责画帧。",
    )

    assert comparison["script_word_count"] > 10
    assert comparison["transcript_matches_script"] is False
    assert comparison["word_accuracy"] < 0.9


def test_final_review_revises_when_narration_transcript_is_missing(tmp_path, monkeypatch):
    output = tmp_path / "renders" / "final.mp4"
    output.parent.mkdir(parents=True)
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
    narration = _touch(tmp_path / "assets" / "audio" / "narration.wav")
    monkeypatch.setattr(
        VideoCompose,
        "_measure_integrated_loudness",
        staticmethod(lambda _path: -16.0),
    )

    review = VideoCompose()._run_final_review(
        output,
        edit_decisions={
            "version": "1.0",
            "render_runtime": "ffmpeg",
            "renderer_family": "footage-first",
            "cuts": [{"id": "c", "source": "x", "in_seconds": 0, "out_seconds": 1}],
            "audio": {
                "narration": {"segments": [{"asset_id": "voice", "start_seconds": 0}]}
            },
        },
        asset_manifest={
            "version": "1.0",
            "assets": [{"id": "voice", "type": "narration", "path": narration}],
        },
        script_text="这不是视频模型。",
    )

    assert review["status"] == "revise"
    assert any("transcript_comparison skipped" in issue for issue in review["issues_found"])


def test_final_review_revises_on_low_transcript_match(tmp_path):
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
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps({"word_timestamps": [{"word": "zeta eta theta"}]}),
        encoding="utf-8",
    )

    review = VideoCompose()._run_final_review(
        output,
        edit_decisions={
            "version": "1.0",
            "render_runtime": "ffmpeg",
            "renderer_family": "footage-first",
            "cuts": [{"id": "c", "source": "x", "in_seconds": 0, "out_seconds": 1}],
        },
        narration_transcript_path=transcript,
        script_text="alpha beta gamma delta",
    )

    assert review["status"] == "revise"
    assert review["checks"]["transcript_comparison"]["transcript_matches_script"] is False


def test_animated_explainer_requires_transcriber_for_delivery_gate():
    root = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load(
        (root / "pipeline_defs" / "animated-explainer.yaml").read_text(encoding="utf-8")
    )
    compose = next(stage for stage in manifest["stages"] if stage["name"] == "compose")

    assert "transcriber" in compose["required_tools"]
    assert "transcriber" in compose["tools_available"]


def test_final_review_rejects_script_projected_subtitles_for_generated_narration(
    tmp_path, monkeypatch
):
    output = tmp_path / "renders" / "final.mp4"
    output.parent.mkdir(parents=True)
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
    narration = _touch(tmp_path / "assets" / "audio" / "narration.wav")
    subtitle = tmp_path / "assets" / "subtitles.srt"
    subtitle.parent.mkdir(parents=True, exist_ok=True)
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nalpha beta gamma delta\n",
        encoding="utf-8",
    )
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps(
            {
                "word_timestamps": [
                    {"word": "alpha"}, {"word": "beta"},
                    {"word": "gamma"}, {"word": "delta"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        VideoCompose,
        "_measure_integrated_loudness",
        staticmethod(lambda _path: -16.0),
    )

    review = VideoCompose()._run_final_review(
        output,
        edit_decisions={
            "version": "1.0",
            "render_runtime": "ffmpeg",
            "renderer_family": "footage-first",
            "cuts": [{"id": "c", "source": "x", "in_seconds": 0, "out_seconds": 1}],
            "audio": {
                "narration": {"segments": [{"asset_id": "voice", "start_seconds": 0}]}
            },
            "subtitles": {"enabled": True, "source": "subs"},
        },
        asset_manifest={
            "version": "1.0",
            "assets": [
                {"id": "voice", "type": "narration", "path": narration},
                {
                    "id": "subs",
                    "type": "subtitle",
                    "path": str(subtitle),
                    "source_tool": "script_timing_projection",
                },
            ],
        },
        narration_transcript_path=transcript,
        script_text="alpha beta gamma delta",
    )

    assert review["status"] == "revise"
    assert review["checks"]["subtitle_check"]["transcript_derived"] is False
