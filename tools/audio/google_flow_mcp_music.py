"""Google Flow Music generation through the local google-flow-mcp-v4 bridge."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from lib.config_model import OpenMontageConfig
from tools._google_flow_mcp.client import google_flow_root
from tools._google_flow_mcp.provider import probe_media, provider_status, run_generation
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


class GoogleFlowMCPMusic(BaseTool):
    name = "google_flow_mcp_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "google_flow"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies = ["cmd:node", "cmd:ffprobe"]
    install_instructions = (
        "Build the local google-flow-mcp-v4 project and set GOOGLE_FLOW_MCP_ROOT if it is not "
        "a sibling of OpenMontage. The persisted Google browser profile must be authenticated."
    )
    fallback_tools: list[str] = []
    agent_skills = ["music", "lyria"]
    supports = {
        "instrumental": True,
        "vocals": True,
        "style_control": True,
        "long_form": True,
        "browser_subscription": True,
        "explicit_credit_approval": False,
        "optional_credit_cap": True,
    }
    best_for = [
        "original cinematic music through the authenticated Flow Music browser workspace",
        "precisely directed instrumentation and emotional arcs",
    ]
    not_good_for = ["generation outside the user-authorized production plan"]
    input_schema = {
        "type": "object",
        "required": ["prompt", "output_path", "confirm_paid_generation"],
        "properties": {
            "prompt": {"type": "string", "description": "Original music direction without artist imitation"},
            "output_path": {"type": "string", "description": "Absolute .m4a output path"},
            "duration_seconds": {"type": "number", "minimum": 5, "maximum": 184, "default": 60},
            "instrumental": {"type": "boolean", "default": True},
            "confirm_paid_generation": {"type": "boolean", "default": False,
                "description": "Set true for music included in the user-authorized production plan; this is not a separate fee approval."},
            "max_budget_credits": {"type": ["number", "null"], "exclusiveMinimum": 0,
                "description": "Optional user-specified cap; omitted/null defaults to no credit ceiling unless configured by the user."},
            "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 900, "default": 180},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=1024, vram_mb=0, disk_mb=512, network_required=True
    )
    idempotency_key_fields = ["prompt", "duration_seconds", "instrumental"]
    side_effects = [
        "uses Google subscription credits after explicit confirmation",
        "drives the authenticated Flow Music browser profile through local MCP",
        "writes a validated M4A audio file to output_path",
    ]
    user_visible_verification = ["Listen to the full track for structure, dynamics, and edit suitability"]

    def get_status(self) -> ToolStatus:
        return provider_status()

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("timeout_seconds", 180))

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        config = OpenMontageConfig.load().google_flow
        return {
            "tool": self.name,
            "status": self.get_status().value,
            "mcp_root": str(google_flow_root()),
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
                error="Google Flow music generation requires confirm_paid_generation=true",
                data={"error_code": "approval_required", "fallback_used": False},
            )
        output_path = Path(str(inputs["output_path"]))
        if output_path.suffix.lower() != ".m4a":
            return ToolResult(success=False, error="Google Flow music output_path must end in .m4a")
        if output_path.exists():
            return ToolResult(
                success=False,
                error="Google Flow music output_path already exists; refusing to overwrite it",
                data={"error_code": "output_exists", "fallback_used": False},
            )

        budget = inputs.get("max_budget_credits", OpenMontageConfig.load().google_flow.max_budget_credits)
        try:
            max_budget_credits = float(budget) if budget is not None else None
        except (TypeError, ValueError):
            return ToolResult(success=False, error="Flow credit budget must be finite and positive")
        if max_budget_credits is not None and not 0 < max_budget_credits < float("inf"):
            return ToolResult(success=False, error="Flow credit budget must be finite and positive")

        duration = float(inputs.get("duration_seconds", 60))
        instrumental = bool(inputs.get("instrumental", True))
        full_prompt = (
            f"请直接生成一首原创{'纯音乐' if instrumental else '音乐'}：{inputs['prompt']}\n"
            f"目标时长约 {duration:g} 秒。不要模仿或点名任何具体在世艺术家。"
        )
        try:
            receipt = run_generation(
                url="https://www.flowmusic.app/session?t=true",
                prompt=full_prompt,
                output_path=output_path,
                expected_media_type="audio",
                max_budget_credits=max_budget_credits,
                timeout_seconds=int(inputs.get("timeout_seconds", 180)),
                music=True,
            )
            probe = probe_media(output_path, "audio")
        except Exception as exc:
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
            return ToolResult(
                success=False,
                error=f"Google Flow MCP music generation failed: {exc}",
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
            "model": "Flow Music",
            "job_id": waited.get("jobId"),
            "output": str(output_path),
            "output_path": str(output_path),
            "sha256": downloaded.get("sha256"),
            "billing_mode": "subscription_credits",
            "max_budget_credits": max_budget_credits,
            "fallback_used": False,
            **probe,
        }
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
            model="Flow Music",
        )
