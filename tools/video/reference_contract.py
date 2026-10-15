"""Mechanical source/timeline bindings; the agent authors and reviews semantics.

The only plan authority is proposal metadata.reference_adaptation. Receipts and
edit mappings reference that file's SHA; they never become another mutable plan.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import jsonschema


def sha256(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def faithful_plan(proposal: dict) -> dict | None:
    plan = proposal.get("metadata", {}).get("reference_adaptation", {})
    return plan if plan.get("mode") == "faithful_replica" else None


def validate_plan(proposal: dict) -> None:
    plan = faithful_plan(proposal)
    if plan is None:
        return  # Legacy and creative adaptation contracts remain compatible.
    from schemas.artifacts import load_schema
    jsonschema.validate(plan.get("replica"), load_schema("reference_replica"))
    evidence = plan.get("reference_evidence", {})
    if not evidence.get("source_path") or not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("sha256", ""))):
        raise ValueError("Faithful replica requires frozen source_path and sha256")
    replica = plan["replica"]
    if any(u["material"] == "authorized_brand" for u in replica["units"]) and not plan.get("intent", {}).get("brand_reuse_authorized"):
        raise ValueError("Original brand reuse requires authorization in the reference intent")
    cursor, ids = 0, set()
    for unit in replica["units"]:
        if unit["id"] in ids or unit["source_start_frame"] != cursor or unit["source_end_frame"] <= cursor:
            raise ValueError("Replica units must be unique, ordered and cover the source without gaps")
        ids.add(unit["id"])
        if unit["internal_cuts"] != sorted(set(unit["internal_cuts"])) or any(
            not cursor < cut < unit["source_end_frame"] for cut in unit["internal_cuts"]
        ):
            raise ValueError("Internal cuts must be unique source-frame boundaries inside their unit")
        cursor = unit["source_end_frame"]
    if cursor != replica["total_frames"]:
        raise ValueError("Replica units must cover total_frames")
    cue_ids = set()
    for cue in replica["captions"]:
        if cue["id"] in cue_ids or cue["unit_id"] not in ids or not 0 <= cue["start_frame"] < cue["end_frame"] <= cursor:
            raise ValueError("Caption requires a unique ID, known unit and valid source interval")
        cue_ids.add(cue["id"])


def load_bound_plan(ref: dict) -> tuple[dict, dict]:
    path = Path(ref["proposal_path"]).resolve()
    if sha256(path) != ref["proposal_sha256"]:
        raise ValueError("Reference proposal SHA changed; refresh dependent bindings")
    proposal = json.loads(path.read_text(encoding="utf8"))
    from schemas.artifacts import validate_artifact
    validate_artifact("proposal_packet", proposal)
    plan = faithful_plan(proposal)
    if plan is None:
        raise ValueError("Source timeline binding requires faithful_replica mode")
    source = plan["reference_evidence"]
    if sha256(source["source_path"]) != source["sha256"]:
        raise ValueError("Frozen reference source SHA changed")
    return proposal, plan


def bound_unit(inputs: dict) -> tuple[dict, dict]:
    _, plan = load_bound_plan(inputs["reference_adaptation_ref"])
    matches = [u for u in plan["replica"]["units"] if u["id"] == inputs["reference_unit_id"]]
    if len(matches) != 1:
        raise ValueError("Unknown reference_unit_id")
    return plan, matches[0]


def probe(path) -> dict:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                            check=True, capture_output=True, text=True, encoding="utf8")
    return json.loads(result.stdout)


def video_duration(path) -> float:
    media = probe(path)
    video = next(s for s in media["streams"] if s["codec_type"] == "video")
    duration = float(video.get("duration") or media["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Reference/output video has no measured positive duration")
    return duration


def prepare_source_clip(tool, inputs: dict) -> dict:
    plan, unit = bound_unit(inputs)
    if unit["material"] != "generated_video":
        raise ValueError("Brand still is not a generation reference unit")
    output = Path(inputs["output_path"]).resolve()
    receipt_path = output.with_suffix(output.suffix + ".reference.json")
    if output.exists() or receipt_path.exists():
        raise ValueError("Reference derivative exists; reuse its receipt or choose a new revision")
    source = plan["reference_evidence"]
    fps = plan["replica"]["fps"]
    start, end = unit["source_start_frame"] / fps, unit["source_end_frame"] / fps
    if end > video_duration(source["source_path"]) + 1 / fps:
        raise ValueError("Source range exceeds measured source duration")
    output.parent.mkdir(parents=True, exist_ok=True)
    tool.run_command(["ffmpeg", "-n", "-i", source["source_path"], "-ss", str(start), "-t", str(end - start),
                      "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(output)])
    duration = video_duration(output)
    if abs(duration - (end - start)) > 1 / fps + .05:
        raise ValueError("Reference derivative duration differs from authored range")
    # Detect mutation during slicing, before recording a binding.
    bound_unit(inputs)
    receipt = {"schema_version": "reference_clip.v1", "reference_adaptation_ref": inputs["reference_adaptation_ref"],
               "unit_id": unit["id"], "source_sha256": source["sha256"],
               "source_start_frame": unit["source_start_frame"], "source_end_frame": unit["source_end_frame"],
               "path": str(output), "sha256": sha256(output), "duration_seconds": duration}
    with receipt_path.open("x", encoding="utf8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    return {**receipt, "reference_receipt_path": str(receipt_path)}


def verify_generation_reference(inputs: dict, references: list[Path]) -> dict | None:
    binding_keys = {"reference_adaptation_ref", "reference_unit_id", "reference_receipt_path"}
    if not binding_keys.intersection(inputs):
        return None
    if not binding_keys.issubset(inputs):
        raise ValueError("Incomplete source reference binding")
    plan, unit = bound_unit(inputs)
    receipt = json.loads(Path(inputs["reference_receipt_path"]).read_text(encoding="utf8"))
    expected = {"schema_version": "reference_clip.v1", "reference_adaptation_ref": inputs["reference_adaptation_ref"],
                "unit_id": unit["id"], "source_sha256": plan["reference_evidence"]["sha256"],
                "source_start_frame": unit["source_start_frame"], "source_end_frame": unit["source_end_frame"]}
    if any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError("Reference receipt does not bind the planned source segment")
    path = Path(receipt["path"]).resolve()
    if path not in [p.resolve() for p in references] or sha256(path) != receipt["sha256"]:
        raise ValueError("Bound source clip is missing from generation references or changed")
    if path.suffix.lower() not in {".mp4", ".mov", ".m4v", ".webm"}:
        raise ValueError("Source reference must be a video")
    return receipt


def compile_timeline(inputs: dict) -> dict | None:
    proposal = inputs.get("proposal_packet", {})
    plan = faithful_plan(proposal)
    if plan is None:
        return None
    edit, manifest = inputs["edit_decisions"], inputs["asset_manifest"]
    ref = edit.get("metadata", {}).get("reference_adaptation_ref")
    bound_proposal, _ = load_bound_plan(ref or {})
    if bound_proposal != proposal or manifest.get("metadata", {}).get("reference_adaptation_ref") != ref:
        raise ValueError("Compose artifacts must reference the same canonical proposal revision")
    if edit["render_runtime"] != "remotion":
        raise ValueError("Faithful replica timeline requires the locked Remotion runtime")
    if edit.get("composition_mode") == "atelier" or inputs.get("profile") or inputs.get("output_profile"):
        raise ValueError("Replica uses source geometry and explicit layers; do not override with atelier/profile")
    replica = plan["replica"]
    # The master clock includes audio and an authorized brand tail. Some sources
    # have a shorter video stream than their soundtrack/container span.
    source_span = float(probe(plan["reference_evidence"]["source_path"])["format"]["duration"])
    if not math.isfinite(source_span) or abs(source_span * replica["fps"] - replica["total_frames"]) > 1.01:
        raise ValueError("Replica clock differs from the measured frozen source duration")
    mapping = edit.get("metadata", {}).get("reference_timeline", {})
    segments = mapping.get("segments", [])
    cuts = edit["cuts"]
    if len(segments) != len(replica["units"]) or len(cuts) != len(segments):
        raise ValueError("Every source unit requires exactly one ordered cut and media mapping")
    assets = {a["id"]: a for a in manifest["assets"]}
    rendered, reviews = [], []
    for unit, segment, cut in zip(replica["units"], segments, cuts):
        if segment["unit_id"] != unit["id"] or segment["cut_id"] != cut["id"]:
            raise ValueError("Replica cut order differs from the frozen source timeline")
        asset = assets[cut["source"]]
        if sha256(asset["path"]) != segment["media_sha256"]:
            raise ValueError("Selected media changed after reference review")
        speed = cut.get("speed", 1)
        if speed != 1 and not segment.get("time_transform_reason"):
            raise ValueError("Time stretching requires an explicit authored reason")
        length = unit["source_end_frame"] - unit["source_start_frame"]
        hold = segment.get("end_hold_frames", 0)
        if not isinstance(hold, int) or not 0 <= hold < length or (hold and not segment.get("time_transform_reason")):
            raise ValueError("End hold requires explicit frame count and authored reason")
        if abs((cut["out_seconds"] - cut["in_seconds"]) / speed * replica["fps"] + hold - length) > .01:
            raise ValueError("Cut duration differs from source timeline; nominal provider duration is not final timing")
        image = unit["material"] == "authorized_brand"
        if image != (asset["type"] == "image"):
            raise ValueError("Generated motion cannot be silently replaced by a brand still")
        if not image and cut["out_seconds"] > video_duration(asset["path"]) + .001:
            raise ValueError("Cut range exceeds actual generated video duration")
        review = segment.get("fidelity_review", {})
        if review.get("status") not in {"pass", "fail", "unverified"} or not review.get("observations"):
            raise ValueError("Every selected segment requires a model-owned fidelity observation")
        checks = review.get("checks", {})
        if set(checks) != {"composition", "action", "timing", "embedded_text", "lip_sync"} or any(
            value not in {"pass", "fail", "unverified", "not_applicable"} for value in checks.values()
        ):
            raise ValueError("Fidelity review requires separate composition/action/timing/text/lip checks")
        if review["status"] == "pass" and any(v in {"fail", "unverified"} for v in checks.values()):
            raise ValueError("Unverified/failed fidelity dimensions cannot be marked pass")
        reviews.append({"unit_id": unit["id"], "media_sha256": segment["media_sha256"], **review})
        rendered.append({"id": unit["id"], "src": asset["path"], "kind": "image" if image else "video",
                         "from": unit["source_start_frame"], "duration": length,
                         "pictureFrames": length - hold,
                         "trimBefore": round(cut["in_seconds"] * replica["fps"]), "playbackRate": speed,
                         "fade_frames": segment.get("fade_frames", 0)})
    dispositions = mapping.get("caption_dispositions", [])
    by_cue = {d["cue_id"]: d for d in dispositions}
    if len(by_cue) != len(dispositions) or set(by_cue) != {c["id"] for c in replica["captions"]}:
        raise ValueError("Caption dispositions must cover each authored cue exactly once")
    overlays = []
    for cue in replica["captions"]:
        disposition = by_cue[cue["id"]]
        if disposition.get("handling") not in {"overlay", "embedded", "omit"} or not disposition.get("evidence"):
            raise ValueError("Caption handling requires actual-media evidence")
        selected = next(s for s in segments if s["unit_id"] == cue["unit_id"])
        if disposition.get("media_sha256") != selected["media_sha256"]:
            raise ValueError("Caption disposition must bind the currently selected media SHA")
        if disposition["handling"] == "overlay":
            overlays.append(cue)
    audio = replica["audio"]
    if audio["policy"] != "none":
        if sha256(audio["path"]) != audio["sha256"]:
            raise ValueError("Authorized audio changed")
        if inputs.get("audio_path") and Path(inputs["audio_path"]).resolve() != Path(audio["path"]).resolve():
            raise ValueError("External audio differs from the authorized replica audio layer")
    elif inputs.get("audio_path"):
        raise ValueError("Replica has no authorized audio layer")
    if inputs.get("subtitle_path") or edit.get("subtitles", {}).get("enabled") or edit.get("overlays"):
        raise ValueError("Replica text uses explicit caption layers; duplicate subtitle/overlay routes are forbidden")
    fidelity_status = "fail" if any(r["status"] == "fail" for r in reviews) else "unverified" if any(r["status"] == "unverified" for r in reviews) else "pass"
    return {"fps": replica["fps"], "total_frames": replica["total_frames"], "width": replica["width"],
            "height": replica["height"], "clips": rendered, "captions": overlays,
            "backgroundColor": replica["background_color"],
            "audioSrc": None if audio["policy"] == "none" else audio["path"],
            "reference_fidelity": {"status": fidelity_status,
                                   "segments": reviews, "caption_dispositions": dispositions}}
