"""Cross-artifact governance contracts for paid model video generation."""

from schemas.artifacts import validate_artifact
from tests.contracts.test_phase0_contracts import sample_artifact
from lib.config_model import BudgetMode, OpenMontageConfig
from lib.pipeline_loader import load_pipeline
from tools.cost_tracker import CostTracker


def test_token_plan_costs_are_unknown_not_fake_zero_usd():
    proposal = sample_artifact("proposal_packet")
    proposal["production_plan"]["video_generation_contract"] = {
        "provider": "agnes",
        "model": "agnes-video-v2.0",
        "delivery_clip_count": 4,
        "completion_policy": "deliver_all_planned_clips",
        "retry_policy": "resume_existing_then_retry_terminal_failure",
        "max_frames_per_call": 441,
        "frame_count_rule": "8n + 1",
        "frame_rate_fps": 24,
        "max_duration_seconds_per_call": 18.375,
        "aspect_ratio_presets": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "long_video_policy": "split_into_planned_shots_then_compose",
    }
    proposal["cost_estimate"] = {
        "billing_mode": "token_plan",
        "total_estimated_usd": None,
        "line_items": [{
            "tool": "agnes_video",
            "operation": "generate four delivery clips; retries are recorded as actual usage",
            "quantity": 4,
            "estimated_usd": None,
            "estimated_tokens": None,
            "notes": "The provider exposes plan usage, not a reliable USD estimate.",
        }],
        "budget_verdict": "usage_unknown",
    }

    assert validate_artifact("proposal_packet", proposal) is None


def test_generated_video_manifest_preserves_provider_attempt_and_billing_identity():
    manifest = sample_artifact("asset_manifest")
    manifest["version"] = "1.1"
    manifest["assets"][0].update({
        "source_tool": "agnes_video",
        "provider": "agnes",
        "model": "agnes-video-v2.0",
        "attempt_id": "attempt-123",
        "provider_task_id": "task-456",
        "request_fingerprint": "sha256:abc",
        "attempt_ledger_path": "assets/video/clip.agnes-attempts.jsonl",
        "billing_mode": "token_plan",
        "usage_units": None,
        "cost_usd": None,
        "aspect_ratio_requested": "16:9",
        "aspect_ratio_actual": "1088:832",
        "aspect_mismatch_policy": "center_crop",
    })
    manifest["total_cost_usd"] = None

    assert validate_artifact("asset_manifest", manifest) is None


def test_animated_explainer_is_completion_driven_not_stopped_by_default_limits():
    pipeline = load_pipeline("animated-explainer")
    orchestration = pipeline["orchestration"]

    assert "budget_default_usd" not in orchestration
    assert "max_revisions_per_stage" not in orchestration
    assert "max_send_backs" not in orchestration
    assert "max_wall_time_minutes" not in orchestration
    assert OpenMontageConfig.load().budget.mode == BudgetMode.OBSERVE
    assert CostTracker().mode == BudgetMode.OBSERVE
