"""Flow browser video setup aligned with the video-platform MCP executor."""

from __future__ import annotations

import re
import time
from typing import Any, Callable
from urllib.parse import urlparse

from tools._google_flow_mcp.client import GoogleFlowMCPError
from tools._google_flow_mcp.provider import select_text_input


def visible(snapshot: dict) -> list[dict]:
    return [i for i in snapshot.get("interactables", [])
            if isinstance(i, dict) and i.get("visible") and not i.get("disabled")]


def matching(snapshot: dict, pattern: str, role: str | None = None) -> str | None:
    for item in visible(snapshot):
        if role and item.get("role") != role:
            continue
        label = f"{item.get('text', '')} {item.get('ariaLabel', '')}".strip()
        if re.search(pattern, label, re.I) and item.get("ref"):
            return str(item["ref"])
    return None


def wait_snapshot(client: Any, ready: Callable[[dict], bool], message: str) -> dict:
    deadline = time.monotonic() + 30
    while True:
        snapshot = client.call_tool("flow_snapshot", {}, timeout_seconds=30)
        if ready(snapshot):
            return snapshot
        if time.monotonic() >= deadline:
            raise GoogleFlowMCPError(message)
        time.sleep(0.5)


def has_prompt(snapshot: dict) -> bool:
    try:
        select_text_input(snapshot, music=False)
        return True
    except GoogleFlowMCPError:
        return False


def resolve_video_project(client: Any) -> str:
    new_project = r"新建项目|new project|create project"
    snapshot = wait_snapshot(client, lambda s: has_prompt(s) or bool(matching(s, new_project)),
                             "Flow has no composer or new-project action")
    if not has_prompt(snapshot):
        client.call_tool("flow_click", {"ref": matching(snapshot, new_project)}, timeout_seconds=60)
        snapshot = wait_snapshot(client, has_prompt, "Flow project has no prompt input")
    url = str(snapshot.get("url") or "")
    parsed = urlparse(url)
    valid = parsed.scheme == "https" and (
        (parsed.hostname == "flow.google.com" and parsed.path.startswith("/project/"))
        or (parsed.hostname == "labs.google" and "/tools/flow/project/" in parsed.path)
    )
    if not valid:
        raise GoogleFlowMCPError("Flow returned an invalid video project URL")
    return url


def configure_video_settings(client: Any, project_url: str, model: str,
                             duration: float, aspect_ratio: str) -> dict:
    if duration not in {4, 6, 8, 10} or aspect_ratio not in {"16:9", "9:16"}:
        raise GoogleFlowMCPError("Flow video requires 4/6/8/10 seconds and 16:9 or 9:16")
    # Match the video-platform executor's modern Tools composer.
    trigger = r"设置触发器|settings trigger|720p.*x[1-4]"
    tools = r"^(?:apps_spark_2\s+)?(?:工具|tools)$"
    snapshot = wait_snapshot(client, lambda s: bool(matching(s, trigger) or matching(s, tools)),
                             "Flow has no video settings or Tools mode")
    if not matching(snapshot, trigger):
        client.call_tool("flow_click", {"ref": matching(snapshot, tools)}, timeout_seconds=30)
    choices = [r"(?:^|\s)(?:视频|video)(?:$|\s)",
               r"crop_16_9|16:9" if aspect_ratio == "16:9" else r"crop_9_16|9:16",
               r"720p", rf"(?:^|\s){duration:g}\s*(?:秒|s|seconds?)(?:$|\s)",
               r"(?:^|\s)x1(?:$|\s)"]

    def open_settings() -> dict:
        current = wait_snapshot(client, lambda s: bool(matching(s, trigger)), "Flow has no settings trigger")
        client.call_tool("flow_click", {"ref": matching(current, trigger)}, timeout_seconds=30)
        return wait_snapshot(client, lambda s: any(model in str(i.get("text", "")) for i in visible(s))
                             and all(matching(s, p, "radio") for p in choices),
                             f"Flow model/settings unavailable: {model}")

    snapshot = open_settings()
    for pattern in choices:
        ref = matching(snapshot, pattern, "radio")
        if not ref:
            snapshot = open_settings()
            ref = matching(snapshot, pattern, "radio")
        client.call_tool("flow_click", {"ref": ref}, timeout_seconds=30)
        snapshot = client.call_tool("flow_snapshot", {}, timeout_seconds=30)

    def retained(s: dict) -> bool:
        return any("720p" in str(i.get("text", "")) and "x1" in str(i.get("text", ""))
                   and re.search(choices[1], str(i.get("text", "")))
                   and re.search(choices[3], str(i.get("text", ""))) for i in visible(s))

    snapshot = wait_snapshot(client, retained, "Flow did not retain the requested video settings")
    if snapshot.get("url") != project_url:
        raise GoogleFlowMCPError("Flow project changed while configuring settings")
    return {"model": model, "duration": duration, "aspect_ratio": aspect_ratio,
            "resolution": "720p", "results": 1, "verified": True}
