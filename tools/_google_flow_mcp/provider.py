"""Provider-level orchestration shared by Google Flow video and music tools."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools._google_flow_mcp.client import (
    GoogleFlowMCPClient,
    GoogleFlowMCPError,
    google_flow_node,
    google_flow_server_entry,
)
from tools.base_tool import ToolStatus


def provider_status(*, require_ffprobe: bool = True) -> ToolStatus:
    entry = google_flow_server_entry()
    tools_bundle = entry.parent / "tools.js"
    if (
        not google_flow_node()
        or (require_ffprobe and not shutil.which("ffprobe"))
        or not entry.is_file()
        or not tools_bundle.is_file()
    ):
        return ToolStatus.UNAVAILABLE
    try:
        contract = tools_bundle.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ToolStatus.UNAVAILABLE
    if (
        "flow_close" not in contract
        or "flow_upload" not in contract
        or "expectedMediaType" not in contract
    ):
        return ToolStatus.UNAVAILABLE
    return ToolStatus.AVAILABLE


def resolve_project_url(inputs: dict[str, Any]) -> str | None:
    value = inputs.get("project_url") or os.environ.get("GOOGLE_FLOW_PROJECT_URL")
    return str(value).strip() if value else None


def select_text_input(snapshot: dict[str, Any], *, music: bool) -> str:
    interactables = [
        item
        for item in snapshot.get("interactables", [])
        if isinstance(item, dict) and item.get("visible") and not item.get("disabled")
        and (item.get("contentEditable") is True
             or item.get("tag") in {"INPUT", "TEXTAREA"}
             or item.get("role") == "textbox")
    ]
    if music:
        preferred = [
            item
            for item in interactables
            if "chat message" in str(item.get("ariaLabel") or "").lower()
        ]
        if preferred:
            return str(preferred[0]["ref"])
    composer_markers = (
        "您希望创作什么",
        "你希望创作什么",
        "what would you like to create",
        "what do you want to create",
        "describe your video",
        "describe the scene",
        "prompt",
    )
    for item in interactables:
        label = " ".join(
            str(item.get(key) or "")
            for key in ("text", "placeholder", "ariaLabel", "value")
        ).lower()
        if any(marker in label for marker in composer_markers):
            return str(item["ref"])
    contenteditable = [
        item for item in interactables
        if item.get("contentEditable") is True
    ]
    if len(contenteditable) == 1:
        return str(contenteditable[0]["ref"])
    raise GoogleFlowMCPError("Google Flow page has no visible prompt input")


def wait_for_text_input(
    client: GoogleFlowMCPClient,
    *,
    music: bool,
    attempts: int = 8,
    delay_seconds: float = 1.5,
) -> str:
    """Wait for Flow's client-rendered composer to become interactive."""
    last_error: GoogleFlowMCPError | None = None
    for attempt in range(attempts):
        snapshot = client.call_tool("flow_snapshot", {}, timeout_seconds=30)
        try:
            return select_text_input(snapshot, music=music)
        except GoogleFlowMCPError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds)
    raise last_error or GoogleFlowMCPError("Google Flow page has no visible prompt input")


def select_generation_submit(snapshot: dict[str, Any]) -> str:
    candidates = []
    for item in snapshot.get("interactables", []):
        if not isinstance(item, dict) or not item.get("visible") or item.get("disabled"):
            continue
        if item.get("contentEditable") or not (
            item.get("tag") == "BUTTON" or item.get("role") == "button"
            or item.get("type") == "submit"
        ):
            continue
        is_submit = item.get("type") == "submit" or any(
            re.fullmatch(r"开始生成|生成|generate|create|arrow_forward|send message|发送消息",
                         str(item.get(key) or "").strip(), re.I)
            for key in ("text", "ariaLabel")
        )
        if is_submit and item.get("ref"):
            candidates.append(str(item["ref"]))
    if len(candidates) == 1:
        return candidates[0]
    raise GoogleFlowMCPError(
        "Google Flow did not expose an enabled generation submit control after typing the prompt"
    )


def wait_for_generation_submit(
    client: GoogleFlowMCPClient,
    *,
    attempts: int = 8,
    delay_seconds: float = 0.5,
) -> str:
    last_error: GoogleFlowMCPError | None = None
    for attempt in range(attempts):
        snapshot = client.call_tool("flow_snapshot", {}, timeout_seconds=30)
        try:
            return select_generation_submit(snapshot)
        except GoogleFlowMCPError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds)
    raise last_error or GoogleFlowMCPError(
        "Google Flow did not expose an enabled generation submit control after typing the prompt"
    )


def wait_for_video_generation(client, *, generation_id, timeout_seconds, attempt_path=None):
    """Query evidence for this submission, retaining each observation for recovery."""
    if not generation_id:
        raise GoogleFlowMCPError("Flow acknowledged a click without a generation identity; status unknown, reconcile before any resubmission")
    deadline = time.monotonic() + timeout_seconds
    last_status = {"state": "unknown", "source": "not_observed"}
    while time.monotonic() < deadline:
        try:
            last_status = client.call_tool(
                "flow_generation_status", {"generationId": generation_id}, timeout_seconds=30,
            )
        except GoogleFlowMCPError as exc:
            last_status = {"state": "unknown", "source": "status_query_error", "error": str(exc)}
        if attempt_path:
            receipt = json.loads(attempt_path.read_text(encoding="utf-8"))
            receipt["generation_status"] = last_status
            receipt["generation_id"] = generation_id
            if last_status.get("jobId"):
                receipt["job_id"] = last_status["jobId"]
            receipt["status_checked_at"] = time.time()
            # Observation failure is not a provider failure and never licenses resubmission.
            receipt["state"] = "provider_failed" if last_status.get("state") == "failed" else "submitted"
            attempt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
            with attempt_path.with_suffix(".status.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"checked_at": time.time(), **last_status}, ensure_ascii=False) + "\n")
        if last_status.get("state") == "failed":
            raise GoogleFlowMCPError("Flow provider reported terminal failure for this generation: " + json.dumps(last_status))
        if last_status.get("state") == "succeeded" and last_status.get("assetUrl"):
            return {"done": True, **last_status}
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise GoogleFlowMCPError("Flow observation deadline reached; do not resubmit. Last generation status: " + json.dumps(last_status))


def run_generation(
    *,
    url: str,
    prompt: str,
    output_path: Path,
    expected_media_type: str,
    max_budget_credits: float | None,
    timeout_seconds: int,
    music: bool,
    reference_paths: list[Path] | None = None,
    video_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with GoogleFlowMCPClient(timeout_seconds=timeout_seconds + 60) as client:
        attempt_path = output_path.with_suffix(output_path.suffix + ".flow-attempt.json")
        def preparation(stage, **updates):
            if video_settings is None:
                return
            receipt = json.loads(attempt_path.read_text(encoding="utf-8"))
            receipt.update(updates, preparation_stage=stage,
                           generation_status={"state": "not_started", "source": "local_handler_before_submit", "stage": stage})
            attempt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        if video_settings is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with attempt_path.open("x", encoding="utf-8") as stream:
                    json.dump({"state": "preparing", "project_url": url, "output_path": str(output_path),
                               "requested_settings": video_settings,
                               "generation_status": {"state": "not_started", "source": "local_handler_before_submit", "stage": "opening_project"}}, stream)
            except FileExistsError as exc:
                raise GoogleFlowMCPError("Flow attempt already exists; reconcile it before submitting again") from exc
        opened = client.call_tool("flow_open", {"url": url}, timeout_seconds=60)
        settings_receipt = None
        if video_settings is not None:
            from tools._google_flow_mcp.video_session import resolve_video_project, configure_video_settings

            project_url = resolve_video_project(client)
            settings_receipt = configure_video_settings(client, project_url, **video_settings)
            opened = {**opened, "url": project_url}
            preparation("settings_verified", project_url=project_url, settings=settings_receipt)
        uploads = []
        for reference_path in reference_paths or []:
            if not reference_path.is_file():
                raise GoogleFlowMCPError(
                    f"Google Flow reference asset does not exist: {reference_path}"
                )
            upload = client.call_tool(
                "flow_upload",
                {"filePath": str(reference_path.resolve()), "confirmUploadRights": True},
                timeout_seconds=120,
            )
            if upload.get("uploaded") is not True or upload.get("verified") is not True:
                raise GoogleFlowMCPError("Flow did not verify the reference upload; not submitting generation")
            uploads.append(upload)
        input_ref = wait_for_text_input(client, music=music)
        composer_text = " ".join(prompt.split())
        preparation("typing_prompt")
        typed = client.call_tool(
            "flow_type",
            {"ref": input_ref, "text": composer_text, "clearFirst": True, "submit": False},
            # flow_type uses per-character keyboard events. Long production
            # prompts need time for those events plus browser scheduling.
            timeout_seconds=max(60, int(30 + len(composer_text) * 0.05)),
        )
        if typed.get("verified") is not True:
            raise GoogleFlowMCPError(
                "Google Flow did not verify the prompt text before submission"
            )
        submit_ref = wait_for_generation_submit(client)
        # A durable claim precedes any credit confirmation/submission. Unknown
        # outcomes retain this identity and cannot silently submit a second job.
        preparation("prompt_verified", typed=typed)
        approval = client.call_tool(
            "flow_confirm_paid_generation",
            {
                "confirm": True,
                **({"maxBudgetCredits": max_budget_credits} if max_budget_credits is not None else {}),
                "reason": f"OpenMontage {expected_media_type} generation",
            },
            timeout_seconds=30,
        )
        if video_settings is not None:
            claim = json.loads(attempt_path.read_text(encoding="utf-8"))
            claim.update(state="submission_pending", generation_status={"state": "unknown", "source": "generation_click_invoked"})
            attempt_path.write_text(json.dumps(claim, ensure_ascii=False), encoding="utf-8")
        submitted = client.call_tool(
            "flow_click",
            {
                "ref": submit_ref,
                "requireGenerationAcknowledgement": True,
                "acknowledgementTimeoutMs": 30_000,
            },
            timeout_seconds=45,
        )
        if submitted.get("submissionAcknowledged") is not True:
            raise GoogleFlowMCPError(
                "Google Flow did not acknowledge the generation submission"
            )
        if video_settings is not None:
            current_receipt = json.loads(attempt_path.read_text(encoding="utf-8"))
            current_receipt.update(state="submitted", submitted=submitted,
                                   generation_id=submitted.get("generationId"),
                                   project_url=opened.get("url"), settings=settings_receipt)
            attempt_path.write_text(json.dumps(current_receipt, ensure_ascii=False), encoding="utf-8")
        waited = wait_for_video_generation(
            client, generation_id=submitted.get("generationId"), timeout_seconds=timeout_seconds,
            attempt_path=attempt_path if video_settings is not None else None,
        ) if expected_media_type == "video" else client.call_tool(
            "flow_wait",
            {
                "forMedia": True,
                "mediaType": expected_media_type,
                "timeoutMs": timeout_seconds * 1000,
            },
            timeout_seconds=timeout_seconds + 30,
        )
        asset_url = waited.get("assetUrl")
        if not asset_url:
            raise GoogleFlowMCPError("Google Flow completed without a downloadable asset URL")
        downloaded = client.call_tool(
            "flow_download",
            {
                "assetUrl": asset_url,
                "outputPath": str(output_path),
                "expectedMediaType": expected_media_type,
            },
            timeout_seconds=300,
        )
        if video_settings is not None:
            current_receipt = json.loads(attempt_path.read_text(encoding="utf-8"))
            current_receipt.update(state="downloaded", wait=waited, download=downloaded)
            attempt_path.write_text(json.dumps(current_receipt, ensure_ascii=False), encoding="utf-8")
        return {
            "opened": opened,
            "uploads": uploads,
            "typed": typed,
            "approval": approval,
            "submitted": submitted,
            "wait": waited,
            "download": downloaded,
            "settings": settings_receipt,
        }


def probe_image(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
            mode = image.mode
    except Exception as exc:
        raise GoogleFlowMCPError(f"Pillow rejected Google Flow image output: {exc}") from exc
    if width <= 0 or height <= 0:
        raise GoogleFlowMCPError("Google Flow image output has invalid dimensions")
    return {
        "width": width,
        "height": height,
        "format_name": image_format,
        "mode": mode,
        "file_size_bytes": path.stat().st_size,
    }


def probe_media(path: Path, expected_media_type: str) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise GoogleFlowMCPError("ffprobe is required to validate Google Flow output")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise GoogleFlowMCPError(
            f"ffprobe rejected Google Flow output: {completed.stderr.strip() or completed.returncode}"
        )
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    matching = [stream for stream in streams if stream.get("codec_type") == expected_media_type]
    duration = float((payload.get("format") or {}).get("duration") or 0)
    if not matching or duration <= 0:
        raise GoogleFlowMCPError(
            f"Google Flow output is not a real {expected_media_type} asset with positive duration"
        )
    primary = matching[0]
    return {
        "duration_seconds": duration,
        "format_name": (payload.get("format") or {}).get("format_name"),
        "codec": primary.get("codec_name"),
        "width": primary.get("width"),
        "height": primary.get("height"),
        "sample_rate": primary.get("sample_rate"),
        "channels": primary.get("channels"),
        "file_size_bytes": path.stat().st_size,
    }
