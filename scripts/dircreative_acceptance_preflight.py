#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from dircreative_install_parity import (
    add_installed_runtime_arguments, installed_runtime_cli_args, verify_installed_runtime,
)


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "film-preproduction" / "live-chat-acceptance-runbook.md"
TEMPLATE = ROOT / "docs" / "film-preproduction" / "templates" / "live-user-acceptance.template.yaml"
RECEIPT = ROOT / ".dircreative" / "runs" / "live-user-acceptance.yaml"


def run(args: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode == 0, (proc.stdout + "\n" + proc.stderr).strip()


def extract_operator_prompt(runbook: str) -> str:
    v2 = re.search(r"(?m)^## V2 Operator Prompt\s*$", runbook)
    if v2:
        section = runbook[v2.end():]
        boundary = re.search(r"(?m)^## ", section)
        runbook = section[:boundary.start()] if boundary else section
    marker = "```text"
    start = runbook.index(marker) + len(marker)
    end = runbook.index("```", start)
    return runbook[start:end].strip()


def has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether DIRcreative is ready to start a real chat acceptance pass.")
    add_installed_runtime_arguments(parser)
    args = parser.parse_args()

    runbook = RUNBOOK.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    installation = verify_installed_runtime(
        required=args.require_installed, source_root=args.source_root, install_target=args.install_target,
        verify_remote_tag=args.verify_remote_tag, caller_root=ROOT,
    )
    objective_cmd = ["python3", "scripts/dircreative_objective_audit.py", *installed_runtime_cli_args(args)]
    objective_ok, objective_output = run(objective_cmd)
    operator_prompt = extract_operator_prompt(runbook)

    checks = [
        (
            "runbook_present",
            has_all(
                runbook,
                [
                    "The acceptance pass must happen in chat.",
                    "Do not create `.dircreative/runs/live-user-acceptance.yaml` until the user explicitly says the workflow is acceptable.",
                    "Required Chat Stages To Show",
                    "User Decision Requirements",
                ],
            ),
        ),
        (
            "template_guarded",
            has_all(
                template,
                [
                    "copy_only_after_real_user_acceptance: true",
                    "simulated_fixture_allowed: false",
                    "terminal_only_demo_allowed: false",
                    "status: not_accepted",
                    "real_user_acceptance_not_recorded",
                ],
            ),
        ),
        ("live_receipt_absent", not RECEIPT.exists()),
        ("installed_skill_present", installation.ok),
        ("install_parity_pass", installation.ok),
        ("technical_readiness_pass", objective_ok and "OBJECTIVE_TECHNICAL_READINESS: PASS" in objective_output),
        ("objective_still_blocked", "OBJECTIVE_COMPLETE: NO" in objective_output and "real user acceptance" in objective_output),
    ]

    print("DIRcreative Acceptance Preflight")
    print("=" * 72)
    failed = False
    for label, ok in checks:
        print(f"{label}: {'pass' if ok else 'fail'}")
        failed = failed or not ok
    print("receipt_creation_allowed: false")
    print("acceptance_mode: real_chat_only")
    print(f"require_installed: {str(args.require_installed).lower()}")
    print(f"installation_verification: {installation.evidence}")
    print("next_required_action: show operator prompt to the user and wait for explicit pass/fail feedback")
    print("operator_prompt:")
    print(operator_prompt)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
