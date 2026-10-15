"""OpenMontage adapter for the migrated Hypit inspection source, executed locally.

No installed Hypit executable, distribution, Runtime, Profile or account is used.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

from tools.base_tool import BaseTool, Determinism, ExecutionMode, ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier

SUPPORTED_VERSION = "0.2.6"
OPTIONS = {
    "probe": set(), "boundaries": {"rate", "threshold"},
    "cut": {"start", "end", "label_time"},
    "frames": {"start", "end", "at", "every", "transcript", "around", "occurrence", "padding", "label_time"},
    "tile": {"start", "end", "at", "every", "transcript", "around", "occurrence", "padding", "frames", "cell", "columns"},
    "tiles": {"start", "end", "at", "every", "transcript", "around", "occurrence", "padding", "frames", "cell", "columns", "rows", "ranges"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


PORT = Path(__file__).resolve().parent / "_reference_media"


def ported_media_command() -> list[str]:
    """Execute only this repository's migrated implementation."""
    node = shutil.which("node")
    loader = PORT / "node_modules/tsx/dist/loader.mjs"
    if not node or not loader.is_file() or not (PORT / "node_modules/sharp/package.json").is_file():
        raise FileNotFoundError("Reference inspection dependencies missing; run npm ci --prefix tools/analysis/_reference_media")
    return [node, "--import", loader.as_uri(), str(PORT / "runner.ts")]


class ReferenceMedia(BaseTool):
    name = "reference_media"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "local_source_port"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    dependencies = ["cmd:node", "cmd:ffmpeg"]
    install_instructions = "Run npm ci --prefix tools/analysis/_reference_media; local migrated source uses Node, sharp, tsx and FFmpeg. Hypit is not a dependency."
    agent_skills = ["video-understand", "ffmpeg"]
    fallback_tools: list[str] = []
    input_schema = {
        "type": "object", "required": ["operation", "input_path"],
        "properties": {
            "operation": {"enum": list(OPTIONS)}, "input_path": {"type": "string"},
            "output_path": {"type": "string"}, "receipt_path": {"type": "string"},
            "options": {"type": "object", "description": "Original Hypit option names using underscores, e.g. every, cell, around, transcript, label_time. Defaults and validation remain upstream."},
        },
    }
    supports = {"migrated_hypit_source": True, "transcript_linked_grids": True, "phrase_windows": True, "local_only": True}
    best_for = ["Hypit's original reference inspection commands at adjustable ranges, densities and cell sizes"]
    side_effects = ["writes local frame/grid/clip outputs and optional source-bound execution receipts"]
    user_visible_verification = ["Inspect the actual native grids and timed words; author Analysis and Timeline using the original Hypit reference method"]

    def get_status(self) -> ToolStatus:
        try:
            ported_media_command()
            return ToolStatus.AVAILABLE if shutil.which("ffmpeg") else ToolStatus.UNAVAILABLE
        except FileNotFoundError:
            return ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            operation = inputs["operation"]
            if operation not in OPTIONS:
                raise ValueError("Only local Hypit media inspection operations are allowed")
            options = inputs.get("options", {})
            if not isinstance(options, dict) or set(options) - OPTIONS[operation]:
                raise ValueError(f"Options must match Hypit media {operation}: {sorted(OPTIONS[operation])}")
            source = Path(inputs["input_path"]).resolve()
            if not source.is_file():
                raise ValueError("Local reference file does not exist")
            output = Path(inputs["output_path"]).resolve() if inputs.get("output_path") else None
            receipt_path = Path(inputs["receipt_path"]).resolve() if inputs.get("receipt_path") else None
            if (output and output.exists()) or (receipt_path and receipt_path.exists()):
                raise ValueError("Existing inspection output/receipt must be reused or a fresh path selected")
            if operation not in {"probe", "boundaries"} and output is None:
                raise ValueError("output_path is required for this media operation")
            if operation in {"probe", "boundaries"} and output is not None:
                raise ValueError("Use receipt_path for probe/boundaries; these original commands have no --to")
            command = ported_media_command()
            provenance_path = Path(__file__).resolve().parents[2] / "third_party/hypit/PROVENANCE.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf8"))
            version = provenance["package_version"]
            if version != SUPPORTED_VERSION:
                raise ValueError("Migrated source version differs from the reviewed port")
            for item in provenance["source_files"]:
                local = provenance_path.parents[2] / item["local"]
                if sha256(local) != item["local_sha256"]:
                    raise ValueError("Migrated source differs from its provenance; review the change before executing")
            source_hash = sha256(source)
            argv = [*command, "media", operation, str(source), "--json"]
            for key, value in options.items():
                flag = "--" + key.replace("_", "-")
                if key == "label_time":
                    if not isinstance(value, bool):
                        raise ValueError("label_time must be boolean")
                    if value:
                        argv.append(flag)
                else:
                    if isinstance(value, list):
                        value = ",".join(map(str, value))
                    argv.extend([flag, str(value)])
            if output:
                argv.extend(["--to", str(output)])
            result = subprocess.run(argv, capture_output=True, text=True, encoding="utf8", errors="replace", timeout=600)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Hypit media command failed")
            native = json.loads(result.stdout)
            if sha256(source) != source_hash:
                raise ValueError("Reference bytes changed during inspection")
            generated = [Path(native["path"])] if output and output.is_file() else []
            if operation == "tiles":
                generated = [Path(grid["path"]) for grid in native["grids"]]
            elif operation == "frames":
                generated = [Path(frame["path"]) for frame in native["frames"]]
            files = [{"path": str(p), "sha256": sha256(p)} for p in generated]
            record = {"provider": "local_source_port", "version": version, "provenance_path": str(provenance_path), "operation": operation, "command": argv,
                      "source_path": str(source), "source_sha256": source_hash, "options": options,
                      "native": native, "outputs": files, "interpretation_status": "not_performed_by_tool",
                      "fallback_used": False}
            if receipt_path:
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
            return ToolResult(success=True, data=record, artifacts=[x["path"] for x in files] + ([str(receipt_path)] if receipt_path else []),
                              duration_seconds=round(time.monotonic() - started, 3))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), data={"fallback_used": False}, duration_seconds=round(time.monotonic() - started, 3))
