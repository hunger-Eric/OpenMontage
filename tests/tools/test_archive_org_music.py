from __future__ import annotations

import io
import json
from urllib.parse import unquote

from tools.audio.archive_org_music import ArchiveOrgMusic


class _Response:
    def __init__(self, payload: dict | None = None, content: bytes = b""):
        self._content = content or json.dumps(payload or {}).encode("utf-8")
        self.headers = {"Content-Type": "audio/mpeg"}

    def read(self) -> bytes:
        return self._content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_archive_org_music_searches_metadata_and_downloads_allowed_track(monkeypatch, tmp_path):
    calls: list[str] = []
    search_payload = {
        "response": {
            "docs": [
                {
                    "identifier": "blocked-nc",
                    "title": "Blocked",
                    "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/",
                    "downloads": 999,
                },
                {
                    "identifier": "allowed-by",
                    "title": "Allowed Album",
                    "creator": "Example Artist",
                    "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
                    "downloads": 100,
                },
            ]
        }
    }
    metadata_payload = {
        "metadata": {
            "identifier": "allowed-by",
            "title": "Allowed Album",
            "creator": "Example Artist",
            "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
        },
        "files": [
            {
                "name": "metadata.xml",
                "format": "Metadata",
                "source": "original",
            },
            {
                "name": "Gentle Theme.mp3",
                "format": "VBR MP3",
                "source": "original",
                "length": "75.5",
                "size": "4096",
                "md5": "abc123",
            },
        ],
    }

    def fake_urlopen(request, timeout=0):
        url = request.full_url
        calls.append(url)
        if "advancedsearch.php" in url:
            return _Response(search_payload)
        if "/metadata/allowed-by" in url:
            return _Response(metadata_payload)
        if "/download/allowed-by/" in url:
            assert "Gentle%20Theme.mp3" in url
            return _Response(content=b"ID3music-bytes")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("tools.audio.archive_org_music.urllib.request.urlopen", fake_urlopen)

    output = tmp_path / "music.mp3"
    result = ArchiveOrgMusic().execute({
        "query": "gentle advertising",
        "min_duration": 30,
        "max_duration": 120,
        "output_path": str(output),
    })

    assert result.success
    assert output.read_bytes() == b"ID3music-bytes"
    assert result.data["provider"] == "archive_org"
    assert result.data["identifier"] == "allowed-by"
    assert result.data["track_title"] == "Gentle Theme"
    assert result.data["duration_seconds"] == 75.5
    assert result.data["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert result.data["attribution_required"] is True
    assert any("advancedsearch.php" in url for url in calls)
    assert any("/metadata/allowed-by" in url for url in calls)
    assert any("/download/allowed-by/" in url for url in calls)


def test_archive_org_music_rejects_noncommercial_results(monkeypatch, tmp_path):
    search_payload = {
        "response": {
            "docs": [{
                "identifier": "only-nc",
                "title": "Noncommercial",
                "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/",
            }]
        }
    }
    monkeypatch.setattr(
        "tools.audio.archive_org_music.urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(search_payload),
    )

    result = ArchiveOrgMusic().execute({
        "query": "ambient",
        "output_path": str(tmp_path / "blocked.mp3"),
    })

    assert not result.success
    assert "commercial-use-compatible" in result.error
    assert not (tmp_path / "blocked.mp3").exists()
