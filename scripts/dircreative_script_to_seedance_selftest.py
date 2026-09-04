from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from dircreative_validation_common import apply_mutations, load_json


def run_self_test(
    *,
    ROOT: Path,
    VALID_PATH: Path,
    CASES_PATH: Path,
    validate: Callable[..., list[str]],
) -> tuple[list[str], dict[str, Any]]:
    from ai_film_asset_stress_test import materialize_fixture as materialize_stress_fixture
    from dircreative_asset_foundation_pass import materialize_fixture as materialize_foundation_fixture

    failures: list[str] = []
    cases = load_json(CASES_PATH).get("cases", [])
    with tempfile.TemporaryDirectory(prefix="dircreative-seedance-asset-gate-") as temp_dir:
        temp_root = Path(temp_dir)
        artifact_root = temp_root / "asset-evidence"
        review_root = temp_root / "reviews"
        trust_root = temp_root / "trust"
        artifact_root.mkdir()
        review_root.mkdir()
        trust_root.mkdir()
        script_fixture = VALID_PATH.parent / "source" / "SCRIPT-001.md"
        script_relative_path = Path("source") / "SCRIPT-001.md"

        def materialize_authoritative_script(
            root: Path,
            *,
            content_suffix: str = "",
            symlink: bool = False,
        ) -> None:
            source_path = root / script_relative_path
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_content = script_fixture.read_text(encoding="utf-8") + content_suffix
            if symlink:
                target = root / "source" / "SCRIPT-001-target.md"
                target.write_text(source_content, encoding="utf-8")
                if source_path.exists() or source_path.is_symlink():
                    source_path.unlink()
                source_path.symlink_to(target.name)
            else:
                if source_path.is_symlink():
                    source_path.unlink()
                source_path.write_text(source_content, encoding="utf-8")

        materialize_authoritative_script(artifact_root)
        stress_template = load_json(
            ROOT / "tests/fixtures/asset-stress-test/valid-report.json"
        )
        base_asset = stress_template["assets"][0]
        base_cases = stress_template["test_cases"]
        asset_specs = [
            ("VE-RING-ID-v01", "vehicle", "RING-IDENTITY", "RING-BASE"),
            ("CF-GU01-END-v01", "state", "RING-CLEAN-FRAME", "GU01-END"),
            ("GEO-RING-LAYOUT-v01", "scene", "RING-GEOGRAPHY", "RING-GEO-BASE"),
        ]
        stress_template["assets"] = []
        stress_template["test_cases"] = []
        for asset_index, (asset_id, asset_kind, state_family, state_id) in enumerate(asset_specs, 1):
            asset = copy.deepcopy(base_asset)
            asset["asset_id"] = asset_id
            asset["asset_kind"] = asset_kind
            asset["asset_version"] = "v1"
            asset["canonical_relative_path"] = f"canonical/{asset_id}.png"
            asset["state_family"] = state_family
            asset["state_id"] = state_id
            asset["descriptor_text"] = f"Fixture descriptor for {asset_id}."
            asset["required_combinations"] = []
            selected_base_cases = [
                case
                for case in base_cases
                if asset_kind == "character"
                or case.get("case_kind") not in {"face_close_up", "headless_wardrobe"}
            ]
            asset["required_case_kinds"] = [
                str(case.get("case_kind")) for case in selected_base_cases
            ]
            for reference_index, reference in enumerate(asset["references"], 1):
                reference["reference_id"] = f"REF-{asset_index}-{reference_index}"
                reference["relative_path"] = f"references/asset-{asset_index}-{reference_index}.png"
                reference["source_kind"] = "scene_anchor" if asset_kind == "scene" else "vehicle_reference"
            stress_template["assets"].append(asset)
            for case_index, base_case in enumerate(selected_base_cases, 1):
                case = copy.deepcopy(base_case)
                case["test_case_id"] = f"TC-{asset_index}-{case_index}"
                case["asset_id"] = asset_id
                case["state_family"] = state_family
                case["combination_ids"] = []
                for evidence in case["evidence"]:
                    evidence["evidence_id"] = f"EV-{asset_index}-{case_index}"
                    evidence["relative_path"] = f"evidence/asset-{asset_index}-case-{case_index}.png"
                stress_template["test_cases"].append(case)
        stress_template["matrix_config"]["minimum_case_count"] = len(stress_template["test_cases"])
        stress_template["matrix_config"]["required_case_kinds"] = sorted(
            {str(case["case_kind"]) for case in stress_template["test_cases"]}
        )
        stress_template["verdict"]["status"] = "certified"
        stress_template["verdict"]["allowed_shot_scope"] = list(
            {
                shot_class
                for asset in stress_template["assets"]
                for shot_class in asset["intended_shot_classes"]
            }
        )
        stress_template["verdict"]["blocked_shot_scope"] = []
        stress, review_receipt, review_signature, trust_registry_path = materialize_stress_fixture(
            stress_template,
            artifact_root,
            review_root,
            trust_root,
        )
        foundation = load_json(
            ROOT / "tests/fixtures/asset-foundation/valid-pass.json"
        )
        foundation["canonical_asset_ids"] = [item["asset_id"] for item in stress["assets"]]
        planning_source = next(
            item
            for item in foundation["source_assets"]
            if item["source_kind"] == "planning_only"
        )
        foundation["source_assets"] = [
            {
                "asset_id": asset_id,
                "source_kind": "canonical_asset",
                "role": "canonical",
                "relative_path": f"canonical/{asset_id}.png",
                "sha256": "0" * 64,
            }
            for asset_id in foundation["canonical_asset_ids"]
        ] + [planning_source]
        all_shots = ["SH01", "SH02", "SH03", "SH04"]
        foundation["target_shot_ids"] = all_shots
        foundation["stress_test_binding"] = {
            "stress_test_id": stress["stress_test_id"],
            "covered_asset_ids": [item["asset_id"] for item in stress["assets"]],
            "report_relative_path": "stress/stress-report.json",
            "report_sha256": "0" * 64,
            "verdict": "certified",
            "validation_status": "passed",
            "allowed_shot_scope": all_shots,
            "blocked_shot_scope": [],
        }
        foundation["compile_gate"] = {
            "requested_shot_ids": all_shots,
            "status": "allowed",
            "reason_codes": [],
        }
        stress_path = artifact_root / foundation["stress_test_binding"]["report_relative_path"]
        stress_path.parent.mkdir(parents=True, exist_ok=True)
        stress_path.write_text(
            json.dumps(stress, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        foundation = materialize_foundation_fixture(foundation, artifact_root)
        foundation["stress_test_binding"]["report_sha256"] = hashlib.sha256(
            stress_path.read_bytes()
        ).hexdigest()
        foundation_path = temp_root / "asset-foundation-pass.json"
        foundation_path.write_text(
            json.dumps(foundation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        valid = load_json(VALID_PATH)
        source_map = {
            item["asset_id"]: item
            for item in foundation["source_assets"]
            if item["source_kind"] == "canonical_asset"
        }
        stress_asset_map = {item["asset_id"]: item for item in stress["assets"]}
        for binding in valid["bindings"]:
            if binding["asset_id"] not in source_map:
                continue
            binding["asset_version"] = stress_asset_map[binding["asset_id"]]["asset_version"]
            binding["relative_path"] = source_map[binding["asset_id"]]["relative_path"]
            binding["sha256"] = source_map[binding["asset_id"]]["sha256"]
        valid["asset_foundation_gate"] = {
            "project_id": foundation["project_id"],
            "pass_id": foundation["pass_id"],
            "pass_artifact_sha256": hashlib.sha256(foundation_path.read_bytes()).hexdigest(),
            "stress_test_id": stress["stress_test_id"],
            "stress_report_sha256": hashlib.sha256(stress_path.read_bytes()).hexdigest(),
            "stress_verdict": "certified",
            "requested_shot_ids": all_shots,
            "allowed_shot_ids": all_shots,
            "blocked_shot_ids": [],
            "covered_asset_ids": foundation["stress_test_binding"]["covered_asset_ids"],
        }
        valid_errors = validate(
            valid,
            project_root=artifact_root,
            asset_foundation_path=foundation_path,
            asset_stress_path=stress_path,
            asset_artifact_root=artifact_root,
            asset_review_receipt=review_receipt,
            asset_review_signature=review_signature,
            _asset_trust_registry_path=trust_registry_path,
        )
        if valid_errors:
            failures.append(f"valid fixture rejected: {valid_errors[:3]}")

        valid25 = copy.deepcopy(valid)
        valid25["model_surface"] = {
            "capability_card_id": "seedance_2_5_official_launch",
            "model_key": "seedance",
            "version": "2.5",
            "provider_surface": "Seedance 2.5 launch product surfaces described by ByteDance Seed",
            "status": "current",
            "verification_status": "verified",
        }
        valid25["provider_limits"] = {
            "max_references_per_unit": 50,
            "max_image_references_per_unit": 30,
            "max_video_references_per_unit": 10,
            "max_audio_references_per_unit": 10,
            "source_type": "version_scoped_official_launch_guide",
            "verification_status": "verified",
            "source": "https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5",
        }
        valid25_errors = validate(
            valid25,
            project_root=artifact_root,
            asset_foundation_path=foundation_path,
            asset_stress_path=stress_path,
            asset_artifact_root=artifact_root,
            asset_review_receipt=review_receipt,
            asset_review_signature=review_signature,
            _asset_trust_registry_path=trust_registry_path,
        )
        if valid25_errors:
            failures.append(f"valid Seedance 2.5 fixture rejected: {valid25_errors[:3]}")

        from dircreative_script_to_seedance_v3_selftest import (
            validate_v3_detail_binding_fixture,
        )

        valid_v3_detail_errors = validate_v3_detail_binding_fixture(
            ROOT=ROOT,
            temp_root=temp_root,
            valid=valid,
            stress_template=stress_template,
            all_shots=all_shots,
            materialize_stress_fixture=materialize_stress_fixture,
            materialize_foundation_fixture=materialize_foundation_fixture,
            validate=validate,
        )
        if valid_v3_detail_errors:
            failures.append(
                f"valid v3 detail binding fixture rejected: {valid_v3_detail_errors[:3]}"
            )

        rejected = 0
        for case in cases:
            materialize_authoritative_script(
                artifact_root,
                content_suffix=str(case.get("script_content_suffix", "")),
                symlink=case.get("script_symlink") is True,
            )
            case_foundation = copy.deepcopy(foundation)
            case_stress = copy.deepcopy(stress)
            dependency_mutations = case.get("dependency_mutations", {})
            if dependency_mutations.get("stress"):
                case_stress = apply_mutations(case_stress, dependency_mutations["stress"])
            case_stress_path = artifact_root / "stress" / f"{case['case_id']}-stress.json"
            case_stress_path.write_text(
                json.dumps(case_stress, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            case_foundation["stress_test_binding"]["report_sha256"] = hashlib.sha256(
                case_stress_path.read_bytes()
            ).hexdigest()
            case_foundation["stress_test_binding"]["report_relative_path"] = str(
                case_stress_path.relative_to(artifact_root)
            )
            if dependency_mutations.get("foundation"):
                case_foundation = apply_mutations(
                    case_foundation,
                    dependency_mutations["foundation"],
                )
            case_foundation_path = temp_root / f"{case['case_id']}-foundation.json"
            case_foundation_path.write_text(
                json.dumps(case_foundation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            case_document = copy.deepcopy(valid)
            case_document["asset_foundation_gate"]["pass_artifact_sha256"] = hashlib.sha256(
                case_foundation_path.read_bytes()
            ).hexdigest()
            case_document["asset_foundation_gate"]["stress_report_sha256"] = hashlib.sha256(
                case_stress_path.read_bytes()
            ).hexdigest()
            case_document = apply_mutations(case_document, case.get("mutations", []))
            errors = validate(
                case_document,
                project_root=artifact_root,
                asset_foundation_path=case_foundation_path,
                asset_stress_path=case_stress_path,
                asset_artifact_root=artifact_root,
                asset_review_receipt=review_receipt,
                asset_review_signature=review_signature,
                _asset_trust_registry_path=trust_registry_path,
            )
            expected = case["expected_error"]
            if any(error.startswith(expected + ":") for error in errors):
                rejected += 1
            else:
                failures.append(
                    f"{case['case_id']}: expected {expected}, got {errors[:3]}"
                )
    return failures, {
        "valid_fixture_passed": not valid_errors,
        "valid_seedance25_fixture_passed": not valid25_errors,
        "valid_v3_detail_binding_fixture_passed": not valid_v3_detail_errors,
        "negative_case_count": len(cases),
        "negative_cases_rejected": rejected,
        "node_count": len(valid.get("narrative_nodes", [])),
        "shot_count": len(valid.get("shots", [])),
        "generation_unit_count": len(valid.get("generation_units", [])),
        "binding_count": len(valid.get("bindings", [])),
        "asset_foundation_gate_validated": not any(
            error.startswith("asset_") for error in valid_errors
        ),
    }
