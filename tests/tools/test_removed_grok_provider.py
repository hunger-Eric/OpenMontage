"""Optional integrations remain installed while preferences can disable selection."""
from tools.tool_registry import ToolRegistry
from tools.provider_routing import enabled_candidates


def test_registry_retains_optional_grok_integrations(monkeypatch, tmp_path):
    registry = ToolRegistry()
    registry.ensure_discovered()
    grok = registry.get_by_provider("grok")
    assert {t.name for t in grok} == {"grok_image", "grok_video"}
    local = tmp_path / "config.local.yaml"
    local.write_text("providers:\n  disabled_providers: [grok]\n", encoding="utf-8")
    monkeypatch.setenv("OPENMONTAGE_LOCAL_CONFIG", str(local))
    assert enabled_candidates(grok) == []
    assert registry.get_by_provider("grok") == grok
