from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = PROJECT_ROOT / ".agents" / "skills" / "ai-video-gen" / "SKILL.md"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_unified_video_entry_separates_production_from_asset_generation():
    skill = _skill_text()

    assert "## Route the deliverable before selecting a provider" in skill
    assert "### Complete production" in skill
    assert "### Single generated asset" in skill
    assert "pipeline_defs/" in skill
    assert "video_selector" in skill
    assert "Do not turn a complete production into a single generated clip" in skill


def test_unified_video_entry_requires_costed_approval_before_paid_execution():
    skill = _skill_text()
    normalized = " ".join(skill.split())

    assert "## Cost and approval gate" in skill
    assert "estimated total" in skill
    assert "budget ceiling" in skill
    assert "awaiting_human" in skill
    assert "Do not call a paid generation operation before this approval" in normalized


def test_unified_video_entry_preserves_pipeline_artifacts_and_quality_gates():
    skill = _skill_text()

    for contract in (
        "project.json",
        "proposal_packet",
        "scene_plan",
        "asset_manifest",
        "edit_decisions",
        "render_report",
        "final_review",
    ):
        assert contract in skill
