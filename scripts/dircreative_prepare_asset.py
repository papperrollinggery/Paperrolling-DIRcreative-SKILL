#!/usr/bin/env python3
"""Prepare one foundation-asset Jingzao call without generating media.

This is deliberately a narrow convenience layer over the existing DIRcreative
handoff, foundation-pass and execution-gate contracts.  It accepts an authored
design-stage payload; it never derives design facts from an asset purpose.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import os
import re
from pathlib import Path
from typing import Any

import dircreative_asset_execution_gate as execution_gate
import dircreative_asset_foundation_pass as foundation
import dircreative_visual_asset_jingzao_handoff as handoff
from dircreative_verify_release import read_relative_regular_file_once
from dircreative_visual_asset_plan import validate_plan


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROVIDER = Path.home() / ".codex/skills/jingzao-image-forge"
ROLE_STAGE = {
    "character_identity_reference": ("identity_state", "character_continuity", "minimum-visual-bible", "character-continuity-bible", "skills/dircreative/references/character-master-sheet.md"),
    "product_identity_board": ("production_design", "production_design", "production-design-worldbuilding", None, "skills/dircreative/references/asset-foundation-pass.md"),
    "prop_continuity_board": ("production_design", "production_design", "production-design-worldbuilding", None, "skills/dircreative/references/asset-foundation-pass.md"),
    "scene_geography_camera_fov_reference": ("camera_geography", "camera_geography", "master-shot-camera-planning", None, "skills/dircreative/references/asset-foundation-pass.md"),
    "lighting_material_style_board": ("material_response", "material_physics", "ai-material-realism", None, "skills/dircreative/references/asset-foundation-pass.md"),
}
REQUIRED_RUNTIME = tuple(sorted(handoff.REQUIRED_PROVIDER_RUNTIME_FILES))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> str:
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def read_json(root: Path, relative: str, label: str) -> tuple[dict[str, Any], bytes]:
    contained_regular_file(root, relative, label)
    raw = read_relative_regular_file_once(root, relative, max_bytes=8 * 1024 * 1024, label=label)
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{label}_must_be_object")
    return value, raw


def bind(root: Path, path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    return {"relative_path": path.relative_to(root).as_posix(), "sha256": sha(raw)}


def contained_regular_file(root: Path, relative: str, label: str) -> Path:
    """Resolve one project input without accepting a symlink as provenance."""
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"{label}_path_invalid")
    candidate = root / relative
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label}_symlink_not_allowed")
    resolved = candidate.resolve(strict=True)
    resolved.relative_to(root)
    if not resolved.is_file():
        raise ValueError(f"{label}_not_regular_file")
    return resolved


def safe_output_dir(root: Path, relative: str) -> Path:
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValueError("output_dir_symlink_not_allowed")
    current.mkdir(parents=True, exist_ok=True)
    current.resolve(strict=True).relative_to(root)
    return current


def write_immutable(root: Path, relative: str, value: Any) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("output_exists_for_different_input")
    else:
        with path.open("xb") as handle:
            handle.write(raw)
    return {"relative_path": relative, "sha256": sha(raw)}


def provider_file(provider: Path, relative: str) -> dict[str, Any]:
    path = provider / relative
    raw = path.read_bytes()
    return {"relative_path": relative, "sha256": sha(raw), "bytes": len(raw)}


def call_json(argv: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("provider_or_selector_failed: " + (result.stderr or result.stdout).strip())
    text = result.stdout.strip()
    if text == "VALID":
        return {"valid": True, "errors": []}
    try:
        value = json.JSONDecoder().raw_decode(text[text.index("{"):])[0]
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("provider_or_selector_json_invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("provider_or_selector_result_invalid")
    return value


def source_references(spec: dict[str, Any], *, source_dir: Path, output_dir: Path, root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Keep caller-declared provenance; do not infer ownership or approval."""
    prepared = copy.deepcopy(spec)
    inputs = prepared.get("inputs", [])
    if not isinstance(inputs, list):
        raise ValueError("source_spec_inputs_invalid")
    refs: list[dict[str, Any]] = []
    for item in inputs:
        if not isinstance(item, dict) or not item.get("must_attach"):
            continue
        required = ("id", "role", "source_kind", "source_ref", "rights_status", "approval_status")
        if any(not isinstance(item.get(key), str) or not item[key] for key in required):
            raise ValueError("required_reference_provenance_missing")
        if item["source_kind"] != "local_path":
            raise ValueError("required_reference_must_be_local_path")
        lexical = source_dir / item["source_ref"]
        # Resolve ordinary ../refs paths without concealing symlink traversal.
        for parent in (lexical, *lexical.parents):
            if parent == root:
                break
            if parent.is_symlink():
                raise ValueError("required_reference_symlink_not_allowed")
        source_ref = Path(os.path.normpath(lexical)).relative_to(root).as_posix()
        path = contained_regular_file(root, source_ref, "required_reference")
        refs.append({"input_id": item["id"], "asset_id": f"reference-{item['id']}", "role": item["role"],
                     "relative_path": path.relative_to(root).as_posix(), "sha256": sha(path.read_bytes()),
                     "rights_status": item["rights_status"], "approval_status": item["approval_status"]})
        # These fields are provenance for DIR, not part of the provider prompt schema.
        item.pop("rights_status"); item.pop("approval_status")
        item["source_ref"] = os.path.relpath(path, output_dir)
    return prepared, refs


def design_document(*, root: Path, out: str, plan: dict[str, Any], asset: dict[str, Any], design: dict[str, Any], design_binding: dict[str, str], references: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, str]]:
    role = str(asset["role"])
    stage_id, gap, owner, collaborator, _stage_ref = ROLE_STAGE[role]
    body = design.get("payload")
    if design.get("contract_id") != "asset_foundation_stage_artifact_v1" or not isinstance(body, dict):
        raise ValueError("design_artifact_payload_required")
    required = foundation.STAGE_PAYLOAD_KEYS.get(stage_id, ())
    if any(not body.get(key) for key in required):
        raise ValueError("design_artifact_required_field_missing")
    # Caller authors the payload; these facts must already name the actual target.
    if stage_id == "identity_state" and set(body.get("asset_descriptors", [])) != {asset["asset_id"]}:
        raise ValueError("design_artifact_asset_coverage_invalid")
    if stage_id == "production_design" and asset["asset_id"] not in body.get("scene_prop_vehicle_specs", []):
        raise ValueError("design_artifact_asset_coverage_invalid")
    source_assets = [{"asset_id": f"design-{asset['asset_id']}", "source_kind": "planning_only", "role": "planning_only",
                      "relative_path": design_binding["relative_path"], "sha256": design_binding["sha256"]},
                     *[{"asset_id": ref["asset_id"], "source_kind": "planning_only", "role": "planning_only",
                       "relative_path": ref["relative_path"], "sha256": ref["sha256"]} for ref in references]]
    pass_id = f"prepare-{asset['asset_id']}"
    intake_id = f"{asset['asset_id']}-foundation-intake"
    output_id = str(design.get("artifact_id") or f"{asset['asset_id']}-{stage_id}")
    intake_body = {"source_assets": source_assets}
    intake_payload = {"contract_id": "asset_foundation_intake_v1", "project_id": plan["project_id"], "pass_id": pass_id,
                      "artifact_id": intake_id, "payload": intake_body, "payload_sha256": canonical(intake_body)}
    intake_binding = write_immutable(root, f"{out}/foundation-intake.json", intake_payload)
    stage_payload = {"contract_id": "asset_foundation_stage_artifact_v1", "project_id": plan["project_id"], "pass_id": pass_id,
                     "stage_id": stage_id, "artifact_id": output_id, "input_artifact_id": intake_id,
                     "input_sha256": intake_binding["sha256"], "required_gaps": [gap], "covered_gaps": [gap],
                     "missing_gaps": [], "payload": body, "payload_sha256": canonical(body)}
    stage_binding = write_immutable(root, f"{out}/foundation-stage.json", stage_payload)
    stage = {"stage_id": stage_id, "sequence": {"identity_state": 1, "production_design": 2, "camera_geography": 3, "material_response": 4}[stage_id],
             "owner_skill_id": owner, "collaborator_skill_ids": [collaborator] if collaborator else [], "validator_skill_id": None,
             "input_artifact": {"artifact_id": intake_id, **intake_binding}, "previous_output_sha256": None,
             "output_artifact": {"artifact_id": output_id, **stage_binding}, "required_gaps": [gap], "covered_gaps": [gap],
             "missing_gaps": [], "status": "passed", "promotion_state": "planning_only"}
    # validate_design requires the formal per-stage validator identity.
    stage["validator_skill_id"] = {"identity_state": None, "production_design": None, "camera_geography": None, "material_response": None}[stage_id]
    document = {"contract_id": "asset_foundation_pass_v1", "authority": "staged_validation", "source_owner": "dircreative", "output_owner": "dircreative",
                "project_id": plan["project_id"], "pass_id": pass_id, "status": "in_progress", "canonical_asset_ids": [],
                "planned_asset_ids": [asset["asset_id"]], "planning_source_ids": [x["asset_id"] for x in source_assets], "source_assets": source_assets,
                "target_shot_ids": [], "stages": [stage], "stress_test_binding": None,
                "compile_gate": {"requested_shot_ids": [], "status": "blocked", "reason_codes": ["image_generation_pending"]}}
    errors = foundation.validate_design(document, artifact_root=root, asset_id=asset["asset_id"], role=role)
    if errors:
        raise ValueError("foundation_design_invalid:" + ",".join(errors))
    return document, write_immutable(root, f"{out}/foundation-pass.json", document)


def validate_existing(*, root: Path, out: str, plan: dict[str, Any], asset: dict[str, Any],
                      provider: Path, execution_task_id: str, original_request: str, test_mode: bool) -> dict[str, Any]:
    result, _ = read_json(root, f"{out}/prepare-result.json", "prepare_result")
    paths = result.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("existing_result_paths_invalid")
    for binding in paths.values():
        if not isinstance(binding, dict) or not isinstance(binding.get("relative_path"), str) or not isinstance(binding.get("sha256"), str):
            raise ValueError("existing_result_binding_invalid")
        if sha(contained_regular_file(root, binding["relative_path"], "existing_output").read_bytes()) != binding["sha256"]:
            raise ValueError("existing_output_hash_mismatch")
    foundation_doc, _ = read_json(root, paths["foundation_pass"]["relative_path"], "foundation_pass")
    foundation_errors = foundation.validate_design(foundation_doc, artifact_root=root, asset_id=asset["asset_id"], role=asset["role"])
    if foundation_errors:
        raise ValueError("existing_foundation_invalid:" + ",".join(foundation_errors))
    handoff_doc, _ = read_json(root, paths["handoff"]["relative_path"], "jingzao_handoff")
    errors, _ = handoff.validate(handoff_doc, project_root=root, provider_root=provider,
                                 trusted_provider_roots=(provider,) if test_mode else None,
                                 allow_unsandboxed_test_replay=test_mode)
    if errors:
        raise ValueError("existing_handoff_invalid:" + ",".join(errors))
    packet, _ = read_json(root, paths["execution_packet"]["relative_path"], "execution_packet")
    delivery, _ = read_json(root, paths["reference_delivery"]["relative_path"], "reference_delivery")
    prepared = execution_gate.prepare_image_call(packet, project_root=root, reference_delivery=delivery,
                                                  execution_task_id=execution_task_id, repo_root=ROOT,
                                                  request_text=original_request,
                                                  _trusted_jingzao_provider_roots=(provider,) if test_mode else None,
                                                  _allow_unsandboxed_jingzao_replay_for_tests=test_mode)
    if prepared.get("preflight_status") != "ready":
        raise ValueError("existing_prepare_call_blocked:" + ",".join(prepared.get("errors", [])))
    return result


def prepare_asset(*, project_root: Path, plan_path: str, asset_id: str, source_spec_path: str,
                  original_request: str, output_dir: str, execution_task_id: str,
                  design_artifact_path: str | None = None, foundation_pass_path: str | None = None,
                  character_contract_path: str | None = None, provider_root: Path = DEFAULT_PROVIDER,
                  style_capsule: str | None = None, approve_review: bool = False,
                  reviewed_prompt_sha256: str | None = None, _test_mode: bool = False) -> dict[str, Any]:
    root = project_root.resolve(strict=True)
    if bool(design_artifact_path) == bool(foundation_pass_path):
        raise ValueError("exactly_one_of_foundation_pass_or_design_artifact_required")
    if not execution_task_id:
        raise ValueError("execution_task_id_required")
    source_path = design_artifact_path or foundation_pass_path
    assert source_path is not None
    for value in (plan_path, source_spec_path, source_path, output_dir, *([character_contract_path] if character_contract_path else [])):
        if Path(value).is_absolute() or ".." in Path(value).parts:
            raise ValueError("project_relative_path_required")
    out = output_dir.rstrip("/")
    if not out:
        raise ValueError("output_dir_required")
    safe_output_dir(root, out)
    plan, plan_raw = read_json(root, plan_path, "visual_plan")
    if validate_plan(plan, base_dir=(root / plan_path).parent)[0]:
        raise ValueError("visual_asset_plan_invalid")
    asset = next((item for item in plan.get("assets", []) if isinstance(item, dict) and item.get("asset_id") == asset_id), None)
    if not isinstance(asset, dict) or asset.get("action") != "generate" or asset.get("role") not in ROLE_STAGE:
        raise ValueError("unsupported_asset_role_or_action")
    if asset.get("compile_route") != "selected_skill_handoff":
        raise ValueError("asset_requires_existing_narrative_or_other_handoff_path")
    source, source_raw = read_json(root, source_spec_path, "source_spec")
    if source.get("mode", "create") != "create" or source.get("intent") != asset.get("purpose"):
        raise ValueError("source_spec_intent_or_mode_invalid")
    design, design_raw = read_json(root, source_path, "design_artifact" if design_artifact_path else "foundation_pass")
    input_lock = {"plan": {"relative_path": plan_path, "sha256": sha(plan_raw)}, "asset_id": asset_id,
                  "source_spec": {"relative_path": source_spec_path, "sha256": sha(source_raw)},
                  "design_artifact": {"relative_path": source_path, "sha256": sha(design_raw)},
                  "original_request_sha256": sha(original_request.encode()), "execution_task_id": execution_task_id,
                  "character_contract": None, "style_capsule": None}
    if style_capsule:
        capsule = contained_regular_file(root, style_capsule, "style_capsule")
        input_lock["style_capsule"] = {"relative_path": style_capsule, "sha256": sha(capsule.read_bytes())}
    if character_contract_path:
        contract_path = contained_regular_file(root, character_contract_path, "character_contract")
        input_lock["character_contract"] = {"relative_path": character_contract_path, "sha256": sha(contract_path.read_bytes())}
    write_immutable(root, f"{out}/input-lock.json", input_lock)
    provider = provider_root.resolve(strict=True)
    runtime_paths = handoff.expected_runtime_paths(provider)
    if not (provider / "SKILL.md").is_file() or any(not (provider / item).is_file() for item in runtime_paths):
        raise ValueError("provider_runtime_incomplete")
    # Immutable input locking prevents overwrite.  Re-read every formal contract
    # on reuse so a changed provider/reference cannot be mistaken for ready work.
    result_path = root / out / "prepare-result.json"
    if result_path.exists():
        return validate_existing(root=root, out=out, plan=plan, asset=asset, provider=provider,
                                 execution_task_id=execution_task_id, original_request=original_request,
                                 test_mode=_test_mode)
    character_master = source.get("character_master")
    if character_contract_path:
        if character_master is not None:
            raise ValueError("character_contract_duplicate")
        character_master, _ = read_json(root, character_contract_path, "character_contract")
    if asset["role"] == "character_identity_reference" and not isinstance(character_master, dict):
        raise ValueError("character_master_contract_required")
    prepared_spec, references = source_references(source, source_dir=(root / source_spec_path).parent,
                                                  output_dir=(root / out), root=root)
    # This is execution-contract evidence, not a Jingzao spec field.
    prepared_spec.pop("character_master", None)
    prepared_spec = handoff.prepare_role_spec(prepared_spec, asset)
    role_binding = write_immutable(root, f"{out}/role-spec.json", prepared_spec)
    if foundation_pass_path:
        foundation_errors = foundation.validate_design(design, artifact_root=root, asset_id=asset_id, role=asset["role"])
        if foundation_errors:
            raise ValueError("foundation_design_invalid:" + ",".join(foundation_errors))
        foundation_binding = {"relative_path": foundation_pass_path, "sha256": sha(design_raw)}
    else:
        design_doc, foundation_binding = design_document(root=root, out=out, plan=plan, asset=asset, design=design,
                                                         design_binding={"relative_path": source_path, "sha256": sha(design_raw)}, references=references)
    validation = call_json([sys.executable, str(provider / "scripts/validate_spec.py"), "--json", str(root / role_binding["relative_path"])], cwd=root)
    if validation.get("valid") is False or validation.get("errors") not in (None, []):
        raise ValueError("provider_spec_validation_failed")
    validation_binding = write_immutable(root, f"{out}/validation.json", validation)
    compile_argv = [sys.executable, str(provider / "scripts/compile_prompt.py"), str(root / role_binding["relative_path"]), "--format", "json"]
    capsule_binding = None
    if style_capsule:
        capsule = contained_regular_file(root, style_capsule, "style_capsule")
        capsule_result = call_json([sys.executable, str(provider / "scripts/validate_style_capsule.py"), str(capsule)], cwd=root)
        write_immutable(root, f"{out}/style-capsule-validation.json", capsule_result)
        compile_argv.extend(["--style-capsule", str(capsule)])
        capsule_binding = bind(root, capsule)
    if approve_review:
        if not isinstance(reviewed_prompt_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", reviewed_prompt_sha256):
            raise ValueError("approve_review_requires_returned_prompt_sha256")
        compile_argv.append("--approve-review")
    compiled = call_json(compile_argv, cwd=root)
    prompt_hash = sha(str(compiled.get("prompt", "")).encode())
    if approve_review and prompt_hash != reviewed_prompt_sha256:
        raise ValueError("reviewed_prompt_changed_reinspect_current_prompt")
    if not handoff.provider_review_ready(compiled.get("prompt_review")):
        pending = write_immutable(root, f"{out}/compiled-review-{prompt_hash[:16]}.json", compiled)
        if (compiled.get("prompt_review") or {}).get("status") == "blocked":
            return {"status": "blocked", "generated": False, "imagegen_arguments": None,
                    "compiled_prompt": pending, "prompt_review": compiled.get("prompt_review"),
                    "next_action": "rewrite the reported source issue and prepare a new input revision; blocked content cannot be approved"}
        return {"status": "review_required", "generated": False, "imagegen_arguments": None,
                "compiled_prompt": pending, "prompt_review": compiled.get("prompt_review"),
                "next_action": "inspect the compiled prompt once; only a clean nonblocking provider review may be accepted",
                "resume_arguments": ["--approve-review", "--reviewed-prompt-sha256", prompt_hash]}
    compiled_binding = write_immutable(root, f"{out}/compiled-prompt.json", compiled)
    delivery = call_json([sys.executable, str(provider / "scripts/reference_delivery.py"), str(root / role_binding["relative_path"]), "--target", "codex_imagegen"], cwd=root)
    delivery_binding = write_immutable(root, f"{out}/reference-delivery.json", delivery)
    intent = {"scenario_id": "visual_asset_compile", "mode": "studio", "route_id": "film_development", "media": "still", "gaps": [], "needs_validation": False}
    intent_binding = write_immutable(root, f"{out}/stack-intent.json", intent)
    stack_request = {"contract_id": "visual_asset_skill_stack_request_v1", "request_text": original_request, "intent": intent}
    stack_request_binding = write_immutable(root, f"{out}/stack-request.json", stack_request)
    stack = call_json([sys.executable, str(ROOT / "scripts/dircreative_skill_stack.py"), "select", "--intent", str(root / intent_binding["relative_path"]), "--request", original_request, "--root", str(provider.parent)], cwd=ROOT)
    stack_binding = write_immutable(root, f"{out}/stack-receipt.json", stack)
    input_spec = {"contract_id": "dircreative_visual_asset_request_v1", "asset_id": asset_id, "role": asset["role"], "truth_sha256": asset["truth_sha256"], "purpose": asset["purpose"], "visual_plan_sha256": sha(plan_raw), "operation": "create", "asset_foundation_pass": foundation_binding, "reference_assets": references}
    input_binding = write_immutable(root, f"{out}/input-spec.json", input_spec)
    output_spec: dict[str, Any] = {"visual_generation_spec": role_binding, "validation_receipt": validation_binding, "compiled_prompt_manifest": compiled_binding, "prompt_sha256": sha(str(compiled["prompt"]).encode())}
    reference_reads = set(handoff.REQUIRED_REFERENCE_READS)
    if capsule_binding:
        output_spec["style_capsule"] = capsule_binding
        # A selected capsule may name its provider-owned source notes. Bind
        # those existing documentation bytes; never treat JSON as an image.
        capsule_doc, _ = read_json(root, capsule_binding["relative_path"], "style_capsule")
        for relative in re.findall(r"references/[a-zA-Z0-9_/-]+\.md", json.dumps(capsule_doc)):
            if (provider / relative).is_file():
                reference_reads.add(relative)
    handoff_doc = {"contract_id": "visual_asset_to_jingzao_v1", "authority": "compile_only", "source_owner": "dircreative", "target_owner": "jingzao-image-forge", "output_owner": "dircreative", "fixture_only": False,
                   "active_asset": {"asset_id": asset_id, "role": asset["role"], "truth_sha256": asset["truth_sha256"], "purpose_sha256": sha(str(asset["purpose"]).encode()), "visual_plan_sha256": sha(plan_raw), "operation": "create"},
                   "visual_plan": {"relative_path": plan_path, "sha256": sha(plan_raw)}, "skill_stack_request": stack_request_binding, "skill_stack_receipt": stack_binding, "input_spec": input_binding,
                   "provider_skill": {"skill_id": "jingzao-image-forge", "sha256": sha((provider / "SKILL.md").read_bytes())}, "provider_runtime_files": [provider_file(provider, item) for item in sorted(runtime_paths)], "reference_reads": [provider_file(provider, item) for item in sorted(reference_reads)], "output_spec": output_spec,
                   "delivery_consumption": {"route_id": "generation_authorization", "adapter": "imagegen", "status": "planned", "consumed_prompt_sha256": output_spec["prompt_sha256"], "generated": False}}
    handoff_binding = write_immutable(root, f"{out}/jingzao-handoff.json", handoff_doc)
    errors, _prompt = handoff.validate(handoff_doc, project_root=root, provider_root=provider,
                                       trusted_provider_roots=(provider,) if _test_mode else None,
                                       allow_unsandboxed_test_replay=_test_mode)
    if errors:
        raise ValueError("jingzao_handoff_invalid:" + ",".join(errors))
    _stage, _gap, _owner, _collaborator, stage_ref = ROLE_STAGE[asset["role"]]
    packet = {"contract_id": execution_gate.CONTRACT_ID, "asset_id": asset_id, "asset_role": asset["role"], "active_asset_truth_sha256": asset["truth_sha256"], "authorization": {"image_generation": True, "video_generation": False, "source": "validated_route_context"}, "media_scope": "pre_video_assets", "dependencies": [], "execution": {"adapter": "imagegen", "mode": "batch_then_review", "parallel_group": None}, "stage_contract": {"stage_id": _stage, "reference": stage_ref, "sha256": sha((ROOT / stage_ref).read_bytes())}, "visual_plan": {"path": plan_path, "sha256": sha(plan_raw)}, "prompt": compiled["prompt"], "prompt_sha256": output_spec["prompt_sha256"], "jingzao_asset_handoff": {"path": handoff_binding["relative_path"], "sha256": handoff_binding["sha256"], "provider_skill_sha256": handoff_doc["provider_skill"]["sha256"], "compiled_prompt_manifest_sha256": compiled_binding["sha256"], "skill_stack_receipt_sha256": stack_binding["sha256"]}}
    if character_master is not None:
        packet["character_master"] = copy.deepcopy(character_master)
    packet["prompt_authority"] = execution_gate.build_prompt_authority(asset, output_spec["prompt_sha256"], jingzao_handoff_sha256=handoff_binding["sha256"], jingzao_provider_skill_sha256=handoff_doc["provider_skill"]["sha256"], jingzao_prompt_manifest_sha256=compiled_binding["sha256"])
    packet_binding = write_immutable(root, f"{out}/execution-packet.json", packet)
    prepared = execution_gate.prepare_image_call(packet, project_root=root, reference_delivery=delivery,
                                                 execution_task_id=execution_task_id, repo_root=ROOT,
                                                 request_text=original_request,
                                                 _trusted_jingzao_provider_roots=(provider,) if _test_mode else None,
                                                 _allow_unsandboxed_jingzao_replay_for_tests=_test_mode)
    if prepared.get("preflight_status") != "ready":
        raise ValueError("prepare_call_blocked:" + ",".join(prepared.get("errors", [])))
    prepared_binding = write_immutable(root, f"{out}/prepared-call.json", prepared)
    result = {"status": "ready", "asset_id": asset_id, "generated": False, "visual_qa_approved": False, "paths": {"role_spec": role_binding, "foundation_pass": foundation_binding, "handoff": handoff_binding, "execution_packet": packet_binding, "reference_delivery": delivery_binding, "prepared_call": prepared_binding}, "imagegen_arguments": prepared["imagegen_arguments"]}
    write_immutable(root, f"{out}/prepare-result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--source-spec", required=True)
    parser.add_argument("--original-request", required=True)
    foundation = parser.add_mutually_exclusive_group(required=True)
    foundation.add_argument("--design-artifact")
    foundation.add_argument("--foundation-pass")
    parser.add_argument("--character-contract")
    parser.add_argument("--execution-task-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--provider-root", type=Path, default=DEFAULT_PROVIDER)
    parser.add_argument("--style-capsule")
    parser.add_argument("--approve-review", action="store_true")
    parser.add_argument("--reviewed-prompt-sha256")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare_asset(project_root=args.project_root, plan_path=args.plan, asset_id=args.asset_id, source_spec_path=args.source_spec, original_request=args.original_request, output_dir=args.output_dir, execution_task_id=args.execution_task_id, design_artifact_path=args.design_artifact, foundation_pass_path=args.foundation_pass, character_contract_path=args.character_contract, provider_root=args.provider_root, style_capsule=args.style_capsule, approve_review=args.approve_review, reviewed_prompt_sha256=args.reviewed_prompt_sha256), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "generated": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
