from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from dircreative_validation_common import load_json


def validate_v3_detail_binding_fixture(
    *,
    ROOT: Path,
    temp_root: Path,
    valid: dict[str, Any],
    stress_template: dict[str, Any],
    all_shots: list[str],
    materialize_stress_fixture: Callable[..., Any],
    materialize_foundation_fixture: Callable[..., Any],
    validate: Callable[..., list[str]],
) -> list[str]:
    v3_artifact_root = temp_root / "v3-asset-evidence"
    v3_review_root = temp_root / "v3-reviews"
    v3_trust_root = temp_root / "v3-trust"
    v3_artifact_root.mkdir()
    v3_review_root.mkdir()
    v3_trust_root.mkdir()
    v3_template = load_json(
        ROOT / "tests/fixtures/asset-stress-test/valid-report-v3-headed.json"
    )
    v3_template["project_id"] = valid["project_id"]
    v3_character_asset = v3_template["assets"][0]
    v3_character_asset["asset_id"] = "VE-RING-ID-v01"
    v3_character_asset["asset_version"] = "v3"
    v3_character_asset["canonical_relative_path"] = "canonical/VE-RING-ID-v01.png"
    v3_character_asset["state_family"] = "RING-IDENTITY"
    v3_character_asset["state_id"] = "RING-BASE"
    for test_case in v3_template["test_cases"]:
        test_case["asset_id"] = v3_character_asset["asset_id"]
        test_case["state_family"] = v3_character_asset["state_family"]
        test_case["test_case_id"] = "V3-" + str(test_case["test_case_id"])
        for evidence in test_case["evidence"]:
            evidence["evidence_id"] = "V3-" + str(evidence["evidence_id"])
            evidence["relative_path"] = "evidence/v3-" + Path(
                str(evidence["relative_path"])
            ).name
    generic_assets = copy.deepcopy(stress_template["assets"][1:])
    generic_asset_ids = {str(asset["asset_id"]) for asset in generic_assets}
    generic_cases = [
        copy.deepcopy(test_case)
        for test_case in stress_template["test_cases"]
        if str(test_case.get("asset_id")) in generic_asset_ids
    ]
    v3_template["assets"] = [v3_character_asset, *generic_assets]
    v3_template["test_cases"] = [*v3_template["test_cases"], *generic_cases]
    v3_template["matrix_config"]["minimum_case_count"] = len(
        v3_template["test_cases"]
    )
    v3_template["matrix_config"]["required_case_kinds"] = sorted(
        {str(test_case["case_kind"]) for test_case in v3_template["test_cases"]}
    )
    v3_template["verdict"]["status"] = "certified"
    v3_template["verdict"]["allowed_shot_scope"] = sorted(
        {
            shot_class
            for asset in v3_template["assets"]
            for shot_class in asset["intended_shot_classes"]
        }
    )
    v3_template["verdict"]["blocked_shot_scope"] = []
    (
        v3_stress,
        v3_review_receipt,
        v3_review_signature,
        v3_trust_registry,
    ) = materialize_stress_fixture(
        v3_template,
        v3_artifact_root,
        v3_review_root,
        v3_trust_root,
    )
    v3_foundation = load_json(
        ROOT / "tests/fixtures/asset-foundation/valid-pass.json"
    )
    v3_foundation["project_id"] = valid["project_id"]
    v3_foundation["canonical_asset_ids"] = [
        asset["asset_id"] for asset in v3_stress["assets"]
    ]
    v3_planning_source = next(
        item
        for item in v3_foundation["source_assets"]
        if item["source_kind"] == "planning_only"
    )
    v3_foundation["source_assets"] = [
        {
            "asset_id": asset["asset_id"],
            "source_kind": "canonical_asset",
            "role": "canonical",
            "relative_path": asset["canonical_relative_path"],
            "sha256": asset["canonical_sha256"],
        }
        for asset in v3_stress["assets"]
    ] + [v3_planning_source]
    v3_foundation["target_shot_ids"] = all_shots
    v3_foundation["stress_test_binding"] = {
        "stress_test_id": v3_stress["stress_test_id"],
        "covered_asset_ids": [asset["asset_id"] for asset in v3_stress["assets"]],
        "report_relative_path": "stress/v3-stress-report.json",
        "report_sha256": "0" * 64,
        "verdict": "certified",
        "validation_status": "passed",
        "allowed_shot_scope": all_shots,
        "blocked_shot_scope": [],
    }
    v3_foundation["compile_gate"] = {
        "requested_shot_ids": all_shots,
        "status": "allowed",
        "reason_codes": [],
    }
    v3_stress_path = v3_artifact_root / "stress/v3-stress-report.json"
    v3_stress_path.parent.mkdir(parents=True, exist_ok=True)
    v3_stress_path.write_text(
        json.dumps(v3_stress, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    v3_foundation = materialize_foundation_fixture(v3_foundation, v3_artifact_root)
    v3_foundation["stress_test_binding"]["report_sha256"] = hashlib.sha256(
        v3_stress_path.read_bytes()
    ).hexdigest()
    v3_foundation_path = temp_root / "v3-asset-foundation-pass.json"
    v3_foundation_path.write_text(
        json.dumps(v3_foundation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    valid_v3_detail = copy.deepcopy(valid)
    v3_source_map = {
        source["asset_id"]: source
        for source in v3_foundation["source_assets"]
        if source["source_kind"] == "canonical_asset"
    }
    v3_stress_asset_map = {
        asset["asset_id"]: asset for asset in v3_stress["assets"]
    }
    for binding in valid_v3_detail["bindings"]:
        if binding["asset_id"] not in v3_source_map:
            continue
        binding["asset_version"] = v3_stress_asset_map[binding["asset_id"]][
            "asset_version"
        ]
        binding["relative_path"] = v3_source_map[binding["asset_id"]][
            "relative_path"
        ]
        binding["sha256"] = v3_source_map[binding["asset_id"]]["sha256"]
    valid_v3_detail["bindings"][0]["source_kind"] = "character_master_sheet"
    v3_detail_reference_id = v3_character_asset["character_sheet_contract"][
        "detail_reference_id"
    ]
    v3_detail_reference = next(
        reference
        for reference in v3_stress_asset_map["VE-RING-ID-v01"]["references"]
        if reference["reference_id"] == v3_detail_reference_id
    )
    detail_binding = copy.deepcopy(valid_v3_detail["bindings"][1])
    detail_binding.update(
        {
            "binding_id": "B07",
            "asset_id": "VE-RING-ID-v01",
            "reference_id": v3_detail_reference_id,
            "asset_version": v3_stress_asset_map["VE-RING-ID-v01"]["asset_version"],
            "relative_path": v3_detail_reference["relative_path"],
            "sha256": v3_detail_reference["sha256"],
            "source_kind": "character_detail_sheet",
            "global_number": 7,
            "converter_slot": "【图片7】",
            "platform_slot": "@Image 7",
            "role": "visible garment detail only",
            "must_not_control": ["face identity", "body proportions"],
            "literal_frame_boolean": False,
            "shot_ids": ["SH01", "SH02"],
            "unit_ids": ["GU01"],
            "local_order_by_gu": {"GU01": 3},
        }
    )
    valid_v3_detail["bindings"].append(detail_binding)
    valid_v3_detail["prompt_units"][0]["binding_ids"].append("B07")
    valid_v3_detail["prompt_units"][0]["prompt_text"] = (
        "@Image 1 locks ring identity. @Image 2 locks the clean end frame. "
        "@Image 3 locks visible garment details only.\n\n\n"
        "Show the enemy entering and the ring receiving one fixed strike."
    )
    valid_v3_detail["prompt_units"][0]["prompt_sha256"] = hashlib.sha256(
        valid_v3_detail["prompt_units"][0]["prompt_text"].encode("utf-8")
    ).hexdigest()
    valid_v3_detail["asset_foundation_gate"] = {
        "project_id": v3_foundation["project_id"],
        "pass_id": v3_foundation["pass_id"],
        "pass_artifact_sha256": hashlib.sha256(
            v3_foundation_path.read_bytes()
        ).hexdigest(),
        "stress_test_id": v3_stress["stress_test_id"],
        "stress_report_sha256": hashlib.sha256(
            v3_stress_path.read_bytes()
        ).hexdigest(),
        "stress_verdict": "certified",
        "requested_shot_ids": all_shots,
        "allowed_shot_ids": all_shots,
        "blocked_shot_ids": [],
        "covered_asset_ids": v3_foundation["stress_test_binding"][
            "covered_asset_ids"
        ],
    }
    valid_v3_detail_errors = validate(
        valid_v3_detail,
        asset_foundation_path=v3_foundation_path,
        asset_stress_path=v3_stress_path,
        asset_artifact_root=v3_artifact_root,
        asset_review_receipt=v3_review_receipt,
        asset_review_signature=v3_review_signature,
        _asset_trust_registry_path=v3_trust_registry,
    )
    return valid_v3_detail_errors
