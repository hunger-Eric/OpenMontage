from __future__ import annotations

import json
from http.cookiejar import CookieJar

import pytest
import yt_dlp

from tools.analysis.video_downloader import VideoDownloader


def _write_storage_state(path):
    path.write_text(json.dumps({
        "cookies": [{
            "name": "session-cookie",
            "value": "secret-value",
            "domain": ".douyin.com",
            "path": "/",
            "expires": -1,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }],
        "origins": [],
    }), encoding="utf-8")


def test_loads_playwright_storage_state_without_creating_a_cookie_file(tmp_path):
    state_path = tmp_path / "storage-state.json"
    _write_storage_state(state_path)

    downloader = VideoDownloader()
    cookies = downloader._load_playwright_cookies(str(state_path.resolve()))

    assert len(cookies) == 1
    assert cookies[0].name == "session-cookie"
    assert cookies[0].value == "secret-value"
    assert cookies[0].domain == ".douyin.com"
    assert cookies[0].secure is True
    assert cookies[0].discard is True
    assert list(tmp_path.iterdir()) == [state_path]


def test_rejects_relative_or_empty_playwright_storage_state(tmp_path):
    downloader = VideoDownloader()
    with pytest.raises(ValueError, match="must be absolute"):
        downloader._load_playwright_cookies("relative.json")

    empty_path = tmp_path / "empty.json"
    empty_path.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="contains no cookies"):
        downloader._load_playwright_cookies(str(empty_path.resolve()))


def test_injects_storage_state_into_yt_dlp_memory_only(tmp_path, monkeypatch):
    state_path = tmp_path / "storage-state.json"
    _write_storage_state(state_path)

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options
            self.cookiejar = CookieJar()

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    ydl = VideoDownloader()._youtube_dl(
        {"quiet": True}, str(state_path.resolve()),
    )

    cookies = list(ydl.cookiejar)
    assert len(cookies) == 1
    assert cookies[0].name == "session-cookie"
    assert cookies[0].value == "secret-value"
    assert ydl.options == {"quiet": True}
    assert list(tmp_path.iterdir()) == [state_path]


def test_execute_forwards_storage_state_to_metadata_and_video_download(tmp_path, monkeypatch):
    state_path = tmp_path / "storage-state.json"
    _write_storage_state(state_path)
    seen = []

    downloader = VideoDownloader()
    monkeypatch.setattr(
        downloader,
        "_extract_metadata",
        lambda _url, storage_state: seen.append(("metadata", storage_state)) or {
            "title": "reference", "duration": 10,
        },
    )
    monkeypatch.setattr(
        downloader,
        "_download_video",
        lambda _url, _output_dir, _max_res, storage_state: (
            seen.append(("video", storage_state)) or (None, None)
        ),
    )

    result = downloader.execute({
        "url": "https://v.douyin.com/example/",
        "output_dir": str(tmp_path / "output"),
        "format": "video",
        "playwright_storage_state_path": str(state_path.resolve()),
    })

    assert result.success is True
    assert seen == [
        ("metadata", str(state_path.resolve())),
        ("video", str(state_path.resolve())),
    ]


def test_normalizes_douyin_jingxuan_modal_url_before_cookie_backed_download(tmp_path, monkeypatch):
    state_path = tmp_path / "storage-state.json"
    _write_storage_state(state_path)
    seen = []
    downloader = VideoDownloader()
    monkeypatch.setattr(
        downloader,
        "_extract_metadata",
        lambda url, storage_state: seen.append(("metadata", url, storage_state)) or {
            "title": "reference", "duration": 133,
        },
    )
    monkeypatch.setattr(
        downloader,
        "_download_video",
        lambda url, _output_dir, _max_res, storage_state: (
            seen.append(("video", url, storage_state)) or (None, None)
        ),
    )

    original = "https://www.douyin.com/jingxuan?modal_id=7681624043124162469"
    canonical = "https://www.douyin.com/video/7681624043124162469"
    result = downloader.execute({
        "url": original,
        "output_dir": str(tmp_path / "output"),
        "format": "video",
        "playwright_storage_state_path": str(state_path.resolve()),
    })

    assert result.success is True
    assert result.data["platform"] == "douyin"
    assert result.data["requested_url"] == original
    assert result.data["resolved_url"] == canonical
    assert result.data["url_resolution_kind"] == "resolved_alias"
    assert seen == [
        ("metadata", canonical, str(state_path.resolve())),
        ("video", canonical, str(state_path.resolve())),
    ]


def test_metadata_only_distinguishes_unsupported_url_from_cookie_failure(tmp_path, monkeypatch):
    downloader = VideoDownloader()
    monkeypatch.setattr(
        downloader,
        "_extract_metadata",
        lambda _url, _storage_state: {
            "error": "ERROR: Unsupported URL", "title": "", "duration": 0,
        },
    )

    result = downloader.execute({
        "url": "https://example.test/watch/123",
        "output_dir": str(tmp_path / "output"),
        "format": "metadata_only",
    })

    assert result.success is False
    assert result.data["error_kind"] == "UNSUPPORTED_URL"
    assert result.data["error_kind"] != "AUTH_REQUIRED"
    assert result.data["url_resolution_kind"] == "passthrough"


@pytest.mark.parametrize("original", [
    "https://www.douyin.com/jingxuan?modal_id=7681624043124162469",
    "https://www.douyin.com/search/%E5%86%B0%E6%B2%B3?modal_id=7681624043124162469",
    "https://www.douyin.com/?modal_id=7681624043124162469",
])
def test_resolves_multiple_douyin_page_url_shapes(original):
    resolved, kind = VideoDownloader()._resolve_url(original)

    assert resolved == "https://www.douyin.com/video/7681624043124162469"
    assert kind == "resolved_alias"


def test_preserves_canonical_douyin_video_url():
    original = "https://www.douyin.com/video/7681624043124162469"

    assert VideoDownloader()._resolve_url(original) == (original, "canonical")


def test_passes_unknown_url_to_extractor_without_auth_assumption():
    original = "https://example.test/watch/123"

    assert VideoDownloader()._resolve_url(original) == (original, "passthrough")


def test_successful_media_download_overrides_remote_metadata_auth_warning(tmp_path, monkeypatch):
    downloader = VideoDownloader()
    state_path = tmp_path / "storage-state.json"
    _write_storage_state(state_path)
    video_path = tmp_path / "reference_video.mp4"
    video_path.write_bytes(b"downloaded-media")
    monkeypatch.setattr(
        downloader,
        "_extract_metadata",
        lambda _url, _storage_state: {
            "error": "Fresh cookies (not necessarily logged in) are needed",
            "title": "", "duration": 0,
        },
    )
    monkeypatch.setattr(
        downloader,
        "_download_video",
        lambda _url, _output_dir, _max_res, _storage_state: (str(video_path), None),
    )
    monkeypatch.setattr(
        downloader,
        "_probe_local_media",
        lambda _video_path: {"duration": 133.0, "resolution": "720x1280", "fps": 30.0},
    )

    result = downloader.execute({
        "url": "https://www.douyin.com/video/7681624043124162469",
        "output_dir": str(tmp_path),
        "format": "video",
        "playwright_storage_state_path": str(state_path.resolve()),
    })

    assert result.success is True
    assert result.data["metadata_status"] == "local_media_recovered"
    assert result.data["remote_metadata_warning_kind"] == "AUTH_REQUIRED"
    assert result.data["metadata"]["duration"] == 133.0
    assert result.data["metadata"]["resolution"] == "720x1280"
    assert "error" not in result.data["metadata"]


def test_douyin_reuses_uploader_default_storage_state(tmp_path):
    home = tmp_path / "tester"
    state_path = home / ".social-auto-upload" / "runtime" / "cookies" / "douyin_tester.json"
    state_path.parent.mkdir(parents=True)
    _write_storage_state(state_path)

    resolved, source = VideoDownloader()._resolve_storage_state_path(
        None, "douyin", env={}, home=home
    )

    assert resolved == str(state_path.resolve())
    assert source == "uploader_default"


def test_non_douyin_url_does_not_inherit_douyin_uploader_state(tmp_path):
    resolved, source = VideoDownloader()._resolve_storage_state_path(
        None, "youtube", env={}, home=tmp_path
    )

    assert resolved is None
    assert source == "none"


def test_cookie_backed_download_retries_ambiguous_fresh_cookie_signal(monkeypatch):
    attempts = []

    class FakeYoutubeDL:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def download(self, urls):
            attempts.append(urls)
            if len(attempts) < 3:
                raise RuntimeError("Fresh cookies (not necessarily logged in) are needed")

    downloader = VideoDownloader()
    monkeypatch.setattr(downloader, "_youtube_dl", lambda _opts, _state: FakeYoutubeDL())
    monkeypatch.setattr("tools.analysis.video_downloader.time.sleep", lambda _delay: None)

    count = downloader._download_with_background_retry(
        "https://www.douyin.com/video/7681624043124162469",
        {"quiet": True},
        "/authorized/storage-state.json",
    )

    assert count == 3
    assert len(attempts) == 3


def test_unsupported_url_is_not_retried_as_an_auth_failure(monkeypatch):
    attempts = []

    class FakeYoutubeDL:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def download(self, _urls):
            attempts.append(True)
            raise RuntimeError("ERROR: Unsupported URL")

    downloader = VideoDownloader()
    monkeypatch.setattr(downloader, "_youtube_dl", lambda _opts, _state: FakeYoutubeDL())

    with pytest.raises(RuntimeError, match="Unsupported URL"):
        downloader._download_with_background_retry(
            "https://example.test/watch/123", {"quiet": True}, "/authorized/storage-state.json"
        )

    assert attempts == [True]
