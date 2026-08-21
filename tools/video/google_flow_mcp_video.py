"""Google Flow video generation through the local google-flow-mcp-v4 bridge."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

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
        "a sibling of OpenMontage. Pass project_url or set GOOGLE_FLOW_PROJECT_URL."
    )
    fallback_tools: list[str] = []
    agent_skills = ["gemini-omni", "ai-video-gen"]
    supports = {
        "text_to_video": True,
        "native_audio": True,
        "cinematic_quality": True,
        "browser_subscription": True,
        "explicit_credit_approval": True,
    }
    best_for = [
        "Google Flow Gemini Omni Flash video through an existing browser subscription",
        "cinematic clips with explicit per-call credit approval",
    ]
    not_good_for = ["unattended generation without a confirmed credit budget"]
    input_schema = {
        "type": "object",
        "required": ["prompt", "output_path", "confirm_paid_generation", "max_budget_credits"],
        "properties": {
            "prompt": {"type": "string"},
            "output_path": {"type": "string", "description": "Absolute .mp4 output path"},
            "project_url": {"type": "string", "description": "Existing Google Flow project URL"},
            "model": {"type": "string", "default": "Gemini Omni Flash"},
            "duration": {"type": "number", "minimum": 1, "maximum": 15, "default": 6},
            "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"], "default": "16:9"},
            "confirm_paid_generation": {"type": "boolean", "default": False},
            "max_budget_credits": {"type": "number", "exclusiveMinimum": 0},
            "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 900, "default": 300},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=1024, vram_mb=0, disk_mb=2048, network_required=True
    )
    idempotency_key_fields = ["prompt", "model", "duration", "aspect_ratio", "project_url"]
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

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("timeout_seconds", 300))

    def is_operation_available(self, operation: str) -> bool:
        return operation == "text_to_video" and self.get_status() == ToolStatus.AVAILABLE

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "status": self.get_status().value,
            "mcp_root": str(google_flow_root()),
            "requires_explicit_credit_approval": True,
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
        project_url = resolve_project_url(inputs)
        if not project_url:
            return ToolResult(
                success=False,
                error="Google Flow video generation requires project_url or GOOGLE_FLOW_PROJECT_URL",
                data={"error_code": "project_url_required", "fallback_used": False},
            )
        output_path = Path(str(inputs["output_path"]))
        if output_path.suffix.lower() != ".mp4":
            return ToolResult(success=False, error="Google Flow video output_path must end in .mp4")
        if output_path.exists():
            return ToolResult(
                success=False,
                error="Google Flow video output_path already exists; refusing to overwrite it",
                data={"error_code": "output_exists", "fallback_used": False},
            )

        model = str(inputs.get("model", "Gemini Omni Flash"))
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
                max_budget_credits=float(inputs["max_budget_credits"]),
                timeout_seconds=int(inputs.get("timeout_seconds", 300)),
                music=False,
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
            "project_url": project_url,
            "job_id": waited.get("jobId"),
            "output": str(output_path),
            "output_path": str(output_path),
            "sha256": downloaded.get("sha256"),
            "billing_mode": "subscription_credits",
            "max_budget_credits": float(inputs["max_budget_credits"]),
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
