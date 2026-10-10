"""Google Flow video generation through the local google-flow-mcp-v4 bridge."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from lib.config_model import OpenMontageConfig

from tools._google_flow_mcp.client import GoogleFlowMCPError, google_flow_root
from tools._google_flow_mcp.provider import (
    probe_media,
    provider_status,
    resolve_project_url,
    run_generation,
)
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class GoogleFlowMCPVideo(BaseTool):
    name = "google_flow_mcp_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "google_flow"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies = ["cmd:node", "cmd:ffprobe"]
    install_instructions = (
        "Build the local google-flow-mcp-v4 project and set GOOGLE_FLOW_MCP_ROOT if it is not "
        "a sibling of OpenMontage. Sign in to its browser profile; optionally pass project_url "
        "or set GOOGLE_FLOW_PROJECT_URL to reuse a project."
    )
    fallback_tools: list[str] = []
    agent_skills = ["gemini-omni", "ai-video-gen"]
    supports = {
        "text_to_video": True,
        "references_to_video": True,
        "native_audio": True,
        "cinematic_quality": True,
        "browser_subscription": True,
        "explicit_credit_approval": False,
        "optional_credit_cap": True,
        "max_concurrent_jobs": 1,
    }
    best_for = [
        "Google Flow Gemini Omni Flash video through an existing browser subscription",
        "cinematic clips requested by the user",
    ]
    not_good_for = ["generation without a user production request"]
    input_schema = {
        "type": "object",
        "required": ["prompt", "output_path", "confirm_paid_generation"],
        "properties": {
            "prompt": {"type": "string"},
            "output_path": {"type": "string", "description": "Absolute .mp4 output path"},
            "project_url": {"type": "string", "description": "Existing Flow project; otherwise start from the configured homepage"},
            "model": {"type": "string", "description": "Exact Flow UI model; defaults to google_flow.model configuration"},
            "duration": {"type": "number", "enum": [4, 6, 8, 10], "default": 6},
            "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16"], "default": "16:9"},
            "reference_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Absolute paths uploaded as Flow ingredients before generation",
            },
            "confirm_paid_generation": {"type": "boolean", "default": False,
                "description": "Set true for a user-authorized video request; no separate fee approval is needed unless the user specified a cap."},
            "max_budget_credits": {"type": ["number", "null"], "exclusiveMinimum": 0,
                "description": "Optional user-specified cap; omitted/null means no credit ceiling."},
            "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 900, "default": 900},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=1024, vram_mb=0, disk_mb=2048, network_required=True
    )
    idempotency_key_fields = [
        "prompt",
        "model",
        "duration",
        "aspect_ratio",
        "project_url",
        "reference_paths",
    ]
    side_effects = [
        "uses Google subscription credits after explicit confirmation",
        "drives the authenticated Google Flow browser profile through local MCP",
        "writes a validated MP4 file to output_path",
    ]
    user_visible_verification = [
        "Play the generated clip and inspect motion, framing, and synchronized audio",
    ]

    def get_status(self) -> ToolStatus:
        return provider_status()

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        config = OpenMontageConfig.load().google_flow
        info["default_model"] = config.model
        info["model_catalog"] = {config.model: {"transport": "mcp_stdio_browser",
                                                 "requires_ui_verification": True}}
        return info

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("timeout_seconds", 900))

    def is_operation_available(self, operation: str) -> bool:
        return operation in {"text_to_video", "references_to_video"} and self.get_status() == ToolStatus.AVAILABLE

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        config = OpenMontageConfig.load().google_flow
        return {
            "tool": self.name,
            "status": self.get_status().value,
            "mcp_root": str(google_flow_root()),
            "model": inputs.get("model") or config.model,
            "start_url": resolve_project_url(inputs) or config.start_url,
            "max_budget_credits": inputs.get("max_budget_credits", config.max_budget_credits),
            "requires_explicit_credit_approval": False,
            "cost_notice": "Uses Flow subscription credits; report available pricing once and continue the authorized production.",
            "would_execute": False,
            "fallback_used": False,
        }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error=self.install_instructions, data={"fallback_used": False})
        if inputs.get("confirm_paid_generation") is not True:
            return ToolResult(
                success=False,
                error="Google Flow video generation requires confirm_paid_generation=true",
                data={"error_code": "approval_required", "fallback_used": False},
            )
        config = OpenMontageConfig.load().google_flow
        project_url = resolve_project_url(inputs) or config.start_url
        output_path = Path(str(inputs["output_path"]))
        if output_path.suffix.lower() != ".mp4":
            return ToolResult(success=False, error="Google Flow video output_path must end in .mp4")
        if output_path.exists():
            return ToolResult(
                success=False,
                error="Google Flow video output_path already exists; refusing to overwrite it",
                data={"error_code": "output_exists", "fallback_used": False},
            )
        if output_path.with_suffix(output_path.suffix + ".flow-attempt.json").exists():
            return ToolResult(success=False, error="Existing Flow attempt requires reconciliation; not submitting again",
                              data={"error_code": "existing_attempt", "fallback_used": False})

        duration = float(inputs.get("duration", 6))
        aspect_ratio = str(inputs.get("aspect_ratio", "16:9"))
        if duration not in {4, 6, 8, 10} or aspect_ratio not in {"16:9", "9:16"}:
            return ToolResult(success=False, error="Flow requires 4/6/8/10 seconds and 16:9 or 9:16",
                              data={"error_code": "invalid_video_settings", "fallback_used": False})
        budget = inputs.get("max_budget_credits", config.max_budget_credits)
        max_budget_credits = float(budget) if budget is not None else None
        if max_budget_credits is not None and not 0 < max_budget_credits < float("inf"):
            return ToolResult(success=False, error="Flow credit budget must be finite and positive")

        reference_paths = [Path(str(value)) for value in inputs.get("reference_paths", [])]
        missing_references = [str(path) for path in reference_paths if not path.is_file()]
        if missing_references:
            return ToolResult(
                success=False,
                error=f"Google Flow video reference asset does not exist: {missing_references[0]}",
                data={"error_code": "reference_missing", "fallback_used": False},
            )

        model = str(inputs.get("model") or config.model)
        full_prompt = (
            f"请立即使用 {model} 生成视频镜头：{inputs['prompt']}\n"
            f"目标时长 {float(inputs.get('duration', 6)):g} 秒，画幅 {inputs.get('aspect_ratio', '16:9')}。"
        )
        try:
            receipt = run_generation(
                url=project_url,
                prompt=full_prompt,
                output_path=output_path,
                expected_media_type="video",
                max_budget_credits=max_budget_credits,
                timeout_seconds=int(inputs.get("timeout_seconds", 900)),
                music=False,
                reference_paths=reference_paths,
                video_settings={"model": model, "duration": duration, "aspect_ratio": aspect_ratio},
            )
            probe = probe_media(output_path, "video")
        except Exception as exc:
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
            return ToolResult(
                success=False,
                error=f"Google Flow MCP video generation failed: {exc}",
                data={
                    "provider": "google_flow",
                    "transport": "mcp_stdio_browser",
                    "fallback_used": False,
                },
            )

        waited = receipt["wait"]
        downloaded = receipt["download"]
        data = {
            "provider": "google_flow",
            "transport": "mcp_stdio_browser",
            "model": model,
            "project_url": receipt["opened"].get("url", project_url),
            "job_id": waited.get("jobId"),
            "output": str(output_path),
            "output_path": str(output_path),
            "sha256": downloaded.get("sha256"),
            "billing_mode": "subscription_credits",
            "max_budget_credits": max_budget_credits,
            "settings_receipt": receipt.get("settings"),
            "reference_count": len(reference_paths),
            "upload_receipts": receipt.get("uploads", []),
            "fallback_used": False,
            **probe,
        }
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )
