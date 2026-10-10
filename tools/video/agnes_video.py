"""Account model discovery and version-aware Agnes video transport."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import mimetypes
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
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
LEGACY_MODEL = "agnes-video-v2.0"
SUPPORTED_MODELS = (LEGACY_MODEL, "agnes-video-2.5-flash", "agnes-video-2.5")
MIN_NUM_FRAMES = 9
MAX_NUM_FRAMES = 441
FRAME_COUNT_STEP = 8
MIN_FRAME_RATE = 1
MAX_FRAME_RATE = 60
DEFAULT_FRAME_RATE = 24
MAX_DURATION_AT_DEFAULT_FPS = MAX_NUM_FRAMES / DEFAULT_FRAME_RATE
TERMINAL_FAILURES = {"failed", "cancelled", "canceled"}
LITTERBOX_UPLOAD_URL = "https://litterbox.catbox.moe/resources/internals/api.php"
ASPECT_RATIO_DIMENSIONS = {
    "16:9": (1152, 648),
    "9:16": (648, 1152),
    "1:1": (768, 768),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
}
LEGACY_USAGE_CONDITIONS = {
    "model_selection": "agent selects an explicit model from live discovery and plan evidence",
    "supported_models": list(SUPPORTED_MODELS),
    "single_call_output": "one generated clip",
    "num_frames": {
        "minimum": MIN_NUM_FRAMES,
        "maximum": MAX_NUM_FRAMES,
        "rule": "8n + 1",
    },
    "frame_rate_fps": {
        "minimum": MIN_FRAME_RATE,
        "maximum": MAX_FRAME_RATE,
        "default": DEFAULT_FRAME_RATE,
    },
    "duration_seconds": {
        "formula": "num_frames / frame_rate",
        "maximum_at_default_24_fps": MAX_DURATION_AT_DEFAULT_FPS,
        "maximum_at_30_fps": MAX_NUM_FRAMES / 30,
        "maximum_at_60_fps": MAX_NUM_FRAMES / 60,
        "absolute_maximum_at_1_fps": float(MAX_NUM_FRAMES),
    },
    "aspect_ratio_presets": list(ASPECT_RATIO_DIMENSIONS),
    "long_video_policy": (
        "Split productions longer than the per-call duration into planned shots, "
        "generate each shot separately, then compose them; never submit the full "
        "production duration as one Agnes task."
    ),
    "fallback_policy": "fail without switching model or provider",
}
V25_USAGE_CONDITIONS = {
    "duration_seconds": {"minimum": 4, "maximum": 12, "integer": True},
    "aspect_ratio_presets": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
    "single_call_output": "one generated clip",
    "long_video_policy": LEGACY_USAGE_CONDITIONS["long_video_policy"],
    "fallback_policy": "fail without switching model or provider",
}
MODEL_USAGE_CONDITIONS = {
    "model_selection": "agent selects an explicit model from live discovery and plan evidence",
    "supported_models": list(SUPPORTED_MODELS),
    "model_contracts": {
        LEGACY_MODEL: LEGACY_USAGE_CONDITIONS,
        "agnes-video-2.5-flash": {**V25_USAGE_CONDITIONS, "sizes": ["720P"], "max_images": 5, "max_audios": 3, "max_videos": 0},
        "agnes-video-2.5": {**V25_USAGE_CONDITIONS, "sizes": ["720P", "1080P", "1K", "2K"], "max_images": 8, "max_audios": 3, "max_videos": 1},
    },
    "long_video_policy": LEGACY_USAGE_CONDITIONS["long_video_policy"],
}


def _v25_payload(inputs: dict[str, Any], model: str, images: list[str], local_image: str | None):
    """Validate version-specific fields before any upload or generation call."""
    conditions = MODEL_USAGE_CONDITIONS["model_contracts"][model]
    for name in ("width", "height", "num_frames", "frame_rate", "fps", "quality", "num_inference_steps", "negative_prompt", "video_url", "video_path", "video_reference", "input_reference", "reference_url"):
        if name in inputs:
            raise ValueError(f"{model} does not support {name}; use seconds/size/aspect_ratio")
    seconds = float(inputs.get("seconds", inputs.get("duration", 5)))
    if not seconds.is_integer() or not 4 <= seconds <= 12:
        raise ValueError(f"{model} requires an integer duration of 4–12 seconds; split longer productions into shots")
    size = str(inputs.get("size", "720P"))
    ratio = str(inputs.get("aspect_ratio", "16:9"))
    if size not in conditions["sizes"] or ratio not in conditions["aspect_ratio_presets"]:
        raise ValueError(f"{model} requires size in {conditions['sizes']} and aspect_ratio in {conditions['aspect_ratio_presets']}")
    operation = str(inputs.get("operation", "text_to_video"))
    mode = str(inputs.get("mode") or {"text_to_video": "text", "image_to_video": "keyframe", "reference_to_video": "reference"}.get(operation, ""))
    if mode not in ("text", "keyframe", "reference"):
        raise ValueError("Unsupported Agnes generation operation/mode")
    first = inputs.get("first_frame")
    last = inputs.get("last_frame")
    audios = list(inputs.get("audios") or [])
    videos = list(inputs.get("videos") or [])
    if len(images) + bool(local_image and not images) > conditions["max_images"] or len(audios) > conditions["max_audios"] or len(videos) > conditions["max_videos"]:
        raise ValueError(f"Reference inputs exceed {model} limits")
    if mode == "text" and (images or local_image or first or last or audios or videos):
        raise ValueError("text mode cannot contain reference media")
    if mode == "keyframe" and (audios or videos or len(images) > 1 or (first and (images or local_image))):
        raise ValueError("keyframe mode accepts only first/last frames")
    if mode == "keyframe" and not (first or last or images or local_image):
        raise ValueError("keyframe mode requires a first or last frame")
    if mode == "reference" and (first or last or not (images or local_image or audios or videos)):
        raise ValueError("reference mode requires reference media and disallows first/last frames")
    for url in [*images, *audios, *([first] if first else []), *([last] if last else [])]:
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ValueError("Agnes reference inputs require public HTTP(S) URLs")
    for video in videos:
        if not isinstance(video, dict) or not isinstance(video.get("url"), str) or not video["url"].startswith(("https://", "http://")):
            raise ValueError("Video references require a public videos[].url")
    payload = {"model": model, "prompt": str(inputs["prompt"]), "seconds": str(int(seconds)), "size": size, "aspect_ratio": ratio, "mode": mode, "n": 1}
    if inputs.get("n", 1) != 1:
        raise ValueError("Agnes supports n=1 only")
    if inputs.get("seed") is not None:
        payload["seed"] = inputs["seed"]
    if mode == "keyframe":
        if first or images:
            payload["first_frame"] = first or images[0]
        if last:
            payload["last_frame"] = last
    elif mode == "reference":
        for name, value in (("images", images), ("audios", audios), ("videos", videos)):
            if value:
                payload[name] = value
    # Geometry describes the requested canvas; decoded output remains authoritative.
    dimensions = {"21:9": (1470, 630), "16:9": (1280, 720), "4:3": (1112, 834), "1:1": (960, 960), "3:4": (834, 1112), "9:16": (720, 1280)}
    width, height = dimensions[ratio]
    if size == "1K":
        width, height = 1024, 1024
    elif size == "2K":
        width, height = width * 2, height * 2
    elif size == "1080P":
        width, height = {"21:9": (2206, 946), "16:9": (1920, 1080), "4:3": (1664, 1248), "1:1": (1440, 1440), "3:4": (1248, 1664), "9:16": (1080, 1920)}[ratio]
    return payload, width, height, seconds


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


def _attempt_ledger_path(output_path: Path) -> Path:
    return output_path.with_suffix(".agnes-attempts.jsonl")


def _read_task_receipt(output_path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(_task_receipt_path(output_path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _append_attempt_event(
    output_path: Path,
    *,
    attempt_id: str,
    event: str,
    payload: dict[str, Any] | None = None,
) -> Path:
    path = _attempt_ledger_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "attempt_id": attempt_id,
        "event": event,
        **(payload or {}),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return path


def _write_task_receipt(output_path: Path, payload: dict[str, Any]) -> Path:
    receipt_path = _task_receipt_path(output_path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "model": payload.get("model") or LEGACY_MODEL,
        "task_id": payload.get("task_id") or payload.get("id"),
        "video_id": payload.get("video_id"),
        "status": payload.get("status"),
        "progress": payload.get("progress"),
        "seconds": payload.get("seconds"),
        "size": payload.get("size"),
        "attempt_id": payload.get("attempt_id"),
        "request_fingerprint": payload.get("request_fingerprint"),
        "request_fingerprint_version": payload.get("request_fingerprint_version"),
        "aspect_mismatch_policy": payload.get("aspect_mismatch_policy"),
        "last_error": payload.get("last_error"),
        "model_discovery": payload.get("model_discovery"),
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
    version = "0.5.0"
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
        "usage_conditions": MODEL_USAGE_CONDITIONS,
    }
    best_for = [
        "account-aware Agnes video discovery and explicit agent-selected models",
        "asynchronous first-party tasks with video_id polling and task_id compatibility",
        "2.5/Flash text, keyframe and reference clips of 4–12 seconds",
    ]
    not_good_for = [
        "offline generation",
        "unsegmented productions beyond the selected model's per-call limits",
    ]
    fallback_tools: list[str] = []

    input_schema = {
        "type": "object",
        "description": (
            "Discover the current key's models, then pass the agent-selected exact model. "
            "2.5/Flash uses integer seconds 4–12, size and aspect_ratio. Legacy v2.0 "
            "retains its frame contract for explicit selections and receipt recovery. "
            "Longer productions must be split into planned shots and composed. "
            "The adapter never selects a semantic fallback model or provider."
        ),
        "if": {"properties": {"operation": {"const": "discover_models"}}, "required": ["operation"]},
        "then": {},
        "else": {"required": ["prompt", "output_path"]},
        "properties": {
            "prompt": {"type": "string"},
            "output_path": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["discover_models", "text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model": {"type": "string", "description": "Exact agent-selected model from discovery; no default. Required for new generation, recovered from existing receipts otherwise."},
            "allow_paid_model": {"type": "boolean", "default": False, "description": "Set true only with user authorization for a route outside the Token Plan."},
            "mode": {"type": "string", "enum": ["text", "keyframe", "reference"]},
            "seconds": {"type": "string", "enum": [str(n) for n in range(4, 13)]},
            "size": {"type": "string", "enum": ["720P", "1080P", "1K", "2K"]},
            "first_frame": {"type": "string"},
            "last_frame": {"type": "string"},
            "images": {"type": "array", "items": {"type": "string"}},
            "audios": {"type": "array", "items": {"type": "string"}},
            "videos": {"type": "array", "items": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "start_seconds": {"type": "number", "minimum": 0}, "require_audio": {"type": "boolean"}}}},
            "image_url": {"type": "string"},
            "reference_image_url": {"type": "string"},
            "reference_image_path": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "aspect_ratio": {
                "type": "string",
                "enum": ["21:9", "16:9", "9:16", "1:1", "4:3", "3:4"],
                "default": "16:9",
                "description": "Selected model's canvas preset; inspect actual output geometry before composition.",
            },
            "aspect_mismatch_policy": {
                "type": "string",
                "enum": ["center_crop", "pad"],
                "description": (
                    "Required for image/reference-driven generation because Agnes inherits "
                    "reference dimensions. Declares how composition will normalize an output "
                    "whose actual aspect ratio differs from the requested canvas."
                ),
            },
            "width": {"type": "integer", "minimum": 1},
            "height": {"type": "integer", "minimum": 1},
            "duration": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": MAX_NUM_FRAMES / MIN_FRAME_RATE,
                "default": 5,
                "description": (
                    "For 2.5/Flash: integer seconds 4–12. Legacy v2.0: converted to the nearest valid "
                    "8n + 1 frame count, so the effective duration may differ slightly. "
                    "duration * frame_rate must not exceed 441. With the default 24 FPS, "
                    "the maximum is 18.375 seconds. Split longer productions into shots."
                ),
            },
            "num_frames": {
                "type": "integer",
                "minimum": MIN_NUM_FRAMES,
                "maximum": MAX_NUM_FRAMES,
                "description": "Exact v2.0 frame count; must satisfy 8n + 1 and be <= 441. Overrides duration.",
            },
            "frame_rate": {
                "type": "number",
                "minimum": MIN_FRAME_RATE,
                "maximum": MAX_FRAME_RATE,
                "description": (
                    "v2.0 playback rate from 1 to 60 FPS; output seconds = num_frames / "
                    "frame_rate. The 441-frame ceiling means higher FPS reduces the maximum "
                    "single-clip duration."
                ),
            },
            "num_inference_steps": {"type": "integer", "minimum": 1},
            "seed": {"type": "integer"},
            "negative_prompt": {"type": "string"},
            "poll_interval_seconds": {"type": "number", "minimum": 1, "maximum": 60, "default": 5},
            "timeout_seconds": {
                "type": "integer",
                "minimum": 30,
                "maximum": 3600,
                "default": 3600,
                "description": "Maximum provider polling window; silence alone is never a terminal task state.",
            },
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
        return operation in {"discover_models", "text_to_video", "image_to_video", "reference_to_video"} and self.get_status() == ToolStatus.AVAILABLE

    def discover_models(self) -> ToolResult:
        """Read current candidates; listing never claims plan access or inference success."""
        if not _api_key():
            return ToolResult(success=False, error=self.install_instructions)
        try:
            response = requests.get(f"{_base_url()}/models", headers={"Authorization": f"Bearer {_api_key()}"}, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("Invalid Agnes model catalog response")
            models = []
            for item in payload["data"]:
                if not isinstance(item, dict):
                    continue
                model = item.get("id")
                if not isinstance(model, str) or not model.startswith("agnes-video-"):
                    continue
                models.append({"id": model, "access": "listed_unverified", "adapter_supported": model in SUPPORTED_MODELS, "usage_conditions": MODEL_USAGE_CONDITIONS["model_contracts"].get(model), "requires_paid_authorization": model == "agnes-video-2.5"})
            return ToolResult(success=True, data={"provider": self.provider, "models": models, "selected_model": None, "selection_required": True, "checked_at": datetime.now(timezone.utc).isoformat()})
        except (requests.RequestException, ValueError) as exc:
            return ToolResult(success=False, error=f"Agnes model discovery failed: {exc}", data={"fallback_used": False})

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("timeout_seconds", 3600))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        if inputs.get("operation") == "discover_models":
            return self.discover_models()
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error=self.install_instructions, data={"fallback_used": False})

        output_path = Path(str(inputs.get("output_path", "")))
        if output_path.suffix.lower() != ".mp4":
            return ToolResult(success=False, error="Agnes video output_path must end in .mp4")
        if output_path.exists():
            return ToolResult(success=False, error="Agnes video output_path already exists; refusing to overwrite it")

        existing_receipt = _read_task_receipt(output_path)
        if _task_receipt_path(output_path).exists() and existing_receipt is None:
            return ToolResult(success=False, error="Unreadable Agnes receipt; reconcile it before any new submission")
        if existing_receipt and existing_receipt.get("status") == "submitting" and not (existing_receipt.get("task_id") or existing_receipt.get("video_id")):
            return ToolResult(success=False, error="Previous Agnes submission outcome is unknown; reconcile it before any new submission", data={"task_receipt_path": str(_task_receipt_path(output_path)), "fallback_used": False})
        aliases = [str(inputs[field]).strip() for field in ("model", "model_name", "model_variant") if field in inputs]
        if any(not alias for alias in aliases) or len(set(aliases)) > 1:
            return ToolResult(success=False, error="Conflicting or empty Agnes model aliases", data={"fallback_used": False})
        model = aliases[0] if aliases else (existing_receipt.get("model") or LEGACY_MODEL if existing_receipt else None)
        if not model:
            discovery = self.discover_models()
            if not discovery.success:
                return discovery
            return ToolResult(success=False, error="Select an eligible model from discovery and pass model explicitly; no permanent default", data={**discovery.data, "fallback_used": False})
        if model not in SUPPORTED_MODELS:
            return ToolResult(success=False, error=f"Unsupported Agnes model contract: {model}; inspect current docs before adding support", data={"model": model, "fallback_used": False})
        if existing_receipt and existing_receipt.get("model") not in (None, model):
            return ToolResult(success=False, error=f"Existing Agnes receipt uses {existing_receipt['model']}; refusing to resume it as {model}", data={"model": model, "fallback_used": False})
        resumable = bool(existing_receipt and (existing_receipt.get("task_id") or existing_receipt.get("video_id")) and str(existing_receipt.get("status") or "").lower() not in TERMINAL_FAILURES)
        if model == "agnes-video-2.5" and not resumable and inputs.get("allow_paid_model") is not True:
            return ToolResult(success=False, error="Agnes ordinary 2.5 requires explicit paid-route authorization; it is not a Token Plan fallback", data={"model": model, "fallback_used": False})
        legacy = model == LEGACY_MODEL
        usage_conditions = MODEL_USAGE_CONDITIONS["model_contracts"][model]

        operation = str(inputs.get("operation", "text_to_video"))
        if (
            legacy and operation in {"image_to_video", "reference_to_video"}
            and not inputs.get("aspect_mismatch_policy")
        ):
            return ToolResult(
                success=False,
                error=(
                    f"{operation} requires aspect_mismatch_policy='center_crop' or 'pad' "
                    "before submission because Agnes inherits reference-image dimensions."
                ),
                data={"provider": "agnes", "model": model, "fallback_used": False},
            )
        image_urls = list(inputs.get("images") or inputs.get("reference_image_urls") or [])
        single_image = inputs.get("image_url") or inputs.get("reference_image_url")
        if single_image:
            image_urls.insert(0, str(single_image))
        local_image = inputs.get("reference_image_path")
        if legacy and operation in {"image_to_video", "reference_to_video"} and not image_urls:
            if not local_image:
                return ToolResult(
                    success=False,
                    error=(
                        f"{operation} requires reference_image_path, image_url, "
                        "or reference_image_urls"
                    ),
                )
            if not Path(str(local_image)).is_file():
                return ToolResult(
                    success=False,
                    error=f"Agnes reference image not found: {local_image}",
                )

        if legacy:
            frame_rate = float(inputs.get("frame_rate", DEFAULT_FRAME_RATE))
            explicit_frames = inputs.get("num_frames")
            duration = float(inputs.get("duration", 5))
            if not MIN_FRAME_RATE <= frame_rate <= MAX_FRAME_RATE:
                return ToolResult(
                    success=False,
                    error=(
                        f"Agnes Video v2.0 frame_rate must be between "
                        f"{MIN_FRAME_RATE} and {MAX_FRAME_RATE} FPS"
                    ),
                )
            if explicit_frames is None and (
                duration <= 0 or duration * frame_rate > MAX_NUM_FRAMES
            ):
                maximum_seconds = MAX_NUM_FRAMES / frame_rate
                return ToolResult(
                    success=False,
                    error=(
                        "Agnes Video v2.0 can generate at most "
                        f"{maximum_seconds:g} seconds in one call at {frame_rate:g} FPS "
                        f"({MAX_NUM_FRAMES} frames). Split a longer production into planned "
                        "shots, generate each shot separately, then compose them."
                    ),
                    data={
                        "provider": "agnes",
                        "model": model,
                        "usage_conditions": usage_conditions,
                        "fallback_used": False,
                    },
                )
            num_frames = int(explicit_frames if explicit_frames is not None else _frame_count(duration, frame_rate))
            if (
                num_frames < MIN_NUM_FRAMES
                or num_frames > MAX_NUM_FRAMES
                or (num_frames - 1) % FRAME_COUNT_STEP != 0
            ):
                return ToolResult(
                    success=False,
                    error=(
                        f"Agnes num_frames must be between {MIN_NUM_FRAMES} and "
                        f"{MAX_NUM_FRAMES} and satisfy 8n + 1"
                    ),
                    data={
                        "provider": "agnes",
                        "model": model,
                        "usage_conditions": usage_conditions,
                        "fallback_used": False,
                    },
                )

            ratio = str(inputs.get("aspect_ratio", "16:9"))
            width, height = ASPECT_RATIO_DIMENSIONS[ratio]
            width = int(inputs.get("width", width))
            height = int(inputs.get("height", height))
            payload: dict[str, Any] = {
                "model": model,
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

        else:
            if local_image and not Path(str(local_image)).is_file():
                return ToolResult(success=False, error=f"Agnes reference image not found: {local_image}")
            try:
                payload, width, height, duration = _v25_payload(inputs, model, image_urls, local_image)
            except (ValueError, TypeError, KeyError) as exc:
                return ToolResult(success=False, error=str(exc), data={"model": model, "usage_conditions": usage_conditions, "fallback_used": False})
            ratio = payload["aspect_ratio"]
            num_frames = None
            frame_rate = None

        discovery_data = (existing_receipt or {}).get("model_discovery")
        if not resumable:
            discovery = self.discover_models()
            if not discovery.success:
                return discovery
            if model not in {item["id"] for item in discovery.data["models"]}:
                return ToolResult(success=False, error=f"Selected model {model} is absent from the current key's model catalog", data={**discovery.data, "model": model, "fallback_used": False})
            discovery_data = discovery.data

        headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
        fingerprint_payload = dict(payload)
        if local_image and not image_urls:
            fingerprint_payload["reference_image_sha256"] = hashlib.sha256(
                Path(str(local_image)).read_bytes()
            ).hexdigest()
        request_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        request_fingerprint_version = 2
        resumable_receipt = (
            existing_receipt
            if existing_receipt
            and (existing_receipt.get("task_id") or existing_receipt.get("video_id"))
            and str(existing_receipt.get("status") or "").lower() not in TERMINAL_FAILURES
            else None
        )
        if (
            resumable_receipt
            and resumable_receipt.get("request_fingerprint")
            and resumable_receipt.get("request_fingerprint_version") == request_fingerprint_version
            and resumable_receipt["request_fingerprint"] != request_fingerprint
        ):
            return ToolResult(
                success=False,
                error=(
                    "A resumable Agnes task already exists for this output_path with different "
                    "inputs. Resume it unchanged or choose a new output_path; refusing a second submit."
                ),
                data={
                    "provider": "agnes",
                    "model": model,
                    "task_id": resumable_receipt.get("task_id"),
                    "video_id": resumable_receipt.get("video_id"),
                    "fallback_used": False,
                },
            )
        task_id: str | None = None
        video_id: str | None = None
        task_receipt_path: Path | None = None
        attempt_id = str(
            (resumable_receipt or {}).get("attempt_id")
            or inputs.get("attempt_id")
            or uuid.uuid4()
        )
        attempt_ledger_path = _attempt_ledger_path(output_path)
        resumed_existing_task = bool(resumable_receipt)
        try:
            if resumable_receipt:
                created_data = dict(resumable_receipt)
                _append_attempt_event(
                    output_path,
                    attempt_id=attempt_id,
                    event="resumed",
                    payload={
                        "task_id": created_data.get("task_id"),
                        "video_id": created_data.get("video_id"),
                        "request_fingerprint": request_fingerprint,
                    },
                )
            else:
                if local_image and not image_urls:
                    try:
                        image_urls.insert(0, upload_image_litterbox(str(local_image)))
                    except Exception as exc:
                        return ToolResult(
                            success=False,
                            error=f"Failed to upload Agnes reference image: {exc}",
                        )
                    if legacy:
                        payload["image"] = image_urls[0]
                        payload["mode"] = "ti2vid"
                    elif payload["mode"] == "keyframe":
                        payload["first_frame"] = image_urls[0]
                    else:
                        payload["images"] = image_urls
                submit_headers = {**headers, "Idempotency-Key": str(inputs.get("idempotency_key") or request_fingerprint)}
                # Persist intent before POST: a timeout must not permit a second submit.
                task_receipt_path = _write_task_receipt(output_path, {
                    "model": model, "status": "submitting", "attempt_id": attempt_id,
                    "request_fingerprint": request_fingerprint,
                    "request_fingerprint_version": request_fingerprint_version,
                    "model_discovery": discovery_data,
                })
                created = requests.post(
                    f"{_base_url()}/videos",
                    headers=submit_headers,
                    json=payload,
                    timeout=120,
                )
                status_code = getattr(created, "status_code", 200)
                if status_code >= 400:
                    try:
                        rejection = created.json()
                        error_code = (rejection.get("error") or {}).get("code") if isinstance(rejection, dict) else None
                    except (ValueError, AttributeError):
                        error_code = None
                    # A server/network failure can have an unknown submission outcome.
                    if status_code in (400, 401, 403, 404, 422, 429) or error_code == "model_not_found":
                        _write_task_receipt(output_path, {"model": model, "status": "failed", "attempt_id": attempt_id, "last_error": f"Create rejected: HTTP {status_code}", "model_discovery": discovery_data})
                created.raise_for_status()
                created_data = created.json()
                if created_data.get("model") not in (None, model):
                    task_receipt_path = _write_task_receipt(output_path, {**created_data, "attempt_id": attempt_id})
                    raise RuntimeError(f"Agnes returned a different model {created_data['model']}; preserve and reconcile the task instead of resubmitting")
            task_id = str(created_data.get("task_id") or created_data.get("id") or "").strip() or None
            video_id = str(created_data.get("video_id") or "").strip() or None
            if not task_id and not video_id:
                raise RuntimeError("Agnes create response did not include a task_id or video_id")
            receipt_data = {
                **created_data,
                "model": model,
                "model_discovery": discovery_data,
                "task_id": task_id,
                "video_id": video_id,
                "attempt_id": attempt_id,
                "request_fingerprint": request_fingerprint,
                "request_fingerprint_version": request_fingerprint_version,
                "aspect_mismatch_policy": inputs.get("aspect_mismatch_policy"),
            }
            task_receipt_path = _write_task_receipt(output_path, receipt_data)
            if not resumable_receipt:
                _append_attempt_event(
                    output_path,
                    attempt_id=attempt_id,
                    event="submitted",
                    payload={
                        "task_id": task_id,
                        "video_id": video_id,
                        "request_fingerprint": request_fingerprint,
                    },
                )

            deadline = time.time() + int(inputs.get("timeout_seconds", 3600))
            interval = float(inputs.get("poll_interval_seconds", 5))
            result_data: dict[str, Any] = created_data
            while time.time() < deadline:
                if video_id:
                    response = requests.get(
                        _video_lookup_url(),
                        headers=headers,
                        params={"video_id": video_id, "model_name": model},
                        timeout=120,
                    )
                else:
                    response = requests.get(f"{_base_url()}/videos/{task_id}", headers=headers, timeout=120)
                response.raise_for_status()
                result_data = response.json()
                receipt_data.update(
                    {key: value for key, value in result_data.items() if value is not None}
                )
                receipt_data.update({"model": model, "task_id": task_id, "video_id": video_id})
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
            actual_ratio = float(probe["video_width"]) / float(probe["video_height"])
            requested_ratio = width / height
            aspect_ratio_matches = abs(actual_ratio - requested_ratio) / requested_ratio <= 0.01
            receipt_data.update({
                "status": "completed",
                "actual_width": probe["video_width"],
                "actual_height": probe["video_height"],
                "aspect_ratio_matches": aspect_ratio_matches,
            })
            _write_task_receipt(output_path, receipt_data)
            _append_attempt_event(
                output_path,
                attempt_id=attempt_id,
                event="completed",
                payload={
                    "task_id": task_id,
                    "video_id": video_id,
                    "actual_width": probe["video_width"],
                    "actual_height": probe["video_height"],
                    "aspect_ratio_matches": aspect_ratio_matches,
                },
            )
        except requests.HTTPError as exc:
            if output_path.exists():
                output_path.unlink()
            response = exc.response
            status_code = response.status_code if response is not None else "unknown"
            try:
                detail = response.json() if response is not None else None
            except ValueError:
                detail = (response.text[:1000] if response is not None else "")
            _append_attempt_event(
                output_path,
                attempt_id=attempt_id,
                event="interrupted",
                payload={"task_id": task_id, "video_id": video_id, "error": f"HTTP {status_code}"},
            )
            return ToolResult(
                success=False,
                error=f"Agnes API HTTP {status_code}: {detail}",
                data={
                    "provider": "agnes",
                    "model": model,
                    "task_id": task_id,
                    "video_id": video_id,
                    "task_receipt_path": str(task_receipt_path) if task_receipt_path else None,
                    "attempt_id": attempt_id,
                    "attempt_ledger_path": str(attempt_ledger_path),
                    "fallback_used": False,
                },
            )
        except Exception as exc:
            if output_path.exists():
                output_path.unlink()
            _append_attempt_event(
                output_path,
                attempt_id=attempt_id,
                event="interrupted",
                payload={"task_id": task_id, "video_id": video_id, "error": str(exc)},
            )
            return ToolResult(
                success=False,
                error=str(exc),
                data={
                    "provider": "agnes",
                    "model": model,
                    "task_id": task_id,
                    "video_id": video_id,
                    "task_receipt_path": str(task_receipt_path) if task_receipt_path else None,
                    "attempt_id": attempt_id,
                    "attempt_ledger_path": str(attempt_ledger_path),
                    "fallback_used": False,
                },
            )

        sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return ToolResult(
            success=True,
            data={
                "provider": "agnes",
                "model": model,
                "task_id": task_id,
                "video_id": video_id,
                "task_receipt_path": str(task_receipt_path) if task_receipt_path else None,
                "attempt_id": attempt_id,
                "attempt_ledger_path": str(attempt_ledger_path),
                "resumed_existing_task": resumed_existing_task,
                "status": "completed",
                "output": str(output_path),
                "output_path": str(output_path),
                "sha256": sha256,
                "width_requested": width,
                "height_requested": height,
                "aspect_ratio_requested": ratio,
                "aspect_ratio_matches": aspect_ratio_matches,
                "aspect_mismatch_policy": inputs.get("aspect_mismatch_policy"),
                "requires_aspect_normalization": not aspect_ratio_matches,
                "num_frames_requested": num_frames,
                "frame_rate_requested": frame_rate,
                "effective_duration_seconds": num_frames / frame_rate if legacy else duration,
                "usage_conditions": usage_conditions,
                "fallback_used": False,
                **probe,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(time.time() - started, 2),
            seed=inputs.get("seed"),
            model=model,
        )
