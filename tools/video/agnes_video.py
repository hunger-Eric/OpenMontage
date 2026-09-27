"""Agnes Video 2.5 Flash generation through the first-party async API."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import time
from pathlib import Path
from typing import Any

import requests

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
from tools.video._shared import probe_output


DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"
DEFAULT_MODEL = "agnes-video-2.5-flash"
TERMINAL_FAILURES = {"failed", "cancelled", "canceled"}


def _api_key() -> str | None:
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None


def _base_url() -> str:
    value = os.environ.get("AGNES_API_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    return value if value.endswith("/v1") else f"{value}/v1"


def _api_root() -> str:
    return _base_url().removesuffix("/v1")


def _video_url(payload: dict[str, Any]) -> str | None:
    for key in ("video_url", "url", "remixed_from_video_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith(("https://", "http://")):
            return value
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                value = _video_url(item)
                if value:
                    return value
    return None


def _seconds(inputs: dict[str, Any]) -> int:
    if inputs.get("seconds") is not None:
        value = float(inputs["seconds"])
    elif inputs.get("duration") is not None:
        value = float(inputs["duration"])
    elif inputs.get("num_frames") is not None:
        value = (int(inputs["num_frames"]) - 1) / float(inputs.get("frame_rate", 24))
    else:
        value = 5
    seconds = max(4, round(value))
    if seconds > 12:
        raise ValueError("Agnes Video 2.5 Flash seconds must be between 4 and 12")
    return seconds


class AgnesVideo(BaseTool):
    name = "agnes_video"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "agnes"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["env:AGNES_API_KEY", "cmd:ffprobe"]
    install_instructions = (
        "Set AGNES_API_KEY and optionally AGNES_API_BASE_URL. "
        "The default endpoint is https://apihub.agnes-ai.com/v1."
    )
    agent_skills = ["agnes-ai-generation", "ai-video-gen"]
    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "reference_image": True,
        "seed": True,
        "async_tasks": True,
    }
    best_for = [
        "free promotional Agnes Video 2.5 Flash text and image-reference generation",
        "asynchronous first-party tasks with video_id polling",
    ]
    not_good_for = ["offline generation"]
    fallback_tools: list[str] = []

    input_schema = {
        "type": "object",
        "required": ["prompt", "output_path"],
        "properties": {
            "prompt": {"type": "string"},
            "output_path": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model": {"type": "string", "enum": [DEFAULT_MODEL], "default": DEFAULT_MODEL},
            "image_url": {"type": "string"},
            "reference_image_url": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"], "default": "16:9"},
            "seconds": {"type": ["string", "number"], "description": "Duration from 4 to 12 seconds"},
            "duration": {"type": "number", "minimum": 4, "maximum": 12},
            "size": {"type": "string", "enum": ["720P"], "default": "720P"},
            "num_frames": {"type": "integer", "minimum": 9, "maximum": 441},
            "frame_rate": {"type": "number", "minimum": 1, "maximum": 60, "default": 24},
            "seed": {"type": "integer"},
            "poll_interval_seconds": {"type": "number", "minimum": 1, "maximum": 60, "default": 2},
            "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 3600, "default": 900},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=2048, network_required=True
    )
    side_effects = [
        "creates one Agnes video task",
        "may consume Agnes account credits",
        "downloads a completed MP4 to output_path",
    ]

    def get_status(self) -> ToolStatus:
        if not _api_key() or importlib.util.find_spec("requests") is None or not shutil.which("ffprobe"):
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def is_operation_available(self, operation: str) -> bool:
        return operation in {"text_to_video", "image_to_video", "reference_to_video"} and self.get_status() == ToolStatus.AVAILABLE

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("timeout_seconds", 900))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error=self.install_instructions, data={"fallback_used": False})

        output_path = Path(str(inputs.get("output_path", "")))
        if output_path.suffix.lower() != ".mp4":
            return ToolResult(success=False, error="Agnes video output_path must end in .mp4")
        if output_path.exists():
            return ToolResult(success=False, error="Agnes video output_path already exists; refusing to overwrite it")

        operation = str(inputs.get("operation", "text_to_video"))
        image_urls = list(inputs.get("reference_image_urls") or [])
        single_image = inputs.get("image_url") or inputs.get("reference_image_url")
        if single_image:
            image_urls.insert(0, str(single_image))
        if operation in {"image_to_video", "reference_to_video"} and not image_urls:
            return ToolResult(success=False, error=f"{operation} requires an image_url or reference_image_urls")

        try:
            seconds = _seconds(inputs)
        except (TypeError, ValueError) as exc:
            return ToolResult(success=False, error=str(exc), data={"fallback_used": False})
        ratio = str(inputs.get("aspect_ratio", "16:9"))
        payload: dict[str, Any] = {
            "model": DEFAULT_MODEL,
            "prompt": str(inputs["prompt"]),
            "seconds": str(seconds),
            "mode": "reference" if image_urls else "text",
            "size": "720P",
            "aspect_ratio": ratio,
            "n": 1,
        }
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        if image_urls:
            payload["images"] = image_urls

        headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
        task_id: str | None = None
        video_id: str | None = None
        try:
            created = requests.post(f"{_base_url()}/videos", headers=headers, json=payload, timeout=120)
            created.raise_for_status()
            created_data = created.json()
            task_id = str(created_data.get("task_id") or created_data.get("id") or "").strip() or None
            video_id = str(created_data.get("video_id") or "").strip() or None
            if not task_id:
                raise RuntimeError("Agnes create response did not include a task id")
            if not video_id:
                raise RuntimeError("Agnes create response did not include a video id")

            deadline = time.time() + int(inputs.get("timeout_seconds", 900))
            interval = float(inputs.get("poll_interval_seconds", 2))
            result_data: dict[str, Any] = created_data
            while time.time() < deadline:
                response = requests.get(
                    f"{_api_root()}/agnesapi",
                    params={"video_id": video_id, "model_name": DEFAULT_MODEL},
                    headers=headers,
                    timeout=120,
                )
                response.raise_for_status()
                result_data = response.json()
                status = str(result_data.get("status", "")).lower()
                if status == "completed":
                    break
                if status in TERMINAL_FAILURES or result_data.get("error"):
                    raise RuntimeError(f"Agnes video task {task_id} failed: {result_data.get('error') or status}")
                time.sleep(interval)
            else:
                raise TimeoutError(f"Timed out waiting for Agnes video task {task_id}")

            url = _video_url(result_data)
            if not url:
                raise RuntimeError(f"Agnes video task {task_id} completed without a video URL")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            download = requests.get(url, timeout=300)
            download.raise_for_status()
            output_path.write_bytes(download.content)
            probe = probe_output(output_path)
            if not probe.get("duration_seconds") or not probe.get("video_width") or not probe.get("video_height"):
                raise RuntimeError("ffprobe rejected the downloaded Agnes video")
        except requests.HTTPError as exc:
            if output_path.exists():
                output_path.unlink()
            response = exc.response
            status_code = response.status_code if response is not None else "unknown"
            try:
                detail = response.json() if response is not None else None
            except ValueError:
                detail = (response.text[:1000] if response is not None else "")
            return ToolResult(
                success=False,
                error=f"Agnes API HTTP {status_code}: {detail}",
                data={"provider": "agnes", "model": DEFAULT_MODEL, "task_id": task_id, "video_id": video_id, "fallback_used": False},
            )
        except Exception as exc:
            if output_path.exists():
                output_path.unlink()
            return ToolResult(
                success=False,
                error=str(exc),
                data={"provider": "agnes", "model": DEFAULT_MODEL, "task_id": task_id, "video_id": video_id, "fallback_used": False},
            )

        sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return ToolResult(
            success=True,
            data={
                "provider": "agnes",
                "model": DEFAULT_MODEL,
                "task_id": task_id,
                "video_id": video_id,
                "status": "completed",
                "output": str(output_path),
                "output_path": str(output_path),
                "sha256": sha256,
                "seconds_requested": seconds,
                "size_requested": "720P",
                "aspect_ratio_requested": ratio,
                "fallback_used": False,
                **probe,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(time.time() - started, 2),
            seed=inputs.get("seed"),
            model=DEFAULT_MODEL,
        )
