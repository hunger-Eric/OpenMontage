from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.analysis.reference_media_resolver import AcquisitionError, BrowserMediaResolver, ResolvedMedia
from tools.analysis.video_downloader import VideoDownloader
from tools.analysis.video_analyzer import VideoAnalyzer
from tools.base_tool import ToolResult

SOURCE = "https://www.douyin.com/video/7681624043124162469"
MEDIA = "https://media.example.org/video.mp4?transient=do-not-log"


def snapshot(**changes):
    data = {"title": "Reference", "text": "", "videos": [
        {"src": MEDIA, "visible": True, "readyState": 4, "duration": 133.466667,
         "source_id": "7681624043124162469"}]}
    data.update(changes)
    return data


@pytest.mark.parametrize("text,kind", [
    ("CAPTCHA Challenge", "CHALLENGE_REQUIRED"),
    ("Sign in to confirm you're not a bot", "CHALLENGE_REQUIRED"),
    ("试看30秒", "INCOMPLETE_REFERENCE_MEDIA"),
    ("Log in to watch", "INCOMPLETE_REFERENCE_MEDIA"),
])
def test_access_gates_precede_playable_media(text, kind):
    with pytest.raises(AcquisitionError) as error:
        BrowserMediaResolver.select_media(SOURCE, snapshot(text=text))
    assert error.value.kind == kind


@pytest.mark.parametrize("src,kind", [
    ("blob:https://example.org/123", "SEGMENTED_MEDIA_UNRESOLVED"),
    ("file:///private.mp4", "INVALID_MEDIA_URL"),
    ("http://127.0.0.1/video", "INVALID_MEDIA_URL"),
    ("https://user:password@example.org/video", "INVALID_MEDIA_URL"),
])
def test_unverified_or_private_sources_are_rejected(src, kind):
    data = snapshot()
    data["videos"][0]["src"] = src
    with pytest.raises(AcquisitionError) as error:
        BrowserMediaResolver.select_media(SOURCE, data)
    assert error.value.kind == kind


def test_media_contract_keeps_signed_transport_out_of_repr():
    media = BrowserMediaResolver.select_media(SOURCE, snapshot())
    assert media.media_url == MEDIA
    assert "transient" not in repr(media)
    assert media.headers == {"Referer": SOURCE}


def test_one_observed_manifest_resolves_blob_but_ambiguous_manifests_stop():
    data = snapshot(manifests=["https://media.example.org/master.m3u8"])
    data["videos"][0]["src"] = "blob:https://example.org/video"
    assert BrowserMediaResolver.select_media(SOURCE, data).media_url.endswith("master.m3u8")
    data["manifests"].append("https://media.example.org/ad.m3u8")
    with pytest.raises(AcquisitionError) as error:
        BrowserMediaResolver.select_media(SOURCE, data)
    assert error.value.kind == "SEGMENTED_MEDIA_UNRESOLVED"


@pytest.mark.parametrize("videos", [[], [snapshot()["videos"][0]] * 2])
def test_no_guess_between_missing_or_multiple_players(videos):
    with pytest.raises(AcquisitionError, match="unambiguous"):
        BrowserMediaResolver.select_media(SOURCE, snapshot(videos=videos))


def test_drm_and_infinite_live_media_do_not_become_references():
    for changes, kind in [({"protected": True}, "MEDIA_PROTECTED"),
                          ({"duration": float("inf")}, "INVALID_REFERENCE_MEDIA")]:
        data = snapshot()
        data["videos"][0].update(changes)
        with pytest.raises(AcquisitionError) as error:
            BrowserMediaResolver.select_media(SOURCE, data)
        assert error.value.kind == kind


def test_default_recovery_routes_generic_extractor_failure_without_replaying_page(tmp_path, monkeypatch):
    tool = VideoDownloader()
    monkeypatch.setattr(tool, "_resolve_storage_state_path", lambda *_: (None, "none"))
    monkeypatch.setattr(tool, "_extract_metadata", lambda *_: {"error": "Fresh cookies are needed"})
    calls = []
    def recover(*args):
        calls.append(args)
        return ToolResult(success=True, data={"acquisition_method": "normal_browser"})
    monkeypatch.setattr(tool, "_acquire_browser_video", recover)
    monkeypatch.setattr(tool, "_download_video", lambda *_: pytest.fail("Do not replay rejected page extraction"))
    result = tool.execute({"url": SOURCE, "output_dir": str(tmp_path)})
    assert result.success and len(calls) == 1
    assert result.data["remote_metadata_warning_kind"] == "EXTRACTOR_BLOCKED"


@pytest.mark.parametrize("message", ["HTTP Error 403: Forbidden", "Login required", "not a bot", "HTTP Error 429"])
def test_auto_does_not_recover_explicit_restrictions(tmp_path, monkeypatch, message):
    tool = VideoDownloader()
    monkeypatch.setattr(tool, "_resolve_storage_state_path", lambda *_: (None, "none"))
    monkeypatch.setattr(tool, "_extract_metadata", lambda *_: {"error": message})
    monkeypatch.setattr(tool, "_acquire_browser_video", lambda *_: pytest.fail("Restrictions must stop"))
    assert not tool.execute({"url": SOURCE, "output_dir": str(tmp_path)}).success


def prepare_acquisition(monkeypatch, tmp_path, duration=133.466667):
    monkeypatch.setattr(BrowserMediaResolver, "resolve", lambda *_: ResolvedMedia(SOURCE, MEDIA, "Reference", 133.466667))
    tool = VideoDownloader()
    monkeypatch.setattr(tool, "_resolve_storage_state_path", lambda *_: (None, "none"))
    def download(_url, staging, *_args, **_kwargs):
        path = staging / "reference_video.mp4"
        path.write_bytes(b"media")
        return str(path), None
    monkeypatch.setattr(tool, "_download_video", download)
    monkeypatch.setattr(tool, "_probe_local_media", lambda *_: {"duration": duration, "resolution": "1920x1080"})
    return tool


@pytest.mark.parametrize("duration", [30, 300, 0, float("inf")])
def test_download_duration_must_match_resolved_reference(tmp_path, monkeypatch, duration):
    tool = prepare_acquisition(monkeypatch, tmp_path, duration)
    monkeypatch.setattr(tool, "run_command", lambda *_a, **_kw: pytest.fail("Invalid duration must stop before decoding"))
    result = tool.execute({"url": SOURCE, "output_dir": str(tmp_path), "reference_acquisition": "browser"})
    assert not result.success
    assert result.data["acquisition_stages"] == ["resolve", "download", "validate"]


def test_complete_decode_is_required_and_safe_errors_do_not_leak_transport(tmp_path, monkeypatch):
    tool = prepare_acquisition(monkeypatch, tmp_path)
    def broken(*_a, **_kw):
        raise RuntimeError(MEDIA)
    monkeypatch.setattr(tool, "run_command", broken)
    result = tool.execute({"url": SOURCE, "output_dir": str(tmp_path), "reference_acquisition": "browser"})
    assert not result.success and result.data["error_kind"] == "INVALID_REFERENCE_MEDIA"
    assert "transient" not in str(result)


def test_receipt_is_written_only_after_complete_validation(tmp_path, monkeypatch):
    tool = prepare_acquisition(monkeypatch, tmp_path)
    monkeypatch.setattr(tool, "run_command", lambda *_a, **_kw: None)
    result = tool.execute({"url": SOURCE, "output_dir": str(tmp_path), "reference_acquisition": "browser"})
    assert result.success
    receipt = json.loads(Path(result.artifacts[-1]).read_text())
    assert receipt["full_decode"] == "passed"
    assert receipt["stages"][-1] == "complete"
    assert "transient" not in json.dumps(result.data) + json.dumps(receipt)


def test_analyzer_passes_selected_acquisition_and_preserves_failure_provenance(tmp_path, monkeypatch):
    seen = []
    def reject(_self, inputs):
        seen.append(inputs)
        return ToolResult(success=False, error="Preview only", data={
            "error_kind": "INCOMPLETE_REFERENCE_MEDIA", "acquisition_method": "normal_browser",
            "acquisition_stages": ["resolve"]})
    monkeypatch.setattr(VideoDownloader, "execute", reject)
    result = VideoAnalyzer().execute({"source": SOURCE, "output_dir": str(tmp_path), "reference_acquisition": "browser"})
    assert not result.success
    assert seen[0]["reference_acquisition"] == "browser"
    assert result.data["source"]["acquisition_method"] == "normal_browser"


@pytest.mark.parametrize("http_status", [200, 403, 429])
def test_browser_isolation_cookie_scope_and_cleanup(tmp_path, monkeypatch, http_status):
    import playwright.sync_api
    from types import SimpleNamespace
    seen = {"cookies": [], "closed": False}
    class Page:
        def set_default_timeout(self, _timeout): pass
        def on(self, *_args): pass
        def goto(self, url, **_kwargs):
            seen["source"] = url
            return SimpleNamespace(status=http_status)
        def wait_for_function(self, *_a, **_kw): pass
        def evaluate(self, js, _arg=None):
            return "Normal Browser UA" if "navigator.userAgent" in js else snapshot()
    class Context:
        def add_cookies(self, cookies): seen["cookies"] = cookies
        def new_page(self): return Page()
    class Browser:
        def new_context(self, **kwargs):
            assert kwargs == {}  # No user profile or localStorage import.
            return Context()
        def close(self): seen["closed"] = True
    class Chromium:
        executable_path = str(Path(__file__))
        def launch(self, **kwargs):
            assert kwargs["headless"] and kwargs["chromium_sandbox"]
            return Browser()
    class Runtime:
        chromium = Chromium()
        def __enter__(self): return self
        def __exit__(self, *_args): return False
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", Runtime)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"cookies": [
        {"name": "source-session", "value": "sensitive", "domain": ".douyin.com", "path": "/"},
        {"name": "unrelated-session", "value": "private", "domain": ".instagram.com", "path": "/"}],
        "origins": [{"origin": "https://unrelated.example.org", "localStorage": []}]}))
    if http_status == 200:
        media = BrowserMediaResolver().resolve(SOURCE, str(state))
        assert media.headers["User-Agent"] == "Normal Browser UA"
    else:
        with pytest.raises(AcquisitionError) as error:
            BrowserMediaResolver().resolve(SOURCE, str(state))
        assert error.value.kind == ("RATE_LIMITED" if http_status == 429 else "ACCESS_DENIED")
    assert seen["closed"]
    assert [c["name"] for c in seen["cookies"]] == ["source-session"]
    assert len(list(tmp_path.iterdir())) == 1


def test_loading_or_recommended_video_is_not_requested_reference():
    data = snapshot()
    data["videos"][0].update(duration=2.6, source_id=None)
    with pytest.raises(AcquisitionError) as error:
        BrowserMediaResolver.select_media(SOURCE, data)
    assert error.value.kind == "REFERENCE_MEDIA_UNAVAILABLE"
    data["videos"][0]["source_id"] = "7681624043124162400"
    with pytest.raises(AcquisitionError):
        BrowserMediaResolver.select_media(SOURCE, data)


def test_detail_response_must_match_requested_id_and_preserve_expected_duration():
    body = {"aweme_detail": {"aweme_id": "different-video", "video": {
        "duration": 133467, "play_addr": {"url_list": [MEDIA]}}}}
    assert BrowserMediaResolver.media_from_douyin_detail(SOURCE, body) is None
    body["aweme_detail"]["aweme_id"] = "7681624043124162469"
    detail = BrowserMediaResolver.media_from_douyin_detail(SOURCE, body)
    assert detail["duration"] == 133.467
    data = snapshot(source_media=detail)
    data["videos"][0].update(duration=2.6, source_id=None)
    assert BrowserMediaResolver.select_media(SOURCE, data).duration == 133.467
