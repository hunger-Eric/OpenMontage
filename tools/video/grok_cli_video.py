"""Grok Imagine video generation through the user's OAuth-backed grok-cli."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolCommandError,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class GrokCliVideo(BaseTool):
    """Expose ``grok-cli video`` as an OpenMontage video provider."""

    name = "grok_cli_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "grok"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["cmd:grok-cli"]
    install_instructions = (
        "Install grok-cli and authenticate it with an OAuth auth file. "
        "Set GROK_CLI_AUTH_FILE only when the file is not at ~/.grok-cli/auth.json."
    )
    agent_skills = ["grok-media", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "reference_image": True,
        "multiple_reference_images": True,
        "native_audio": True,
        "lip_sync": True,
        "cinematic_quality": True,
        "oauth_subscription": True,
    }
    best_for = [
        "Grok Imagine generation using an existing Grok subscription",
        "reference-conditioned short video through a local OAuth CLI",
        "cinematic clips with native synchronized audio",
    ]
    not_good_for = ["offline generation", "USD cost estimation for subscription quota"]
    fallback_tools: list[str] = []
    quality_score = 0.9

    input_schema = {
        "type": "object",
        "required": ["prompt", "output_path"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model": {"type": "string", "default": "grok-imagine-video"},
            "duration": {"type": "integer", "minimum": 1, "maximum": 15, "default": 5},
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"],
                "default": "16:9",
            },
            "resolution": {"type": "string", "enum": ["480p", "720p"], "default": "720p"},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "output_path": {"type": "string"},
            "timeout_seconds": {"type": "integer", "minimum": 30, "default": 900},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
        disk_mb=500,
        network_required=True,
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "prompt",
        "operation",
        "model",
        "duration",
        "aspect_ratio",
        "resolution",
    ]
    side_effects = [
        "consumes the user's Grok subscription quota",
        "writes a downloaded video file to output_path",
    ]
    user_visible_verification = ["Watch generated clip for motion quality and prompt fidelity"]

    @staticmethod
    def _auth_file_path() -> Path:
        configured = os.environ.get("GROK_CLI_AUTH_FILE")
        if configured:
            return Path(configured).expanduser().resolve()
        return (Path.home() / ".grok-cli" / "auth.json").resolve()

    def get_status(self) -> ToolStatus:
        if shutil.which("grok-cli") is None:
            return ToolStatus.UNAVAILABLE
        if not self._auth_file_path().is_file():
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """The CLI exposes subscription quota, not a trustworthy USD unit price."""
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(int(inputs.get("timeout_seconds", 900)))

    def _build_command(self, inputs: dict[str, Any]) -> list[str]:
        operation = str(inputs.get("operation", "text_to_video"))
        timeout_seconds = int(inputs.get("timeout_seconds", 900))
        command = [
            "grok-cli",
            "video",
            "--json",
            "--auth-file",
            str(self._auth_file_path()),
            "--prompt",
            str(inputs["prompt"]),
            "--duration",
            str(int(inputs.get("duration", 5))),
            "--aspect-ratio",
            str(inputs.get("aspect_ratio", "16:9")),
            "--resolution",
            str(inputs.get("resolution", "720p")),
            "--model",
            str(inputs.get("model", "grok-imagine-video")),
            "--timeout",
            str(timeout_seconds),
        ]

        if operation == "image_to_video":
            if inputs.get("image_path"):
                command.extend(["--image", str(inputs["image_path"])])
            elif inputs.get("image_url"):
                command.extend(["--image-url", str(inputs["image_url"])])
            else:
                raise ValueError("image_to_video requires image_path or image_url")
        elif operation == "reference_to_video":
            paths = list(inputs.get("reference_image_paths") or [])
            urls = list(inputs.get("reference_image_urls") or [])
            if not paths and not urls:
                raise ValueError(
                    "reference_to_video requires reference_image_paths or reference_image_urls"
                )
            for path in paths:
                command.extend(["--reference-image", str(path)])
            for url in urls:
                command.extend(["--reference-image-url", str(url)])
        elif operation != "text_to_video":
            raise ValueError(f"Unsupported Grok CLI video operation: {operation}")

        return command

    @staticmethod
    def _parse_envelope(raw: str | None) -> dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            raise ValueError("grok-cli returned no JSON output")
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("grok-cli returned malformed JSON output") from None
            value = json.loads(text[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("grok-cli returned a non-object JSON envelope")
        return value

    def _run_json(self, command: list[str], *, timeout: int) -> dict[str, Any]:
        try:
            completed = self.run_command(command, timeout=timeout)
            return self._parse_envelope(completed.stdout)
        except ToolCommandError as exc:
            raw = exc.output or exc.stderr or exc.detail
            try:
                return self._parse_envelope(raw)
            except (ValueError, json.JSONDecodeError):
                raise RuntimeError(str(exc)) from exc

    @staticmethod
    def _failure_result(envelope: dict[str, Any]) -> ToolResult:
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = str(error.get("code") or "grok_cli_failed")
        message = str(error.get("message") or "grok-cli video generation failed")
        recovery_action = str(error.get("recovery_action") or "none")
        return ToolResult(
            success=False,
            error=f"{code}: {message}",
            data={
                "provider": "grok",
                "transport": "grok-cli",
                "error_code": code,
                "recovery_action": recovery_action,
                "fallback_used": False,
            },
        )

    def _recover_auth(self, recovery_action: str, *, timeout: int) -> bool:
        auth_file = str(self._auth_file_path())
        if recovery_action == "refresh_then_retry":
            command = ["grok-cli", "refresh", "--json", "--auth-file", auth_file]
        else:
            return False
        envelope = self._run_json(command, timeout=min(max(timeout, 30), 300))
        return bool(envelope.get("ok"))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from tools.video._shared import probe_output

        started = time.time()
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="grok-cli or its explicit OAuth auth file is unavailable. "
                + self.install_instructions,
                data={"provider": "grok", "transport": "grok-cli", "fallback_used": False},
            )

        try:
            command = self._build_command(inputs)
        except (KeyError, TypeError, ValueError) as exc:
            return ToolResult(success=False, error=str(exc), data={"fallback_used": False})

        timeout_seconds = int(inputs.get("timeout_seconds", 900))
        process_timeout = timeout_seconds + 30
        auth_recovery: str | None = None

        try:
            envelope = self._run_json(command, timeout=process_timeout)
            if not envelope.get("ok"):
                error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
                recovery_action = str(error.get("recovery_action") or "none")
                if recovery_action == "refresh_then_retry":
                    if not self._recover_auth(recovery_action, timeout=timeout_seconds):
                        return self._failure_result(envelope)
                    auth_recovery = recovery_action
                    envelope = self._run_json(command, timeout=process_timeout)
                if not envelope.get("ok"):
                    return self._failure_result(envelope)

            data = envelope.get("data")
            if not isinstance(data, dict):
                return ToolResult(success=False, error="grok-cli success envelope missing data")
            video_url = data.get("video")
            if not video_url:
                return ToolResult(success=False, error="grok-cli video output missing data.video")

            import requests

            download = requests.get(str(video_url), timeout=300)
            download.raise_for_status()
            output_path = Path(str(inputs["output_path"]))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download.content)
            probed = probe_output(output_path)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Grok CLI video generation failed: {exc}",
                data={"provider": "grok", "transport": "grok-cli", "fallback_used": False},
            )

        result_data = {
            "provider": "grok",
            "transport": "grok-cli",
            "model": data.get("model") or inputs.get("model", "grok-imagine-video"),
            "prompt": inputs["prompt"],
            "operation": inputs.get("operation", "text_to_video"),
            "request_id": data.get("request_id"),
            "modality": data.get("modality"),
            "source_video_url": str(video_url),
            "output": str(output_path),
            "output_path": str(output_path),
            "format": "mp4",
            "billing_mode": "subscription_quota",
            "cost_tracking": "subscription_quota_unpriced",
            "fallback_used": False,
            **probed,
        }
        if auth_recovery:
            result_data["auth_recovery"] = auth_recovery

        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
            model=str(result_data["model"]),
        )
