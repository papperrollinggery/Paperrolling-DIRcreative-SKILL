#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from dircreative_validation_common import (
    add_error,
    apply_mutations,
    load_json,
    safe_relative_path,
    schema_errors as validate_schema,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/asset-foundation-pass.schema.json"
VALID_PATH = ROOT / "tests/fixtures/asset-foundation/valid-pass.json"
CASES_PATH = ROOT / "tests/fixtures/asset-foundation/cases.json"

STAGE_CONTRACT = [
    ("identity_state", "minimum-visual-bible", None),
    ("production_design", "production-design-worldbuilding", None),
    ("camera_geography", "master-shot-camera-planning", None),
    ("material_response", "ai-material-realism", None),
    ("constraint_assignment", "constraint-input-router", None),
    ("stress_certification", "dircreative", "ai-film-asset-stress-test"),
]
STAGE_PAYLOAD_KEYS = {
    "identity_state": ("asset_descriptors", "state_families"),
    "production_design": ("production_design_rules", "scene_prop_vehicle_specs"),
    "camera_geography": ("geo_landmarks", "axis_rules", "camera_zones"),
    "material_response": ("material_response_rules", "lighting_conditions"),
    "constraint_assignment": ("reference_assignments", "must_not_control_rules"),
    "stress_certification": ("stress_test_id", "verdict", "covered_asset_ids", "report_sha256"),
}


def verify_artifact(
    artifact: dict[str, Any],
    *,
    artifact_root: Path,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    relative = artifact.get("relative_path")
    if not safe_relative_path(relative):
        add_error(errors, "stage_artifact_path_invalid", f"{label}:{relative}")
        return None
    try:
        root = artifact_root.resolve(strict=True)
        path = (root / str(relative)).resolve(strict=True)
        path.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError):
        add_error(errors, "stage_artifact_missing", f"{label}:{relative}")
        return None
    if not path.is_file():
        add_error(errors, "stage_artifact_missing", f"{label}:{relative}")
        return None
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != artifact.get("sha256"):
        add_error(errors, "stage_artifact_hash_mismatch", f"{label}:{relative}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        add_error(errors, "stage_artifact_payload_invalid", f"{label}:{relative}")
        return None
    if not isinstance(payload, dict):
        add_error(errors, "stage_artifact_payload_invalid", f"{label}:{relative}")
        return None
    return payload


def verify_source_file(
    source: dict[str, Any],
    *,
    artifact_root: Path,
    errors: list[str],
) -> None:
    relative = source.get("relative_path")
    if not safe_relative_path(relative):
        add_error(errors, "source_asset_path_invalid", str(source.get("asset_id")))
        return
    try:
        root = artifact_root.resolve(strict=True)
        path = (root / str(relative)).resolve(strict=True)
        path.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError):
        add_error(errors, "source_asset_file_missing", str(source.get("asset_id")))
        return
    if hashlib.sha256(path.read_bytes()).hexdigest() != source.get("sha256"):
        add_error(errors, "source_asset_hash_mismatch", str(source.get("asset_id")))


def validate_stage_artifact_payload(
    document: dict[str, Any],
    stage: dict[str, Any],
    payload: dict[str, Any] | None,
    *,
    intake: bool,
    errors: list[str],
) -> None:
    if payload is None:
        return
    body = payload.get("payload")
    expected_contract = "asset_foundation_intake_v1" if intake else "asset_foundation_stage_artifact_v1"
    if (
        payload.get("contract_id") != expected_contract
        or payload.get("project_id") != document.get("project_id")
        or payload.get("pass_id") != document.get("pass_id")
        or payload.get("artifact_id")
        != stage.get("input_artifact" if intake else "output_artifact", {}).get("artifact_id")
        or not isinstance(body, dict)
        or not body
        or payload.get("payload_sha256")
        != hashlib.sha256(
            json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    ):
        add_error(errors, "stage_artifact_contract_invalid", str(stage.get("stage_id")))
        return
    if intake:
        if body.get("source_assets") != document.get("source_assets"):
            add_error(errors, "stage_artifact_content_missing", "asset_intake")
        return
    if (
        payload.get("stage_id") != stage.get("stage_id")
        or payload.get("input_artifact_id") != stage.get("input_artifact", {}).get("artifact_id")
        or payload.get("input_sha256") != stage.get("input_artifact", {}).get("sha256")
        or set(payload.get("required_gaps", [])) != set(stage.get("required_gaps", []))
        or set(payload.get("covered_gaps", [])) != set(stage.get("covered_gaps", []))
        or set(payload.get("missing_gaps", [])) != set(stage.get("missing_gaps", []))
    ):
        add_error(errors, "stage_artifact_contract_invalid", str(stage.get("stage_id")))
    required_keys = STAGE_PAYLOAD_KEYS.get(str(stage.get("stage_id")), ())
    if any(not body.get(key) for key in required_keys):
        add_error(errors, "stage_artifact_content_missing", str(stage.get("stage_id")))
    canonical_assets = set(document.get("canonical_asset_ids", []))
    if stage.get("stage_id") == "identity_state" and set(body.get("asset_descriptors", [])) != canonical_assets:
        add_error(errors, "stage_artifact_asset_coverage_invalid", "identity_state")
    if stage.get("stage_id") == "production_design" and not canonical_assets.issubset(
        set(body.get("scene_prop_vehicle_specs", []))
    ):
        add_error(errors, "stage_artifact_asset_coverage_invalid", "production_design")
    if stage.get("stage_id") == "constraint_assignment" and set(
        body.get("reference_assignments", [])
    ) != canonical_assets:
        add_error(errors, "stage_artifact_asset_coverage_invalid", "constraint_assignment")
    if stage.get("stage_id") == "stress_certification":
        stress = document.get("stress_test_binding", {})
        if (
            body.get("stress_test_id") != stress.get("stress_test_id")
            or body.get("verdict") != stress.get("verdict")
            or set(body.get("covered_asset_ids", [])) != set(stress.get("covered_asset_ids", []))
            or body.get("report_sha256") != stress.get("report_sha256")
        ):
            add_error(errors, "stage_artifact_stress_binding_invalid", "stress_certification")


def schema_errors(document: dict[str, Any]) -> list[str]:
    return validate_schema(document, SCHEMA_PATH)


def semantic_errors(document: dict[str, Any], *, artifact_root: Path | None) -> list[str]:
    errors: list[str] = []
    stages = [item for item in document.get("stages", []) if isinstance(item, dict)]
    actual_stage_ids = [str(item.get("stage_id")) for item in stages]
    expected_stage_ids = [item[0] for item in STAGE_CONTRACT]
    complete = document.get("status") == "complete"
    if actual_stage_ids != expected_stage_ids or [item.get("sequence") for item in stages] != list(
        range(1, len(STAGE_CONTRACT) + 1)
    ):
        add_error(errors, "stage_set_invalid", str(actual_stage_ids))
    if complete and artifact_root is None:
        add_error(errors, "stage_artifact_root_required", str(document.get("pass_id")))

    output_ids: set[str] = set()
    for index, stage in enumerate(stages):
        if index < len(STAGE_CONTRACT):
            stage_id, owner, validator = STAGE_CONTRACT[index]
            if (
                stage.get("stage_id") != stage_id
                or stage.get("owner_skill_id") != owner
                or stage.get("validator_skill_id") != validator
            ):
                add_error(errors, "stage_owner_contract_invalid", str(stage.get("stage_id")))
        output = stage.get("output_artifact", {})
        output_id = output.get("artifact_id")
        if isinstance(output_id, str):
            if output_id in output_ids:
                add_error(errors, "stage_output_duplicate", output_id)
            output_ids.add(output_id)
        if artifact_root is not None:
            input_payload = verify_artifact(
                stage.get("input_artifact", {}),
                artifact_root=artifact_root,
                label=f"{stage.get('stage_id')}:input",
                errors=errors,
            )
            output_payload = verify_artifact(
                output,
                artifact_root=artifact_root,
                label=f"{stage.get('stage_id')}:output",
                errors=errors,
            )
            if index == 0:
                validate_stage_artifact_payload(
                    document,
                    stage,
                    input_payload,
                    intake=True,
                    errors=errors,
                )
            validate_stage_artifact_payload(
                document,
                stage,
                output_payload,
                intake=False,
                errors=errors,
            )
        if index == 0:
            if stage.get("previous_output_sha256") is not None:
                add_error(errors, "stage_hash_chain_invalid", f"{stage.get('stage_id')}:first")
        else:
            previous_output = stages[index - 1].get("output_artifact", {})
            if (
                stage.get("previous_output_sha256") != previous_output.get("sha256")
                or stage.get("input_artifact", {}).get("artifact_id")
                != previous_output.get("artifact_id")
                or stage.get("input_artifact", {}).get("sha256") != previous_output.get("sha256")
                or stage.get("input_artifact", {}).get("relative_path")
                != previous_output.get("relative_path")
            ):
                add_error(errors, "stage_hash_chain_invalid", str(stage.get("stage_id")))
        required = set(stage.get("required_gaps", []))
        covered = set(stage.get("covered_gaps", []))
        missing = set(stage.get("missing_gaps", []))
        if stage.get("status") == "passed" and missing:
            add_error(errors, "stage_pass_with_gaps", str(stage.get("stage_id")))
        if stage.get("status") == "passed" and covered != required:
            add_error(errors, "stage_coverage_invalid", str(stage.get("stage_id")))
        if missing != required - covered:
            add_error(errors, "stage_gap_accounting_invalid", str(stage.get("stage_id")))

    all_passed = len(stages) == len(STAGE_CONTRACT) and all(
        stage.get("status") == "passed" for stage in stages
    )
    if complete and not all_passed:
        add_error(errors, "incomplete_stage_promoted", str(document.get("pass_id")))

    planning = set(document.get("planning_source_ids", []))
    canonical = set(document.get("canonical_asset_ids", []))
    if planning & canonical:
        add_error(errors, "planning_source_promoted", ",".join(sorted(planning & canonical)))
    source_assets = [item for item in document.get("source_assets", []) if isinstance(item, dict)]
    source_ids = [str(item.get("asset_id")) for item in source_assets]
    if len(source_ids) != len(set(source_ids)):
        add_error(errors, "source_asset_id_duplicate", str(source_ids))
    canonical_records = {
        str(item.get("asset_id"))
        for item in source_assets
        if item.get("source_kind") == "canonical_asset" and item.get("role") == "canonical"
    }
    planning_records = {
        str(item.get("asset_id"))
        for item in source_assets
        if item.get("source_kind") == "planning_only" and item.get("role") == "planning_only"
    }
    if canonical_records != canonical or planning_records != planning:
        add_error(errors, "source_asset_role_mismatch", str(document.get("pass_id")))
    provenance_by_path: dict[str, tuple[Any, Any]] = {}
    provenance_by_hash: dict[str, tuple[Any, Any]] = {}
    for source in source_assets:
        role = (source.get("source_kind"), source.get("role"))
        for identity, role_map in (
            (str(source.get("relative_path")), provenance_by_path),
            (str(source.get("sha256")), provenance_by_hash),
        ):
            prior = role_map.get(identity)
            if prior is not None and prior != role:
                add_error(errors, "source_asset_alias_role_conflict", str(source.get("asset_id")))
            role_map[identity] = role
        if artifact_root is not None:
            verify_source_file(
                source,
                artifact_root=artifact_root,
                errors=errors,
            )

    target_shots = set(document.get("target_shot_ids", []))
    stress = document.get("stress_test_binding", {})
    covered_assets = set(stress.get("covered_asset_ids", []))
    allowed = set(stress.get("allowed_shot_scope", []))
    blocked = set(stress.get("blocked_shot_scope", []))
    verdict = stress.get("verdict")
    validation_status = stress.get("validation_status")
    compile_gate = document.get("compile_gate", {})
    requested = set(compile_gate.get("requested_shot_ids", []))
    compile_allowed = compile_gate.get("status") == "allowed"
    if complete and covered_assets != canonical:
        add_error(
            errors,
            "stress_asset_coverage_incomplete",
            ",".join(sorted(canonical - covered_assets)),
        )
    if artifact_root is not None:
        verify_artifact(
            {
                "relative_path": stress.get("report_relative_path"),
                "sha256": stress.get("report_sha256"),
            },
            artifact_root=artifact_root,
            label="stress_report",
            errors=errors,
        )
    if allowed & blocked or not (allowed | blocked).issubset(target_shots):
        add_error(errors, "stress_scope_invalid", str(stress.get("stress_test_id")))
    if verdict == "conditional" and (not allowed or not blocked):
        add_error(errors, "conditional_scope_missing", str(stress.get("stress_test_id")))
    if complete and compile_allowed and (
        validation_status != "passed" or verdict not in {"certified", "conditional"}
    ):
        add_error(errors, "stress_verdict_not_compilable", str(verdict))
    if not requested.issubset(target_shots):
        add_error(errors, "compile_scope_outside_target", ",".join(sorted(requested - target_shots)))
    effective_allowed = target_shots if verdict == "certified" else allowed
    if compile_allowed and (not complete or not requested.issubset(effective_allowed) or bool(requested & blocked)):
        add_error(errors, "compile_scope_blocked", ",".join(sorted(requested)))
    if not compile_allowed and not compile_gate.get("reason_codes"):
        add_error(errors, "blocked_compile_without_reason", str(document.get("pass_id")))
    return errors


def validate(document: dict[str, Any], *, artifact_root: Path | None = None) -> list[str]:
    structural = schema_errors(document)
    if structural:
        return structural
    return semantic_errors(document, artifact_root=artifact_root)


def materialize_fixture(template: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    document = copy.deepcopy(template)
    stress = document["stress_test_binding"]
    stress_path = artifact_root / stress["report_relative_path"]
    stress_path.parent.mkdir(parents=True, exist_ok=True)
    if not stress_path.exists():
        stress_path.write_text(
            json.dumps(
                {
                    "project_id": document["project_id"],
                    "stress_test_id": stress["stress_test_id"],
                    "covered_asset_ids": stress["covered_asset_ids"],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    stress["report_sha256"] = hashlib.sha256(stress_path.read_bytes()).hexdigest()
    for source in document["source_assets"]:
        source_path = artifact_root / source["relative_path"]
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            source_path.write_bytes(
                b"\x89PNG\r\n\x1a\n" + source["asset_id"].encode("utf-8")
            )
        source["sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    first_input = copy.deepcopy(document["stages"][0]["input_artifact"])
    intake_body = {
        "source_assets": document["source_assets"],
    }
    intake_payload = {
        "contract_id": "asset_foundation_intake_v1",
        "project_id": document["project_id"],
        "pass_id": document["pass_id"],
        "artifact_id": first_input["artifact_id"],
        "payload": intake_body,
        "payload_sha256": hashlib.sha256(
            json.dumps(intake_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    intake_path = artifact_root / first_input["relative_path"]
    intake_path.parent.mkdir(parents=True, exist_ok=True)
    intake_path.write_text(
        json.dumps(intake_payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    first_input["sha256"] = hashlib.sha256(intake_path.read_bytes()).hexdigest()
    prior_artifact = first_input
    payloads = {
        "identity_state": {
            "asset_descriptors": document["canonical_asset_ids"],
            "state_families": ["declared_state_families"],
        },
        "production_design": {
            "production_design_rules": ["declared_world_language"],
            "scene_prop_vehicle_specs": document["canonical_asset_ids"],
        },
        "camera_geography": {
            "geo_landmarks": ["declared_landmarks"],
            "axis_rules": ["declared_axis"],
            "camera_zones": ["declared_camera_zones"],
        },
        "material_response": {
            "material_response_rules": ["declared_material_response"],
            "lighting_conditions": ["declared_target_lighting"],
        },
        "constraint_assignment": {
            "reference_assignments": document["canonical_asset_ids"],
            "must_not_control_rules": ["declared_negative_constraints"],
        },
        "stress_certification": {
            "stress_test_id": stress["stress_test_id"],
            "verdict": stress["verdict"],
            "covered_asset_ids": stress["covered_asset_ids"],
            "report_sha256": stress["report_sha256"],
        },
    }
    for index, stage in enumerate(document["stages"]):
        stage["input_artifact"] = copy.deepcopy(prior_artifact)
        stage["previous_output_sha256"] = None if index == 0 else prior_artifact["sha256"]
        output = stage["output_artifact"]
        body = payloads[stage["stage_id"]]
        artifact_payload = {
            "contract_id": "asset_foundation_stage_artifact_v1",
            "project_id": document["project_id"],
            "pass_id": document["pass_id"],
            "stage_id": stage["stage_id"],
            "artifact_id": output["artifact_id"],
            "input_artifact_id": prior_artifact["artifact_id"],
            "input_sha256": prior_artifact["sha256"],
            "required_gaps": stage["required_gaps"],
            "covered_gaps": stage["covered_gaps"],
            "missing_gaps": stage["missing_gaps"],
            "payload": body,
            "payload_sha256": hashlib.sha256(
                json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }
        output_path = artifact_root / output["relative_path"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact_payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output["sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
        prior_artifact = copy.deepcopy(output)
    return document


def self_test() -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    template = load_json(VALID_PATH)
    with tempfile.TemporaryDirectory(prefix="dircreative-asset-foundation-") as temp_dir:
        artifact_root = Path(temp_dir) / "artifacts"
        artifact_root.mkdir()
        valid = materialize_fixture(template, artifact_root)
        valid_errors = validate(valid, artifact_root=artifact_root)
        if valid_errors:
            failures.append(f"valid fixture rejected: {valid_errors[:3]}")
        cases = load_json(CASES_PATH).get("cases", [])
        rejected = 0
        for case in cases:
            errors = validate(
                apply_mutations(valid, case["mutations"]),
                artifact_root=artifact_root,
            )
            expected = case["expected_error"]
            if any(error.startswith(expected + ":") for error in errors):
                rejected += 1
            else:
                failures.append(f"{case['case_id']}: expected {expected}, got {errors[:3]}")
        hollow_root = Path(temp_dir) / "hollow-artifacts"
        hollow_root.mkdir()
        hollow = materialize_fixture(template, hollow_root)
        hollow_stage = hollow["stages"][2]
        hollow_path = hollow_root / hollow_stage["output_artifact"]["relative_path"]
        hollow_path.write_text(
            json.dumps({"artifact_id": hollow_stage["output_artifact"]["artifact_id"]}) + "\n",
            encoding="utf-8",
        )
        hollow_sha256 = hashlib.sha256(hollow_path.read_bytes()).hexdigest()
        hollow_stage["output_artifact"]["sha256"] = hollow_sha256
        hollow["stages"][3]["input_artifact"]["sha256"] = hollow_sha256
        hollow["stages"][3]["previous_output_sha256"] = hollow_sha256
        hollow_errors = validate(hollow, artifact_root=hollow_root)
        hollow_rejected = any(
            error.startswith("stage_artifact_contract_invalid:") for error in hollow_errors
        )
        if hollow_rejected:
            rejected += 1
        else:
            failures.append(f"hollow stage artifact accepted: {hollow_errors[:3]}")
    return failures, {
        "valid_fixture_passed": not valid_errors,
        "stage_count": len(valid.get("stages", [])),
        "negative_case_count": len(cases) + 1,
        "negative_cases_rejected": rejected,
        "compile_gate_status": valid.get("compile_gate", {}).get("status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate staged DIRcreative asset-foundation passes.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--artifact-root", type=Path)
    args = parser.parse_args()
    if args.command == "self-test":
        failures, summary = self_test()
        print(json.dumps({**summary, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"DIRCREATIVE_ASSET_FOUNDATION_PASS_AUDIT: {'PASS' if not failures else 'FAIL'}")
        return 0 if not failures else 1
    errors = validate(load_json(args.path), artifact_root=args.artifact_root)
    print(json.dumps({"path": str(args.path), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
