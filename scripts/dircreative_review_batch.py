#!/usr/bin/env python3
"""Record one substantive batch review; never infer a visual pass or user lock."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dircreative_visual_asset_plan as planmod
from dircreative_verify_release import read_relative_regular_file_once

RUBRIC = (
    "truth_and_role_match", "coverage_and_continuity_match", "composition_readable",
    "artifact_free", "downstream_use_fit",
)
REVIEWER_TYPES = ("executor", "independent_ai", "human", "authorized_reviewer")


def review_input_help(plan: dict[str, Any], asset_ids: list[str]) -> dict[str, Any]:
    """Describe conditional inputs alongside the template, not inside its schema."""
    return {
        "reviewer_type_values": list(REVIEWER_TYPES),
        "rubric_values": [True, False, None],
        "rubric_note": "Use JSON booleans, not pass/fail strings. A pass requires all rubric values true; null remains unreviewed.",
        "decision_values": ["pass", "retry", "reject", "defer"],
        "retry_or_reject_requires": {"defects": [{"check_id": "one id from check_ids_by_asset", "observed": "the concrete visible failure"}]},
        "check_ids_by_asset": {a["asset_id"]: planmod.candidate_check_ids(a) for a in plan["assets"] if a["asset_id"] in asset_ids},
        "note": "Keep protected hashes/IDs from the template. Observations support AI review, not user acceptance. Do not add this help object to the saved review.",
    }


def read_object(root: Path, relative: str) -> dict[str, Any]:
    raw = read_relative_regular_file_once(root, relative, max_bytes=8 * 1024 * 1024, label="batch review input")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("batch_review_input_must_be_object")
    return value


def evidence_for(plan: dict[str, Any], ids: list[str], base: Path) -> dict[str, dict[str, Any]]:
    assets = {a["asset_id"]: a for a in plan["assets"]}
    result = {}
    for asset_id in ids:
        asset = assets.get(asset_id)
        if not isinstance(asset, dict) or asset.get("status") != "generated_candidate":
            raise ValueError("batch_review_requires_candidate:" + asset_id)
        image = planmod.contained_file(asset.get("generated_file"), base)
        evidence, reason = planmod.inspect_raster(image) if image else (None, "missing")
        if evidence is None or evidence["sha256"] != asset.get("generated_sha256") or evidence["pixel_sha256"] != asset.get("generated_pixel_sha256"):
            raise ValueError("batch_review_pixels_changed:" + asset_id + ":" + str(reason or "hash"))
        problem = planmod.validate_technical_receipt(
            asset.get("technical_receipt"), asset_id=asset_id, evidence=evidence,
            truth_locked_at=plan["truth_locked_at"],
        )
        if problem:
            raise ValueError("batch_review_technical_invalid:" + asset_id + ":" + problem)
        result[asset_id] = evidence
    return result


def make_template(plan: dict[str, Any], *, base_dir: Path, asset_ids: list[str] | None = None, prepare_probes: bool = True) -> dict[str, Any]:
    """Return the existing review manifest shape with all decisions pending."""
    errors, _ = planmod.validate_plan(plan, base_dir=base_dir, _validate_recorded_assets=False)
    if errors:
        raise ValueError("batch_review_plan_invalid:" + ",".join(errors))
    ids = asset_ids if asset_ids is not None else [
        a["asset_id"] for a in plan["assets"]
        if a.get("status") == "generated_candidate" and a.get("visual_qa_receipt") is None
    ]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("batch_review_scope_empty_or_duplicate")
    evidence = evidence_for(plan, ids, base_dir)
    assets = {a["asset_id"]: a for a in plan["assets"]}
    entries = []
    for asset_id in ids:
        asset = assets[asset_id]
        entries.append({
            "asset_id": asset_id, "role": asset["role"], "file_sha256": asset["generated_sha256"],
            "pixel_sha256": asset["generated_pixel_sha256"], "truth_sha256": asset["truth_sha256"],
            "rubric_id": planmod.visual_review_rubric_id(asset["role"]),
            "rubric": {key: None for key in RUBRIC}, "decision": "pending", "notes": "",
        })
        if prepare_probes and asset.get("role") == "character_identity_reference" and asset.get("identity_kind", "human") == "human":
            import dircreative_character_master_visual_gate as characters

            image_relative = asset["generated_file"]
            sidecar = base_dir / Path(image_relative).with_suffix(".character-master-visual.json")
            if sidecar.exists():
                probe, errors = characters.load_character_master_receipt(asset, base_dir=base_dir, image_evidence=evidence[asset_id])
                if errors:
                    raise ValueError("batch_review_probe_invalid:" + ",".join(errors))
            else:
                image_raw = read_relative_regular_file_once(base_dir, image_relative, max_bytes=characters.MAX_IMAGE_BYTES, label="reviewed character image")
                measured, error = characters.run_probe(image_raw)
                if error:
                    raise ValueError("batch_review_probe_unavailable:" + error)
                probe = characters.make_receipt(
                    asset_id=asset_id, asset_truth_sha256=asset["truth_sha256"],
                    image_evidence=evidence[asset_id], probe=measured,
                    checked_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    mode=asset["character_mode"],
                    derived_from_asset_id=asset.get("derived_from_asset_id"),
                    approved_source_master_sha256=asset.get("approved_source_master_sha256"),
                )
                immutable_json(sidecar, probe)
            if probe.get("status") == "blocked" and asset.get("character_mode") in {"headed_master", "headed_state"}:
                # The reviewer sees the diagnostic during the one visual review;
                # the helper never explains it away or marks it passed.
                entries[-1]["probe_resolution"] = {"receipt_sha256": probe["receipt_sha256"], "observed": ""}
    return {
        "schema_version": planmod.LOCAL_VISUAL_REVIEW_MANIFEST_VERSION,
        "ruleset": planmod.VISUAL_QA_RULESET,
        "review_subject_sha256": planmod.visual_review_subject_sha256(plan, scope_asset_ids=ids, asset_local=True),
        "scope_asset_ids": ids, "reviewed_at": None, "reviewer_type": None,
        "reviewer_id": None, "review_task_id": None, "assets": entries,
    }


def immutable_json(path: Path, value: dict[str, Any]) -> str:
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = read_relative_regular_file_once(path.parent, path.name, max_bytes=8 * 1024 * 1024, label="existing batch output")
        if existing != raw:
            raise ValueError("batch_review_output_exists_with_other_content")
    else:
        with path.open("xb") as f:
            f.write(raw)
    return hashlib.sha256(raw).hexdigest()


def record_review(
    plan: dict[str, Any], review: dict[str, Any], *, base_dir: Path, output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mechanical recording only. Review decisions must already be explicit."""
    base_dir = base_dir.resolve(strict=True)
    if output_dir.is_symlink():
        raise ValueError("batch_review_output_symlink")
    output_dir = output_dir.resolve()
    output_dir.relative_to(base_dir)
    ids = review.get("scope_asset_ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("batch_review_scope_invalid")
    expected = make_template(plan, base_dir=base_dir, asset_ids=ids, prepare_probes=False)
    if review.get("review_subject_sha256") != expected["review_subject_sha256"]:
        raise ValueError("batch_review_subject_changed")
    if set(review) != set(expected):
        raise ValueError("batch_review_fields_invalid")
    if any(review.get(key) != expected[key] for key in ("schema_version", "ruleset")):
        raise ValueError("batch_review_contract_invalid")
    rows = review.get("assets")
    if not isinstance(rows, list) or len(rows) != len(ids) or [r.get("asset_id") for r in rows if isinstance(r, dict)] != ids:
        raise ValueError("batch_review_entries_invalid")
    # Bind the supplied observations to the original draft, including rejected
    # rows; no stale rejection or acceptance may be copied onto new pixels.
    protected = ("asset_id", "role", "file_sha256", "pixel_sha256", "truth_sha256", "rubric_id")
    for row, template in zip(rows, expected["assets"]):
        extra = set(row) - set(template)
        if not set(template).issubset(row) or extra - {"probe_resolution", "defects"}:
            raise ValueError("batch_review_entry_fields_invalid")
        if any(row.get(k) != template[k] for k in protected):
            raise ValueError("batch_review_entry_changed:" + template["asset_id"])
        if row.get("decision") not in {"pass", "retry", "reject", "defer"}:
            raise ValueError("batch_review_decision_required:" + template["asset_id"])
        if not isinstance(row.get("notes"), str) or len(row["notes"].strip()) < 12:
            raise ValueError("batch_review_observation_required:" + template["asset_id"])
        if row["decision"] in {"retry", "reject"}:
            defects = row.get("defects")
            if (not isinstance(defects, list) or not defects
                or any(not isinstance(d, dict) or set(d) != {"check_id", "observed"} for d in defects)):
                raise ValueError("batch_review_failed_check_observations_required:" + template["asset_id"])
        elif "defects" in row:
            raise ValueError("batch_review_defects_require_retry_or_reject")
    reviewed = copy.deepcopy(review)
    if not reviewed.get("reviewed_at"):
        prior = output_dir / "observations.json"
        if prior.exists():
            existing = read_object(output_dir, prior.name)
            reviewed["reviewed_at"] = existing.get("reviewed_at")
        else:
            reviewed["reviewed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if (reviewed.get("reviewer_type") not in REVIEWER_TYPES
        or any(not isinstance(reviewed.get(k), str) or not planmod.ID_RE.fullmatch(reviewed[k]) for k in ("reviewer_id", "review_task_id"))
        or not planmod.timestamp_in_review_window(reviewed["reviewed_at"], not_before=plan["truth_locked_at"])):
        raise ValueError("batch_review_identity_or_timestamp_required")
    passed = [row for row in reviewed["assets"] if row["decision"] == "pass"]
    updated = copy.deepcopy(plan)
    receipts = []
    evidence = evidence_for(plan, ids, base_dir)
    # Per-asset manifests make subsequent changes to another batch member
    # independent. This is one visual review, not one review ceremony per file.
    prepared = []
    for row in passed:
        asset_id = row["asset_id"]
        single = {**reviewed, "scope_asset_ids": [asset_id], "assets": [row],
                  "review_subject_sha256": planmod.visual_review_subject_sha256(plan, scope_asset_ids=[asset_id], asset_local=True)}
        _entries, problem = planmod.validate_visual_review_manifest(
            single, payload=plan, evidence_by_asset=evidence, truth_locked_at=plan["truth_locked_at"],
        )
        if problem:
            raise ValueError("batch_review_invalid:" + problem)
        prepared.append((row, single))
    failed_checks = []
    for row in reviewed["assets"]:
        if row["decision"] not in {"retry", "reject"}:
            continue
        failed = planmod.candidate_self_check_template(plan, row["asset_id"])
        failed.update(schema_version=planmod.FAILED_BATCH_OBSERVATIONS_VERSION,
                      ruleset=planmod.FAILED_BATCH_OBSERVATIONS_RULESET, reviewer_type="batch_review",
                      reviewed_at=reviewed["reviewed_at"], reviewer_id=reviewed["reviewer_id"], review_task_id=reviewed["review_task_id"])
        failed["assets"][0].update(decision=row["decision"], observations=[
            {"check_id": d["check_id"], "result": "fail", "observed": d["observed"]} for d in row["defects"]
        ])
        errors = planmod.validate_candidate_self_check(failed, payload=plan, asset_id=row["asset_id"], base_dir=base_dir)
        if errors != ["candidate_self_check_requires_repair"]:
            raise ValueError("batch_review_failed_observations_invalid:" + ",".join(errors))
        failed_checks.append((row["asset_id"], failed))
    # No evidence writes before every passing row's substantive inputs validate.
    for row, single in prepared:
        asset_id = row["asset_id"]
        manifest_path = output_dir / f"{asset_id}.json"
        mh = immutable_json(manifest_path, single)
        receipt = {
            "receipt_version": planmod.VISUAL_QA_RECEIPT_VERSION, "asset_id": asset_id,
            "file_sha256": row["file_sha256"], "pixel_sha256": row["pixel_sha256"],
            "truth_sha256": row["truth_sha256"], "ruleset": planmod.VISUAL_QA_RULESET,
            **{key: single[key] for key in ("reviewed_at", "reviewer_type", "reviewer_id", "review_task_id")},
            "review_manifest_file": manifest_path.relative_to(base_dir).as_posix(),
            "review_manifest_sha256": mh, "review_subject_sha256": single["review_subject_sha256"],
            "status": "visual_qa_pass",
        }
        receipt["receipt_sha256"] = planmod.receipt_sha256(receipt)
        asset = next(a for a in updated["assets"] if a["asset_id"] == asset_id)
        asset["visual_qa_receipt"] = receipt
        # Keep generated_candidate. A review is not user adoption.
        receipts.append(asset_id)
    for row in reviewed["assets"]:
        if row["decision"] != "pass":
            next(a for a in updated["assets"] if a["asset_id"] == row["asset_id"])["visual_qa_receipt"] = None
    for asset_id, failed in failed_checks:
        failed_path = output_dir / f"{asset_id}-defects.json"
        failed_hash = immutable_json(failed_path, failed)
        next(a for a in updated["assets"] if a["asset_id"] == asset_id)["candidate_self_check"] = {
            "relative_path": failed_path.relative_to(base_dir).as_posix(), "sha256": failed_hash,
        }
    immutable_json(output_dir / "observations.json", reviewed)
    for asset_id in receipts:
        problems = planmod.candidate_visual_review_errors(updated, asset_id=asset_id, base_dir=base_dir)
        if problems:
            raise ValueError("batch_review_readback_invalid:" + ",".join(problems))
        asset = next(a for a in updated["assets"] if a["asset_id"] == asset_id)
        if asset.get("role") == "character_identity_reference" and asset.get("identity_kind", "human") == "human":
            import dircreative_character_master_visual_gate as characters

            probe, errors = characters.load_character_master_receipt(asset, base_dir=base_dir, image_evidence=evidence[asset_id])
            if errors or not isinstance(probe, dict):
                raise ValueError("batch_review_character_structure_invalid:" + asset_id)
            if asset.get("character_mode") == "headless_safe":
                _review, errors = characters.load_headless_review_authorization(asset, base_dir=base_dir, image_evidence=evidence[asset_id])
                if errors:
                    raise ValueError("batch_review_headless_authorization_required:" + asset_id)
            elif probe.get("status") != "pass" and not planmod.character_probe_resolved_by_review(asset, probe, base_dir=base_dir):
                raise ValueError("batch_review_character_probe_disagreement_unresolved:" + asset_id)
    summary = {
        "status": "review_recorded", "reviewed_asset_ids": receipts,
        "needs_attention": [r["asset_id"] for r in rows if r["decision"] != "pass"],
        "user_adoption": False, "completion_claim_changed": False,
        "next_action": "continue independent work; reuse passed review for unchanged draft inputs; repair only observed defects",
    }
    return updated, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("template", "record"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--asset-id", action="append")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--records-dir", type=Path)
    args = parser.parse_args()
    try:
        base = args.plan.parent.resolve(strict=True)
        plan = read_object(base, args.plan.name)
        output = args.output.absolute()
        if output.parent.resolve() != base or output.is_symlink():
            raise ValueError("batch_review_output_must_share_plan_directory")
        if args.action == "template":
            ids = args.asset_id
            if ids is None:
                ids = [a["asset_id"] for a in plan["assets"] if a.get("status") == "generated_candidate"
                       and (a.get("visual_qa_receipt") is None or planmod.candidate_visual_review_errors(plan, asset_id=a["asset_id"], base_dir=base))]
                if not ids:
                    errors, _ = planmod.validate_plan(plan, base_dir=base)
                    if errors:
                        raise ValueError("batch_review_plan_invalid:" + ",".join(errors))
                    print(json.dumps({"status": "no_review_required", "next_action": "reuse existing valid reviews; continue requested work"}))
                    return 0
            draft = make_template(plan, base_dir=base, asset_ids=ids)
            immutable_json(output, draft)
            print(json.dumps({"status": "review_pending", "review": str(output),
                              "asset_ids": draft["scope_asset_ids"],
                              "instruction": "view saved images once; fill explicit reviewer identity, rubric, decision and concrete notes; no pass is prefilled",
                              "input_help": review_input_help(plan, draft["scope_asset_ids"])}))
        else:
            if args.review is None:
                raise ValueError("record_requires_review")
            review_path = args.review.absolute()
            try:
                relative = review_path.relative_to(args.plan.parent.absolute())
            except ValueError:
                relative = review_path.relative_to(base)
            review = read_object(base, relative.as_posix())
            records = args.records_dir or (base / (output.stem + "-reviews"))
            updated, summary = record_review(plan, review, base_dir=base, output_dir=records)
            immutable_json(output, updated)
            print(json.dumps({**summary, "output": str(output)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "errors": [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
