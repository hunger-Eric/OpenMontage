from tools.video.video_compose import VideoCompose


def test_schema_display_mode_keeps_explicit_subtitle_font_settings():
    style = VideoCompose._resolve_subtitle_style(
        {"font": "Microsoft YaHei", "font_size": 24, "margin_v": 24},
        {"subtitles": {"enabled": True, "style": "sentence"}},
        None,
    )
    assert style["font"] == "Microsoft YaHei"
    assert style["font_size"] == 24
    assert style["margin_v"] == 24


def test_legacy_font_mapping_preserves_layered_overrides():
    style = VideoCompose._resolve_subtitle_style(
        {"font_size": 24},
        {"subtitles": {"style": {"font": "Microsoft YaHei", "font_size": 32}}},
        None,
    )
    assert style["font"] == "Microsoft YaHei"
    assert style["font_size"] == 24
