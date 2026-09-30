"""Video downloader tool wrapping yt-dlp.

Downloads video, audio, or subtitles from YouTube, Shorts, Instagram Reels,
TikTok, and 1000+ other sites. Designed for reference video analysis — downloads
at analysis quality (720p), not production quality.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from http.cookiejar import Cookie
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
    ToolRuntime,
)


class VideoDownloader(BaseTool):
    name = "video_downloader"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "source_ingest"
    provider = "yt-dlp"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["python:yt_dlp"]
    install_instructions = (
        "Install yt-dlp: pip install yt-dlp\n"
        "For YouTube support, also install Deno (JS runtime): "
        "https://deno.land/#installation\n"
        "Without Deno, YouTube downloads may fail but other platforms still work."
    )
    agent_skills = ["video-download"]

    capabilities = [
        "download_video",
        "download_audio",
        "download_subtitles",
        "extract_metadata",
    ]

    best_for = [
        "downloading reference video from URL",
        "extracting audio from online video",
        "downloading subtitles from YouTube",
        "getting video metadata without downloading",
    ]

    not_good_for = [
        "downloading entire playlists",
        "downloading DRM-protected content",
    ]

    input_schema = {
        "type": "object",
        "required": ["url", "output_dir"],
        "properties": {
            "url": {"type": "string", "description": "Video URL to download"},
            "output_dir": {"type": "string", "description": "Directory for downloaded files"},
            "format": {
                "type": "string",
                "enum": ["video", "audio_only", "subtitles_only", "metadata_only"],
                "default": "video",
                "description": "What to download",
            },
            "max_resolution": {
                "type": "string",
                "enum": ["360p", "480p", "720p", "1080p"],
                "default": "720p",
                "description": "Maximum video resolution (for analysis, 720p is sufficient)",
            },
            "max_duration_seconds": {
                "type": "integer",
                "default": 600,
                "description": "Reject videos longer than this (safety limit)",
            },
            "playwright_storage_state_path": {
                "type": "string",
                "description": (
                    "Optional absolute path to a Playwright storage_state JSON file. "
                    "Cookies are loaded read-only into yt-dlp memory and are never emitted."
                ),
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "video_path": {"type": ["string", "null"]},
            "audio_path": {"type": ["string", "null"]},
            "subtitle_path": {"type": ["string", "null"]},
            "metadata": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "duration": {"type": "number"},
                    "uploader": {"type": "string"},
                    "upload_date": {"type": "string"},
                    "description": {"type": "string"},
                    "view_count": {"type": "integer"},
                    "like_count": {"type": "integer"},
                },
            },
            "platform": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=2000,
        network_required=True,
    )
    idempotency_key_fields = [
        "url", "format", "max_resolution", "playwright_storage_state_path",
    ]
    side_effects = [
        "downloads media files to output_dir",
        "reads an optional Playwright storage-state file without modifying it",
    ]
    resume_support_value = "from_start"
    user_visible_verification = [
        "Check downloaded file plays correctly",
        "Verify resolution matches requested max",
    ]

    # --- Resolution mapping ---
    _RES_MAP = {
        "360p": 360,
        "480p": 480,
        "720p": 720,
        "1080p": 1080,
    }
    _BACKGROUND_RETRY_DELAYS = (0.5, 1.5)

    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if "youtube.com/shorts" in url_lower or "youtu.be" in url_lower and "/shorts" in url_lower:
            return "shorts"
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        if "instagram.com" in url_lower:
            return "instagram"
        if "tiktok.com" in url_lower:
            return "tiktok"
        if "douyin.com" in url_lower:
            return "douyin"
        if "vimeo.com" in url_lower:
            return "vimeo"
        if "twitter.com" in url_lower or "x.com" in url_lower:
            return "twitter"
        return "other_url"

    def _resolve_url(self, url: str) -> tuple[str, str]:
        """Classify canonical URLs, resolve known aliases, and pass unknowns through."""
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            is_douyin = host == "douyin.com" or host.endswith(".douyin.com")
            if is_douyin and re.fullmatch(r"/video/\d{10,30}/?", parsed.path):
                return url, "canonical"
            if is_douyin:
                modal_ids = parse_qs(parsed.query).get("modal_id", [])
                if len(modal_ids) == 1 and re.fullmatch(r"\d{10,30}", modal_ids[0]):
                    return f"https://www.douyin.com/video/{modal_ids[0]}", "resolved_alias"
        except (TypeError, ValueError):
            pass
        return url, "passthrough"

    def _classify_download_error(self, message: str) -> str:
        lowered = message.lower()
        if "unsupported url" in lowered:
            return "UNSUPPORTED_URL"
        if any(marker in lowered for marker in (
            "fresh cookies", "sign in", "login required", "log in", "cookie",
        )):
            return "AUTH_REQUIRED"
        if any(marker in lowered for marker in ("timed out", "timeout", "temporary", "http error 5")):
            return "TRANSIENT_NETWORK"
        return "DOWNLOAD_FAILED"

    def _download_with_background_retry(
        self, url: str, ydl_opts: dict[str, Any], storage_state_path: str | None,
    ) -> int:
        """Retry read-only media acquisition when an authenticated endpoint is unstable."""
        attempts = 0
        while True:
            attempts += 1
            try:
                with self._youtube_dl(ydl_opts, storage_state_path) as ydl:
                    ydl.download([url])
                return attempts
            except Exception as exc:
                kind = self._classify_download_error(str(exc))
                retry_index = attempts - 1
                can_retry = (
                    storage_state_path is not None
                    and kind in {"AUTH_REQUIRED", "TRANSIENT_NETWORK"}
                    and retry_index < len(self._BACKGROUND_RETRY_DELAYS)
                )
                if not can_retry:
                    raise
                time.sleep(self._BACKGROUND_RETRY_DELAYS[retry_index])

    def _load_playwright_cookies(self, storage_state_path: str | None) -> list[Cookie]:
        """Load Playwright storage-state cookies without persisting their values."""
        if not storage_state_path:
            return []

        path = Path(storage_state_path)
        if not path.is_absolute():
            raise ValueError("playwright_storage_state_path must be absolute")
        if not path.is_file():
            raise ValueError("playwright_storage_state_path does not exist or is not a file")

        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("playwright_storage_state_path is not valid JSON") from exc

        raw_cookies = state.get("cookies") if isinstance(state, dict) else None
        if not isinstance(raw_cookies, list) or not raw_cookies:
            raise ValueError("Playwright storage state contains no cookies")

        cookies: list[Cookie] = []
        for index, raw in enumerate(raw_cookies):
            if not isinstance(raw, dict):
                raise ValueError(f"Playwright storage state cookie {index} is invalid")
            name, value, domain = raw.get("name"), raw.get("value"), raw.get("domain")
            if not all(isinstance(item, str) and item for item in (name, value, domain)):
                raise ValueError(f"Playwright storage state cookie {index} is incomplete")

            raw_expires = raw.get("expires")
            expires = None
            if isinstance(raw_expires, (int, float)) and math.isfinite(raw_expires) and raw_expires > 0:
                expires = int(raw_expires)
            cookie_path = raw.get("path") if isinstance(raw.get("path"), str) else "/"
            cookies.append(Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=True,
                domain_initial_dot=domain.startswith("."),
                path=cookie_path or "/",
                path_specified=True,
                secure=bool(raw.get("secure", False)),
                expires=expires,
                discard=expires is None,
                comment=None,
                comment_url=None,
                rest={"HttpOnly": None} if raw.get("httpOnly") else {},
                rfc2109=False,
            ))
        return cookies

    def _resolve_storage_state_path(
        self,
        explicit_path: str | None,
        platform: str,
        *,
        env: dict[str, str] | None = None,
        home: Path | None = None,
    ) -> tuple[str | None, str]:
        """Resolve one authorized state source without copying cookie contents."""
        if platform != "douyin":
            return explicit_path, "input" if explicit_path else "none"

        environment = os.environ if env is None else env
        configured = explicit_path or environment.get("CODEX_DOUYIN_STORAGE_STATE_PATH")
        if configured:
            absolute = str(Path(configured).expanduser().resolve())
            self._load_playwright_cookies(absolute)
            return absolute, "input" if explicit_path else "environment"

        account_home = Path.home() if home is None else home
        default_path = (
            account_home / ".social-auto-upload" / "runtime" / "cookies"
            / f"douyin_{account_home.name}.json"
        )
        try:
            absolute = str(default_path.resolve())
            self._load_playwright_cookies(absolute)
            return absolute, "uploader_default"
        except ValueError:
            return None, "none"

    def _youtube_dl(self, ydl_opts: dict[str, Any], storage_state_path: str | None):
        """Create yt-dlp and inject cookies in memory only."""
        import yt_dlp

        ydl = yt_dlp.YoutubeDL(ydl_opts)
        for cookie in self._load_playwright_cookies(storage_state_path):
            ydl.cookiejar.set_cookie(cookie)
        return ydl

    def _probe_local_media(self, video_path: str) -> dict[str, Any]:
        """Recover technical metadata from downloaded bytes when page metadata fails."""
        result = self.run_command([
            "ffprobe", "-v", "quiet", "-of", "json",
            "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate",
            video_path,
        ], timeout=30)
        payload = json.loads(result.stdout)
        video_stream = next(
            (item for item in payload.get("streams", []) if item.get("codec_type") == "video"), {}
        )
        fps = 0.0
        rate = video_stream.get("avg_frame_rate")
        if isinstance(rate, str) and re.fullmatch(r"\d+(?:\.\d+)?/\d+(?:\.\d+)?", rate):
            numerator, denominator = (float(item) for item in rate.split("/", 1))
            if denominator:
                fps = numerator / denominator
        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        return {
            "duration": float(payload.get("format", {}).get("duration") or 0),
            "resolution": f"{width}x{height}" if width and height else "",
            "fps": fps,
        }

    def _extract_metadata(self, url: str, storage_state_path: str | None = None) -> dict:
        """Extract metadata without downloading."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        try:
            with self._youtube_dl(ydl_opts, storage_state_path) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return {"error": "No info extracted", "title": "", "duration": 0}
                return {
                    "title": info.get("title", ""),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", info.get("channel", "")),
                    "upload_date": info.get("upload_date", ""),
                    "description": (info.get("description", "") or "")[:500],
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("like_count", 0),
                    "resolution": f"{info.get('width', 0)}x{info.get('height', 0)}",
                    "fps": info.get("fps", 0),
                }
        except Exception as e:
            return {"error": str(e), "title": "", "duration": 0}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        requested_url = inputs["url"]
        url, url_resolution_kind = self._resolve_url(requested_url)
        output_dir = Path(inputs["output_dir"])
        dl_format = inputs.get("format", "video")
        max_res = inputs.get("max_resolution", "720p")
        max_duration = inputs.get("max_duration_seconds", 600)
        platform = self._detect_platform(url)
        try:
            storage_state_path, storage_state_source = self._resolve_storage_state_path(
                inputs.get("playwright_storage_state_path"), platform
            )
        except ValueError as exc:
            return ToolResult(
                success=False,
                error=f"Storage state invalid: {exc}",
                data={
                    "platform": platform,
                    "requested_url": requested_url,
                    "resolved_url": url,
                    "url_resolution_kind": url_resolution_kind,
                    "error_kind": "INVALID_STORAGE_STATE",
                    "storage_state_source": "input" if inputs.get("playwright_storage_state_path") else "environment",
                },
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        start = time.time()

        # Step 1: Always get metadata first
        metadata = self._extract_metadata(url, storage_state_path)

        # Check duration limit
        duration = metadata.get("duration", 0)
        if duration and duration > max_duration:
            return ToolResult(
                success=False,
                error=(
                    f"Video is {duration}s, exceeds max_duration_seconds={max_duration}. "
                    f"Increase the limit or use a shorter video."
                ),
                data={"metadata": metadata, "platform": platform, "storage_state_source": storage_state_source},
            )

        if dl_format == "metadata_only":
            if metadata.get("error"):
                return ToolResult(
                    success=False,
                    error=f"Metadata extraction failed: {metadata['error']}",
                    data={
                        "metadata": metadata,
                        "platform": platform,
                        "requested_url": requested_url,
                        "resolved_url": url,
                        "url_resolution_kind": url_resolution_kind,
                        "error_kind": self._classify_download_error(metadata["error"]),
                        "storage_state_source": storage_state_source,
                    },
                    duration_seconds=round(time.time() - start, 2),
                )
            return ToolResult(
                success=True,
                data={
                    "video_path": None,
                    "audio_path": None,
                    "subtitle_path": None,
                    "metadata": metadata,
                    "platform": platform,
                    "requested_url": requested_url,
                    "resolved_url": url,
                    "url_resolution_kind": url_resolution_kind,
                    "storage_state_source": storage_state_source,
                },
                duration_seconds=round(time.time() - start, 2),
            )

        video_path = None
        audio_path = None
        subtitle_path = None

        try:
            if dl_format == "video":
                video_path, audio_path = self._download_video(
                    url, output_dir, max_res, storage_state_path
                )
            elif dl_format == "audio_only":
                audio_path = self._download_audio(url, output_dir, storage_state_path)
            elif dl_format == "subtitles_only":
                subtitle_path = self._download_subtitles(url, output_dir, storage_state_path)
        except Exception as e:
            elapsed = time.time() - start
            message = str(e)
            return ToolResult(
                success=False,
                error=f"Download failed: {message}",
                data={
                    "metadata": metadata,
                    "platform": platform,
                    "requested_url": requested_url,
                    "resolved_url": url,
                    "url_resolution_kind": url_resolution_kind,
                    "error_kind": self._classify_download_error(message),
                    "storage_state_source": storage_state_source,
                },
                duration_seconds=round(elapsed, 2),
            )

        elapsed = time.time() - start
        artifacts = [p for p in [video_path, audio_path, subtitle_path] if p]
        metadata_status = "complete"
        remote_metadata_error = metadata.pop("error", None)
        if video_path and (remote_metadata_error or not metadata.get("duration")):
            try:
                local_metadata = self._probe_local_media(video_path)
                for key, value in local_metadata.items():
                    if value:
                        metadata[key] = value
                metadata_status = "local_media_recovered"
            except Exception:
                metadata_status = "partial"
        elif remote_metadata_error:
            metadata_status = "partial"

        return ToolResult(
            success=True,
            data={
                "video_path": video_path,
                "audio_path": audio_path,
                "subtitle_path": subtitle_path,
                "metadata": metadata,
                "platform": platform,
                "requested_url": requested_url,
                "resolved_url": url,
                "url_resolution_kind": url_resolution_kind,
                "metadata_status": metadata_status,
                "remote_metadata_warning_kind": (
                    self._classify_download_error(remote_metadata_error)
                    if remote_metadata_error else None
                ),
                "storage_state_source": storage_state_source,
            },
            artifacts=artifacts,
            duration_seconds=round(elapsed, 2),
        )

    def _download_video(
        self, url: str, output_dir: Path, max_res: str,
        storage_state_path: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Download video + extract audio track."""
        height = self._RES_MAP.get(max_res, 720)
        video_out = str(output_dir / "reference_video.%(ext)s")

        ydl_opts = {
            "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best",
            "merge_output_format": "mp4",
            "outtmpl": video_out,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        self._download_with_background_retry(url, ydl_opts, storage_state_path)

        # Find the downloaded video file
        video_path = self._find_downloaded(output_dir, "reference_video", ["mp4", "mkv", "webm"])

        # Extract audio separately for transcription
        audio_path = None
        if video_path:
            audio_out = output_dir / "reference_audio.wav"
            try:
                audio_cmd = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-vn",
                    "-acodec", "pcm_s16le",
                    "-ar", "16000",
                    "-ac", "1",
                    str(audio_out),
                ]
                self.run_command(audio_cmd, timeout=120)
                if audio_out.exists():
                    audio_path = str(audio_out)
            except Exception:
                pass  # Audio extraction is optional

        return video_path, audio_path

    def _download_audio(
        self, url: str, output_dir: Path, storage_state_path: str | None = None,
    ) -> str | None:
        """Download audio only."""
        audio_out = str(output_dir / "reference_audio.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }],
            "outtmpl": audio_out,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        self._download_with_background_retry(url, ydl_opts, storage_state_path)
        return self._find_downloaded(output_dir, "reference_audio", ["wav", "mp3", "m4a", "opus"])

    def _download_subtitles(
        self, url: str, output_dir: Path, storage_state_path: str | None = None,
    ) -> str | None:
        """Download subtitles only."""
        sub_out = str(output_dir / "reference_subs.%(ext)s")
        ydl_opts = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "srt",
            "skip_download": True,
            "outtmpl": sub_out,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        try:
            self._download_with_background_retry(url, ydl_opts, storage_state_path)
        except Exception:
            pass
        return self._find_downloaded(output_dir, "reference_subs", ["srt", "vtt", "ass"])

    def _find_downloaded(
        self, output_dir: Path, prefix: str, extensions: list[str]
    ) -> str | None:
        """Find a downloaded file by prefix and possible extensions."""
        for ext in extensions:
            candidates = list(output_dir.glob(f"{prefix}*.{ext}"))
            if candidates:
                return str(candidates[0])
        return None
