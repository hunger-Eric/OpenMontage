"""Resolve normally playable reference media without a third-party parsing service.

Signed media URLs and session headers are transient transport data, never receipts.
This adapter is selected explicitly for an authorized browser acquisition task.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import math
import re
import time
from pathlib import Path
from urllib.parse import urlparse

_VISIBLE_CHALLENGE_FRAME = """[...document.querySelectorAll('iframe[src*="captcha"],iframe[src*="challenge"]')].some(e => {
    const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
})"""

class AcquisitionError(Exception):
    def __init__(self, kind: str, message: str, diagnostics: dict | None = None):
        self.kind = kind
        self.diagnostics = diagnostics or {}
        super().__init__(message)


@dataclass
class ResolvedMedia:
    source_url: str
    media_url: str = field(repr=False)
    title: str = ""
    duration: float = 0
    headers: dict = field(default_factory=dict, repr=False)


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise AcquisitionError("INVALID_MEDIA_URL", "A public HTTP(S) address is required")
    if host.lower() == "localhost" or host.lower().endswith((".localhost", ".local")):
        raise AcquisitionError("INVALID_MEDIA_URL", "Local addresses are not reference media")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise AcquisitionError("INVALID_MEDIA_URL", "Private addresses are not reference media")


class BrowserMediaResolver:
    """Use an isolated normal browser context; no login or challenge automation."""

    @staticmethod
    def select_media(source_url: str, snapshot: dict) -> ResolvedMedia:
        validate_public_url(source_url)
        text = (snapshot.get("text") or "").lower()
        challenge_markers = [marker for marker in (
            "captcha challenge", "verify to continue", "sign in to confirm", "人机验证", "安全验证",
        ) if marker in text]
        if challenge_markers or snapshot.get("challenge"):
            raise AcquisitionError("CHALLENGE_REQUIRED", "The source requires human verification", {
                "text_markers": challenge_markers,
                "visible_challenge_frame": bool(snapshot.get("challenge")),
                "playable_video_count": sum(v.get("readyState", 0) >= 2 for v in snapshot.get("videos", [])),
            })
        if any(marker in text for marker in ("试看", "preview only", "登录后观看", "log in to watch")):
            raise AcquisitionError("INCOMPLETE_REFERENCE_MEDIA", "The page offers only a preview or restricted playback")
        source_id = BrowserMediaResolver.douyin_source_id(source_url)
        detail = snapshot.get("source_media")
        if source_id and detail and detail.get("source_id") == source_id:
            videos = [detail]
        else:
            videos = [v for v in snapshot.get("videos", [])
                      if v.get("visible") and v.get("readyState", 0) >= 2
                      and (not source_id or v.get("source_id") == source_id)]
        if len(videos) != 1:
            raise AcquisitionError("REFERENCE_MEDIA_UNAVAILABLE", "One unambiguous playable video is required")
        video = videos[0]
        if video.get("protected"):
            raise AcquisitionError("MEDIA_PROTECTED", "Protected media cannot be acquired")
        media_url = video.get("src") or ""
        if media_url.startswith("blob:"):
            manifests = list(dict.fromkeys(snapshot.get("manifests", [])))
            if len(manifests) != 1:
                raise AcquisitionError("SEGMENTED_MEDIA_UNRESOLVED", "The player uses segmented media; one unambiguous manifest is required")
            media_url = manifests[0]
        validate_public_url(media_url)
        duration = video.get("duration")
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
            raise AcquisitionError("INVALID_REFERENCE_MEDIA", "The player has no finite positive duration")
        return ResolvedMedia(source_url, media_url, snapshot.get("title") or "", duration,
                             {"Referer": source_url})

    @staticmethod
    def douyin_source_id(source_url: str) -> str | None:
        parsed = urlparse(source_url)
        host = parsed.hostname or ""
        match = re.fullmatch(r"/video/(\d{10,30})/?", parsed.path)
        return match.group(1) if match and (host == "douyin.com" or host.endswith(".douyin.com")) else None

    @staticmethod
    def media_from_douyin_detail(source_url: str, body: dict) -> dict | None:
        """Bind media from a response the normal page fetched to the requested ID."""
        source_id = BrowserMediaResolver.douyin_source_id(source_url)
        detail = body.get("aweme_detail") or {}
        if not source_id or detail.get("aweme_id") != source_id:
            return None
        video = detail.get("video") or {}
        urls = (video.get("play_addr") or {}).get("url_list") or []
        duration = video.get("duration")
        if not urls or not isinstance(duration, (int, float)):
            return None
        return {"source_id": source_id, "src": urls[0], "duration": duration / 1000,
                "protected": bool(video.get("is_drm")), "title": detail.get("desc") or ""}

    def resolve(self, source_url: str, storage_state_path: str | None = None) -> ResolvedMedia:
        validate_public_url(source_url)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise AcquisitionError("BROWSER_RUNTIME_UNAVAILABLE", "Playwright is not installed") from None
        try:
            with sync_playwright() as runtime:
                # Use existing browsers only. Do not install a runtime in a task.
                options = {"headless": True, "chromium_sandbox": True, "timeout": 15000}
                if not Path(runtime.chromium.executable_path).is_file():
                    import sys
                    if sys.platform == "win32":
                        options["channel"] = "msedge"
                    else:
                        raise AcquisitionError("BROWSER_RUNTIME_UNAVAILABLE", "No installed Chromium runtime is available")
                browser = runtime.chromium.launch(**options)
                try:
                    context = browser.new_context()
                    if storage_state_path:
                        import json
                        state = json.loads(Path(storage_state_path).read_text(encoding="utf-8"))
                        host = urlparse(source_url).hostname
                        cookies = [c for c in state.get("cookies", [])
                                   if host == c.get("domain", "").lstrip(".")
                                   or host.endswith("." + c.get("domain", "").lstrip("."))]
                        if cookies:
                            context.add_cookies(cookies)
                    page = context.new_page()
                    manifests = []
                    source_media = []
                    def observe_manifest(response):
                        path = urlparse(response.url).path.lower()
                        if response.status == 200 and path.endswith((".m3u8", ".mpd")) and len(manifests) < 10:
                            manifests.append(response.url)
                        host = urlparse(response.url).hostname or ""
                        if (response.status == 200 and host.endswith(".douyin.com")
                                and path.endswith("/aweme/detail/")):
                            try:
                                media = self.media_from_douyin_detail(source_url, response.json())
                                if media:
                                    source_media[:] = [media]
                            except Exception:
                                pass  # Unrelated or malformed responses are not media evidence.
                    page.on("response", observe_manifest)
                    page.set_default_timeout(20000)
                    response = page.goto(source_url, wait_until="domcontentloaded", timeout=30000)
                    if response and response.status in {401, 403, 412, 429}:
                        kind = "RATE_LIMITED" if response.status == 429 else "ACCESS_DENIED"
                        raise AcquisitionError(kind, "The source rejected normal browser access")
                    challenge_frame = _VISIBLE_CHALLENGE_FRAME
                    source_id = self.douyin_source_id(source_url)
                    deadline = time.monotonic() + 25
                    while True:
                        snapshot = page.evaluate("""(sourceId) => ({title: document.title,
                        text: document.body.innerText,
                        challenge: """ + challenge_frame + """,
                        videos: [...document.querySelectorAll('video')].map(v => ({
                            src: v.currentSrc || v.src, duration: v.duration, readyState: v.readyState,
                            protected: !!v.mediaKeys,
                            source_id: sourceId && v.closest('.video_' + sourceId) ? sourceId : null,
                            visible: !!v.getClientRects().length && getComputedStyle(v).visibility !== 'hidden'
                        }))})""", source_id)
                        snapshot["manifests"] = manifests
                        if source_media:
                            snapshot["source_media"] = source_media[0]
                            snapshot["title"] = source_media[0]["title"]
                        try:
                            resolved = self.select_media(source_url, snapshot)
                            break
                        except AcquisitionError as exc:
                            if exc.kind not in {"REFERENCE_MEDIA_UNAVAILABLE", "INVALID_MEDIA_URL"} or time.monotonic() >= deadline:
                                raise
                        page.wait_for_timeout(250)
                    resolved.headers["User-Agent"] = page.evaluate("() => navigator.userAgent")
                    return resolved
                finally:
                    browser.close()
        except AcquisitionError:
            raise
        except Exception:
            # Browser exceptions may contain cookies or signed URLs. Never emit them.
            raise AcquisitionError("BROWSER_ACQUISITION_FAILED", "Normal browser acquisition did not produce verified media") from None
