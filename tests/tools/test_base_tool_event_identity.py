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
