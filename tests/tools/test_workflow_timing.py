import json

import pytest
from lib import events


def test_report_unions_overlap_excludes_nested_and_leaves_gaps_unknown():
    entries = [
        {"ts": "2026-10-14T00:00:00+00:00", "event": "start", "call_id": "outer"},
        {"ts": "2026-10-14T00:00:10+00:00", "event": "finish", "call_id": "outer",
         "duration_s": 10, "activity": "generation"},
        {"ts": "2026-10-14T00:00:09+00:00", "event": "finish", "depth": 1,
         "duration_s": 9, "activity": "generation"},
        {"ts": "2026-10-14T00:00:10+00:00", "event": "finish",
         "duration_s": 5, "activity": "preparation"},
        {"ts": "2026-10-14T00:00:20+00:00", "event": "start", "call_id": "unclosed"},
    ]
    result = events.summarize_timing(entries)
    assert result["covered_s"] == 10
    assert result["unattributed_s"] == 10
    assert result["by_activity_s"] == {"generation": 10, "preparation": 5}
    assert result["open_call_ids"] == ["unclosed"]


def test_legacy_failed_calls_and_malformed_records_remain_readable():
    result = events.summarize_timing([
        {"ts": "2026-10-14T00:00:10+00:00", "event": "finish",
         "duration_s": 3, "success": False, "tool": "old-provider"},
        {"ts": "bad", "event": "finish"},
    ])
    assert result["observed_span_s"] == result["covered_s"] == 3
    assert result["failed_calls"] == [{"tool": "old-provider", "duration_s": 3}]


def test_cli_markers_keep_run_identity_and_report_is_read_only(tmp_path, monkeypatch, capsys):
    from scripts.workflow_timing import main
    project = tmp_path / "projects" / "demo"
    project.mkdir(parents=True)
    monkeypatch.setattr(events, "PROJECTS_DIR", project.parent)
    def run(*args):
        monkeypatch.setattr("sys.argv", ["workflow_timing", *args])
        main()
        return json.loads(capsys.readouterr().out)
    assert run("begin", str(project), "--run-id", "one", "--activity", "human_wait", "--activity-id", "wait-1")["recorded"]
    with pytest.raises(SystemExit):
        run("end", str(project), "--activity-id", "wait-1", "--run-id", "other")
    assert run("end", str(project), "--activity-id", "wait-1")["recorded"]
    emitted = events.read_events(project)
    assert [e["event"] for e in emitted] == ["start", "finish"]
    assert all(e["run_id"] == "one" for e in emitted)
    before = (project / "events.jsonl").read_bytes()
    assert "human_wait" in run("report", str(project), "--run-id", "one")["by_activity_s"]
    assert (project / "events.jsonl").read_bytes() == before
    with pytest.raises(SystemExit):
        run("end", str(project), "--activity-id", "wait-1")
