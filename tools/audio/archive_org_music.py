"""Commercial-use-compatible music search and download from Internet Archive."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"
USER_AGENT = "OpenMontage/0.1 (royalty-free music acquisition; contact via repository)"


def _license_info(license_url: str) -> tuple[str, bool] | None:
    normalized = license_url.strip().lower().replace("http://", "https://")
    if not normalized or "/by-nc" in normalized or "/by-nd" in normalized:
        return None
    if "/publicdomain/" in normalized:
        return "Public Domain", False
    if "/zero/" in normalized:
        return "CC0", False
    if "/licenses/by-sa/" in normalized:
        return "CC BY-SA", True
    if "/licenses/by/" in normalized:
        return "CC BY", True
    return None


def _duration_seconds(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    parts = str(value).split(":")
    try:
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
        return seconds
    except ValueError:
        return None


class ArchiveOrgMusic(BaseTool):
    name = "archive_org_music"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "music_search"
    provider = "archive_org"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies: list[str] = []
    install_instructions = (
        "No setup required. Uses Internet Archive's public Advanced Search, metadata, "
        "and download endpoints without an API key."
    )
    agent_skills = ["music"]
    capabilities = ["search_music", "download_music", "stock_music"]
    supports = {
        "duration_filter": True,
        "free_commercial_use": True,
        "no_api_key": True,
        "license_metadata": True,
        "attribution_receipt": True,
    }
    best_for = [
        "publicly downloadable instrumental and ambient music",
        "stable no-key automation through documented Internet Archive APIs",
        "music with explicit Public Domain, CC0, CC BY, or CC BY-SA metadata",
    ]
    not_good_for = [
        "projects that cannot carry required attribution or ShareAlike obligations",
        "precise BPM or stem filtering",
        "guaranteed short-form cues without downstream trimming",
    ]
    fallback_tools = ["freesound_music", "music_gen"]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "min_duration": {"type": "number", "minimum": 1, "default": 30},
            "max_duration": {"type": "number", "maximum": 3600, "default": 600},
            "max_download_mb": {"type": "number", "minimum": 1, "maximum": 200, "default": 50},
            "output_path": {"type": "string"},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "server_error"])
    idempotency_key_fields = ["query", "min_duration", "max_duration"]
    side_effects = [
        "calls Internet Archive public search and metadata APIs",
        "writes one MP3 file to output_path",
    ]
    user_visible_verification = [
        "Listen to the downloaded track for mood and quality",
        "Preserve the returned license URL and attribution metadata",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        output_path = Path(str(inputs.get("output_path", "archive_org_music.mp3")))
        if output_path.suffix.lower() != ".mp3":
            return ToolResult(success=False, error="Internet Archive music output_path must end in .mp3")
        if output_path.exists():
            return ToolResult(success=False, error="Music output_path already exists; refusing to overwrite it")

        try:
            tracks = self._find_tracks(inputs)
            if not tracks:
                return ToolResult(
                    success=False,
                    error=(
                        "No commercial-use-compatible Internet Archive music found for query: "
                        f"{inputs['query']}"
                    ),
                    data={"query": inputs["query"], "provider": "archive_org"},
                    duration_seconds=round(time.time() - started, 2),
                )
            track = tracks[0]
            self._download(track, output_path)
        except Exception as exc:
            if output_path.exists():
                output_path.unlink()
            return ToolResult(
                success=False,
                error=f"Internet Archive music acquisition failed: {exc}",
                data={"query": inputs["query"], "provider": "archive_org"},
                duration_seconds=round(time.time() - started, 2),
            )

        return ToolResult(
            success=True,
            data={
                "provider": "archive_org",
                "identifier": track["identifier"],
                "item_title": track["item_title"],
                "track_title": Path(track["filename"]).stem,
                "artist": track["creator"],
                "duration_seconds": track["duration"],
                "query": inputs["query"],
                "output": str(output_path),
                "format": "mp3",
                "license": track["license"],
                "license_url": track["license_url"],
                "attribution_required": track["attribution_required"],
                "attribution": f"{track['creator']} — {track['item_title']}",
                "source_url": f"https://archive.org/details/{track['identifier']}",
                "download_url": track["download_url"],
                "source_md5": track.get("md5"),
                "file_size_bytes": output_path.stat().st_size,
                "results_found": len(tracks),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
        )

    def _request_json(self, url: str, timeout: int = 30) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _search(self, query: str) -> list[dict[str, Any]]:
        tokens = re.findall(r"[\w-]+", query, flags=re.UNICODE)
        if not tokens:
            raise ValueError("Music query must contain searchable words")
        token_query = " OR ".join(tokens[:8])
        archive_query = (
            "collection:netlabels AND mediatype:audio AND "
            f"(title:({token_query}) OR description:({token_query}) OR subject:({token_query}))"
        )
        params = urllib.parse.urlencode(
            [
                ("q", archive_query),
                ("fl[]", "identifier"),
                ("fl[]", "title"),
                ("fl[]", "creator"),
                ("fl[]", "licenseurl"),
                ("fl[]", "downloads"),
                ("rows", "50"),
                ("page", "1"),
                ("sort[]", "downloads desc"),
                ("output", "json"),
            ]
        )
        payload = self._request_json(f"{SEARCH_URL}?{params}")
        return list(payload.get("response", {}).get("docs", []))

    def _find_tracks(self, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        min_duration = float(inputs.get("min_duration", 30))
        max_duration = float(inputs.get("max_duration", 600))
        max_bytes = int(float(inputs.get("max_download_mb", 50)) * 1024 * 1024)
        tracks: list[dict[str, Any]] = []

        for item in self._search(str(inputs["query"])):
            identifier = str(item.get("identifier", "")).strip()
            listed_license = str(item.get("licenseurl", "")).strip()
            if not identifier or (listed_license and _license_info(listed_license) is None):
                continue
            metadata = self._request_json(METADATA_URL.format(identifier=urllib.parse.quote(identifier, safe="")))
            item_metadata = metadata.get("metadata", {}) or {}
            license_url = str(item_metadata.get("licenseurl") or listed_license).strip()
            license_info = _license_info(license_url)
            if license_info is None:
                continue
            license_name, attribution_required = license_info
            creator = item_metadata.get("creator") or item.get("creator") or "Unknown"
            if isinstance(creator, list):
                creator = ", ".join(str(value) for value in creator)
            item_title = str(item_metadata.get("title") or item.get("title") or identifier)

            for file_info in metadata.get("files", []):
                filename = str(file_info.get("name", ""))
                if not filename.lower().endswith(".mp3"):
                    continue
                size = int(file_info.get("size") or 0)
                if size <= 0 or size > max_bytes:
                    continue
                duration = _duration_seconds(file_info.get("length"))
                if duration is None:
                    continue
                download_url = DOWNLOAD_URL.format(
                    identifier=urllib.parse.quote(identifier, safe=""),
                    filename=urllib.parse.quote(filename, safe=""),
                )
                tracks.append({
                    "identifier": identifier,
                    "item_title": item_title,
                    "creator": str(creator),
                    "filename": filename,
                    "duration": duration,
                    "size": size,
                    "md5": file_info.get("md5"),
                    "license": license_name,
                    "license_url": license_url,
                    "attribution_required": attribution_required,
                    "download_url": download_url,
                    "duration_match": min_duration <= duration <= max_duration,
                    "license_rank": {"Public Domain": 0, "CC0": 0, "CC BY": 1, "CC BY-SA": 2}[license_name],
                    "downloads": int(item.get("downloads") or 0),
                })

        tracks.sort(
            key=lambda track: (
                not track["duration_match"],
                track["license_rank"],
                -track["downloads"],
                track["duration"],
            )
        )
        return tracks

    def _download(self, track: dict[str, Any], output_path: Path) -> None:
        request = urllib.request.Request(
            track["download_url"],
            headers={"User-Agent": USER_AGENT, "Accept": "audio/mpeg,*/*;q=0.8"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read()
        if not content:
            raise RuntimeError("Internet Archive returned an empty MP3 file")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
