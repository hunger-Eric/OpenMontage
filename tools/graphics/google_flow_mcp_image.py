"""Google Flow image generation through the local google-flow-mcp-v4 bridge."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools._google_flow_mcp.client import google_flow_root
from tools._google_flow_mcp.provider import (
    probe_image,
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


class GoogleFlowMCPImage(BaseTool):
    name = "google_flow_mcp_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "google_flow"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies = ["cmd:node", "python:PIL"]
    install_instructions = (
        "Build the local google-flow-mcp-v4 project and set GOOGLE_FLOW_MCP_ROOT if it is not "
        "a sibling of OpenMontage. Pass project_url or set GOOGLE_FLOW_PROJECT_URL."
    )
    fallback_tools: list[str] = []
    agent_skills = ["gemini-omni"]
    supports = {
        "text_to_image": True,
        "references_to_image": True,
        "browser_subscription": True,
        "explicit_credit_approval": True,
    }
    best_for = [
        "Google Flow Nano Banana 2 images through an existing browser subscription",
        "project-local ingredient images with explicit per-call credit approval",
    ]
    not_good_for = ["unattended generation without a confirmed credit budget"]
    input_schema = {
        "type": "object",
        "required": ["prompt", "output_path", "confirm_paid_generation", "max_budget_credits"],
        "properties": {
            "prompt": {"type": "string"},
            "output_path": {"type": "string", "description": "Absolute image output path"},
            "project_url": {"type": "string", "description": "Existing Google Flow project URL"},
            "model": {"type": "string", "default": "Nano Banana 2"},
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "3:4", "4:3", "9:16", "16:9"],
                "default": "9:16",
            },
            "reference_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Absolute paths uploaded as Flow ingredients before generation",
            },
            "confirm_paid_generation": {"type": "boolean", "default": False},
            "max_budget_credits": {"type": "number", "exclusiveMinimum": 0},
            "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 900, "default": 300},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=1024, vram_mb=0, disk_mb=512, network_required=True
    )
    idempotency_key_fields = ["prompt", "model", "aspect_ratio", "project_url", "reference_paths"]
    side_effects = [
        "uses Google subscription credits after explicit confirmation",
        "drives the authenticated Google Flow browser profile through local MCP",
        "writes a validated image file to output_path",
    ]
    user_visible_verification = ["Inspect the generated ingredient image for identity and style"]

    def get_status(self) -> ToolStatus:
        return provider_status(require_ffprobe=False)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("timeout_seconds", 300))

    def is_operation_available(self, operation: str) -> bool:
        return operation in {"text_to_image", "references_to_image"} and self.get_status() == ToolStatus.AVAILABLE

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
                error="Google Flow image generation requires confirm_paid_generation=true",
                data={"error_code": "approval_required", "fallback_used": False},
            )
        project_url = resolve_project_url(inputs)
        if not project_url:
            return ToolResult(
                success=False,
                error="Google Flow image generation requires project_url or GOOGLE_FLOW_PROJECT_URL",
                data={"error_code": "project_url_required", "fallback_used": False},
            )
        output_path = Path(str(inputs["output_path"]))
        if output_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            return ToolResult(success=False, error="Google Flow image output_path must use png, jpg, jpeg, or webp")
        if output_path.exists():
            return ToolResult(
                success=False,
                error="Google Flow image output_path already exists; refusing to overwrite it",
                data={"error_code": "output_exists", "fallback_used": False},
            )
        reference_paths = [Path(str(value)) for value in inputs.get("reference_paths", [])]
        missing_references = [str(path) for path in reference_paths if not path.is_file()]
        if missing_references:
            return ToolResult(
                success=False,
                error=f"Google Flow image reference asset does not exist: {missing_references[0]}",
                data={"error_code": "reference_missing", "fallback_used": False},
            )

        model = str(inputs.get("model", "Nano Banana 2"))
        full_prompt = (
            f"请立即使用 {model} 生成单张图片：{inputs['prompt']}\n"
            f"画幅 {inputs.get('aspect_ratio', '9:16')}，不要输出文字说明，只生成图片。"
        )
        try:
            receipt = run_generation(
                url=project_url,
                prompt=full_prompt,
                output_path=output_path,
                expected_media_type="image",
                max_budget_credits=float(inputs["max_budget_credits"]),
                timeout_seconds=int(inputs.get("timeout_seconds", 300)),
                music=False,
                reference_paths=reference_paths,
            )
            probe = probe_image(output_path)
        except Exception as exc:
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
            return ToolResult(
                success=False,
                error=f"Google Flow MCP image generation failed: {exc}",
                data={"provider": "google_flow", "transport": "mcp_stdio_browser", "fallback_used": False},
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
