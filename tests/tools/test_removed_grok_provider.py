"""Regression coverage for the project-wide Grok provider removal."""

from tools.tool_registry import ToolRegistry


def test_registry_does_not_discover_grok_tools() -> None:
    registry = ToolRegistry()
    registry.ensure_discovered()

    assert registry.get_by_provider("grok") == []
    assert all("grok" not in name.lower() for name in registry.list_all())
