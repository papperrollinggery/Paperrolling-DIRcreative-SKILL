#!/usr/bin/env python3
"""Local-only, evidence-bound video distillation bundle helper.

This tool deliberately prepares evidence and a reviewable analysis draft.  It
does not inspect creative quality, call models, execute input, or alter an
imported Video Evidence Workbench project.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


AXES = (
    "narrative", "dialogue", "directing", "cinematography", "color_light",
    "texture", "performance", "editing", "sound", "continuity", "vfx",
    "ai_workflow",
)
STATUSES = {"observed", "inferred", "unknown"}
GAP_KINDS = {"missing_capability", "integration_gap", "unverified"}
SHA256_LENGTH = 64
MAX_JSON_BYTES = 16 * 1024 * 1024
COMPARISON_OUTCOMES = {"improved", "unresolved", "untestable"}
SUPPORTING_KINDS = {"transcript", "audio_measurement", "review_record", "production_artifact"}


class DistillError(ValueError):
    pass


def sanitized_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 4096:
        raise DistillError("source URL must be a public HTTP(S) string up to 4096 characters")
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("unsupported source URL")
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except (TypeError, ValueError) as exc:
        raise DistillError("source URL must be public HTTP(S) without userinfo") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == SHA256_LENGTH and all(character in "0123456789abcdef" for character in value)


def finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def load_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise DistillError(f"required regular file is unavailable: {path.name}")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise DistillError(f"JSON exceeds {MAX_JSON_BYTES} byte limit: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise DistillError(f"invalid JSON: {path.name}") from exc


def existing_file(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    if path.is_symlink() or not path.is_file():
        raise DistillError(f"{label} must be an existing regular file")
    return path.resolve(strict=True)


def existing_dir(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    if path.is_symlink() or not path.is_dir():
        raise DistillError(f"{label} must be an existing non-symlink directory")
    return path.resolve(strict=True)


def safe_relative(value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DistillError("frame reference must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DistillError("frame reference escapes workbench project")
    return path


def ratio(value: Any) -> float:
    try:
        parsed = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError) as exc:
        raise DistillError("ffprobe returned invalid frame rate") from exc
    if parsed <= 0:
        raise DistillError("ffprobe returned non-positive frame rate")
    return round(parsed, 6)


def probe_media(video: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise DistillError("trusted ffprobe is unavailable on PATH")
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise DistillError("ffprobe exceeded 60 second timeout") from exc
    if proc.returncode:
        raise DistillError("ffprobe could not inspect video")
    try:
        payload = json.loads(proc.stdout)
        streams = payload["streams"]
        video_stream = next(item for item in streams if item.get("codec_type") == "video")
        duration = float(payload["format"]["duration"])
        width, height = int(video_stream["width"]), int(video_stream["height"])
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DistillError("ffprobe returned incomplete media metadata") from exc
    if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0:
        raise DistillError("ffprobe returned invalid media dimensions or duration")
    return {
        "source_path": str(video), "file_name": video.name, "sha256": sha256_file(video),
        "size_bytes": video.stat().st_size, "duration_seconds": round(duration, 6),
        "width": width, "height": height,
        "fps": ratio(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        "has_audio": any(item.get("codec_type") == "audio" for item in streams),
    }


def media_matches(package: dict[str, Any], media: dict[str, Any]) -> bool:
    metadata = package.get("metadata")
    receipt = metadata.get("media_receipt", {}) if isinstance(metadata, dict) else {}
    if not isinstance(receipt, dict):
        return False
    bindings = [receipt.get("master"), receipt.get("review")]
    for item in bindings:
        if isinstance(item, dict) and item.get("sha256") == media["sha256"] and item.get("size_bytes") == media["size_bytes"]:
            return True
    for key in ("source", "local_master_path", "review_copy_path"):
        raw = package.get(key)
        if isinstance(raw, str):
            candidate = Path(raw)
            if candidate.is_file() and not candidate.is_symlink() and sha256_file(candidate) == media["sha256"]:
                return True
    return False


def locate_frame(root: Path, reference: str) -> tuple[Path, str]:
    relative = safe_relative(reference)
    for candidate in (root / "assets" / "keyframes" / relative, root / relative):
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if resolved.is_file() and not candidate.is_symlink():
            return resolved, resolved.relative_to(root).as_posix()
    raise DistillError(f"referenced workbench frame is unavailable: {reference}")


def import_workbench(root_value: str, media: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = existing_dir(root_value, "workbench project")
    package = load_json(root / "data" / "media_package.json")
    shots = load_json(root / "data" / "shots.json")
    if not isinstance(package, dict) or not isinstance(shots, list) or not media_matches(package, media):
        raise DistillError("workbench package does not bind to the selected video")
    imported: list[dict[str, Any]] = []
    ids: set[str] = set()
    for shot in shots:
        if not isinstance(shot, dict):
            raise DistillError("workbench shots must be objects")
        shot_id, start, end = shot.get("shot_id"), shot.get("start_time"), shot.get("end_time")
        if not isinstance(shot_id, str) or not shot_id or shot_id in ids:
            raise DistillError("workbench shot IDs must be unique non-empty strings")
        try:
            if not finite_number(start) or not finite_number(end):
                raise ValueError("non-finite timing")
            start_f, end_f = float(start), float(end)
        except (TypeError, ValueError, OverflowError) as exc:
            raise DistillError(f"workbench shot timing is invalid: {shot_id}") from exc
        if start_f < 0 or end_f <= start_f or end_f > media["duration_seconds"] + 0.01:
            raise DistillError(f"workbench shot timing is outside selected video: {shot_id}")
        references = shot.get("frame_refs") or [shot.get("primary_frame_ref") or shot.get("frame_ref")]
        if not isinstance(references, list) or not references or not all(isinstance(item, str) for item in references):
            raise DistillError(f"workbench shot has no usable frame references: {shot_id}")
        frames = []
        for reference in dict.fromkeys(references):
            frame, relative = locate_frame(root, reference)
            frames.append({"id": f"frame:{shot_id}:{Path(relative).name}", "relative_path": relative, "sha256": sha256_file(frame)})
        ids.add(shot_id)
        imported.append({"id": f"shot:{shot_id}", "kind": "workbench_shot_boundary", "start_seconds": round(start_f, 6), "end_seconds": round(end_f, 6), "frames": frames})
    return {"status": "imported", "project_path": str(root), "media_package_sha256": sha256_file(root / "data" / "media_package.json"), "project_id": package.get("project_id") if isinstance(package.get("project_id"), str) else None}, imported


def default_analysis(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0", "source_evidence_sha256": json_hash(evidence), "status": "partial",
        "axes": {axis: {"status": "unknown", "observations": [], "inference_boundary": "No source-bound observation recorded."} for axis in AXES},
        "mechanisms": [], "gap_proposals": [], "comparison_cycles": [],
        "scope": "Local evidence preparation and human-review draft only; no model calls, source patches, or creative-quality verdict.",
        "limitations": ["Machine annotations from the workbench are not imported as facts.", "Structural validation does not establish creative or media quality."],
    }


def prepare(video_value: str, output_value: str, workbench: str | None, source_url: str | None) -> dict[str, Any]:
    source_url = sanitized_source_url(source_url)
    video = existing_file(video_value, "video")
    output = Path(output_value).expanduser()
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise DistillError("output directory must be new and have an existing non-symlink parent")
    media = probe_media(video)
    workbench_data, evidence_items = ({"status": "unavailable"}, []) if not workbench else import_workbench(workbench, media)
    evidence = {"schema_version": "1.0", "media": media, "source_url": source_url, "workbench": workbench_data, "evidence": evidence_items, "supporting_evidence": []}
    output.mkdir()
    (output / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "analysis.json").write_text(json.dumps(default_analysis(evidence), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "partial", "bundle_dir": str(output), "evidence_count": len(evidence_items)}


def errors_for(evidence: Any, analysis: Any, bundle: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    missing: list[str] = []
    if not isinstance(evidence, dict) or not isinstance(analysis, dict):
        return ["bundle documents must be JSON objects"], missing
    try:
        if sanitized_source_url(evidence.get("source_url")) != evidence.get("source_url"):
            errors.append("source URL contains uncurated query or fragment")
    except DistillError:
        errors.append("source URL is invalid")
    media = evidence.get("media", {})
    required_media = ("source_path", "file_name", "sha256", "size_bytes", "duration_seconds", "width", "height", "fps", "has_audio")
    current_media: dict[str, Any] | None = None
    if not isinstance(media, dict) or any(key not in media for key in required_media):
        errors.append("media binding is incomplete")
    else:
        try:
            source = existing_file(media["source_path"], "bound media")
            if sha256_file(source) != media["sha256"] or source.stat().st_size != media["size_bytes"]:
                errors.append("bound media changed")
            current_media = probe_media(source)
            if any(current_media[key] != media[key] for key in ("sha256", "size_bytes", "duration_seconds", "width", "height", "fps", "has_audio")):
                errors.append("bound media metadata changed")
            if (not isinstance(media["source_path"], str) or not isinstance(media["file_name"], str) or not media["file_name"]
                    or not all(finite_number(media[key]) for key in ("duration_seconds", "fps"))
                    or not isinstance(media["width"], int) or isinstance(media["width"], bool)
                    or not isinstance(media["height"], int) or isinstance(media["height"], bool)
                    or float(media["duration_seconds"]) <= 0 or media["width"] <= 0
                    or media["height"] <= 0 or float(media["fps"]) <= 0
                    or not isinstance(media["size_bytes"], int) or media["size_bytes"] < 0
                    or not isinstance(media["has_audio"], bool)):
                errors.append("media binding has invalid dimensions, duration, or fps")
            if not is_sha256(media.get("sha256")):
                errors.append("media binding has invalid SHA-256")
        except (DistillError, OSError, TypeError, ValueError):
            errors.append("bound media is unavailable or invalid")
    seen: set[str] = set()
    evidence_ids: set[str] = set()
    items = evidence.get("evidence")
    if not isinstance(items, list):
        errors.append("evidence must be a list")
        items = []
    try:
        duration = float(current_media["duration_seconds"]) if current_media else float(media.get("duration_seconds", 0)) if isinstance(media, dict) else 0
    except (TypeError, ValueError, OverflowError):
        duration = 0
        errors.append("media binding has invalid duration")
    workbench = evidence.get("workbench")
    workbench_status = workbench.get("status") if isinstance(workbench, dict) else None
    if not isinstance(workbench_status, str) or workbench_status not in {"imported", "unavailable"}:
        errors.append("invalid workbench status")
    elif workbench_status == "imported":
        try:
            root = existing_dir(workbench.get("project_path"), "bound workbench project")
            package_path = root / "data" / "media_package.json"
            package = load_json(package_path)
            if (not is_sha256(workbench.get("media_package_sha256"))
                    or sha256_file(package_path) != workbench["media_package_sha256"]
                    or not isinstance(package, dict) or not media_matches(package, media)):
                errors.append("bound workbench media package changed or mismatches media")
        except (DistillError, OSError, TypeError, ValueError):
            errors.append("bound workbench media package is unavailable")
    all_ids: set[str] = set()
    visual_evidence_ids: set[str] = set()
    previous_end = -1.0
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in seen or item["id"] in all_ids:
            errors.append("evidence IDs must be unique strings")
            continue
        seen.add(item["id"]); all_ids.add(item["id"]); evidence_ids.add(item["id"]); visual_evidence_ids.add(item["id"])
        try:
            if not finite_number(item["start_seconds"]) or not finite_number(item["end_seconds"]):
                raise ValueError("non-finite timing")
            start, end = float(item["start_seconds"]), float(item["end_seconds"])
            if start < 0 or end <= start or end > duration + 0.01:
                errors.append(f"invalid evidence timing: {item['id']}")
            elif start < previous_end - 0.000001:
                errors.append(f"evidence intervals are unordered or overlap: {item['id']}")
            previous_end = max(previous_end, end)
        except (KeyError, TypeError, ValueError, OverflowError):
            errors.append(f"invalid evidence timing: {item['id']}")
        frames = item.get("frames", [])
        if not isinstance(frames, list):
            errors.append(f"frames must be a list: {item['id']}")
            frames = []
        if not frames:
            errors.append(f"evidence requires at least one frame: {item['id']}")
        for frame in frames:
            frame_id = frame.get("id") if isinstance(frame, dict) else None
            if not isinstance(frame, dict) or not isinstance(frame_id, str) or not frame_id or frame_id in all_ids:
                errors.append(f"invalid frame binding: {item['id']}"); continue
            all_ids.add(frame_id); evidence_ids.add(frame_id); visual_evidence_ids.add(frame_id)
            if not is_sha256(frame.get("sha256")):
                errors.append(f"invalid frame hash: {frame['id']}")
            project = workbench.get("project_path") if isinstance(workbench, dict) else None
            try:
                if not isinstance(project, str): raise DistillError("missing workbench project")
                root = existing_dir(project, "bound workbench project")
                frame_path = root / safe_relative(frame.get("relative_path"))
                resolved = frame_path.resolve(strict=True); resolved.relative_to(root)
                if frame_path.is_symlink() or not resolved.is_file() or sha256_file(resolved) != frame.get("sha256"):
                    errors.append(f"bound frame changed: {frame['id']}")
            except (DistillError, OSError, ValueError):
                errors.append(f"bound frame is unavailable: {frame.get('id', item['id'])}")
    supporting = evidence.get("supporting_evidence", [])
    if not isinstance(supporting, list):
        errors.append("supporting evidence must be a list")
        supporting = []
    support_fields = {"id", "kind", "relative_path", "sha256", "source_media_sha256"}
    support_index: dict[str, dict[str, Any]] = {}
    audio_measurement_ids: set[str] = set()
    for item in supporting:
        item_id = item.get("id") if isinstance(item, dict) else None
        kind = item.get("kind") if isinstance(item, dict) else None
        if not isinstance(item, dict) or set(item) != support_fields or not isinstance(item_id, str) or not item_id or item_id in all_ids or not isinstance(kind, str) or kind not in SUPPORTING_KINDS or not is_sha256(item.get("sha256")) or item.get("source_media_sha256") != media.get("sha256"):
            errors.append("invalid supporting evidence")
            continue
        all_ids.add(item_id); evidence_ids.add(item_id); support_index[item_id] = item
        if kind == "audio_measurement": audio_measurement_ids.add(item_id)
        try:
            relative = safe_relative(item["relative_path"])
            if not relative.parts or relative.parts[0] != "supporting":
                raise DistillError("supporting evidence must stay under supporting/")
            candidate = bundle / relative
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(bundle)
            if candidate.is_symlink() or not resolved.is_file() or sha256_file(resolved) != item["sha256"]:
                errors.append(f"supporting evidence changed: {item_id}")
        except (DistillError, OSError, ValueError):
            errors.append(f"supporting evidence is unavailable: {item_id}")
    axes = analysis.get("axes")
    analysis_status = analysis.get("status")
    if not isinstance(analysis_status, str) or analysis_status not in {"partial", "valid"}:
        errors.append("invalid analysis status")
    if not isinstance(analysis.get("scope"), str) or not isinstance(analysis.get("limitations"), list) or not all(isinstance(item, str) for item in analysis["limitations"]):
        errors.append("analysis scope or limitations is invalid")
    if not isinstance(axes, dict) or set(axes) != set(AXES):
        errors.append("analysis must contain exactly the 12 required axes")
        axes = {}
    for name, axis in axes.items():
        axis_status = axis.get("status") if isinstance(axis, dict) else None
        if not isinstance(axis, dict) or not isinstance(axis_status, str) or axis_status not in STATUSES or not isinstance(axis.get("observations"), list):
            errors.append(f"invalid axis: {name}"); continue
        observations = axis["observations"]
        if axis_status == "unknown":
            if observations: errors.append(f"unknown axis cannot contain observations: {name}")
            missing.append(name)
        elif not observations:
            errors.append(f"{axis_status} axis needs at least one observation: {name}")
        if axis_status == "inferred" and not isinstance(axis.get("inference_boundary"), str): errors.append(f"inferred axis needs inference boundary: {name}")
        for observation in observations:
            refs = observation.get("evidence_ids") if isinstance(observation, dict) else None
            valid_refs = isinstance(refs, list) and bool(refs) and all(isinstance(ref, str) and ref in evidence_ids for ref in refs)
            if not isinstance(observation, dict) or not isinstance(observation.get("text"), str) or not observation["text"].strip() or not valid_refs:
                errors.append(f"invalid observation evidence references: {name}")
            elif axis_status == "observed" and not any(ref in (audio_measurement_ids if name == "sound" else visual_evidence_ids) for ref in refs):
                errors.append(f"observed {name} requires {'audio measurement' if name == 'sound' else 'shot or frame'} evidence")
    mechanisms = analysis.get("mechanisms")
    if not isinstance(mechanisms, list):
        errors.append("mechanisms must be a list")
        mechanisms = []
    for mechanism in mechanisms:
        need = {"evidence_ids", "problem", "mechanism", "controls", "when_to_use", "misuse_boundary", "review_check", "validation_status"}
        validation_status = mechanism.get("validation_status") if isinstance(mechanism, dict) else None
        if not isinstance(mechanism, dict) or not need <= set(mechanism) or validation_status != "candidate" or not isinstance(mechanism.get("evidence_ids"), list) or not mechanism["evidence_ids"] or not all(isinstance(ref, str) for ref in mechanism["evidence_ids"]) or any(ref not in evidence_ids for ref in mechanism["evidence_ids"]) or any(not isinstance(mechanism[key], str) or not mechanism[key].strip() for key in need - {"evidence_ids", "validation_status"}): errors.append("invalid mechanism; this helper permits candidate status only")
    gaps = analysis.get("gap_proposals")
    if not isinstance(gaps, list):
        errors.append("gap proposals must be a list")
        gaps = []
    for gap in gaps:
        need = {"kind", "target", "hypothesis", "test", "scope"}
        gap_kind = gap.get("kind") if isinstance(gap, dict) else None
        if not isinstance(gap, dict) or not need <= set(gap) or not isinstance(gap_kind, str) or gap_kind not in GAP_KINDS or any(not isinstance(gap[key], str) or not gap[key].strip() for key in need - {"kind"}): errors.append("invalid gap proposal")
    cycles = analysis.get("comparison_cycles")
    if not isinstance(cycles, list):
        errors.append("comparison cycles must be a list")
        cycles = []
    cycle_fields = {"criterion_id", "reference_effect", "why_needed", "artifact_before", "gap", "change", "artifact_after", "review_evidence", "outcome"}
    for cycle in cycles:
        outcome = cycle.get("outcome") if isinstance(cycle, dict) else None
        text_fields = {"criterion_id", "reference_effect", "why_needed", "gap", "change"}
        if (not isinstance(cycle, dict) or set(cycle) != cycle_fields or not isinstance(outcome, str)
                or outcome not in COMPARISON_OUTCOMES
                or any(not isinstance(cycle[key], str) or not cycle[key].strip() for key in text_fields)):
            errors.append("invalid comparison cycle")
        elif outcome == "untestable":
            if cycle["artifact_before"] is not None or cycle["artifact_after"] is not None or not isinstance(cycle["review_evidence"], str) or not cycle["review_evidence"].strip():
                errors.append("invalid untestable comparison cycle")
        elif (any(not isinstance(cycle[key], str) or cycle[key] not in support_index for key in ("artifact_before", "artifact_after", "review_evidence"))
                or any(support_index[cycle[key]]["kind"] != "production_artifact" for key in ("artifact_before", "artifact_after"))
                or support_index[cycle["review_evidence"]]["kind"] != "review_record"):
            errors.append("comparison cycle requires bound supporting evidence")
    if analysis.get("source_evidence_sha256") != json_hash(evidence): errors.append("analysis does not bind current evidence")
    if isinstance(workbench, dict) and workbench.get("status") == "unavailable": missing.append("workbench shot evidence")
    return errors, sorted(set(missing))


def validate(bundle_value: str) -> dict[str, Any]:
    bundle = existing_dir(bundle_value, "bundle directory")
    evidence, analysis = load_json(bundle / "evidence.json"), load_json(bundle / "analysis.json")
    errors, missing = errors_for(evidence, analysis, bundle)
    structural_status = "invalid" if errors else ("partial" if missing else "valid")
    cycles = analysis.get("comparison_cycles") if isinstance(analysis, dict) else None
    return {"status": structural_status, "structural_status": structural_status, "validation_scope": "structural_only", "creative_quality": "unverified", "iteration_status": "review_recorded" if isinstance(cycles, list) and cycles else "not_evaluated", "errors": errors, "missing_coverage": missing}


def markdown_text(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("`", "\\`").replace("*", "\\*").replace("_", "\\_").replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;").replace(">", "&gt;").replace("\r", " ").replace("\n", " ")


def render(bundle_value: str, report_name: str = "report.md") -> Path:
    if Path(report_name).name != report_name or "\\" in report_name or not report_name.endswith(".md"):
        raise DistillError("report name must be a local Markdown filename")
    result = validate(bundle_value)
    if result["errors"]: raise DistillError("cannot render invalid bundle: " + "; ".join(result["errors"]))
    bundle = existing_dir(bundle_value, "bundle directory")
    target = bundle / report_name
    if target.exists() or target.is_symlink(): raise DistillError("report already exists; choose a new --report-name")
    evidence, analysis = load_json(bundle / "evidence.json"), load_json(bundle / "analysis.json")
    media = evidence["media"]
    support_index = {item["id"]: item for item in evidence.get("supporting_evidence", [])}
    def support_label(value: Any) -> str:
        if not isinstance(value, str):
            return "not available"
        item = support_index[value]
        return f"{value} ({item['relative_path']}; {item['sha256']})"
    source_url = evidence.get("source_url")
    source_line = f"- Claimed source URL (not fetched): {markdown_text(source_url)}" if source_url else "- Claimed source URL: none"
    lines = ["# Video Distillation Draft", "", "## Validation boundary", "", f"- Structural status: {result['structural_status']}", "- Creative quality: unverified (structural validation is not a quality verdict).", f"- Iteration status: {result['iteration_status']}", "", "## Source", "", f"- File: `{markdown_text(media['file_name'])}`", f"- SHA-256: `{media['sha256']}`", f"- Media: {media['width']}x{media['height']}, {media['fps']} fps, {media['duration_seconds']} s, audio={str(media['has_audio']).lower()}", source_line, f"- Evidence: {len(evidence['evidence'])} imported Workbench intervals (not a definitive shot count); workbench={markdown_text(evidence['workbench']['status'])}", "", "## Analysis axes", ""]
    for name in AXES:
        axis = analysis["axes"][name]
        lines += [f"### {name}", "", f"Status: {axis['status']}", ""]
        if name == "sound" and axis["status"] == "observed":
            lines += ["Boundary: observed audio measurement only; it is not proof of heard content or verified quality.", ""]
        for observation in axis["observations"]:
            lines.append(f"- {markdown_text(observation['text'])} (`{', '.join(markdown_text(ref) for ref in observation['evidence_ids'])}`)")
        if axis.get("inference_boundary"): lines += [f"Boundary: {markdown_text(axis['inference_boundary'])}", ""]
    lines += ["## Mechanisms", ""]
    for item in analysis["mechanisms"]:
        lines += [f"### {markdown_text(item['problem'])}", "", f"- Mechanism: {markdown_text(item['mechanism'])} ({item['validation_status']})"]
        for key in ("controls", "when_to_use", "misuse_boundary", "review_check"):
            lines.append(f"- {key}: {markdown_text(item[key])}")
        lines += [f"- Evidence: {markdown_text(', '.join(item['evidence_ids']))}", ""]
    lines += ["", "## Gap proposals", ""]
    for item in analysis["gap_proposals"]: lines.append(f"- [{item['kind']}] {markdown_text(item['target'])}: {markdown_text(item['hypothesis'])}; test: {markdown_text(item['test'])}; scope: {markdown_text(item['scope'])}")
    lines += ["", "## Comparison cycles", ""]
    for item in analysis["comparison_cycles"]:
        review = support_label(item["review_evidence"]) if item["outcome"] != "untestable" else item["review_evidence"]
        lines += [f"### {markdown_text(item['reference_effect'])}", "", f"- Criterion ID: {markdown_text(item['criterion_id'])}", f"- Why needed: {markdown_text(item['why_needed'])}", f"- Before: {markdown_text(support_label(item['artifact_before']))}", f"- Gap: {markdown_text(item['gap'])}", f"- Change: {markdown_text(item['change'])}", f"- After: {markdown_text(support_label(item['artifact_after']))}", f"- Review evidence: {markdown_text(review)}", f"- Outcome record: {markdown_text(item['outcome'])} (not an automated quality certification)", ""]
    lines += ["## Supporting evidence appendix", ""]
    for item in evidence["supporting_evidence"]:
        lines.append(f"- `{markdown_text(item['id'])}` [{markdown_text(item['kind'])}]: `{markdown_text(item['relative_path'])}`; SHA-256 `{item['sha256']}`")
    lines += ["", "## Scope and limitations", "", markdown_text(analysis["scope"]), ""] + [f"- {markdown_text(item)}" for item in analysis["limitations"]]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare, validate, or render a local evidence-bound video distillation draft.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--video", required=True); prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--workbench-project"); prepare_parser.add_argument("--source-url")
    validate_parser = commands.add_parser("validate"); validate_parser.add_argument("bundle_dir")
    render_parser = commands.add_parser("render"); render_parser.add_argument("bundle_dir")
    render_parser.add_argument("--report-name", default="report.md", help="New versioned Markdown filename; never overwrites.")
    args = parser.parse_args()
    try:
        if args.command == "prepare": payload = prepare(args.video, args.output_dir, args.workbench_project, args.source_url)
        elif args.command == "validate": payload = validate(args.bundle_dir)
        else: payload = {"status": "rendered", "report": str(render(args.bundle_dir, args.report_name))}
    except DistillError as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)})); return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 1 if payload.get("status") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
