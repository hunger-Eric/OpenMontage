"""Same-engine preview acceptance and byte-preserving finalization.

Creative and semantic decisions remain with the production owner. This module
checks local input identity and technical evidence; it never calls a provider.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from schemas.artifacts import validate_artifact
from tools.base_tool import ToolResult


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preflight(tool, inputs: dict) -> dict:
    """Validate final inputs without running a renderer or judging aesthetics."""
    for name in ("edit_decisions", "asset_manifest", "proposal_packet", "decision_log"):
        validate_artifact(name, inputs.get(name, {}))
    edit = inputs["edit_decisions"]
    plan = inputs["proposal_packet"]["production_plan"]
    if edit["render_runtime"] != plan.get("render_runtime"):
        raise ValueError("proposal and edit render_runtime differ")
    files = set()

    def require(raw):
        path = Path(raw).resolve()
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Required input missing or empty: {path}")
        files.add(path)
        return path

    assets = {asset["id"]: asset for asset in inputs["asset_manifest"]["assets"]}
    for asset in assets.values():
        require(asset["path"])
    for cut in edit["cuts"]:
        if cut["out_seconds"] <= cut["in_seconds"]:
            raise ValueError(f"Invalid cut interval: {cut['id']}")
        if cut["source"] not in assets and edit.get("composition_mode") != "atelier":
            require(cut["source"])
    for key in ("audio_path", "subtitle_path", "script_path", "narration_transcript_path"):
        if inputs.get(key):
            require(inputs[key])
    narration = any(a["type"] == "narration" for a in assets.values())
    if narration:
        transcript = require(inputs.get("narration_transcript_path") or "")
        script = inputs.get("script_text") or tool._read_text_file(inputs.get("script_path"))
        comparison = tool._compare_transcript_to_script(transcript, script)
        if not comparison.get("transcript_matches_script"):
            raise ValueError(f"Narration transcript preflight failed: {comparison.get('issues')}")
        if edit.get("subtitles", {}).get("enabled"):
            subtitle_id = edit["subtitles"].get("source")
            subtitle = assets.get(subtitle_id) if subtitle_id else next(
                (a for a in assets.values() if a["type"] == "subtitle"), None)
            if not subtitle or subtitle.get("source_tool") != "transcript_whisperx":
                raise ValueError("Generated narration requires transcript_whisperx subtitle provenance")
            if require(subtitle["path"]) != transcript:
                raise ValueError("Subtitle source must reference the verified final-audio transcript")
    bespoke = edit.get("bespoke", {})
    if bespoke.get("art_direction") and Path(bespoke["art_direction"]).is_file():
        require(bespoke["art_direction"])
    if bespoke.get("entry"):
        entry = require(bespoke["entry"])
        # Include sibling source modules, styles and bundled static resources.
        # Output/review directories are excluded so writing evidence cannot
        # invalidate its own source identity.
        for path in entry.parent.rglob("*"):
            relative = path.relative_to(entry.parent)
            if any(p in {"node_modules", ".git", "renders", "snapshots", "artifacts", "history"}
                   for p in relative.parts):
                continue
            if path.is_file() and (path.suffix in {".tsx", ".ts", ".js", ".jsx", ".css", ".html"}
                                   or "public" in relative.parts):
                require(path)
        for key in ("props_path",):
            if bespoke.get(key):
                require(bespoke[key])
        if bespoke.get("public_dir"):
            public = Path(bespoke["public_dir"]).resolve()
            if not public.is_dir():
                raise ValueError(f"Public directory missing: {public}")
            for path in public.rglob("*"):
                if path.is_file():
                    require(path)
    repo = Path(__file__).resolve().parents[2]
    # Bind engine implementation as well as creative source. An engine upgrade
    # cannot silently finalize an older preview as if it used current inputs.
    for path in (repo / "tools/video").glob("*.py"):
        require(path)
    if edit["render_runtime"] == "remotion":
        composer = repo / "remotion-composer"
        for name in ("package.json", "package-lock.json"):
            require(composer / name)
        for path in (composer / "src").rglob("*"):
            if path.is_file():
                require(path)
    parameters = {k: v for k, v in inputs.items() if k not in {
        "operation", "output_path", "input_path", "preview_receipt_path", "visual_review_path"}}
    snapshot = {"parameters": parameters,
                "files": {str(path): file_hash(path) for path in sorted(files)}}
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode("utf8")).hexdigest()
    return {"input_sha256": fingerprint, "file_count": len(files)}


def preview(tool, inputs: dict) -> ToolResult:
    identity = preflight(tool, inputs)
    output = Path(inputs["output_path"]).resolve()
    receipt_path = output.with_suffix(output.suffix + ".preview.json")
    if output.exists() or receipt_path.exists():
        raise ValueError("Preview already exists; retain it and choose a new revision path")
    result = tool._render(inputs)
    if not result.success:
        return result
    if identity != preflight(tool, inputs):
        raise ValueError("Composition inputs changed while rendering; preview cannot be accepted")
    tool.run_command(["ffmpeg", "-v", "error", "-xerror", "-i", str(output),
                      "-map", "0:v:0", "-map", "0:a:0?", "-f", "null", "-"], timeout=1800)
    receipt = {"schema_version": "composition_preview.v1", **identity,
               "video_path": str(output), "video_sha256": file_hash(output),
               "full_decode": True, "final_review": result.data["final_review"]}
    with receipt_path.open("x", encoding="utf8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    result.data.update({"operation": "preview", "acceptance_eligible": True,
                        "delivery_ready": False, "preview_receipt_path": str(receipt_path),
                        "video_sha256": receipt["video_sha256"]})
    result.artifacts.append(str(receipt_path))
    return result


def finalize(tool, inputs: dict) -> ToolResult:
    identity = preflight(tool, inputs)
    receipt = json.loads(Path(inputs["preview_receipt_path"]).read_text(encoding="utf8"))
    if (receipt.get("schema_version") != "composition_preview.v1"
            or receipt.get("input_sha256") != identity["input_sha256"]
            or receipt.get("full_decode") is not True
            or receipt.get("final_review", {}).get("status") != "pass"):
        raise ValueError("Preview evidence is incomplete or inputs changed; render and review a new revision")
    source = Path(receipt["video_path"]).resolve()
    video_sha = file_hash(source)
    if video_sha != receipt.get("video_sha256"):
        raise ValueError("Preview video changed after technical review")
    visual = json.loads(Path(inputs["visual_review_path"]).read_text(encoding="utf8"))
    if (visual.get("verdict") != "accept" or visual.get("video_sha256") != video_sha
            or visual.get("owner") != "current_codex_main_agent"
            or visual.get("method") not in {"full_frame_sequence", "continuous_watch"}
            or not visual.get("observations")):
        raise ValueError("Owner must inspect this exact preview and record visual acceptance")
    output = Path(inputs["output_path"]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create preserves historical final files and the reviewed bytes.
    with source.open("rb") as src, output.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    if file_hash(output) != video_sha:
        raise ValueError("Final copy differs from accepted preview")
    review = dict(receipt["final_review"], output_path=str(output))
    return ToolResult(success=True, data={"operation": "finalize", "output": str(output),
        "reused_preview": str(source), "video_sha256": video_sha, "final_review": review,
        "final_review_status": "pass", "delivery_ready": True}, artifacts=[str(output)])
