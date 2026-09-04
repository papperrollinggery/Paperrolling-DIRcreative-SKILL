#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from dircreative_verify_release import read_regular_file_once


CONTRACT_ID = "humanization_execution_gate_v1"
ACTIVE_AUTHORITIES = {"new_draft", "bounded_edit", "pending_evidence_bound_edit"}
MAX_INPUT_BYTES = 1024 * 1024
MAX_TEXT_BYTES = 8 * 1024 * 1024


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _contained_file(base_dir: Path, relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    try:
        root = base_dir.resolve(strict=True)
        candidate = root.joinpath(*relative.split("/"))
        path = candidate.resolve(strict=True)
        path.relative_to(root)
    except (OSError, ValueError, RuntimeError):
        return None
    if path != candidate or not path.is_file():
        return None
    return path


def _sha256_file(path: Path) -> str:
    data = read_regular_file_once(path, max_bytes=MAX_TEXT_BYTES, label="humanization text")
    return hashlib.sha256(data).hexdigest()


def required_providers(plan: dict[str, Any]) -> set[str]:
    required: set[str] = set()
    for step in plan.get("provider_steps", []):
        if not isinstance(step, dict):
            continue
        provider = step.get("provider")
        if step.get("authority") in ACTIVE_AUTHORITIES and provider not in {None, "dircreative"}:
            required.add(str(provider))
        validator = step.get("validator")
        if validator:
            required.add(str(validator))
    return required


def evaluate(
    plan: Any,
    receipt: Any | None,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    base = {
        "execution_status": "not_run",
        "text_revision_applied": False,
        "completion_claim_allowed": False,
        "evidence_authority": "none",
        "reason_codes": [],
    }
    if not isinstance(plan, dict) or plan.get("status") != "ready":
        return {**base, "execution_status": "invalid", "reason_codes": ["humanization_plan_not_ready"]}
    if receipt is None:
        return base
    if not isinstance(receipt, dict) or receipt.get("contract_id") != CONTRACT_ID:
        return {**base, "execution_status": "invalid", "reason_codes": ["execution_receipt_invalid"]}
    reasons: list[str] = []
    if receipt.get("plan_sha256") != canonical_sha256(plan):
        reasons.append("humanization_plan_hash_mismatch")
    draft_path = _contained_file(base_dir, receipt.get("draft_file"))
    result_path = _contained_file(base_dir, receipt.get("result_file"))
    if draft_path is None:
        reasons.append("draft_file_missing_or_outside_root")
    else:
        try:
            if receipt.get("draft_sha256") != _sha256_file(draft_path):
                reasons.append("draft_sha256_mismatch")
        except ValueError:
            reasons.append("draft_file_unsafe")
    if result_path is None:
        reasons.append("result_file_missing_or_outside_root")
    else:
        try:
            if receipt.get("result_sha256") != _sha256_file(result_path):
                reasons.append("result_sha256_mismatch")
        except ValueError:
            reasons.append("result_file_unsafe")

    runs = receipt.get("provider_runs")
    executed: dict[str, dict[str, Any]] = {}
    if not isinstance(runs, list):
        reasons.append("provider_runs_missing")
    else:
        for run in runs:
            if not isinstance(run, dict) or run.get("status") != "executed":
                continue
            provider = run.get("provider")
            if isinstance(provider, str):
                executed[provider] = run
        for provider in sorted(required_providers(plan)):
            if provider not in executed:
                reasons.append(f"required_provider_not_executed:{provider}")
    result_sha = receipt.get("result_sha256")
    for provider, run in executed.items():
        output_sha = run.get("output_sha256")
        if not isinstance(output_sha, str) or len(output_sha) != 64 or any(
            char not in "0123456789abcdef" for char in output_sha
        ):
            reasons.append(f"provider_output_hash_invalid:{provider}")
    validator_providers = {
        str(step.get("validator"))
        for step in plan.get("provider_steps", [])
        if isinstance(step, dict) and step.get("validator")
    }
    for provider in validator_providers:
        if provider in executed and executed[provider].get("output_sha256") != result_sha:
            reasons.append(f"final_validator_not_bound_to_result:{provider}")

    for field in ("protected_content_diff", "overcorrection_check", "read_aloud_review"):
        if receipt.get(field) != "pass":
            reasons.append(f"{field}_not_passed")
    if receipt.get("status") != "applied":
        reasons.append("execution_receipt_not_applied")
    if (
        draft_path is not None
        and result_path is not None
        and receipt.get("draft_sha256") == receipt.get("result_sha256")
    ):
        reasons.append("revision_bytes_unchanged")
    if reasons:
        return {
            **base,
            "execution_status": "blocked",
            "reason_codes": list(dict.fromkeys(reasons)),
        }
    return {
        **base,
        "execution_status": "applied_unverified",
        "text_revision_applied": True,
        "completion_claim_allowed": False,
        "evidence_authority": "self_reported_local_receipt",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a DIRcreative humanization plan was actually executed on bound text.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.plan.stat().st_size > MAX_INPUT_BYTES or args.receipt.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("humanization_gate_input_too_large")
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        result = evaluate(plan, receipt, base_dir=args.artifact_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "execution_status": "invalid",
            "text_revision_applied": False,
            "completion_claim_allowed": False,
            "evidence_authority": "none",
            "reason_codes": [f"input_unreadable:{type(exc).__name__}"],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["execution_status"] == "applied_unverified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
