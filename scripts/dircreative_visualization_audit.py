#!/usr/bin/env python3
from __future__ import annotations

import json
import copy
import hashlib
import sys
import tempfile
from pathlib import Path

from dircreative_visualization_spec import load_document, render_fallback, schema_errors, validate_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/chat-visualization"
MANIFEST = FIXTURE_ROOT / "manifest.json"
REGISTRY = ROOT / "skills/dircreative/assets/visualizations/stage-surface-registry.json"
REQUIRED_SKILLS = {
    "chat-facilitator",
    "co-creation-gate-runtime",
    "director-room",
    "story-development",
    "script-treatment",
    "shot-design",
    "visual-bible",
    "reference-image-planner",
    "image-prompt-compiler",
    "video-model-adapter",
    "generation-qa",
    "checkpoint",
}
ACTION_KINDS = {
    "submit_selection",
    "request_revision",
    "request_mix",
    "request_fullscreen",
    "retry_smallest",
    "stop",
    "pause_prompt_only",
}


def registry_errors() -> list[str]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    errors: list[str] = []
    if registry.get("registry_version") not in {"1.0", "1.1"}:
        errors.append("registry_version must be 1.0 or 1.1")
    if registry.get("spec_contract") != f"dircreative.chat-visualization@{registry.get('registry_version')}":
        errors.append("registry spec_contract mismatch")
    surfaces = registry.get("surfaces") if isinstance(registry.get("surfaces"), list) else []
    skill_ids = {surface.get("skill_id") for surface in surfaces if isinstance(surface, dict)}
    missing = sorted(REQUIRED_SKILLS - skill_ids)
    if missing:
        errors.append("registry missing skills: " + ", ".join(missing))
    surface_ids: set[str] = set()
    for surface in surfaces:
        surface_id = surface.get("surface_id")
        if not surface_id or surface_id in surface_ids:
            errors.append(f"missing or duplicate surface_id: {surface_id}")
        surface_ids.add(surface_id)
        if surface.get("requires_gate", True) and not surface.get("gate_types"):
            errors.append(f"{surface_id} has no gate_types")
        if surface.get("requires_gate", True) and len(surface.get("minimum_visible_fields", [])) < 4:
            errors.append(f"{surface_id} needs at least four visible fields")
        actions = set(surface.get("primary_action_kinds", [])) | set(surface.get("secondary_action_kinds", []))
        unknown = sorted(actions - ACTION_KINDS)
        if unknown:
            errors.append(f"{surface_id} has unknown actions: {unknown}")
        if surface.get("fallback") not in {"markdown", "table", "mermaid"}:
            errors.append(f"{surface_id} has invalid fallback")
    return errors


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    print("DIRcreative Chat Visualization Audit")
    print("=" * 72)

    registry_failures = registry_errors()
    if registry_failures:
        failures.extend(registry_failures)
        print("[FAIL] stage-surface-registry.json")
    else:
        print("[PASS] stage-surface-registry.json")

    for filename in manifest["valid"]:
        path = FIXTURE_ROOT / filename
        errors = validate_document(load_document(path))
        if errors:
            failures.append(f"{filename}: expected PASS, got {errors}")
            print(f"[FAIL] {filename}")
        else:
            print(f"[PASS] {filename}")

    invalid_curve = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-story-beat-ribbon-inline.json"))
    curve_value = next(field["value"] for field in invalid_curve["presentation"]["fields"] if field["id"] == "story_curve")
    curve_value["series"][0]["points"][1]["time"] = curve_value["series"][0]["points"][0]["time"]
    curve_errors = "\n".join(validate_document(invalid_curve))
    if "times must increase within duration" not in curve_errors:
        failures.append("invalid story curve time order was not rejected")
        print("[FAIL] invalid story curve time order")
    else:
        print("[PASS] invalid story curve time order rejected")

    presentation_only_with_gate = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-blocking-camera-presentation-only.json"))
    presentation_only_with_gate["stage_gate"] = {
        "id": "forged-layout-gate",
        "type": "shot_list_approval_gate",
        "status": "needs_user",
        "decision_owner": "user",
    }
    presentation_only_errors = "\n".join(validate_document(presentation_only_with_gate))
    if "presentation_only visualization must not create a stage_gate" not in presentation_only_errors:
        failures.append("presentation-only visualization accepted a fabricated gate")
        print("[FAIL] presentation-only fabricated gate")
    else:
        print("[PASS] presentation-only fabricated gate rejected")

    schema_action_overflow = load_document(FIXTURE_ROOT / "invalid-action-overflow.json")
    schema_action_overflow_errors = "\n".join(schema_errors(schema_action_overflow))
    if not any(marker in schema_action_overflow_errors for marker in ("is too long", "expected at most 2 items")):
        failures.append("schema-only maxItems action overflow was not rejected")
        print("[FAIL] schema-only maxItems action overflow")
    else:
        print("[PASS] schema-only maxItems action overflow rejected")

    invalid_rhythm = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-shot-timeline-fullscreen.json"))
    rhythm_value = next(field["value"] for field in invalid_rhythm["presentation"]["fields"] if field["id"] == "shot_rhythm")
    rhythm_value["shots"][1]["start"] = rhythm_value["shots"][0]["end"] - 1
    rhythm_errors = "\n".join(validate_document(invalid_rhythm))
    if "invalid or overlapping timing" not in rhythm_errors:
        failures.append("invalid shot rhythm overlap was not rejected")
        print("[FAIL] invalid shot rhythm overlap")
    else:
        print("[PASS] invalid shot rhythm overlap rejected")

    invalid_graph = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-reference-asset-graph-fullscreen.json"))
    graph_value = next(field["value"] for field in invalid_graph["presentation"]["fields"] if field["id"] == "asset_graph")
    graph_value["edges"][0]["target"] = "missing-shot"
    graph_errors = "\n".join(validate_document(invalid_graph))
    if "references unknown node" not in graph_errors:
        failures.append("invalid asset graph edge was not rejected")
        print("[FAIL] invalid asset graph edge")
    else:
        print("[PASS] invalid asset graph edge rejected")

    invalid_qa = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    qa_value = next(field["value"] for field in invalid_qa["presentation"]["fields"] if field["id"] == "qa_delta")
    del qa_value["dimensions"][0]["results"]["candidate-b"]
    qa_errors = "\n".join(validate_document(invalid_qa))
    if "missing result for candidate-b" not in qa_errors:
        failures.append("invalid QA candidate result was not rejected")
        print("[FAIL] invalid QA candidate result")
    else:
        print("[PASS] invalid QA candidate result rejected")

    invalid_image_hash = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_image_hash["source_truth"]["artifacts"][2]["sha256"] = "0" * 64
    image_hash_errors = "\n".join(validate_document(invalid_image_hash))
    if "image sha256 mismatch" not in image_hash_errors:
        failures.append("invalid image preview hash was not rejected")
        print("[FAIL] invalid image preview hash")
    else:
        print("[PASS] invalid image preview hash rejected")

    invalid_real_candidate = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_real_candidate["source_truth"]["artifacts"][2]["lifecycle_status"] = "stale"
    real_candidate_errors = "\n".join(validate_document(invalid_real_candidate))
    if "real candidate requires current lifecycle and confirmed source, authorization, and channel fit" not in real_candidate_errors:
        failures.append("stale real image candidate was not rejected")
        print("[FAIL] stale real image candidate")
    else:
        print("[PASS] stale real image candidate rejected")

    invalid_self_evidence = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_self_evidence["source_truth"]["artifacts"][2]["source_evidence_ref"] = "candidate-a-preview#/self_claim"
    self_evidence_errors = "\n".join(validate_document(invalid_self_evidence))
    if "cannot self-reference the image artifact" not in self_evidence_errors:
        failures.append("self-declared real image evidence was not rejected")
        print("[FAIL] self-declared real image evidence")
    else:
        print("[PASS] self-declared real image evidence rejected")

    invalid_cross_image_evidence = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_cross_image_evidence["source_truth"]["artifacts"][2]["source_evidence_ref"] = "candidate-b-preview#/image"
    cross_image_errors = "\n".join(validate_document(invalid_cross_image_evidence))
    if "must reference a non-image evidence artifact" not in cross_image_errors:
        failures.append("cross-image provenance evidence was not rejected")
        print("[FAIL] cross-image provenance evidence")
    else:
        print("[PASS] cross-image provenance evidence rejected")

    invalid_evidence_pointer = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_evidence_pointer["source_truth"]["artifacts"][2]["source_evidence_ref"] = "qa-report-01#/does/not/exist"
    evidence_pointer_errors = "\n".join(validate_document(invalid_evidence_pointer))
    if "references missing evidence content" not in evidence_pointer_errors:
        failures.append("missing evidence JSON Pointer was not rejected")
        print("[FAIL] missing evidence JSON Pointer")
    else:
        print("[PASS] missing evidence JSON Pointer rejected")

    invalid_evidence_lifecycle = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_evidence_lifecycle["source_truth"]["artifacts"][0]["lifecycle_status"] = "stale"
    evidence_lifecycle_errors = "\n".join(validate_document(invalid_evidence_lifecycle))
    if "evidence record must have current lifecycle" not in evidence_lifecycle_errors:
        failures.append("stale evidence record was not rejected")
        print("[FAIL] stale evidence record")
    else:
        print("[PASS] stale evidence record rejected")

    invalid_evidence_hash = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_evidence_hash["source_truth"]["artifacts"][0]["sha256"] = "0" * 64
    evidence_hash_errors = "\n".join(validate_document(invalid_evidence_hash))
    if "evidence sha256 mismatch" not in evidence_hash_errors:
        failures.append("invalid evidence record hash was not rejected")
        print("[FAIL] invalid evidence record hash")
    else:
        print("[PASS] invalid evidence record hash rejected")

    with tempfile.TemporaryDirectory(prefix="dircreative-evidence-content-") as raw:
        evidence_root = Path(raw)
        evidence_project = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
        for artifact in evidence_project["source_truth"]["artifacts"]:
            artifact_path_key = "path" if artifact.get("path") else "evidence_path" if artifact.get("evidence_path") else None
            if artifact_path_key is None:
                continue
            source = ROOT / artifact[artifact_path_key]
            target = evidence_root / source.name
            target.write_bytes(source.read_bytes())
            artifact[artifact_path_key] = target.name
        candidate_index_path = evidence_root / "candidate-index-01.json"
        candidate_index = json.loads(candidate_index_path.read_text(encoding="utf-8"))
        candidate_index["candidates"][0]["source"]["status"] = "unconfirmed"
        candidate_index_path.write_text(json.dumps(candidate_index, ensure_ascii=False), encoding="utf-8")
        evidence_project["source_truth"]["artifacts"][1]["sha256"] = hashlib.sha256(candidate_index_path.read_bytes()).hexdigest()
        evidence_content_errors = "\n".join(validate_document(evidence_project, project_root=evidence_root))
        if "must resolve to confirmed evidence content" not in evidence_content_errors:
            failures.append("unconfirmed evidence content was not rejected")
            print("[FAIL] unconfirmed evidence content")
        else:
            print("[PASS] unconfirmed evidence content rejected")

    invalid_preview_binding = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    invalid_preview_binding["presentation"]["previews"][0]["option_id"] = "candidate-b"
    invalid_preview_binding["presentation"]["previews"][1]["option_id"] = "candidate-a"
    preview_binding_errors = "\n".join(validate_document(invalid_preview_binding))
    if "image artifact is not bound to its option source_refs" not in preview_binding_errors:
        failures.append("swapped candidate image binding was not rejected")
        print("[FAIL] swapped candidate image binding")
    else:
        print("[PASS] swapped candidate image binding rejected")

    invalid_placeholder_action = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    for artifact in invalid_placeholder_action["source_truth"]["artifacts"][2:4]:
        artifact["review_classification"] = "illustrative_placeholder"
        artifact["source_status"] = "unconfirmed"
        artifact["authorization_status"] = "not_applicable"
        artifact["channel_fit_status"] = "not_applicable"
        for key in ("source_evidence_ref", "authorization_evidence_ref", "channel_fit_evidence_ref"):
            artifact.pop(key, None)
    placeholder_action_errors = "\n".join(validate_document(invalid_placeholder_action))
    if "illustrative placeholder preview may only request a real candidate or stop" not in placeholder_action_errors:
        failures.append("placeholder image retry action was not rejected")
        print("[FAIL] placeholder image retry action")
    else:
        print("[PASS] placeholder image retry action rejected")

    with tempfile.TemporaryDirectory(prefix="dircreative-external-image-project-") as raw:
        project_root = Path(raw)
        media_root = project_root / "media"
        media_root.mkdir()
        external_project = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
        for artifact in external_project["source_truth"]["artifacts"]:
            artifact_path_key = "path" if artifact.get("path") else "evidence_path" if artifact.get("evidence_path") else None
            if artifact_path_key is None:
                continue
            source = ROOT / artifact[artifact_path_key]
            relative = Path("media") / source.name
            target = project_root / relative
            target.write_bytes(source.read_bytes())
            artifact[artifact_path_key] = relative.as_posix()
        external_project_errors = validate_document(external_project, project_root=project_root)
        if external_project_errors:
            failures.append(f"external project image paths were rejected: {external_project_errors}")
            print("[FAIL] external project image paths")
        else:
            print("[PASS] external project image paths accepted")

        active_svg = media_root / "active.svg"
        active_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" onload="alert(1)"></svg>', encoding="utf-8")
        external_project["source_truth"]["artifacts"][2]["path"] = "media/active.svg"
        external_project["source_truth"]["artifacts"][2]["mime_type"] = "image/svg+xml"
        external_project["source_truth"]["artifacts"][2]["sha256"] = hashlib.sha256(active_svg.read_bytes()).hexdigest()
        active_svg_errors = "\n".join(validate_document(external_project, project_root=project_root))
        if "contains active or external SVG content" not in active_svg_errors:
            failures.append("active SVG event handler was not rejected")
            print("[FAIL] active SVG event handler")
        else:
            print("[PASS] active SVG event handler rejected")

        oversized_pixels = media_root / "oversized.png"
        oversized_pixels.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (10000).to_bytes(4, "big") + (10000).to_bytes(4, "big"))
        external_project["source_truth"]["artifacts"][2]["path"] = "media/oversized.png"
        external_project["source_truth"]["artifacts"][2]["mime_type"] = "image/png"
        external_project["source_truth"]["artifacts"][2]["sha256"] = hashlib.sha256(oversized_pixels.read_bytes()).hexdigest()
        oversized_pixel_errors = "\n".join(validate_document(external_project, project_root=project_root))
        if "image exceeds 16000000 pixels" not in oversized_pixel_errors:
            failures.append("oversized image pixel dimensions were not rejected")
            print("[FAIL] oversized image pixel dimensions")
        else:
            print("[PASS] oversized image pixel dimensions rejected")

    invalid_board = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-visual-direction-compare-inline.json"))
    board_value = next(field["value"] for field in invalid_board["presentation"]["fields"] if field["id"] == "visual_board")
    board_value["directions"][0]["palette"][0]["color"] = "warm-gray"
    board_errors = "\n".join(validate_document(invalid_board))
    if "invalid palette color" not in board_errors:
        failures.append("invalid visual board palette was not rejected")
        print("[FAIL] invalid visual board palette")
    else:
        print("[PASS] invalid visual board palette rejected")

    video_fallback = render_fallback(load_document(FIXTURE_ROOT / "valid-video-route-capability-inline.json"))
    for label in ("模型路线", "时长", "参考素材", "音频", "可靠程度", "主要风险"):
        if label not in video_fallback:
            failures.append(f"video route fallback missing customer-facing detail: {label}")

    for item in manifest["invalid"]:
        filename = item["file"]
        expected = item["expected_error"]
        path = FIXTURE_ROOT / filename
        errors = validate_document(load_document(path))
        joined = "\n".join(errors)
        if not errors:
            failures.append(f"{filename}: expected rejection but passed")
            print(f"[FAIL] {filename}")
        elif expected not in joined:
            failures.append(f"{filename}: missing expected error {expected!r}; got {joined!r}")
            print(f"[FAIL] {filename}")
        else:
            print(f"[PASS] {filename} rejected: {expected}")

    print(f"CHAT_VISUALIZATION_AUDIT: {'PASS' if not failures else 'FAIL'}")
    if failures:
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
