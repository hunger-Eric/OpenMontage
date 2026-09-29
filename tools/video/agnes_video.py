"""Agnes Video v2.0 generation through the first-party asynchronous API."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import mimetypes
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
DEFAULT_MODEL = "agnes-video-v2.0"
TERMINAL_FAILURES = {"failed", "cancelled", "canceled"}
LITTERBOX_UPLOAD_URL = "https://litterbox.catbox.moe/resources/internals/api.php"
ASPECT_RATIO_DIMENSIONS = {
    "16:9": (1152, 648),
    "9:16": (648, 1152),
    "1:1": (768, 768),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
}


def _api_key() -> str | None:
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None


def _base_url() -> str:
    value = os.environ.get("AGNES_API_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    return value if value.endswith("/v1") else f"{value}/v1"


def _video_lookup_url() -> str:
    return f"{_base_url().removesuffix('/v1')}/agnesapi"


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


def _frame_count(duration_seconds: float, frame_rate: float) -> int:
    requested = max(1, round(duration_seconds * frame_rate))
    return max(9, round((requested - 1) / 8) * 8 + 1)


def _task_receipt_path(output_path: Path) -> Path:
    return output_path.with_suffix(".agnes-task.json")


def _write_task_receipt(output_path: Path, payload: dict[str, Any]) -> Path:
    receipt_path = _task_receipt_path(output_path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "model": DEFAULT_MODEL,
        "task_id": payload.get("task_id") or payload.get("id"),
        "video_id": payload.get("video_id"),
        "status": payload.get("status"),
        "progress": payload.get("progress"),
        "seconds": payload.get("seconds"),
        "size": payload.get("size"),
    }
    temporary_path = receipt_path.with_suffix(f"{receipt_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(receipt_path)
    return receipt_path


def upload_image_litterbox(image_path: str) -> str:
    """Upload a local Agnes reference image to an ephemeral public URL."""
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as handle:
        response = requests.post(
            LITTERBOX_UPLOAD_URL,
            data={"reqtype": "fileupload", "time": "1h"},
            files={"fileToUpload": (path.name, handle, content_type)},
            timeout=120,
        )
    response.raise_for_status()
    image_url = response.text.strip()
    if not image_url.startswith("https://"):
        raise RuntimeError("Litterbox upload did not return an HTTPS image URL")
    return image_url


class AgnesVideo(BaseTool):
    name = "agnes_video"
    version = "0.4.0"
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
    agent_skills = ["ai-video-gen"]
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
        "Token Plan Agnes Video v2.0 text and image-conditioned generation",
        "asynchronous first-party tasks with video_id polling and task_id compatibility",
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
            "reference_image_path": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                "default": "16:9",
                "description": "v2.0 request canvas preset; image-driven modes inherit the reference image dimensions.",
            },
            "width": {"type": "integer", "minimum": 1},
            "height": {"type": "integer", "minimum": 1},
            "duration": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": 441,
                "default": 5,
                "description": "Adapter convenience input. It is converted to the nearest valid 8n + 1 frame count; duration * frame_rate must not exceed 441.",
            },
            "num_frames": {
                "type": "integer",
                "minimum": 9,
                "maximum": 441,
                "description": "Exact v2.0 frame count; must satisfy 8n + 1 and be <= 441. Overrides duration.",
            },
            "frame_rate": {
                "type": "number",
                "minimum": 1,
                "maximum": 60,
                "default": 24,
                "description": "v2.0 playback rate from 1 to 60 FPS; output seconds = num_frames / frame_rate.",
            },
            "num_inference_steps": {"type": "integer", "minimum": 1},
            "seed": {"type": "integer"},
            "negative_prompt": {"type": "string"},
            "poll_interval_seconds": {"type": "number", "minimum": 1, "maximum": 60, "default": 5},
            "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 3600, "default": 900},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=2048, network_required=True
    )
    side_effects = [
        "uploads local reference images to ephemeral public Litterbox storage for 1 hour",
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
        local_image = inputs.get("reference_image_path")
        if (
            operation in {"image_to_video", "reference_to_video"}
            and local_image
            and not image_urls
        ):
            try:
                image_urls.insert(0, upload_image_litterbox(str(local_image)))
            except Exception as exc:
                return ToolResult(
                    success=False,
                    error=f"Failed to upload Agnes reference image: {exc}",
                )
        if operation in {"image_to_video", "reference_to_video"} and not image_urls:
            return ToolResult(
                success=False,
                error=(
                    f"{operation} requires reference_image_path, image_url, "
                    "or reference_image_urls"
                ),
            )

        frame_rate = float(inputs.get("frame_rate", 24))
        explicit_frames = inputs.get("num_frames")
        duration = float(inputs.get("duration", 5))
        if not 1 <= frame_rate <= 60:
            return ToolResult(
                success=False,
                error="Agnes Video v2.0 frame_rate must be between 1 and 60",
            )
        if explicit_frames is None and (duration <= 0 or duration * frame_rate > 441):
            return ToolResult(
                success=False,
                error="Agnes Video v2.0 duration * frame_rate must be greater than 0 and no more than 441",
            )
        num_frames = int(explicit_frames if explicit_frames is not None else _frame_count(duration, frame_rate))
        if num_frames < 9 or num_frames > 441 or (num_frames - 1) % 8 != 0:
            return ToolResult(success=False, error="Agnes num_frames must be between 9 and 441 and satisfy 8n + 1")

        ratio = str(inputs.get("aspect_ratio", "16:9"))
        width, height = ASPECT_RATIO_DIMENSIONS[ratio]
        width = int(inputs.get("width", width))
        height = int(inputs.get("height", height))
        payload: dict[str, Any] = {
            "model": DEFAULT_MODEL,
            "prompt": str(inputs["prompt"]),
            "num_frames": num_frames,
            "frame_rate": frame_rate,
        }
        if operation == "text_to_video":
            payload["width"] = width
            payload["height"] = height
        for name in ("num_inference_steps", "seed", "negative_prompt"):
            if inputs.get(name) is not None:
                payload[name] = inputs[name]
        if len(image_urls) == 1:
            payload["image"] = image_urls[0]
            payload["mode"] = "ti2vid"
        elif image_urls:
            payload["extra_body"] = {"image": image_urls}

        headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
        task_id: str | None = None
        video_id: str | None = None
        task_receipt_path: Path | None = None
        try:
            created = requests.post(f"{_base_url()}/videos", headers=headers, json=payload, timeout=120)
            created.raise_for_status()
            created_data = created.json()
            task_id = str(created_data.get("task_id") or created_data.get("id") or "").strip() or None
            video_id = str(created_data.get("video_id") or "").strip() or None
            if not task_id and not video_id:
                raise RuntimeError("Agnes create response did not include a task_id or video_id")
            receipt_data = {
                **created_data,
                "task_id": task_id,
                "video_id": video_id,
            }
            task_receipt_path = _write_task_receipt(output_path, receipt_data)

            deadline = time.time() + int(inputs.get("timeout_seconds", 900))
            interval = float(inputs.get("poll_interval_seconds", 5))
            result_data: dict[str, Any] = created_data
            while time.time() < deadline:
                if video_id:
                    response = requests.get(
                        _video_lookup_url(),
                        headers=headers,
                        params={"video_id": video_id, "model_name": DEFAULT_MODEL},
                        timeout=120,
                    )
                else:
                    response = requests.get(f"{_base_url()}/videos/{task_id}", headers=headers, timeout=120)
                response.raise_for_status()
                result_data = response.json()
                receipt_data.update(
                    {key: value for key, value in result_data.items() if value is not None}
                )
                receipt_data.update({"task_id": task_id, "video_id": video_id})
                _write_task_receipt(
                    output_path,
                    receipt_data,
                )
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
                data={
                    "provider": "agnes",
                    "model": DEFAULT_MODEL,
                    "task_id": task_id,
                    "video_id": video_id,
                    "task_receipt_path": str(task_receipt_path) if task_receipt_path else None,
                    "fallback_used": False,
                },
            )
        except Exception as exc:
            if output_path.exists():
                output_path.unlink()
            return ToolResult(
                success=False,
                error=str(exc),
                data={
                    "provider": "agnes",
                    "model": DEFAULT_MODEL,
                    "task_id": task_id,
                    "video_id": video_id,
                    "task_receipt_path": str(task_receipt_path) if task_receipt_path else None,
                    "fallback_used": False,
                },
            )

        sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return ToolResult(
            success=True,
            data={
                "provider": "agnes",
                "model": DEFAULT_MODEL,
                "task_id": task_id,
                "video_id": video_id,
                "task_receipt_path": str(task_receipt_path) if task_receipt_path else None,
                "status": "completed",
                "output": str(output_path),
                "output_path": str(output_path),
                "sha256": sha256,
                "width_requested": width,
                "height_requested": height,
                "num_frames_requested": num_frames,
                "frame_rate_requested": frame_rate,
                "effective_duration_seconds": num_frames / frame_rate,
                "fallback_used": False,
                **probe,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(time.time() - started, 2),
            seed=inputs.get("seed"),
            model=DEFAULT_MODEL,
        )
