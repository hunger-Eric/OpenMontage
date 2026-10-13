"""Google Flow video generation through the local google-flow-mcp-v4 bridge."""

from __future__ import annotations

import time
import json
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
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Compatibility alias for reference_paths from VideoSelector image inputs",
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

    @staticmethod
    def _normalize_reference_values(field: str, value: object) -> list[tuple[str, Path]]:
        """Validate one supported reference field without silently dropping it."""
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"Google Flow video {field} must be an array of paths")
        normalized: list[tuple[str, Path]] = []
        for raw_path in value:
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError(
                    f"Google Flow video {field} contains an invalid reference path"
                )
            path = Path(raw_path)
            normalized.append((str(path.resolve()), path))
        return normalized

    @classmethod
    def _reference_paths_from_inputs(cls, inputs: dict[str, Any]) -> list[Path]:
        """Accept the selector's image alias while rejecting conflicting inputs."""
        has_canonical = "reference_paths" in inputs
        has_image_alias = "reference_image_paths" in inputs
        canonical = cls._normalize_reference_values(
            "reference_paths", inputs["reference_paths"]
        ) if has_canonical else []
        image_alias = cls._normalize_reference_values(
            "reference_image_paths", inputs["reference_image_paths"]
        ) if has_image_alias else []
        if has_canonical and has_image_alias:
            if [item[0] for item in canonical] != [item[0] for item in image_alias]:
                raise ValueError(
                    "Google Flow video reference_paths conflicts with reference_image_paths"
                )

        selected = canonical if has_canonical else image_alias
        unique_paths: list[Path] = []
        seen: set[str] = set()
        for identity, path in selected:
            if identity not in seen:
                seen.add(identity)
                unique_paths.append(path)
        return unique_paths

    def prepare_video_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Add the provider-native reference field without altering frozen inputs."""
        self._reference_paths_from_inputs(inputs)
        prepared = dict(inputs)
        if "reference_image_paths" in inputs and "reference_paths" not in inputs:
            prepared["reference_paths"] = list(inputs["reference_image_paths"])
        return prepared

    def idempotency_key(self, inputs: dict[str, Any]) -> str:
        """Hash the effective reference set for canonical and alias callers alike."""
        if "reference_paths" not in inputs and "reference_image_paths" not in inputs:
            return super().idempotency_key(inputs)
        canonical_inputs = dict(inputs)
        canonical_inputs["reference_paths"] = [
            str(path.resolve()) for path in self._reference_paths_from_inputs(inputs)
        ]
        return super().idempotency_key(canonical_inputs)

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

        try:
            reference_paths = self._reference_paths_from_inputs(inputs)
        except ValueError as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                data={"error_code": "invalid_reference", "fallback_used": False},
            )
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
            attempt_path = output_path.with_suffix(output_path.suffix + ".flow-attempt.json")
            generation_status = None
            attempt_record = {}
            try:
                attempt_record = json.loads(attempt_path.read_text(encoding="utf-8"))
                generation_status = attempt_record.get("generation_status")
            except (OSError, ValueError):
                pass
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
                    "generation_status": generation_status,
                    "generation_id": attempt_record.get("generation_id"),
                    "job_id": attempt_record.get("job_id"),
                    "attempt_record": str(attempt_path) if attempt_path.exists() else None,
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
            "generation_id": waited.get("generationId"),
            "generation_status": {key: waited[key] for key in ("state", "source", "operations", "checkedAt") if key in waited},
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
