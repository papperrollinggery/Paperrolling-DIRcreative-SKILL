#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dircreative_specialist_exchange_contract import valid_v2_handoff


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL_PATH = ROOT / "skills/dircreative/SKILL.md"
SKILL_PATH = SOURCE_SKILL_PATH if SOURCE_SKILL_PATH.exists() else ROOT / "SKILL.md"
POLICY_PATH = ROOT / "skills/dircreative/agents/openai.yaml"
CASES_PATH = ROOT / "tests/fixtures/activation-policy/cases.json"
HANDOFF_PATH = ROOT / "tests/fixtures/activation-policy/valid-adco-v2-handoff.json"


def activation_decision(text: str = "", handoff: dict[str, Any] | None = None) -> dict[str, Any]:
    if handoff is not None:
        valid = valid_v2_handoff(handoff)
        return {
            "allowed": valid,
            "execution_context": "orchestrated_worker" if valid else None,
            "reason_code": "valid_adco_v2_handoff" if valid else "invalid_adco_handoff",
        }
    explicit = "$dircreative" in text.casefold()
    return {
        "allowed": explicit,
        "execution_context": "standalone_chat" if explicit else None,
        "reason_code": "explicit_invocation" if explicit else "implicit_invocation_disabled",
    }


def audit() -> list[str]:
    failures: list[str] = []
    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    policy_text = POLICY_PATH.read_text(encoding="utf-8")
    required_description_terms = (
        "explicitly invokes $dircreative",
        "maintaining, debugging, refactoring, testing, or evaluating",
        "maintaining ADCO",
        "ordinary code work",
        "factual questions",
        "generic advertising requests",
        "validated Specialist Exchange handoff",
    )
    for term in required_description_terms:
        if term not in skill_text:
            failures.append(f"SKILL description missing activation boundary: {term}")
    for term in (
        'display_name: "DIRcreative"',
        'default_prompt: "Use $dircreative for this film-preproduction task."',
        "allow_implicit_invocation: false",
    ):
        if term not in policy_text:
            failures.append(f"openai policy missing: {term}")

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        actual = activation_decision(case["input"])
        if actual["allowed"] is not case["expected_allowed"]:
            failures.append(f"{case['id']}: allowed={actual['allowed']}")
        if actual["execution_context"] != case["expected_context"]:
            failures.append(f"{case['id']}: execution_context={actual['execution_context']}")

    handoff = json.loads(HANDOFF_PATH.read_text(encoding="utf-8"))
    decision = activation_decision(handoff=handoff)
    if decision != {
        "allowed": True,
        "execution_context": "orchestrated_worker",
        "reason_code": "valid_adco_v2_handoff",
    }:
        failures.append(f"valid ADCO v2 handoff was not accepted: {decision}")
    invalid_handoff = dict(handoff, execution_mode="codex_thread")
    if activation_decision(handoff=invalid_handoff)["allowed"]:
        failures.append("non-inline ADCO v2 handoff was accepted")
    invalid_shapes = [
        dict(handoff, requested_outputs=[]),
        dict(handoff, locked_decisions=[1]),
        dict(handoff, quality_targets=[""]),
        dict(handoff, requested_outputs=[handoff["requested_outputs"][0]] * 2),
        dict(
            handoff,
            requested_outputs=[
                handoff["requested_outputs"][0],
                {**handoff["requested_outputs"][0], "output_id": "OUT-02"},
            ],
        ),
    ]
    for index, invalid_shape in enumerate(invalid_shapes, start=1):
        if activation_decision(handoff=invalid_shape)["allowed"]:
            failures.append(f"schema-invalid ADCO v2 handoff {index} was accepted")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative explicit activation policy.")
    parser.add_argument("--text", help="Classify a standalone user request.")
    parser.add_argument("--handoff", type=Path, help="Classify an ADCO handoff JSON file.")
    args = parser.parse_args()
    if args.text is not None or args.handoff is not None:
        handoff = json.loads(args.handoff.read_text(encoding="utf-8")) if args.handoff else None
        print(json.dumps(activation_decision(args.text or "", handoff), ensure_ascii=False, indent=2))
        return 0
    failures = audit()
    if failures:
        print("DIRCREATIVE_ACTIVATION_POLICY_AUDIT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("DIRCREATIVE_ACTIVATION_POLICY_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
