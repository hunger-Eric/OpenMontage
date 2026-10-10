"""Route configuration must preserve portability and explicit production scope."""
from pathlib import Path
from types import SimpleNamespace
import json
import subprocess

from lib.config_model import OpenMontageConfig
from tools.base_tool import ToolResult, ToolStatus
from tools.provider_routing import apply_provider_preferences, enabled_candidates
from tools.graphics.image_selector import ImageSelector
from tools.video.video_selector import VideoSelector
from tools.audio.tts_selector import TTSSelector
from tools.video.video_compose import VideoCompose
from tests.tools.test_video_selector_routing import _StubTool, _ScoreStub


def test_local_overlay_preserves_unrelated_shared_settings(tmp_path, monkeypatch):
    base = tmp_path / "config.yaml"
    local = tmp_path / "config.local.yaml"
    base.write_text("output:\n  default_fps: 24\nproviders:\n  video_provider: auto\n", encoding="utf-8")
    local.write_text("providers:\n  video_provider: agnes\n  disabled_providers: [grok]\n", encoding="utf-8")
    monkeypatch.setenv("OPENMONTAGE_LOCAL_CONFIG", str(local))
    config = OpenMontageConfig.load(base)
    assert config.output.default_fps == 24
    assert config.providers.video_provider == "agnes"
    assert config.providers.image_provider == "auto"
    assert config.providers.disabled_providers == ["grok"]


def test_personal_route_is_bounded_but_explicit_request_overrides_it(tmp_path, monkeypatch):
    local = tmp_path / "local.yaml"
    local.write_text("providers:\n  video_provider: agnes\n  restrict_to_preferences: true\n", encoding="utf-8")
    monkeypatch.setenv("OPENMONTAGE_LOCAL_CONFIG", str(local))
    implicit = apply_provider_preferences({}, "video")
    assert implicit["allowed_providers"] == ["agnes"]
    explicit = apply_provider_preferences({"preferred_provider": "auto"}, "video")
    assert "allowed_providers" not in explicit
    incompatible = apply_provider_preferences({"allowed_providers": ["wan"]}, "video")
    assert incompatible["allowed_providers"] == ["__no_authorized_provider__"]


def test_unavailable_personal_video_route_never_spends_elsewhere(tmp_path, monkeypatch):
    local = tmp_path / "local.yaml"
    local.write_text("providers:\n  video_provider: agnes\n  restrict_to_preferences: true\n", encoding="utf-8")
    monkeypatch.setenv("OPENMONTAGE_LOCAL_CONFIG", str(local))
    agnes = _StubTool("agnes_video", "agnes", status=ToolStatus.UNAVAILABLE)
    other = _StubTool("other_video", "other")
    monkeypatch.setattr("lib.scoring.rank_providers", lambda tools, ctx: [_ScoreStub(t.name, t.provider, 1) for t in tools])
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [agnes, other])
    assert not selector.execute({"prompt": "scene"}).success
    assert other.last_execute_inputs is None
    assert selector.execute({"prompt": "scene", "preferred_provider": "auto"}).success
    assert other.last_execute_inputs is not None


def test_python_image_route_works_without_native_session_tool(monkeypatch):
    tool = _StubTool("api_image", "test")
    tool.capability = "image_generation"
    tool.supports = {}
    monkeypatch.setattr("lib.scoring.rank_providers", lambda tools, ctx: [_ScoreStub(t.name, t.provider, 1) for t in tools])
    selector = ImageSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])
    result = selector.execute({"prompt": "scene"})
    assert result.success
    assert result.data["selected_provider"] == "test"
    assert tool.last_execute_inputs is not None


def test_explicit_model_remains_strict_with_same_provider_siblings(monkeypatch):
    a = _StubTool("tts_a", "shared")
    b = _StubTool("tts_b", "shared")
    for t, model in [(a, "model-a"), (b, "model-b")]:
        t.input_schema = {"properties": {"model_id": {"enum": [model]}}}
    monkeypatch.setattr("lib.scoring.rank_providers", lambda tools, ctx: [_ScoreStub(t.name, t.provider, 1) for t in tools])
    selector = TTSSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [a, b])
    assert selector.execute({"text": "words", "model_id": "model-b"}).success
    assert a.last_execute_inputs is None
    assert b.last_execute_inputs["model_id"] == "model-b"
    assert not selector.execute({"text": "words", "model_id": "missing-model"}).success


def test_audio_style_thresholds_are_advisory_unless_project_enforces_them(tmp_path, monkeypatch):
    output = tmp_path / "final.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x240:duration=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(output)], check=True, capture_output=True, timeout=30)
    voice, music = tmp_path / "voice.wav", tmp_path / "music.wav"
    voice.write_bytes(b"fixture"); music.write_bytes(b"fixture")
    transcript = tmp_path / "transcript.json"
    transcript.write_text(json.dumps({"word_timestamps": [{"word": "alpha beta gamma delta"}]}), encoding="utf-8")
    manifest = {"version": "1.0", "assets": [{"id": "voice", "type": "narration", "path": str(voice)}, {"id": "music", "type": "music", "path": str(music)}]}
    edit = {"version": "1.0", "render_runtime": "ffmpeg", "renderer_family": "footage-first", "cuts": [{"id": "c", "source": "x", "in_seconds": 0, "out_seconds": 2}], "audio": {"narration": {"segments": [{"asset_id": "voice", "start_seconds": 0}]}, "music": {"asset_id": "music", "volume": 0.05}}}
    monkeypatch.setattr(VideoCompose, "_measure_integrated_loudness", staticmethod(lambda path: -16.0))
    def review(ed):
        return VideoCompose()._run_final_review(output, edit_decisions=ed, asset_manifest=manifest, narration_transcript_path=transcript, script_text="alpha beta gamma delta")
    advisory = review(edit)
    assert advisory["status"] == "pass"
    assert advisory["checks"]["audio_spotcheck"]["music_audible"] is False
    assert advisory["checks"]["audio_spotcheck"]["blocking_issues"] == []
    enforced = review({**edit, "audio_review_policy": {"mode": "enforce"}})
    assert enforced["status"] == "revise"
    permitted = review({**edit, "audio_review_policy": {"mode": "enforce", "max_music_gap_lu": 30}})
    assert permitted["status"] == "pass"
