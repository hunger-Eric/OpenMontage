"""Opt-in deterministic image/video preparation from an approved media plan."""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from uuid import uuid4

import jsonschema

from tools.base_tool import BaseTool, Determinism, ExecutionMode, ResourceProfile, ToolResult, ToolStability, ToolTier


class MediaPrepare(BaseTool):
    name = "media_prepare"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "enhancement"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    dependencies = ["cmd:ffmpeg", "cmd:ffprobe", "python:PIL"]
    install_instructions = "Use the project Python and install FFmpeg/ffprobe."
    agent_skills = ["ffmpeg"]
    capabilities = ["prepare_image", "prepare_video", "aspect_fit", "basic_color_correction"]
    supports = {"automatic_on_upload": False, "preserves_original": True}
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=2000)
    idempotency_key_fields = ["input_path", "width", "height", "fit_mode", "brightness", "contrast", "saturation", "fps"]
    side_effects = ["writes a separate prepared file and source-bound JSON receipt only after plan authorization"]
    user_visible_verification = ["Check approved framing and color against the original; technical probes do not prove creative suitability."]
    input_schema = {
        "type": "object", "additionalProperties": False,
        "required": ["input_path", "output_path", "media_type", "width", "height", "confirm_processing"],
        "properties": {
            "input_path": {"type": "string"}, "output_path": {"type": "string"},
            "media_type": {"enum": ["image", "video"]},
            "width": {"type": "integer", "minimum": 2, "maximum": 8192},
            "height": {"type": "integer", "minimum": 2, "maximum": 8192},
            "fit_mode": {"enum": ["contain", "cover"], "default": "contain",
                         "description": "contain keeps the full frame with padding; cover crops to fill, only as specified in the approved plan."},
            "brightness": {"type": "number", "minimum": -1, "maximum": 1, "default": 0},
            "contrast": {"type": "number", "minimum": 0.1, "maximum": 3, "default": 1},
            "saturation": {"type": "number", "minimum": 0, "maximum": 3, "default": 1},
            "fps": {"type": "number", "minimum": 1, "maximum": 120},
            "confirm_processing": {"type": "boolean", "default": False,
                                   "description": "True when the customer has approved these processing choices in the production plan or explicitly requested this standalone processing."},
            "plan_revision": {"type": "string", "description": "Approved project plan revision/hash, retained in the receipt."},
            "source_asset_id": {"type": "string"},
        },
    }

    def _probe(self, path: Path) -> dict:
        result = self.run_command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], timeout=30)
        return json.loads(result.stdout)

    @staticmethod
    def _sha(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def execute(self, inputs: dict) -> ToolResult:
        started = time.monotonic()
        temporary = None
        temporary_receipt = None
        try:
            jsonschema.validate(inputs, self.input_schema)
            if any(not math.isfinite(inputs[key]) for key in ("brightness", "contrast", "saturation", "fps") if key in inputs):
                raise ValueError("Correction and fps values must be finite")
            if inputs["confirm_processing"] is not True:
                return ToolResult(success=False, error="Processing requires an approved plan or explicit customer request", data={"error_code": "processing_not_authorized"})
            source, output = Path(inputs["input_path"]), Path(inputs["output_path"])
            if not source.is_absolute() or not output.is_absolute():
                raise ValueError("Input and output paths must be absolute")
            if source.is_symlink() or not source.is_file():
                raise ValueError("Input must be a real media file")
            if source.resolve() == output.resolve():
                raise ValueError("Output must be a separate file; originals cannot be overwritten")
            receipt_path = output.with_suffix(output.suffix + ".prepare.json")
            if output.exists() or output.is_symlink() or receipt_path.exists():
                raise ValueError("Output or receipt already exists; reuse its recorded identity or choose a new output")
            is_image = inputs["media_type"] == "image"
            if output.suffix.lower() not in ({".png", ".jpg", ".jpeg"} if is_image else {".mp4"}):
                raise ValueError("Images require PNG/JPEG output; videos require MP4 output")
            width, height = inputs["width"], inputs["height"]
            if not is_image and (width % 2 or height % 2):
                raise ValueError("H.264 output width and height must be even")
            if is_image:
                from PIL import Image
                with Image.open(source) as image:
                    if getattr(image, "n_frames", 1) != 1:
                        raise ValueError("Animated images require an explicit video plan, not a still-image conversion")
                if "fps" in inputs:
                    raise ValueError("fps applies only to video")
            original_hash = self._sha(source)
            before = self._probe(source)
            if not any(s.get("codec_type") == "video" for s in before["streams"]):
                raise ValueError("Input has no visual stream")
            if any(s.get("color_transfer") in {"smpte2084", "arib-std-b67"} for s in before["streams"]):
                raise ValueError("HDR input needs an explicit HDR/tone-mapping route; basic correction will not silently convert it to SDR")
            mode = inputs.get("fit_mode", "contain")
            # Correct non-square source pixels before fitting; no geometric stretching.
            filters = ["scale=trunc(iw*sar/2)*2:ih", "setsar=1"]
            if mode == "contain":
                filters += [f"scale={width}:{height}:force_original_aspect_ratio=decrease", f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"]
            else:
                filters += [f"scale={width}:{height}:force_original_aspect_ratio=increase", f"crop={width}:{height}"]
            correction = {k: inputs.get(k, default) for k, default in (("brightness", 0), ("contrast", 1), ("saturation", 1))}
            if correction != {"brightness": 0, "contrast": 1, "saturation": 1}:
                filters.append("eq=" + ":".join(f"{k}={v}" for k, v in correction.items()))
            if "fps" in inputs:
                filters.append(f"fps={inputs['fps']}")
            filters.append("setsar=1")
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.parent / f".prepare-{uuid4().hex}{output.suffix}"
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(source), "-map", "0:v:0", "-vf", ",".join(filters)]
            if is_image:
                command += ["-frames:v", "1", "-update", "1"]
            else:
                command += ["-map", "0:a?", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
            command.append(str(temporary))
            self.run_command(command, timeout=600)
            after = self._probe(temporary)
            stream = next(s for s in after["streams"] if s.get("codec_type") == "video")
            if (stream["width"], stream["height"]) != (width, height):
                raise ValueError("Prepared output dimensions do not match the request")
            if not is_image:
                if any(s.get("codec_type") == "audio" for s in before["streams"]) and not any(s.get("codec_type") == "audio" for s in after["streams"]):
                    raise ValueError("Source audio was lost")
                self.run_command(["ffmpeg", "-v", "error", "-i", str(temporary), "-f", "null", "-"], timeout=600)
            if self._sha(source) != original_hash:
                raise ValueError("Input changed during preparation; output not committed")
            receipt = {"tool": self.name, "source": str(source), "source_sha256": original_hash,
                       "output": str(output), "output_sha256": self._sha(temporary),
                       "parameters": inputs, "before": before, "after": after,
                       "original_preserved": True, "creative_acceptance": "not_verified"}
            temporary_receipt = output.parent / f".prepare-{uuid4().hex}.json"
            temporary_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            # Same-directory hard links commit without overwriting a concurrent file.
            os.link(temporary_receipt, receipt_path)
            try:
                os.link(temporary, output)
            except Exception:
                receipt_path.unlink()
                raise
            return ToolResult(success=True, data=receipt, artifacts=[str(output), str(receipt_path)], duration_seconds=round(time.monotonic()-started, 2))
        except Exception as exc:
            return ToolResult(success=False, error=f"Media preparation failed: {exc}", data={"error_code": "media_preparation_failed"})
        finally:
            for own_file in (temporary, temporary_receipt):
                if own_file is not None:
                    own_file.unlink(missing_ok=True)
