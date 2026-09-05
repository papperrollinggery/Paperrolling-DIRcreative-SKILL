#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL_PATH = ROOT / "skills/dircreative/SKILL.md"
SKILL_PATH = SOURCE_SKILL_PATH if SOURCE_SKILL_PATH.exists() else ROOT / "SKILL.md"
POLICY_PATH = ROOT / "skills/dircreative/agents/openai.yaml"
CASES_PATH = ROOT / "tests/fixtures/activation-policy/cases.json"
HANDOFF_PATH = ROOT / "tests/fixtures/activation-policy/valid-adco-v2-handoff.json"
DESCRIPTOR_PATH = ROOT / "docs/film-preproduction/schemas/adco-specialist-descriptor.json"


def activation_decision(
    text: str = "",
    handoff: dict[str, Any] | None = None,
    *,
    project_root: Path | None = None,
    descriptor: dict[str, Any] | None = None,
    handoff_path: Path | None = None,
) -> dict[str, Any]:
    if handoff is not None:
        from dircreative_adco_native_exchange import validate_handoff
        from dircreative_specialist_exchange_contract import valid_v2_handoff

        schema_valid = valid_v2_handoff(handoff)
        project_valid = (
            schema_valid
            and project_root is not None
            and descriptor is not None
            and not validate_handoff(
                project_root,
                handoff,
                descriptor,
                handoff_path=handoff_path,
            )
        )
        return {
            "allowed": project_valid,
            "execution_context": "orchestrated_worker" if project_valid else None,
            "reason_code": (
                "validated_adco_v2_handoff"
                if project_valid
                else "unverified_adco_handoff"
                if schema_valid
                else "invalid_adco_handoff"
            ),
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
    # Check the actual activation policy and behavior below, not one obsolete
    # English wording of the description. The entry still needs its identity
    # and a stated invocation/maintenance boundary.
    for term in ("name: dircreative", "description:", "## Invocation Boundary", "$dircreative", "source_maintenance"):
        if term not in skill_text:
            failures.append(f"SKILL missing activation boundary: {term}")
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
    descriptor = json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    unverified = activation_decision(handoff=handoff)
    if unverified["allowed"] or unverified["reason_code"] != "unverified_adco_handoff":
        failures.append(f"schema-only ADCO v2 handoff did not fail closed: {unverified}")
    with tempfile.TemporaryDirectory(prefix="dircreative-activation-adco-") as raw:
        from dircreative_adco_native_exchange import register_v2_fixture_handoff

        project = Path(raw)
        validated_handoff = copy.deepcopy(handoff)
        brief_path = project / str(validated_handoff["brief_snapshot"])
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text("Evidence-bound activation fixture.\n", encoding="utf-8")
        validated_handoff["locked_decisions"][0]["sha256"] = hashlib.sha256(
            brief_path.read_bytes()
        ).hexdigest()
        validated_handoff_path = project / "exchange/v2-handoff.json"
        validated_handoff_path.parent.mkdir(parents=True, exist_ok=True)
        validated_handoff_path.write_text(
            json.dumps(validated_handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output_parent = Path(str(validated_handoff["requested_outputs"][0]["path_root"])).parent
        register_v2_fixture_handoff(
            project,
            validated_handoff,
            validated_handoff_path,
            descriptor,
            receipt_path=(output_parent / "receipt.json").as_posix(),
        )
        decision = activation_decision(
            handoff=validated_handoff,
            project_root=project,
            descriptor=descriptor,
            handoff_path=validated_handoff_path,
        )
        if decision != {
            "allowed": True,
            "execution_context": "orchestrated_worker",
            "reason_code": "validated_adco_v2_handoff",
        }:
            failures.append(f"valid ADCO v2 handoff was not accepted: {decision}")
        invalid_handoff = dict(validated_handoff, execution_mode="codex_thread")
        if activation_decision(
            handoff=invalid_handoff,
            project_root=project,
            descriptor=descriptor,
            handoff_path=validated_handoff_path,
        )["allowed"]:
            failures.append("non-inline ADCO v2 handoff was accepted")
        invalid_shapes = [
            dict(validated_handoff, requested_outputs=[]),
            dict(validated_handoff, locked_decisions=[1]),
            dict(validated_handoff, quality_targets=[""]),
            dict(validated_handoff, requested_outputs=[validated_handoff["requested_outputs"][0]] * 2),
            dict(
                validated_handoff,
                requested_outputs=[
                    validated_handoff["requested_outputs"][0],
                    {**validated_handoff["requested_outputs"][0], "output_id": "OUT-02"},
                ],
            ),
        ]
        for index, invalid_shape in enumerate(invalid_shapes, start=1):
            if activation_decision(
                handoff=invalid_shape,
                project_root=project,
                descriptor=descriptor,
                handoff_path=validated_handoff_path,
            )["allowed"]:
                failures.append(f"invalid ADCO v2 handoff {index} was accepted")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative explicit activation policy.")
    parser.add_argument("--text", help="Classify a standalone user request.")
    parser.add_argument("--handoff", type=Path, help="Classify an ADCO handoff JSON file.")
    parser.add_argument("--project-root", type=Path, help="Project root required for a real handoff.")
    parser.add_argument("--descriptor", type=Path, default=DESCRIPTOR_PATH)
    args = parser.parse_args()
    if args.text is not None or args.handoff is not None:
        handoff = json.loads(args.handoff.read_text(encoding="utf-8")) if args.handoff else None
        descriptor = json.loads(args.descriptor.read_text(encoding="utf-8")) if handoff and args.project_root else None
        project_root = args.project_root.expanduser().resolve() if args.project_root else None
        print(
            json.dumps(
                activation_decision(
                    args.text or "",
                    handoff,
                    project_root=project_root,
                    descriptor=descriptor,
                    handoff_path=args.handoff.expanduser().resolve() if args.handoff else None,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
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
