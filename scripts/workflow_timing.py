"""Local timing report and explicit wait/handoff markers; never runs providers."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.events import emit_event, infer_project_dir, read_events, summarize_timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["report", "begin", "end"])
    parser.add_argument("project_dir")
    parser.add_argument("--run-id")
    parser.add_argument("--activity-id")
    parser.add_argument("--activity", choices=["human_wait", "handoff", "recovery", "preparation"])
    args = parser.parse_args()
    project = infer_project_dir({"project_dir": args.project_dir})
    if project is None or not project.is_dir():
        parser.error("Expected an existing project under the canonical projects root")
    entries = read_events(project)
    if args.operation == "report":
        if args.run_id:
            entries = [e for e in entries if e.get("run_id") == args.run_id]
        result = summarize_timing(entries)
    elif args.operation == "begin":
        if not args.activity or not args.run_id:
            parser.error("begin requires --activity and --run-id")
        identity = args.activity_id or uuid4().hex
        if any(e.get("call_id") == identity for e in entries):
            parser.error("Activity ID already exists; do not duplicate markers")
        emit_event(project, {"tool": "workflow_activity", "event": "start", "call_id": identity,
                             "activity": args.activity, "run_id": args.run_id})
        result = {"activity_id": identity,
                  "recorded": any(e.get("call_id") == identity for e in read_events(project))}
    else:
        matches = [e for e in entries if e.get("call_id") == args.activity_id]
        starts = [e for e in matches if e.get("event") == "start" and e.get("tool") == "workflow_activity"]
        if len(starts) != 1 or any(e.get("event") == "finish" for e in matches):
            parser.error("end requires one unfinished workflow activity ID")
        start = starts[0]
        if args.run_id and args.run_id != start.get("run_id"):
            parser.error("Activity belongs to another run")
        duration = (datetime.now(timezone.utc) - datetime.fromisoformat(start["ts"])).total_seconds()
        emit_event(project, {"tool": "workflow_activity", "event": "finish", "call_id": args.activity_id,
                             "activity": start["activity"], "run_id": start.get("run_id"),
                             "duration_s": round(duration, 2)})
        result = {"activity_id": args.activity_id, "duration_s": round(duration, 2),
                  "recorded": any(e.get("call_id") == args.activity_id and e.get("event") == "finish"
                                  for e in read_events(project))}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
