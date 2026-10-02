"""Agnes first-party images, with durable single-submit receipts.

The agent owns prompts and visual judgment. This adapter only transports,
validates and saves images; transient failures retry on the same model.
Unknown submissions are preserved, and downloads resume the original image.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import time
from pathlib import Path
from typing import Any

import requests

from tools.base_tool import BaseTool, ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier
from tools.video.agnes_video import _api_key, _base_url

DEFAULT_MODEL = "agnes-image-2.1-flash"


class AgnesImage(BaseTool):
    name = "agnes_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "agnes"
    runtime = ToolRuntime.API
    stability = ToolStability.BETA
    dependencies = ["env:AGNES_API_KEY", "pkg:Pillow"]
    install_instructions = "Configure AGNES_API_KEY (or AGNES_API_TOKEN / APIHUB_AGNES_API_KEY)."
    agent_skills = ["visual-style"]
    capabilities = ["text_to_image", "generate_image", "image_edit"]
    supports = {"custom_size": True, "image_edit": True, "multiple_reference_images": True}
    best_for = ["Default OpenMontage Agnes image-to-video route", "Agnes text-to-image and reference editing"]
    not_good_for = ["offline generation", "assuming subscription quota is free"]
    fallback_tools: list[str] = []
    input_schema = {
        "type": "object", "required": ["prompt", "output_path"],
        "properties": {
            "prompt": {"type": "string", "minLength": 1},
            "model": {"type": "string", "enum": [DEFAULT_MODEL], "default": DEFAULT_MODEL},
            "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1024},
            "height": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1024},
            "n": {"type": "integer", "enum": [1], "default": 1},
            "generation_mode": {"type": "string", "enum": ["generate", "edit"], "default": "generate"},
            "image_url": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "output_path": {"type": "string"},
            "max_attempts": {"type": "integer", "minimum": 1, "default": 3},
            "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 3600, "default": 300},
        },
    }
    side_effects = ["Agnes generation requests and transient retries may consume quota", "writes PNG and sanitized receipt"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if _api_key() and importlib.util.find_spec("PIL") else ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        state: dict[str, Any] = {"provider": self.provider, "model": DEFAULT_MODEL, "fallback_used": False, "cost_known": False}
        receipt: Path | None = None
        owns_receipt = False
        def failure(code: str) -> ToolResult:
            state["error_code"] = code
            if receipt and owns_receipt:
                receipt.write_text(json.dumps(state, indent=2), encoding="utf-8")
            return ToolResult(success=False, error=code, data=dict(state), model=DEFAULT_MODEL)

        if self.get_status() != ToolStatus.AVAILABLE:
            return failure("provider_unavailable")
        try:
            max_attempts = inputs.get("max_attempts", 3)
            if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
                return failure("invalid_max_attempts")
            if inputs.get("model", DEFAULT_MODEL) != DEFAULT_MODEL:
                return failure("model_not_approved")
            width, height = int(inputs.get("width", 1024)), int(inputs.get("height", 1024))
            if not (64 <= width <= 4096 and 64 <= height <= 4096) or inputs.get("n", 1) != 1:
                return failure("invalid_dimensions_or_count")
            prompt = str(inputs.get("prompt", "")).strip()
            if not prompt:
                return failure("prompt_required")
            output = Path(inputs["output_path"])
            if output.suffix.lower() != ".png":
                return failure("png_output_required")
            refs = list(inputs.get("image_urls") or [])
            if inputs.get("image_url"):
                refs.insert(0, inputs["image_url"])
            mode = inputs.get("generation_mode", "generate")
            if mode not in {"generate", "edit"} or (mode == "edit" and not refs):
                return failure("invalid_edit_references")
            if any(not isinstance(url, str) or not url.startswith("https://") for url in refs):
                return failure("https_reference_required")
            payload = {"model": DEFAULT_MODEL, "prompt": prompt, "n": 1, "size": f"{width}x{height}"}
            if refs:
                payload["extra_body"] = {"image": refs, "response_format": "url"}
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            receipt = output.with_suffix(".agnes-image.json")
            output.parent.mkdir(parents=True, exist_ok=True)
            if receipt.exists():
                existing = json.loads(receipt.read_text(encoding="utf-8"))
                if existing.get("request_fingerprint") != fingerprint:
                    return failure("request_conflict")
                if existing.get("status") == "completed" and output.exists():
                    if hashlib.sha256(output.read_bytes()).hexdigest() != existing.get("sha256"):
                        return failure("artifact_integrity_failed")
                    return ToolResult(success=True, data={**existing, "reused_existing": True}, artifacts=[str(output), str(receipt)], model=DEFAULT_MODEL)
                if existing.get("image_url") and not output.exists():
                    state = existing
                    owns_receipt = True
                    image_bytes = self._download(state, max_attempts)
                    return self._save(image_bytes, output, receipt, state, started)
                return failure("existing_attempt_requires_inspection")
            if output.exists():
                return failure("output_already_exists")
            state.update(request_fingerprint=fingerprint, status="submitting", output=str(output), requested_dimensions=[width, height])
            # Exclusive creation blocks concurrent duplicate submissions.
            with receipt.open("x", encoding="utf-8") as stream:
                json.dump(state, stream, indent=2)
            owns_receipt = True
            for attempt in range(1, max_attempts + 1):
                state.update(status="submitting", provider_request_count=attempt, retry_dispatched=attempt > 1)
                receipt.write_text(json.dumps(state, indent=2), encoding="utf-8")
                response = requests.post(
                    f"{_base_url()}/images/generations",
                    headers={"Authorization": f"Bearer {_api_key()}", "Idempotency-Key": fingerprint},
                    json=payload, timeout=int(inputs.get("timeout_seconds", 300)),
                )
                state["http_status"] = response.status_code
                if response.status_code != 200:
                    state["status"] = "rejected" if response.status_code < 500 else "unknown"
                    # A 429 explicitly rejects the request. For 5xx, only a
                    # structured error with no task/result identity is a known
                    # failure; ambiguous gateway failures must not resubmit.
                    retryable = response.status_code == 429
                    if response.status_code in {500, 502, 503, 504}:
                        try:
                            body = response.json()
                            retryable = isinstance(body, dict) and bool(body.get("error")) and not any(body.get(key) for key in ("id", "task_id", "data", "url"))
                        except (ValueError, AttributeError):
                            retryable = False
                    if retryable:
                        state["status"] = "rejected"
                    if retryable and attempt < max_attempts:
                        from tools.generation_retry import retry_delay
                        state.setdefault("retry_history", []).append({"attempt": attempt, "reason": f"provider_http_{response.status_code}"})
                        receipt.write_text(json.dumps(state, indent=2), encoding="utf-8")
                        delay = retry_delay(response)
                        time.sleep(delay if delay is not None else 2 ** attempt)
                        continue
                    return failure("provider_http_error")
                body = response.json()
                state.update(status="submitted", response_id=body.get("id"), created=body.get("created"))
                receipt.write_text(json.dumps(state, indent=2), encoding="utf-8")
                entries = body.get("data") or []
                if len(entries) == 1 and isinstance(entries[0], dict):
                    break
                # Empty completed response, with no identity to recover.
                if not body.get("id") and not body.get("task_id") and attempt < max_attempts:
                    state.setdefault("retry_history", []).append({"attempt": attempt, "reason": "empty_image_response"})
                    receipt.write_text(json.dumps(state, indent=2), encoding="utf-8")
                    time.sleep(2 ** attempt)
                    continue
                return failure("invalid_image_response")
            item = entries[0]
            if item.get("b64_json"):
                image_bytes = base64.b64decode(item["b64_json"], validate=True)
            elif isinstance(item.get("url"), str) and item["url"].startswith("https://"):
                state["image_url"] = item["url"]
                receipt.write_text(json.dumps(state, indent=2), encoding="utf-8")
                image_bytes = self._download(state, max_attempts)
            else:
                return failure("image_payload_missing")
            return self._save(image_bytes, output, receipt, state, started)
        except Exception as exc:
            # Do not expose provider body, auth headers or exception URLs.
            state["exception_type"] = type(exc).__name__
            return failure("image_execution_unconfirmed")


    @staticmethod
    def _download(state: dict[str, Any], max_attempts: int) -> bytes:
        for attempt in range(1, max_attempts + 1):
            state["download_attempt_count"] = state.get("download_attempt_count", 0) + 1
            try:
                response = requests.get(state["image_url"], timeout=120)
                response.raise_for_status()
                return response.content
            except requests.RequestException as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status not in {429, 500, 502, 503, 504}:
                    raise
                if attempt >= max_attempts:
                    raise
                from tools.generation_retry import retry_delay
                response = getattr(exc, "response", None)
                delay = retry_delay(response) if response is not None else None
                state["download_retry_dispatched"] = True
                state.setdefault("retry_history", []).append({"download_attempt": attempt, "reason": type(exc).__name__})
                time.sleep(delay if delay is not None else 2 ** attempt)
        raise RuntimeError("download_attempts_exhausted")

    @staticmethod
    def _save(image_bytes: bytes, output: Path, receipt: Path, state: dict[str, Any], started: float) -> ToolResult:
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.load()
            actual_dimensions = list(img.size)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
        png = buffer.getvalue()
        with output.open("xb") as stream:
            stream.write(png)
        state.update(status="completed", dimensions=actual_dimensions, sha256=hashlib.sha256(png).hexdigest())
        state.pop("error_code", None)
        state.pop("exception_type", None)
        receipt.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return ToolResult(success=True, data=dict(state), artifacts=[str(output), str(receipt)], model=DEFAULT_MODEL, duration_seconds=time.monotonic()-started)
