from __future__ import annotations

from tools.analysis.video_analyzer import VideoAnalyzer
from tools.analysis.video_downloader import VideoDownloader
from tools.base_tool import ToolResult


def test_analyzer_identifies_douyin_reference_urls():
    analyzer = VideoAnalyzer()

    assert analyzer._detect_platform(
        "https://www.douyin.com/jingxuan?modal_id=7681624043124162469"
    ) == "douyin"
    assert analyzer._detect_platform(
        "https://www.douyin.com/video/7681624043124162469"
    ) == "douyin"


def test_standard_url_analysis_fails_when_reference_media_was_not_acquired(tmp_path, monkeypatch):
    def unavailable(_self, _inputs):
        return ToolResult(
            success=False,
            error="Metadata extraction failed: ERROR: Unsupported URL",
            data={"error_kind": "UNSUPPORTED_URL"},
        )

    monkeypatch.setattr(VideoDownloader, "execute", unavailable)

    result = VideoAnalyzer().execute({
        "source": "https://example.test/watch/123",
        "analysis_depth": "standard",
        "output_dir": str(tmp_path / "analysis"),
    })

    assert result.success is False
    assert result.error == "Reference media unavailable (UNSUPPORTED_URL)"
    assert result.data["source"]["download_error_kind"] == "UNSUPPORTED_URL"
    assert result.data["_analysis_meta"]["steps_completed"] == []
    assert any(step.startswith("download:") for step in result.data["_analysis_meta"]["steps_failed"])
