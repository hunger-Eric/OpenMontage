from tools.base_tool import BaseTool, ToolResult, ToolStatus
from tools.tool_registry import ToolRegistry


class CountingTool(BaseTool):
    provider = "local"
    capability = "composition"

    def __init__(self, name):
        self.name = name
        self.probes = 0

    def get_status(self):
        self.probes += 1
        return ToolStatus.AVAILABLE

    def get_info(self):
        info = super().get_info()
        info.update(render_engines={"remotion": True},
                    hyperframes_runtime={"reasons": ["missing optional runtime"]})
        return info

    def execute(self, inputs):
        return ToolResult(success=True)


def test_summary_probes_each_provider_once_and_preserves_runtime_warnings(monkeypatch):
    registry = ToolRegistry()
    tools = [CountingTool("video_compose"), CountingTool("hyperframes_compose")]
    for tool in tools:
        registry.register(tool)
    monkeypatch.setattr(registry, "ensure_discovered", lambda: None)
    result = registry.provider_menu_summary()
    assert [t.probes for t in tools] == [1, 1]
    assert result["composition_runtimes"] == {"remotion": True}
    assert result["runtime_warnings"] == ["hyperframes: missing optional runtime"]
    registry.provider_menu_summary()  # a requested refresh is still live
    assert [t.probes for t in tools] == [2, 2]
