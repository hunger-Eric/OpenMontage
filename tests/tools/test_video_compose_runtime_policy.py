from __future__ import annotations

from tools.base_tool import ToolResult
from tools.video.video_compose import VideoCompose


def test_new_work_discovery_exposes_only_remotion_when_all_runtimes_are_available(monkeypatch):
    """Compatibility availability must not become a new-work runtime menu."""
    monkeypatch.setattr(VideoCompose, "_remotion_available", lambda self: True)
    monkeypatch.setattr(VideoCompose, "_hyperframes_available", lambda self: True)
    monkeypatch.setattr(VideoCompose, "_ffmpeg_available", lambda self: True)

    info = VideoCompose().get_info()

    assert info["default_render_runtime"] == "remotion"
    assert info["user_facing_render_runtimes"] == ["remotion"]
    assert info["compatibility_render_runtimes"] == ["hyperframes", "ffmpeg"]
    assert info["render_engines"] == {
        "ffmpeg": True,
        "remotion": True,
        "hyperframes": True,
    }


def test_new_work_discovery_keeps_remotion_selected_when_it_is_unavailable(monkeypatch):
    """A missing Remotion install is a blocker, not a prompt to choose a legacy runtime."""
    monkeypatch.setattr(VideoCompose, "_remotion_available", lambda self: False)
    monkeypatch.setattr(VideoCompose, "_hyperframes_available", lambda self: True)
    monkeypatch.setattr(VideoCompose, "_ffmpeg_available", lambda self: True)

    info = VideoCompose().get_info()

    assert info["user_facing_render_runtimes"] == ["remotion"]
    assert info["default_render_runtime"] == "remotion"
    assert info["render_engines"]["remotion"] is False


def test_explicit_hyperframes_lock_still_uses_compatibility_route(monkeypatch, tmp_path):
    """Historical explicitly locked work retains its existing routing behavior."""
    tool = VideoCompose()
    captured = {}

    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *args: None)

    def fake_hyperframes(**kwargs):
        captured.update(kwargs)
        return ToolResult(success=True, data={"route": "hyperframes"})

    monkeypatch.setattr(tool, "_render_via_hyperframes", fake_hyperframes)
    result = tool._render(
        {
            "output_path": str(tmp_path / "output.mp4"),
            "asset_manifest": {"version": "1.0", "assets": []},
            "edit_decisions": {
                "version": "1.0",
                "render_runtime": "hyperframes",
                "renderer_family": "animation-first",
                "cuts": [{"id": "cut-1", "source": "legacy.mp4"}],
            },
        }
    )

    assert result.success
    assert result.data == {"route": "hyperframes"}
    assert captured["edit_decisions"]["render_runtime"] == "hyperframes"
