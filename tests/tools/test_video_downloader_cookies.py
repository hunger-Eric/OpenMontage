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
