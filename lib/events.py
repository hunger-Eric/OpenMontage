"""Backlot event stream — append-only tool-event log per project.

Written by the BaseTool instrumentation layer (tools/base_tool.py) whenever a
tool executes against a project directory; consumed by the Backlot board's
watcher to power live activity and per-scene generating states.

Design rules:
- Observability must never break production: every public function swallows
  its own errors. A failed event write is silently dropped.
- Zero agent burden: project attribution is inferred from the tool's inputs
  (explicit ``project_dir`` or any path argument under ``projects/``).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lib.paths import PROJECTS_DIR, REPO_ROOT  # single source of truth

EVENTS_FILENAME = "events.jsonl"
WORKFLOW_ACTIVITIES = {"generation", "composition", "recovery", "human_wait",
                       "handoff", "preparation", "tool_execution"}


def activity_category(tool, operation: str | None, explicit: str | None = None) -> str:
    if isinstance(explicit, str) and explicit in WORKFLOW_ACTIVITIES:
        return explicit
    if isinstance(operation, str) and operation in {"status", "poll", "recover", "reconcile", "generation_status"}:
        return "recovery"
    if operation in ("discover_models", "list_models", "get_info"):
        return "tool_execution"
    if getattr(tool, "name", "") == "video_compose":
        return "composition"
    if "generation" in getattr(tool, "capability", ""):
        return "generation"
    return "tool_execution"


def failure_details(error: Any) -> dict[str, str]:
    """Coarse reason without persisting credentials, prompts or provider bodies.

    Keep the full error in the existing tool result/owning receipt. A timeout
    classifies the local call only; it does not declare a provider task failed.
    """
    message = str(error or "").lower()
    groups = (
        ("timeout", ("timeout", "timed out")),
        ("authentication", ("unauthorized", "authentication", "401", "403")),
        ("safety_block", ("moderation", "safety block")),
        ("dependency", ("modulenotfound", "no module named", "executable doesn't exist")),
        ("invalid_input", ("validation", "required", "missing", "invalid", "preflight")),
    )
    category = next((name for name, terms in groups if any(t in message for t in terms)), "unknown")
    return {"error_category": category, "error": f"Tool call failed ({category}); inspect owning receipt/result"}

# Thread-level serialization only. Cross-PROCESS appends are unsynchronized
# by design: single-line O_APPEND writes rarely tear, and read_events skips
# malformed lines, so a torn line degrades to one missing activity entry.
_write_lock = threading.Lock()

# Input keys checked (in order) when inferring the project a tool call
# belongs to. Explicit project keys win over path inference.
_EXPLICIT_PROJECT_KEYS = ("project_dir", "project_path")
_PATH_HINT_KEYS = (
    "output_path",
    "output_dir",
    "output_file",
    "input_path",
    "video_path",
    "audio_path",
    "image_path",
    "file_path",
)


def infer_project_dir(inputs: Any) -> Optional[Path]:
    """Best-effort: which project directory does this tool call belong to?

    Returns None when the call can't be attributed — the event is then
    simply not emitted (principle: never guess loudly, never fail).
    """
    if not isinstance(inputs, dict):
        return None
    try:
        # Only paths under the canonical projects root are attributable —
        # an explicit project_dir pointing elsewhere (HyperFrames workspace,
        # arbitrary user dir) must not receive an events.jsonl. Explicit
        # values are normalized to the project ROOT the same way hints are,
        # so project_dir="projects/x/renders/build" attributes to projects/x.
        projects_root = PROJECTS_DIR.resolve()
        for key in _EXPLICIT_PROJECT_KEYS + _PATH_HINT_KEYS:
            value = inputs.get(key)
            if not isinstance(value, (str, Path)) or not str(value):
                continue
            try:
                resolved = Path(value).resolve()
                rel = resolved.relative_to(projects_root)
            except (ValueError, OSError):
                continue
            if rel.parts:
                return PROJECTS_DIR / rel.parts[0]
    except Exception:
        return None
    return None


def emit_event(project_dir: Path | str, payload: dict[str, Any]) -> None:
    """Append one event to the project's events.jsonl. Never raises.

    Writes only into an EXISTING project directory — a typo'd path must not
    spawn a ghost project on the board.
    """
    try:
        project_dir = Path(project_dir)
        if not project_dir.is_dir():
            return
        entry = {"ts": datetime.now(timezone.utc).isoformat()}
        entry.update({k: v for k, v in payload.items() if v is not None})
        path = project_dir / EVENTS_FILENAME
        line = json.dumps(entry, default=str)
        with _write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def read_events(project_dir: Path | str, limit: Optional[int] = None) -> list[dict[str, Any]]:
    """Read events for a project (oldest first). Tolerates malformed lines."""
    path = Path(project_dir) / EVENTS_FILENAME
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    if limit is not None:
        return events[-limit:]
    return events


def summarize_timing(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Union observed intervals, excluding nested selectors/providers.

    Categories can overlap (preparation during generation); their totals must
    not be added. Missing terminals and historical gaps remain unattributed.
    """
    timestamps, intervals, groups = [], [], {}
    failures = []
    starts, terminals = set(), set()
    for entry in entries:
        try:
            stamp = datetime.fromisoformat(entry["ts"]).timestamp()
            timestamps.append(stamp)
            if entry.get("call_id"):
                if entry.get("event") == "start":
                    starts.add(entry["call_id"])
                elif entry.get("event") in {"finish", "error"}:
                    terminals.add(entry["call_id"])
            if entry.get("depth", 0):
                continue
            if entry.get("event") not in {"finish", "error"}:
                continue
            duration = float(entry["duration_s"])
            if not (0 <= duration < float("inf")):
                continue
            interval = (stamp - duration, stamp)
            intervals.append(interval)
            category = entry.get("activity", "tool_execution")
            if category not in WORKFLOW_ACTIVITIES:
                category = "tool_execution"
            groups.setdefault(category, []).append(interval)
            if entry.get("success") is False or entry.get("event") == "error":
                failures.append({k: entry[k] for k in (
                    "tool", "operation", "call_id", "attempt_id", "error_category", "duration_s") if k in entry})
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

    def union_seconds(values):
        total, end = 0.0, float("-inf")
        for left, right in sorted(values):
            total += max(0.0, right - max(left, end))
            end = max(end, right)
        return round(total, 2)

    # Finish-only histories still include the duration preceding the first ts.
    timestamps.extend(left for left, _ in intervals)
    span = round(max(timestamps) - min(timestamps), 2) if timestamps else 0.0
    covered = union_seconds(intervals)
    return {"observed_span_s": span, "covered_s": covered,
            "unattributed_s": round(max(0.0, span - covered), 2),
            "by_activity_s": {k: union_seconds(v) for k, v in sorted(groups.items())},
            "categories_may_overlap": True, "open_call_ids": sorted(starts - terminals),
            "failed_calls": failures}
