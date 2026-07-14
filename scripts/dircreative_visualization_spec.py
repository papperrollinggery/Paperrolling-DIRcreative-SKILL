#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "docs/film-preproduction/schemas/chat-visualization-spec.schema.json"
REQUIRED_FORBIDDEN_CLAIMS = {
    "lock",
    "readiness",
    "acceptance",
    "completion",
    "generation_authorization",
}
REQUIRED_FALLBACK_FIELDS = {
    "current_stage",
    "decision_prompt",
    "downstream_effects",
}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
MAX_IMAGE_BYTES = 325_000
MAX_IMAGE_PIXELS = 16_000_000
MAX_EVIDENCE_BYTES = 1_000_000
BACKSTAGE_VISIBLE_RE = re.compile(
    r"(?:\b(?:artifact|gate|receipt|sha256|writeback|prompt-only)\b|source truth|项目写回|新建锁|保留锁)",
    re.IGNORECASE,
)
CUSTOMER_STAGE_LABELS = {
    "director_room": "导演组创意方向",
    "story": "故事",
    "script": "脚本",
    "shot": "分镜",
    "visual_direction": "视觉方向",
    "visual_bible": "视觉圣经",
    "reference_pack": "参考图方案",
    "image_prompt": "出图执行建议",
    "video_prompt": "视频生成建议",
    "generation_qa": "QA 与重试",
    "retry": "最小重试",
    "checkpoint": "当前进度",
}


class SpecLoadError(Exception):
    pass


def image_dimensions(path: Path, mime_type: str) -> tuple[int, int] | None:
    with path.open("rb") as stream:
        data = stream.read(65_536)
    if mime_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if mime_type == "image/jpeg" and data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset : offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height = int.from_bytes(data[offset + 3 : offset + 5], "big")
                width = int.from_bytes(data[offset + 5 : offset + 7], "big")
                return width, height
            offset += length
    if mime_type == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X" and len(data) >= 30:
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF)
        marker = data.find(b"\x9d\x01\x2a")
        if marker >= 0 and marker + 7 <= len(data):
            width = int.from_bytes(data[marker + 3 : marker + 5], "little") & 0x3FFF
            height = int.from_bytes(data[marker + 5 : marker + 7], "little") & 0x3FFF
            return width, height
    if mime_type == "image/svg+xml":
        text = data.decode("utf-8", errors="replace")
        width_match = re.search(r"<svg\b[^>]*\bwidth=['\"]([0-9.]+)", text, re.IGNORECASE)
        height_match = re.search(r"<svg\b[^>]*\bheight=['\"]([0-9.]+)", text, re.IGNORECASE)
        if width_match and height_match:
            return int(float(width_match.group(1))), int(float(height_match.group(1)))
        view_box = re.search(
            r"<svg\b[^>]*\bviewBox=['\"]\s*[-+]?[0-9.]+\s+[-+]?[0-9.]+\s+([0-9.]+)\s+([0-9.]+)['\"]",
            text,
            re.IGNORECASE,
        )
        if view_box:
            return int(float(view_box.group(1))), int(float(view_box.group(2)))
    return None


def load_document(path: Path) -> Any:
    if not path.exists():
        raise SpecLoadError(f"missing file: {path}")
    if path.suffix.lower() == ".json":
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SpecLoadError(f"invalid JSON: {exc}") from exc
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise SpecLoadError(f"invalid YAML: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SpecLoadError(f"YAML conversion failed: {exc}") from exc


def schema_errors(document: Any, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if os.environ.get("DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"):
        from dircreative_state_audit import _builtin_schema_errors

        return [f"schema:{failure}" for failure in _builtin_schema_errors(document, schema, schema, "$")]
    try:
        import jsonschema
    except ImportError:
        from dircreative_state_audit import _builtin_schema_errors

        return [f"schema:{failure}" for failure in _builtin_schema_errors(document, schema, schema, "$")]
    validator = jsonschema.Draft202012Validator(schema)
    failures: list[str] = []
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        failures.append(f"schema:{location}: {error.message}")
    return failures


def resolve_json_pointer(document: Any, pointer: str) -> tuple[bool, Any]:
    if not pointer.startswith("#/"):
        return False, None
    current = document
    for raw_token in pointer[2:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                return False, None
            index = int(token)
            if index >= len(current):
                return False, None
            current = current[index]
        else:
            return False, None
    return True, current


def semantic_errors(document: Any, project_root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["document must be an object"]

    gate = document.get("stage_gate") if isinstance(document.get("stage_gate"), dict) else {}
    gate_id = gate.get("id")
    execution_context = document.get("execution_context")
    controller = document.get("controller") if isinstance(document.get("controller"), dict) else {}
    view = document.get("view") if isinstance(document.get("view"), dict) else {}
    source_truth = document.get("source_truth") if isinstance(document.get("source_truth"), dict) else {}
    presentation = document.get("presentation") if isinstance(document.get("presentation"), dict) else {}
    interactions = document.get("interactions") if isinstance(document.get("interactions"), dict) else {}
    write_boundary = document.get("write_boundary") if isinstance(document.get("write_boundary"), dict) else {}
    fallback = document.get("fallback") if isinstance(document.get("fallback"), dict) else {}

    visible_strings: list[tuple[str, str]] = []

    def collect_visible(value: Any, location: str) -> None:
        if isinstance(value, str):
            visible_strings.append((location, value))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                collect_visible(item, f"{location}[{index}]")
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in {"id", "source_ref", "source_refs", "target_gate_id", "kind", "classification"}:
                    collect_visible(item, f"{location}.{key}")

    collect_visible(view, "view")
    collect_visible(presentation, "presentation")
    collect_visible(
        [
            {"label": item.get("label"), "conversation_intent": item.get("conversation_intent")}
            for item in interactions.get("actions", [])
            if isinstance(item, dict)
        ],
        "interactions.actions",
    )
    collect_visible({"decision_question": fallback.get("decision_question")}, "fallback")
    for location, value in visible_strings:
        if BACKSTAGE_VISIBLE_RE.search(value):
            errors.append(f"customer-visible text leaks backstage term at {location}")

    artifacts = source_truth.get("artifacts") if isinstance(source_truth.get("artifacts"), list) else []
    artifact_ids: set[str] = set()
    artifact_map: dict[str, dict[str, Any]] = {}
    evidence_documents: dict[str, Any] = {}
    resolved_project_root = project_root.expanduser().resolve()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"source artifact {index} must be an object")
            continue
        artifact_id = artifact.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            errors.append(f"source artifact {index} missing artifact_id")
        elif artifact_id in artifact_ids:
            errors.append(f"duplicate source artifact_id: {artifact_id}")
        else:
            artifact_ids.add(artifact_id)
            artifact_map[artifact_id] = artifact
        if not SHA256_RE.fullmatch(str(artifact.get("sha256", ""))):
            errors.append(f"source artifact {artifact_id or index} has invalid sha256")
        path_value = artifact.get("path")
        evidence_path_value = artifact.get("evidence_path")
        if path_value is not None and evidence_path_value is not None:
            errors.append(f"source artifact {artifact_id or index} cannot provide both path and evidence_path")
        if path_value is not None:
            path = Path(str(path_value))
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"source artifact {artifact_id or index} has unsafe path")
                continue
            resolved = (resolved_project_root / path).resolve()
            try:
                resolved.relative_to(resolved_project_root)
            except ValueError:
                errors.append(f"source artifact {artifact_id or index} escapes project root")
                continue
            expected_mime = IMAGE_MIME_BY_SUFFIX.get(resolved.suffix.lower())
            if expected_mime is None or artifact.get("mime_type") != expected_mime:
                errors.append(f"source artifact {artifact_id or index} has unsupported or mismatched image type")
            if not resolved.is_file():
                errors.append(f"source artifact {artifact_id or index} image file is missing")
            else:
                image_size = resolved.stat().st_size
                if image_size > MAX_IMAGE_BYTES:
                    errors.append(f"source artifact {artifact_id or index} image exceeds {MAX_IMAGE_BYTES} bytes")
                else:
                    actual_sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
                    if actual_sha != artifact.get("sha256"):
                        errors.append(f"source artifact {artifact_id or index} image sha256 mismatch")
                    dimensions = image_dimensions(resolved, str(artifact.get("mime_type", "")))
                    if dimensions is None or min(dimensions) <= 0:
                        errors.append(f"source artifact {artifact_id or index} image dimensions are unreadable")
                    elif dimensions[0] * dimensions[1] > MAX_IMAGE_PIXELS:
                        errors.append(f"source artifact {artifact_id or index} image exceeds {MAX_IMAGE_PIXELS} pixels")
                if resolved.suffix.lower() == ".svg" and image_size <= MAX_IMAGE_BYTES:
                    svg_text = resolved.read_text(encoding="utf-8", errors="replace")
                    external_refs = re.findall(r"(?:href|src)\s*=\s*['\"]([^'\"]+)", svg_text, re.IGNORECASE)
                    if (
                        re.search(
                            r"<(?:script|foreignObject)\b|\bon[a-z]+\s*=|<!DOCTYPE|<!ENTITY|@import|url\s*\(\s*['\"]?(?!#)",
                            svg_text,
                            re.IGNORECASE,
                        )
                        or any(not value.startswith("#") for value in external_refs)
                    ):
                        errors.append(f"source artifact {artifact_id or index} contains active or external SVG content")
        if evidence_path_value is not None:
            evidence_path = Path(str(evidence_path_value))
            if evidence_path.is_absolute() or ".." in evidence_path.parts or evidence_path.suffix.lower() != ".json":
                errors.append(f"source artifact {artifact_id or index} has unsafe or unsupported evidence_path")
                continue
            resolved_evidence = (resolved_project_root / evidence_path).resolve()
            try:
                resolved_evidence.relative_to(resolved_project_root)
            except ValueError:
                errors.append(f"source artifact {artifact_id or index} evidence_path escapes project root")
                continue
            if artifact.get("lifecycle_status") != "current":
                errors.append(f"source artifact {artifact_id or index} evidence record must have current lifecycle")
            if not resolved_evidence.is_file():
                errors.append(f"source artifact {artifact_id or index} evidence file is missing")
                continue
            evidence_size = resolved_evidence.stat().st_size
            if evidence_size > MAX_EVIDENCE_BYTES:
                errors.append(f"source artifact {artifact_id or index} evidence file exceeds {MAX_EVIDENCE_BYTES} bytes")
                continue
            evidence_bytes = resolved_evidence.read_bytes()
            if hashlib.sha256(evidence_bytes).hexdigest() != artifact.get("sha256"):
                errors.append(f"source artifact {artifact_id or index} evidence sha256 mismatch")
                continue
            try:
                evidence_documents[str(artifact_id)] = json.loads(evidence_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError):
                errors.append(f"source artifact {artifact_id or index} evidence file is invalid JSON")

    def validate_source_ref(source_ref: Any, label: str) -> None:
        if not isinstance(source_ref, str) or "#/" not in source_ref:
            errors.append(f"{label} has invalid source_ref")
            return
        artifact_id, pointer_suffix = source_ref.split("#/", 1)
        if artifact_id not in artifact_ids:
            errors.append(f"{label} references unknown artifact: {artifact_id}")
            return
        if artifact_id in evidence_documents:
            exists, _ = resolve_json_pointer(evidence_documents[artifact_id], f"#/{pointer_suffix}")
            if not exists:
                errors.append(f"{label} references missing evidence content: {source_ref}")

    fields = presentation.get("fields") if isinstance(presentation.get("fields"), list) else []
    field_ids: set[str] = set()
    qa_candidate_ids: set[str] | None = None
    visual_direction_ids: set[str] | None = None

    previews = presentation.get("previews") if isinstance(presentation.get("previews"), list) else []
    preview_option_ids: set[str] = set()
    for index, preview in enumerate(previews):
        if not isinstance(preview, dict):
            errors.append(f"preview {index} must be an object")
            continue
        artifact_id = preview.get("artifact_id")
        artifact = artifact_map.get(str(artifact_id))
        if artifact is None:
            errors.append(f"preview {index} references unknown artifact: {artifact_id}")
            continue
        if not artifact.get("path") or not artifact.get("mime_type"):
            errors.append(f"preview {index} artifact must provide path and mime_type")
        classification = artifact.get("review_classification")
        if classification not in {"real_candidate", "illustrative_placeholder"}:
            errors.append(f"preview {index} artifact requires review_classification")
        if classification == "real_candidate":
            if artifact.get("lifecycle_status") != "current" or not all(
                artifact.get(key) == "confirmed"
                for key in ("source_status", "authorization_status", "channel_fit_status")
            ):
                errors.append(f"preview {index} real candidate requires current lifecycle and confirmed source, authorization, and channel fit")
            for evidence_key in ("source_evidence_ref", "authorization_evidence_ref", "channel_fit_evidence_ref"):
                evidence_ref = artifact.get(evidence_key)
                validate_source_ref(evidence_ref, f"preview {index} {evidence_key}")
                if isinstance(evidence_ref, str) and evidence_ref.split("#/", 1)[0] == artifact_id:
                    errors.append(f"preview {index} {evidence_key} cannot self-reference the image artifact")
                if isinstance(evidence_ref, str):
                    evidence_artifact_id, evidence_pointer = evidence_ref.split("#/", 1) if "#/" in evidence_ref else ("", "")
                    evidence_artifact = artifact_map.get(evidence_artifact_id, {})
                    if evidence_artifact.get("review_classification") is not None:
                        errors.append(f"preview {index} {evidence_key} must reference a non-image evidence artifact")
                    if (
                        not evidence_artifact.get("evidence_path")
                        or evidence_artifact.get("lifecycle_status") != "current"
                        or evidence_artifact_id not in evidence_documents
                    ):
                        errors.append(f"preview {index} {evidence_key} must reference a verified current evidence record")
                    elif evidence_pointer:
                        exists, evidence_value = resolve_json_pointer(
                            evidence_documents[evidence_artifact_id], f"#/{evidence_pointer}"
                        )
                        if exists and (
                            not isinstance(evidence_value, dict) or evidence_value.get("status") != "confirmed"
                        ):
                            errors.append(f"preview {index} {evidence_key} must resolve to confirmed evidence content")
        elif classification == "illustrative_placeholder":
            if not (
                artifact.get("source_status") == "unconfirmed"
                and artifact.get("authorization_status") == "not_applicable"
                and artifact.get("channel_fit_status") == "not_applicable"
            ):
                errors.append(f"preview {index} illustrative image requires unconfirmed source and non-applicable authorization/channel status")
        option_id = preview.get("option_id")
        if isinstance(option_id, str):
            if option_id in preview_option_ids:
                errors.append(f"duplicate preview option_id: {option_id}")
            preview_option_ids.add(option_id)
    has_placeholder_preview = bool(previews) and any(
        artifact_map.get(str(preview.get("artifact_id")), {}).get("review_classification") == "illustrative_placeholder"
        for preview in previews
        if isinstance(preview, dict)
    )
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            errors.append(f"presentation field {index} must be an object")
            continue
        field_id = str(field.get("id", index))
        if field_id in field_ids:
            errors.append(f"duplicate presentation field id: {field_id}")
        field_ids.add(field_id)
        classification = field.get("classification")
        source_ref = field.get("source_ref")
        if classification == "source_bound":
            validate_source_ref(source_ref, f"field {field_id}")
        elif classification == "presentation_only" and source_ref is not None:
            errors.append(f"presentation_only field {field_id} must use null source_ref")

        if field_id == "story_curve":
            curve = field.get("value")
            if not isinstance(curve, dict):
                errors.append("story_curve value must be an object")
                continue
            duration = curve.get("duration")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
                errors.append("story_curve duration must be a positive number")
                duration = None
            if curve.get("source_kind") not in {"artifact", "confirmed_user_input", "creative_projection"}:
                errors.append("story_curve source_kind is invalid")
            series = curve.get("series")
            if not isinstance(series, list) or not 2 <= len(series) <= 5:
                errors.append("story_curve requires 2 to 5 series")
                series = []
            series_ids: set[str] = set()
            for series_index, item in enumerate(series):
                if not isinstance(item, dict):
                    errors.append(f"story_curve series {series_index} must be an object")
                    continue
                series_id = item.get("id")
                if not isinstance(series_id, str) or not series_id or series_id in series_ids:
                    errors.append(f"story_curve series {series_index} has missing or duplicate id")
                else:
                    series_ids.add(series_id)
                if not isinstance(item.get("label"), str) or not item.get("label", "").strip():
                    errors.append(f"story_curve series {series_id or series_index} requires a label")
                if not isinstance(item.get("insight"), str) or not item.get("insight", "").strip():
                    errors.append(f"story_curve series {series_id or series_index} requires an insight")
                points = item.get("points")
                if not isinstance(points, list) or len(points) < 2:
                    errors.append(f"story_curve series {series_id or series_index} requires at least 2 points")
                    continue
                previous_time = -1.0
                for point_index, point in enumerate(points):
                    if not isinstance(point, dict):
                        errors.append(f"story_curve series {series_id or series_index} point {point_index} must be an object")
                        continue
                    time = point.get("time")
                    value = point.get("value")
                    if not isinstance(time, (int, float)) or isinstance(time, bool):
                        errors.append(f"story_curve series {series_id or series_index} point {point_index} has invalid time")
                    elif time <= previous_time or (duration is not None and not 0 <= time <= duration):
                        errors.append(f"story_curve series {series_id or series_index} times must increase within duration")
                    else:
                        previous_time = float(time)
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 100:
                        errors.append(f"story_curve series {series_id or series_index} point {point_index} value must be 0..100")
            annotations = curve.get("annotations", [])
            if not isinstance(annotations, list):
                errors.append("story_curve annotations must be a list")
            else:
                for annotation_index, annotation in enumerate(annotations):
                    if not isinstance(annotation, dict):
                        errors.append(f"story_curve annotation {annotation_index} must be an object")
                        continue
                    time = annotation.get("time")
                    if not isinstance(time, (int, float)) or isinstance(time, bool) or (duration is not None and not 0 <= time <= duration):
                        errors.append(f"story_curve annotation {annotation_index} time is outside duration")
                    if not isinstance(annotation.get("label"), str) or not annotation.get("label", "").strip():
                        errors.append(f"story_curve annotation {annotation_index} requires a label")

        if field_id == "shot_rhythm":
            rhythm = field.get("value")
            if not isinstance(rhythm, dict):
                errors.append("shot_rhythm value must be an object")
                continue
            duration = rhythm.get("duration")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
                errors.append("shot_rhythm duration must be a positive number")
                duration = None
            shots = rhythm.get("shots")
            if not isinstance(shots, list) or not 2 <= len(shots) <= 30:
                errors.append("shot_rhythm requires 2 to 30 shots")
                shots = []
            shot_ids: set[str] = set()
            previous_end = 0.0
            required_text = ("label", "size", "movement", "action", "audio", "risk")
            for shot_index, shot in enumerate(shots):
                if not isinstance(shot, dict):
                    errors.append(f"shot_rhythm shot {shot_index} must be an object")
                    continue
                shot_id = shot.get("id")
                if not isinstance(shot_id, str) or not shot_id or shot_id in shot_ids:
                    errors.append(f"shot_rhythm shot {shot_index} has missing or duplicate id")
                else:
                    shot_ids.add(shot_id)
                start = shot.get("start")
                end = shot.get("end")
                if (
                    not isinstance(start, (int, float))
                    or isinstance(start, bool)
                    or not isinstance(end, (int, float))
                    or isinstance(end, bool)
                    or start < previous_end
                    or end <= start
                    or (duration is not None and end > duration)
                ):
                    errors.append(f"shot_rhythm shot {shot_id or shot_index} has invalid or overlapping timing")
                else:
                    previous_end = float(end)
                for key in required_text:
                    if not isinstance(shot.get(key), str) or not shot.get(key, "").strip():
                        errors.append(f"shot_rhythm shot {shot_id or shot_index} requires {key}")

        if field_id == "asset_graph":
            graph = field.get("value")
            if not isinstance(graph, dict):
                errors.append("asset_graph value must be an object")
                continue
            nodes = graph.get("nodes")
            edges = graph.get("edges")
            if not isinstance(nodes, list) or len(nodes) < 2:
                errors.append("asset_graph requires at least 2 nodes")
                nodes = []
            if not isinstance(edges, list) or not edges:
                errors.append("asset_graph requires at least 1 edge")
                edges = []
            node_ids: set[str] = set()
            for node_index, node in enumerate(nodes):
                if not isinstance(node, dict):
                    errors.append(f"asset_graph node {node_index} must be an object")
                    continue
                node_id = node.get("id")
                if not isinstance(node_id, str) or not node_id or node_id in node_ids:
                    errors.append(f"asset_graph node {node_index} has missing or duplicate id")
                else:
                    node_ids.add(node_id)
                if node.get("type") not in {"asset", "shot"}:
                    errors.append(f"asset_graph node {node_id or node_index} has invalid type")
                for key in ("label", "detail"):
                    if not isinstance(node.get(key), str) or not node.get(key, "").strip():
                        errors.append(f"asset_graph node {node_id or node_index} requires {key}")
            edge_ids: set[str] = set()
            for edge_index, edge in enumerate(edges):
                if not isinstance(edge, dict):
                    errors.append(f"asset_graph edge {edge_index} must be an object")
                    continue
                edge_id = edge.get("id")
                if not isinstance(edge_id, str) or not edge_id or edge_id in edge_ids:
                    errors.append(f"asset_graph edge {edge_index} has missing or duplicate id")
                else:
                    edge_ids.add(edge_id)
                if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
                    errors.append(f"asset_graph edge {edge_id or edge_index} references unknown node")
                if edge.get("kind") not in {"direct_input", "planning_reference", "inherits", "forbidden"}:
                    errors.append(f"asset_graph edge {edge_id or edge_index} has invalid kind")

        if field_id == "qa_delta":
            qa = field.get("value")
            if not isinstance(qa, dict):
                errors.append("qa_delta value must be an object")
                continue
            candidates = qa.get("candidates")
            dimensions = qa.get("dimensions")
            if not isinstance(candidates, list) or len(candidates) != 2:
                errors.append("qa_delta requires exactly 2 candidates")
                candidates = []
            qa_candidate_ids = set()
            for candidate_index, candidate in enumerate(candidates):
                if not isinstance(candidate, dict):
                    errors.append(f"qa_delta candidate {candidate_index} must be an object")
                    continue
                candidate_id = candidate.get("id")
                if not isinstance(candidate_id, str) or not candidate_id or candidate_id in qa_candidate_ids:
                    errors.append(f"qa_delta candidate {candidate_index} has missing or duplicate id")
                else:
                    qa_candidate_ids.add(candidate_id)
                for key in ("label", "judgment", "blocker", "retry", "preserve", "action_label", "conversation_intent"):
                    if not isinstance(candidate.get(key), str) or not candidate.get(key, "").strip():
                        errors.append(f"qa_delta candidate {candidate_id or candidate_index} requires {key}")
            if not isinstance(dimensions, list) or not 3 <= len(dimensions) <= 10:
                errors.append("qa_delta requires 3 to 10 dimensions")
                dimensions = []
            dimension_ids: set[str] = set()
            for dimension_index, dimension in enumerate(dimensions):
                if not isinstance(dimension, dict):
                    errors.append(f"qa_delta dimension {dimension_index} must be an object")
                    continue
                dimension_id = dimension.get("id")
                if not isinstance(dimension_id, str) or not dimension_id or dimension_id in dimension_ids:
                    errors.append(f"qa_delta dimension {dimension_index} has missing or duplicate id")
                else:
                    dimension_ids.add(dimension_id)
                for key in ("label", "target"):
                    if not isinstance(dimension.get(key), str) or not dimension.get(key, "").strip():
                        errors.append(f"qa_delta dimension {dimension_id or dimension_index} requires {key}")
                results = dimension.get("results")
                if not isinstance(results, dict):
                    errors.append(f"qa_delta dimension {dimension_id or dimension_index} requires results")
                    continue
                for candidate_id in qa_candidate_ids:
                    result = results.get(candidate_id)
                    if not isinstance(result, dict):
                        errors.append(f"qa_delta dimension {dimension_id or dimension_index} missing result for {candidate_id}")
                        continue
                    if result.get("status") not in {"pass", "warn", "fail"}:
                        errors.append(f"qa_delta dimension {dimension_id or dimension_index} has invalid status for {candidate_id}")
                    elif has_placeholder_preview and result.get("status") != "warn":
                        errors.append("illustrative placeholder QA results must remain pending")
                    if not isinstance(result.get("value"), str) or not result.get("value", "").strip():
                        errors.append(f"qa_delta dimension {dimension_id or dimension_index} requires value for {candidate_id}")

        if field_id == "visual_board":
            board = field.get("value")
            if not isinstance(board, dict):
                errors.append("visual_board value must be an object")
                continue
            directions = board.get("directions")
            if not isinstance(directions, list) or not 2 <= len(directions) <= 3:
                errors.append("visual_board requires 2 to 3 directions")
                directions = []
            visual_direction_ids = set()
            for direction_index, direction in enumerate(directions):
                if not isinstance(direction, dict):
                    errors.append(f"visual_board direction {direction_index} must be an object")
                    continue
                direction_id = direction.get("id")
                if not isinstance(direction_id, str) or not direction_id or direction_id in visual_direction_ids:
                    errors.append(f"visual_board direction {direction_index} has missing or duplicate id")
                else:
                    visual_direction_ids.add(direction_id)
                for key in ("judgment", "lighting", "impact"):
                    if not isinstance(direction.get(key), str) or not direction.get(key, "").strip():
                        errors.append(f"visual_board direction {direction_id or direction_index} requires {key}")
                palette = direction.get("palette")
                if not isinstance(palette, list) or not 3 <= len(palette) <= 5:
                    errors.append(f"visual_board direction {direction_id or direction_index} requires 3 to 5 palette colors")
                else:
                    for color_index, color in enumerate(palette):
                        if not isinstance(color, dict) or not isinstance(color.get("label"), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(color.get("color", ""))):
                            errors.append(f"visual_board direction {direction_id or direction_index} has invalid palette color {color_index}")
                for key in ("materials", "optics", "allow", "avoid"):
                    values = direction.get(key)
                    if not isinstance(values, list) or not 1 <= len(values) <= 5 or not all(isinstance(item, str) and item.strip() for item in values):
                        errors.append(f"visual_board direction {direction_id or direction_index} requires 1 to 5 {key} values")

    options = presentation.get("options") if isinstance(presentation.get("options"), list) else []
    if len(options) > 3:
        errors.append("presentation supports at most 3 options")
    option_ids: set[str] = set()
    option_map: dict[str, dict[str, Any]] = {}
    for index, option in enumerate(options):
        if not isinstance(option, dict):
            errors.append(f"option {index} must be an object")
            continue
        option_id = str(option.get("id", index))
        if option_id in option_ids:
            errors.append(f"duplicate option id: {option_id}")
        option_ids.add(option_id)
        option_map[option_id] = option
        refs = option.get("source_refs") if isinstance(option.get("source_refs"), list) else []
        if not refs:
            errors.append(f"option {option_id} has no source_refs")
        for source_ref in refs:
            validate_source_ref(source_ref, f"option {option_id}")
        details = option.get("details") if isinstance(option.get("details"), list) else []
        detail_ids = [item.get("id") for item in details if isinstance(item, dict)]
        if len(detail_ids) != len(set(detail_ids)):
            errors.append(f"option {option_id} has duplicate detail ids")

    if view.get("intent") == "compare" and len(options) < 2:
        errors.append("compare view requires at least 2 options")
    recommendation = presentation.get("recommendation")
    if isinstance(recommendation, dict) and recommendation.get("option_id") not in option_ids:
        errors.append("recommendation references an option not present in the view")
    if has_placeholder_preview and recommendation is not None:
        errors.append("illustrative placeholder preview cannot carry a recommendation")
    if qa_candidate_ids is not None and qa_candidate_ids != option_ids:
        errors.append("qa_delta candidates must match presentation options")
    if visual_direction_ids is not None and visual_direction_ids != option_ids:
        errors.append("visual_board directions must match presentation options")
    if previews and not preview_option_ids.issubset(option_ids):
        errors.append("preview option_ids must match presentation options")
    for index, preview in enumerate(previews):
        if not isinstance(preview, dict):
            continue
        option = option_map.get(str(preview.get("option_id")))
        expected_prefix = f'{preview.get("artifact_id")}#/'
        if option is not None and not any(
            isinstance(source_ref, str) and source_ref.startswith(expected_prefix)
            for source_ref in option.get("source_refs", [])
        ):
            errors.append(f"preview {index} image artifact is not bound to its option source_refs")

    actions = interactions.get("actions") if isinstance(interactions.get("actions"), list) else []
    if not 1 <= len(actions) <= 2:
        errors.append("interaction action count must be between 1 and 2")
    action_ids: set[str] = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"action {index} must be an object")
            continue
        action_id = str(action.get("id", index))
        if action_id in action_ids:
            errors.append(f"duplicate action id: {action_id}")
        action_ids.add(action_id)
        if action.get("target_gate_id") != gate_id:
            errors.append(f"action {action_id} does not target current gate")
        if has_placeholder_preview and action.get("kind") not in {"request_revision", "stop"}:
            errors.append("illustrative placeholder preview may only request a real candidate or stop")
    if interactions.get("max_actions") != 2:
        errors.append("max_actions must be 2")
    if interactions.get("deep_navigation") is not False:
        errors.append("deep_navigation must be false")
    if interactions.get("nested_scroll") is not False:
        errors.append("nested_scroll must be false")
    if has_placeholder_preview and not any(action.get("kind") == "request_revision" for action in actions if isinstance(action, dict)):
        errors.append("illustrative placeholder preview requires a request_revision action for a real candidate")

    if write_boundary.get("preview_only") is not True:
        errors.append("visualization must remain preview_only")
    if write_boundary.get("confirmation_required") is not True:
        errors.append("visualization must require confirmation")
    if write_boundary.get("writes_authoritative_state") is not False:
        errors.append("visualization cannot write authoritative state")
    claims = set(write_boundary.get("forbidden_claims", []))
    missing_claims = sorted(REQUIRED_FORBIDDEN_CLAIMS - claims)
    if missing_claims:
        errors.append("missing forbidden claims: " + ", ".join(missing_claims))

    if execution_context == "standalone_chat":
        if controller.get("surface_owner") != "dircreative" or controller.get("user_facing") is not True:
            errors.append("standalone_chat requires DIRcreative user-facing controller")
        if write_boundary.get("write_owner") != "dircreative":
            errors.append("standalone_chat write_owner must be dircreative")
    elif execution_context == "orchestrated_worker":
        if controller.get("surface_owner") != "ad-creative-orchestrator" or controller.get("user_facing") is not False:
            errors.append("orchestrated_worker visualization must remain ADCO-controlled and provider-hidden")
        if write_boundary.get("write_owner") != "ad-creative-orchestrator":
            errors.append("orchestrated_worker write_owner must be ad-creative-orchestrator")

    fallback_fields = set(fallback.get("required_visible_fields", []))
    missing_fallback = sorted(REQUIRED_FALLBACK_FIELDS - fallback_fields)
    if options and "options" not in fallback_fields:
        missing_fallback.append("options")
    if missing_fallback:
        errors.append("fallback missing visible fields: " + ", ".join(missing_fallback))
    if not isinstance(fallback.get("decision_question"), str) or not fallback.get("decision_question", "").strip():
        errors.append("fallback requires a decision question")

    return errors


def validate_document(
    document: Any,
    schema_path: Path = DEFAULT_SCHEMA,
    project_root: Path = ROOT,
) -> list[str]:
    return schema_errors(document, schema_path) + semantic_errors(document, project_root)


def customer_stage_label(value: Any) -> str:
    text = str(value)
    return CUSTOMER_STAGE_LABELS.get(text, text)


def render_fallback(document: dict[str, Any]) -> str:
    gate = document["stage_gate"]
    view = document["view"]
    presentation = document["presentation"]
    fallback = document["fallback"]
    lines = [
        f"阶段: {view['customer_stage_label']}",
        "",
        f"当前状态: {gate['status']}",
        f"当前决定: {view['decision_prompt']}",
        "",
    ]
    options = presentation.get("options", [])
    if options:
        lines.extend(["| 选项 | 核心内容 | 制作权衡 |", "| --- | --- | --- |"])
        for option in options:
            detail_text = "；".join(
                f"{item['label']}: {item['value']}" for item in option.get("details", [])
            )
            summary = option["summary"] + (f"；{detail_text}" if detail_text else "")
            lines.append(f"| {option['label']} | {summary} | {option['tradeoff']} |")
        lines.append("")
    curve_field = next((field for field in presentation.get("fields", []) if field.get("id") == "story_curve"), None)
    curve = curve_field.get("value") if isinstance(curve_field, dict) else None
    if isinstance(curve, dict) and isinstance(curve.get("series"), list):
        labels = [item.get("label", item.get("id", "曲线")) for item in curve["series"]]
        point_maps = [
            {point.get("time"): point.get("value") for point in item.get("points", []) if isinstance(point, dict)}
            for item in curve["series"]
        ]
        times = sorted({time for point_map in point_maps for time in point_map if isinstance(time, (int, float))})
        source_label = "创作推演" if curve.get("source_kind") == "creative_projection" else "已确认数据"
        lines.extend([
            f"曲线性质: {source_label}",
            "",
            "| 时间 | " + " | ".join(str(label) for label in labels) + " |",
            "| --- | " + " | ".join("---" for _ in labels) + " |",
        ])
        for time in times:
            values = [str(point_map.get(time, "—")) for point_map in point_maps]
            lines.append(f"| {time:g}s | " + " | ".join(values) + " |")
        lines.append("")
        for item in curve["series"]:
            lines.append(f"- {item.get('label', item.get('id', '曲线'))}: {item.get('insight', '')}")
        lines.append("")
    rhythm_field = next((field for field in presentation.get("fields", []) if field.get("id") == "shot_rhythm"), None)
    rhythm = rhythm_field.get("value") if isinstance(rhythm_field, dict) else None
    if isinstance(rhythm, dict) and isinstance(rhythm.get("shots"), list):
        lines.extend([
            "| 镜头 | 时间 | 景别 | 运动 | 动作 | 声音 | 风险 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for shot in rhythm["shots"]:
            lines.append(
                f"| {shot.get('id', '')} {shot.get('label', '')} | {shot.get('start', 0):g}–{shot.get('end', 0):g}s | "
                f"{shot.get('size', '')} | {shot.get('movement', '')} | {shot.get('action', '')} | "
                f"{shot.get('audio', '')} | {shot.get('risk', '')} |"
            )
        lines.append("")
    graph_field = next((field for field in presentation.get("fields", []) if field.get("id") == "asset_graph"), None)
    graph = graph_field.get("value") if isinstance(graph_field, dict) else None
    if isinstance(graph, dict) and isinstance(graph.get("nodes"), list) and isinstance(graph.get("edges"), list):
        node_labels = {node.get("id"): node.get("label", node.get("id", "")) for node in graph["nodes"]}
        lines.extend([
            "| 参考素材 | 关系 | 镜头 |",
            "| --- | --- | --- |",
        ])
        relationship_labels = {
            "direct_input": "直接使用",
            "planning_reference": "仅策划参考",
            "inherits": "继承",
            "forbidden": "禁止使用",
        }
        for edge in graph["edges"]:
            lines.append(
                f"| {node_labels.get(edge.get('source'), edge.get('source', ''))} | "
                f"{relationship_labels.get(edge.get('kind'), edge.get('kind', ''))} | "
                f"{node_labels.get(edge.get('target'), edge.get('target', ''))} |"
            )
        lines.append("")
    qa_field = next((field for field in presentation.get("fields", []) if field.get("id") == "qa_delta"), None)
    qa = qa_field.get("value") if isinstance(qa_field, dict) else None
    if isinstance(qa, dict) and isinstance(qa.get("candidates"), list) and isinstance(qa.get("dimensions"), list):
        candidate_labels = {candidate.get("id"): candidate.get("label", candidate.get("id", "")) for candidate in qa["candidates"]}
        candidate_ids = list(candidate_labels)
        lines.extend([
            "媒体状态: " + str(qa.get("media_status", "未说明")),
            "",
            "| 检查维度 | 目标 | " + " | ".join(candidate_labels[candidate_id] for candidate_id in candidate_ids) + " |",
            "| --- | --- | " + " | ".join("---" for _ in candidate_ids) + " |",
        ])
        status_labels = {"pass": "通过", "warn": "需注意", "fail": "失败"}
        for dimension in qa["dimensions"]:
            results = []
            for candidate_id in candidate_ids:
                result = dimension.get("results", {}).get(candidate_id, {})
                results.append(f"{status_labels.get(result.get('status'), result.get('status', ''))}: {result.get('value', '')}")
            lines.append(f"| {dimension.get('label', '')} | {dimension.get('target', '')} | " + " | ".join(results) + " |")
        lines.append("")
    board_field = next((field for field in presentation.get("fields", []) if field.get("id") == "visual_board"), None)
    board = board_field.get("value") if isinstance(board_field, dict) else None
    if isinstance(board, dict) and isinstance(board.get("directions"), list):
        lines.extend([
            "| 视觉方向 | 色板 | 光线 | 材质 | 镜头语言 | 允许 | 避开 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        option_labels = {option.get("id"): option.get("label", option.get("id", "")) for option in presentation.get("options", [])}
        for direction in board["directions"]:
            palette = "、".join(color.get("label", "") for color in direction.get("palette", []))
            lines.append(
                f"| {option_labels.get(direction.get('id'), direction.get('id', ''))} | {palette} | {direction.get('lighting', '')} | "
                f"{'、'.join(direction.get('materials', []))} | {'、'.join(direction.get('optics', []))} | "
                f"{'、'.join(direction.get('allow', []))} | {'、'.join(direction.get('avoid', []))} |"
            )
        lines.append("")
    effects = presentation.get("downstream_effects", [])
    if effects:
        lines.append("下游影响:")
        lines.extend(f"- {customer_stage_label(effect['stage'])}: {effect['effect']}" for effect in effects)
        lines.append("")
    lines.append(f"用户确认点: {fallback['decision_question']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIRcreative chat visualization specs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.add_argument("--project-root")
    fallback_parser = subparsers.add_parser("render-fallback")
    fallback_parser.add_argument("path")
    fallback_parser.add_argument("--project-root")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    try:
        document = load_document(path)
    except SpecLoadError as exc:
        print(f"CHAT_VISUALIZATION_SPEC: FAIL\n- {exc}")
        return 1
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else ROOT
    errors = validate_document(document, project_root=project_root)
    if errors:
        print("CHAT_VISUALIZATION_SPEC: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    if args.command == "render-fallback":
        print(render_fallback(document))
    else:
        print("CHAT_VISUALIZATION_SPEC: PASS")
        print(f"view_id: {document['view_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
