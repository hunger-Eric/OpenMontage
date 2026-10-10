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
    # Agent chat hides the ordinary composer. The header's Tools link goes to
    # the applet gallery, not video mode; never use it as a mode switch.
    trigger = r"设置触发器|settings trigger|720p.*x[1-4]"

    def button(snapshot: dict, pattern: str) -> str | None:
        filtered = {"interactables": [i for i in visible(snapshot)
                    if i.get("tag") == "BUTTON" or i.get("role") == "button"]}
        return matching(filtered, pattern)

    close_agent = r"^(?:close|关闭)(?:\s+(?:close|关闭))?$"
    expand_agent = r"^(?:expand_content\s+)?(?:展开|expand)$"
    agent_toggle = r"^(?:智能体|agent)$"

    def agent_control(s: dict) -> str | None:
        # Require an Agent-specific marker before interpreting Close/Expand.
        if not matching(s, r"智能体指令|agent instructions|^智能体$|^agent$"):
            return None
        return button(s, agent_toggle) or button(s, close_agent) or button(s, expand_agent)

    snapshot = wait_snapshot(client, lambda s: bool(button(s, trigger) or agent_control(s)),
                             "Flow has no video composer or supported Agent panel controls")
    if not button(snapshot, trigger):
        close_ref = button(snapshot, agent_toggle) or button(snapshot, close_agent)
        if not close_ref:
            client.call_tool("flow_click", {"ref": button(snapshot, expand_agent)}, timeout_seconds=30)
            snapshot = wait_snapshot(client, lambda s: bool(button(s, trigger) or
                                     (agent_control(s) and button(s, close_agent))),
                                     "Flow Agent panel did not expose its close control")
            close_ref = button(snapshot, close_agent)
        if not button(snapshot, trigger):
            client.call_tool("flow_click", {"ref": close_ref}, timeout_seconds=30)
            snapshot = wait_snapshot(client, lambda s: bool(button(s, trigger) or
                                     (agent_control(s) and button(s, agent_toggle))),
                                     "Flow Agent panel did not return to its composer")
            if not button(snapshot, trigger):
                client.call_tool("flow_click", {"ref": button(snapshot, agent_toggle)}, timeout_seconds=30)
                snapshot = wait_snapshot(client, lambda s: bool(button(s, trigger)),
                                     "Flow video composer unavailable after closing Agent panel")
    if snapshot.get("url") != project_url:
        raise GoogleFlowMCPError("Flow project changed while exiting Agent panel")
    choices = [r"(?:^|\s)(?:视频|video)(?:$|\s)",
               r"crop_16_9|16:9" if aspect_ratio == "16:9" else r"crop_9_16|9:16",
               r"720p", rf"(?:^|\s){duration:g}\s*(?:秒|s|seconds?)(?:$|\s)",
               r"(?:^|\s)x1(?:$|\s)"]

    def open_settings() -> dict:
        current = wait_snapshot(client, lambda s: bool(button(s, trigger)), "Flow has no settings trigger")
        client.call_tool("flow_click", {"ref": button(current, trigger)}, timeout_seconds=30)
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
