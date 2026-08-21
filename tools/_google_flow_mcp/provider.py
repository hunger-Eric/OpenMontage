"""Provider-level orchestration shared by Google Flow video and music tools."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools._google_flow_mcp.client import (
    GoogleFlowMCPClient,
    GoogleFlowMCPError,
    google_flow_node,
    google_flow_server_entry,
)
from tools.base_tool import ToolStatus


def provider_status() -> ToolStatus:
    entry = google_flow_server_entry()
    tools_bundle = entry.parent / "tools.js"
    if not google_flow_node() or not shutil.which("ffprobe") or not entry.is_file() or not tools_bundle.is_file():
        return ToolStatus.UNAVAILABLE
    try:
        contract = tools_bundle.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ToolStatus.UNAVAILABLE
    if "flow_close" not in contract or "expectedMediaType" not in contract:
        return ToolStatus.UNAVAILABLE
    return ToolStatus.AVAILABLE


def resolve_project_url(inputs: dict[str, Any]) -> str | None:
    value = inputs.get("project_url") or os.environ.get("GOOGLE_FLOW_PROJECT_URL")
    return str(value).strip() if value else None


def select_text_input(snapshot: dict[str, Any], *, music: bool) -> str:
    interactables = [
        item
        for item in snapshot.get("interactables", [])
        if isinstance(item, dict) and item.get("visible") and not item.get("disabled")
    ]
    if music:
        preferred = [
            item
            for item in interactables
            if "chat message" in str(item.get("ariaLabel") or "").lower()
        ]
        if preferred:
            return str(preferred[0]["ref"])
    role_textboxes = [item for item in interactables if item.get("role") == "textbox"]
    if role_textboxes:
        return str(role_textboxes[0]["ref"])
    textareas = [item for item in interactables if item.get("tag") == "TEXTAREA"]
    if textareas:
        return str(textareas[0]["ref"])
    raise GoogleFlowMCPError("Google Flow page has no visible prompt input")


def wait_for_text_input(
    client: GoogleFlowMCPClient,
    *,
    music: bool,
    attempts: int = 8,
    delay_seconds: float = 1.5,
) -> str:
    """Wait for Flow's client-rendered composer to become interactive."""
    last_error: GoogleFlowMCPError | None = None
    for attempt in range(attempts):
        snapshot = client.call_tool("flow_snapshot", {}, timeout_seconds=30)
        try:
            return select_text_input(snapshot, music=music)
        except GoogleFlowMCPError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds)
    raise last_error or GoogleFlowMCPError("Google Flow page has no visible prompt input")


def run_generation(
    *,
    url: str,
    prompt: str,
    output_path: Path,
    expected_media_type: str,
    max_budget_credits: float,
    timeout_seconds: int,
    music: bool,
) -> dict[str, Any]:
    with GoogleFlowMCPClient(timeout_seconds=timeout_seconds + 60) as client:
        opened = client.call_tool("flow_open", {"url": url}, timeout_seconds=60)
        input_ref = wait_for_text_input(client, music=music)
        approval = client.call_tool(
            "flow_confirm_paid_generation",
            {
                "confirm": True,
                "maxBudgetCredits": max_budget_credits,
                "reason": f"OpenMontage {expected_media_type} generation",
            },
            timeout_seconds=30,
        )
        client.call_tool(
            "flow_type",
            {"ref": input_ref, "text": prompt, "clearFirst": True, "submit": True},
            timeout_seconds=60,
        )
        waited = client.call_tool(
            "flow_wait",
            {
                "forMedia": True,
                "mediaType": expected_media_type,
                "timeoutMs": timeout_seconds * 1000,
            },
            timeout_seconds=timeout_seconds + 30,
        )
        asset_url = waited.get("assetUrl")
        if not asset_url:
            raise GoogleFlowMCPError("Google Flow completed without a downloadable asset URL")
        downloaded = client.call_tool(
            "flow_download",
            {
                "assetUrl": asset_url,
                "outputPath": str(output_path),
                "expectedMediaType": expected_media_type,
            },
            timeout_seconds=300,
        )
        return {
            "opened": opened,
            "approval": approval,
            "wait": waited,
            "download": downloaded,
        }


def probe_media(path: Path, expected_media_type: str) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise GoogleFlowMCPError("ffprobe is required to validate Google Flow output")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise GoogleFlowMCPError(
            f"ffprobe rejected Google Flow output: {completed.stderr.strip() or completed.returncode}"
        )
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    matching = [stream for stream in streams if stream.get("codec_type") == expected_media_type]
    duration = float((payload.get("format") or {}).get("duration") or 0)
    if not matching or duration <= 0:
        raise GoogleFlowMCPError(
            f"Google Flow output is not a real {expected_media_type} asset with positive duration"
        )
    primary = matching[0]
    return {
        "duration_seconds": duration,
        "format_name": (payload.get("format") or {}).get("format_name"),
        "codec": primary.get("codec_name"),
        "width": primary.get("width"),
        "height": primary.get("height"),
        "sample_rate": primary.get("sample_rate"),
        "channels": primary.get("channels"),
        "file_size_bytes": path.stat().st_size,
    }
