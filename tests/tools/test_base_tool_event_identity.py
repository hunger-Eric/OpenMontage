from __future__ import annotations

from tools.base_tool import BaseTool, ToolResult
from lib import events


class _EventTool(BaseTool):
    name = "event_tool"

    def execute(self, inputs):
        return ToolResult(
            success=True,
            data={"task_id": "provider-task", "attempt_id": "attempt-result"},
        )


def test_tool_events_preserve_operation_run_and_attempt_identity(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    monkeypatch.setattr(events, "PROJECTS_DIR", projects)

    _EventTool().execute({
        "project_dir": str(project),
        "operation": "review",
        "run_id": "run-1",
        "stage_attempt_id": "compose-2",
        "attempt_id": "attempt-input",
    })

    emitted = events.read_events(project)
    assert [item["event"] for item in emitted] == ["start", "finish"]
    assert all(item["operation"] == "review" for item in emitted)
    assert all(item["run_id"] == "run-1" for item in emitted)
    assert all(item["stage_attempt_id"] == "compose-2" for item in emitted)
    assert emitted[0]["attempt_id"] == "attempt-input"
    assert emitted[1]["provider_task_id"] == "provider-task"
    assert emitted[1]["attempt_id"] == "attempt-result"


def test_nested_calls_have_unique_ids_and_safe_failure_reason(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    monkeypatch.setattr(events, "PROJECTS_DIR", projects)
    class Provider(BaseTool):
        name = "provider"
        capability = "video_generation"
        def execute(self, inputs):
            return ToolResult(success=False, error="Timed out Bearer TOP_SECRET token=SECRET")
    class Selector(BaseTool):
        name = "selector"
        capability = "video_generation"
        def execute(self, inputs):
            return Provider().execute(inputs)
    Selector().execute({"project_dir": str(project), "operation": "text_to_video"})
    emitted = events.read_events(project)
    outer, inner = emitted[:2]
    assert outer["call_id"] != inner["call_id"]
    assert inner["parent_call_id"] == outer["call_id"]
    assert inner["activity"] == "generation"
    assert emitted[2]["error_category"] == "timeout"
    assert "SECRET" not in (project / "events.jsonl").read_text()
    assert all(e["event"] != "error" for e in emitted)  # original ToolResult unchanged


def test_exception_event_is_safe_and_depth_resets(tmp_path, monkeypatch):
    import pytest
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    monkeypatch.setattr(events, "PROJECTS_DIR", projects)
    class Broken(BaseTool):
        name = "broken"
        def execute(self, inputs):
            raise RuntimeError("No module named example TOKEN_SECRET")
    with pytest.raises(RuntimeError):
        Broken().execute({"project_dir": str(project)})
    _EventTool().execute({"project_dir": str(project)})
    emitted = events.read_events(project)
    assert emitted[1]["error_category"] == "dependency"
    assert emitted[1]["error_type"] == "RuntimeError"
    assert not emitted[2].get("parent_call_id")
    assert "TOKEN_SECRET" not in (project / "events.jsonl").read_text()
