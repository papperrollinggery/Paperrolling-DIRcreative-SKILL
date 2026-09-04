#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from dircreative_visual_asset_plan import (
    GENERATED_STATUSES,
    TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED,
    load_json,
    validate_plan,
    contained_file,
    inspect_raster,
)
from dircreative_character_master_visual_gate import (
    load_character_master_receipt,
    load_headless_review_authorization,
)


ROOT = Path(__file__).resolve().parents[1]
MEDIA_SCOPES = {"prompt_only", "dry_run_fixture", "pre_video_assets"}


def evaluate(
    plan: Any,
    *,
    base_dir: Path,
    media_scope: str,
    image_generation_authorized: bool,
    video_generation_authorized: bool,
) -> dict[str, Any]:
    required_assets = [
        asset
        for asset in plan.get("assets", [])
        if isinstance(asset, dict) and asset.get("required") is True
    ] if isinstance(plan, dict) else []
    generated_assets = [
        asset
        for asset in required_assets
        if asset.get("status") in GENERATED_STATUSES
    ]
    missing_asset_ids = [
        str(asset.get("asset_id"))
        for asset in required_assets
        if asset.get("status") not in GENERATED_STATUSES
    ]
    base = {
        "media_scope": media_scope,
        "required_asset_count": len(required_assets),
        "generated_asset_count": len(generated_assets),
        "missing_asset_ids": missing_asset_ids,
        "generated_asset_set_complete": False,
        "visual_assets_complete": False,
        "reason_codes": [],
        "validation_errors": [],
    }
    if media_scope not in MEDIA_SCOPES:
        return {**base, "status": "invalid", "reason_codes": ["media_scope_invalid"]}
    if media_scope in {"prompt_only", "dry_run_fixture"}:
        return {**base, "status": "not_applicable"}
    if image_generation_authorized is not True:
        return {
            **base,
            "status": "invalid",
            "reason_codes": ["pre_video_assets_requires_image_authorization"],
        }
    if video_generation_authorized is not False:
        return {
            **base,
            "status": "invalid",
            "reason_codes": ["pre_video_assets_must_defer_video_generation"],
        }

    structural_errors, _metrics = validate_plan(plan, base_dir=base_dir)
    if structural_errors:
        return {
            **base,
            "status": "invalid",
            "reason_codes": ["visual_asset_plan_invalid"],
            "validation_errors": structural_errors,
        }
    if missing_asset_ids:
        return {
            **base,
            "status": "blocked",
            "reason_codes": ["pre_video_assets_requires_verified_images"],
        }

    evidence_plan = copy.deepcopy(plan)
    evidence_plan["completion_claim"] = (
        "sample_visual_assets_complete"
        if evidence_plan.get("scope") == "representative_sample"
        else "visual_assets_complete"
    )
    evidence_errors, _metrics = validate_plan(evidence_plan, base_dir=base_dir)
    permitted_non_acceptance_errors = {
        TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED,
        "independent_ai_review_cannot_grant_visual_assets_complete_without_human_or_authorized_review",
    }
    blocking_evidence_errors = [
        error for error in evidence_errors if error not in permitted_non_acceptance_errors
    ]
    if blocking_evidence_errors:
        return {
            **base,
            "status": "blocked",
            "reason_codes": ["generated_asset_evidence_incomplete"],
            "validation_errors": blocking_evidence_errors,
        }
    character_structure_errors: list[str] = []
    for asset in required_assets:
        if asset.get("role") != "character_identity_reference":
            continue
        image_path = contained_file(asset.get("generated_file"), base_dir)
        evidence, _reason = inspect_raster(image_path) if image_path is not None else (None, "missing")
        if evidence is None:
            character_structure_errors.append(str(asset.get("asset_id")))
            continue
        receipt, receipt_errors = load_character_master_receipt(
            asset,
            base_dir=base_dir,
            image_evidence=evidence,
        )
        headless_review_errors: list[str] = []
        if (
            isinstance(receipt, dict)
            and asset.get("character_mode") == "headless_safe"
            and receipt.get("status") == "applied_unverified"
        ):
            _review, headless_review_errors = load_headless_review_authorization(
                asset,
                base_dir=base_dir,
                image_evidence=evidence,
            )
        structure_status_ok = (
            isinstance(receipt, dict)
            and (
                receipt.get("status") == "pass"
                or (
                    asset.get("character_mode") == "headless_safe"
                    and receipt.get("status") == "applied_unverified"
                    and not headless_review_errors
                )
            )
        )
        if receipt_errors or headless_review_errors or not structure_status_ok:
            character_structure_errors.append(str(asset.get("asset_id")))
    if character_structure_errors:
        return {
            **base,
            "status": "blocked",
            "reason_codes": ["character_master_visual_structure_incomplete"],
            "validation_errors": character_structure_errors,
        }
    return {
        **base,
        "status": "ready_for_user_review",
        "generated_asset_set_complete": True,
        "reason_codes": ["trusted_host_adoption_and_user_lock_pending"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that an authorized pre-video workflow produced real reviewed image assets."
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--media-scope", required=True, choices=sorted(MEDIA_SCOPES))
    parser.add_argument("--image-generation-authorized", action="store_true")
    parser.add_argument("--video-generation-authorized", action="store_true")
    args = parser.parse_args()
    try:
        plan_path = args.plan.expanduser().resolve(strict=True)
        plan = load_json(plan_path)
        result = evaluate(
            plan,
            base_dir=plan_path.parent,
            media_scope=args.media_scope,
            image_generation_authorized=args.image_generation_authorized,
            video_generation_authorized=args.video_generation_authorized,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "status": "invalid",
            "reason_codes": ["input_unreadable"],
            "validation_errors": [f"{type(exc).__name__}:{exc}"],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"not_applicable", "ready_for_user_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
