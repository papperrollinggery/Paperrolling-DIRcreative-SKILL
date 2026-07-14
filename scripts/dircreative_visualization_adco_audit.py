#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dircreative_visualization_spec import load_document, render_fallback, validate_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/chat-visualization/valid-adco-worker-fallback.json"
CAPABILITY = "dircreative.chat-visualization@1.0"
BACKSTAGE_RE = re.compile(
    r"(?:\b(?:artifact|gate|receipt|sha256|writeback|prompt-only)\b|source truth|项目写回|新建锁|保留锁)",
    re.IGNORECASE,
)


def negotiated_mode(capabilities: list[str]) -> str:
    return "adco_projection" if CAPABILITY in capabilities else "text_fallback"


def adco_projection(provider: dict[str, Any]) -> dict[str, Any]:
    errors = validate_document(provider)
    if errors:
        raise ValueError("invalid DIR provider visualization: " + "; ".join(errors))
    if provider.get("execution_context") != "orchestrated_worker":
        raise ValueError("ADCO projection requires an orchestrated_worker provider spec")
    if provider.get("controller") != {"surface_owner": "ad-creative-orchestrator", "user_facing": False}:
        raise ValueError("DIR provider spec must remain ADCO-owned and provider-hidden")
    artifacts = [
        {
            "artifact_id": item["artifact_id"],
            "path": f"AD-creative/handoff/{item['artifact_id']}.json",
            "version": item["version"],
            "sha256": item["sha256"],
            "lifecycle": "current",
        }
        for item in provider["source_truth"]["artifacts"]
    ]
    fields = [
        {
            "id": item["id"].replace("_", "-"),
            "label": item["label"],
            "value": item["value"],
            "provenance": "source-bound" if item["classification"] == "source_bound" else "presentation-only",
            "source_ref": item["source_ref"],
        }
        for item in provider["presentation"]["fields"]
    ]
    if len(fields) < 2:
        fields.append(
            {
                "id": "provider-boundary",
                "label": "当前边界",
                "value": "由项目负责人决定是否向用户展示",
                "provenance": "presentation-only",
                "source_ref": None,
            }
        )
    options = [
        {
            "id": item["id"].replace("_", "-"),
            "label": item["label"],
            "summary": item["summary"],
            "tradeoff": item["tradeoff"],
            "source_refs": item["source_refs"],
        }
        for item in provider["presentation"].get("options", [])
    ]
    recommendation = provider["presentation"].get("recommendation")
    if recommendation:
        recommendation = {
            "option_id": recommendation["option_id"].replace("_", "-"),
            "reason": recommendation["reason"],
        }
    effects = [
        {"phase": "P3", "effect": item["effect"]}
        for item in provider["presentation"].get("downstream_effects", [])
    ]
    return {
        "contract": "adco.chat-visualization@1.0",
        "view_id": provider["view_id"],
        "execution_context": "orchestrated_provider",
        "controller": {"surface_owner": "ad-creative-orchestrator", "user_facing": False},
        "phase": "P3",
        "surface": {
            "kind": "option-comparison" if options else "current-status",
            "title": "故事建议待检查",
            "summary": "DIRcreative 返回了故事转折建议，由项目负责人决定是否进入用户讨论。",
            "question": provider["fallback"]["decision_question"],
        },
        "source_truth": {
            "project_id": "adco-host-project",
            "current_version": artifacts[0]["version"],
            "artifacts": artifacts,
        },
        "presentation": {
            "fields": fields,
            "options": options,
            "recommendation": recommendation,
            "downstream_effects": effects,
        },
        "interactions": {
            "local_state": ["expanded-detail"],
            "actions": [
                {
                    "id": "adco-inspect",
                    "label": "交由项目负责人检查",
                    "kind": "inspect-detail",
                    "target_gate": "provider-adoption-gate",
                    "conversation_intent": "请检查这项故事建议，再决定是否向用户展示。",
                }
            ],
        },
        "write_boundary": {
            "component_writes_authoritative_state": False,
            "conversation_intent_only": True,
            "write_owner": "ad-creative-orchestrator",
            "revalidation_command": "adco validate <project>",
            "forbidden_claims": ["approval", "readiness", "send", "completion", "global-install"],
        },
        "fallback": {
            "summary": "故事建议由项目负责人检查后再决定是否展示。",
            "table": {
                "headers": ["内容", "当前说明"],
                "rows": [[item["label"], str(item["value"])] for item in fields],
            },
            "mermaid": "flowchart LR\n  DIRcreative --> ADCO --> User",
            "decision_prompt": provider["fallback"]["decision_question"],
        },
    }


def frontstage_strings(document: dict[str, Any]) -> list[str]:
    values: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in {"target_gate", "revalidation_command", "source_ref", "source_refs"}:
                    walk(item)

    for key in ("surface", "presentation", "interactions", "fallback"):
        walk(document[key])
    return values


def self_test() -> list[str]:
    failures: list[str] = []
    provider = load_document(FIXTURE)
    if negotiated_mode([]) != "text_fallback":
        failures.append("missing capability must preserve text fallback")
    if negotiated_mode([CAPABILITY]) != "adco_projection":
        failures.append("negotiated capability did not enable ADCO projection")
    if validate_document(provider):
        failures.append("DIR provider fixture is invalid")
        return failures
    if "故事逻辑" not in render_fallback(provider):
        failures.append("DIR provider fallback is incomplete")
    projected = adco_projection(provider)
    if not provider["presentation"].get("options") and projected["surface"]["kind"] != "current-status":
        failures.append("provider status projection fabricated a blocking user decision")
    if projected["execution_context"] != "orchestrated_provider":
        failures.append("projection lost ADCO provider context")
    if projected["controller"] != {"surface_owner": "ad-creative-orchestrator", "user_facing": False}:
        failures.append("projection escalated provider visibility or ownership")
    if projected["write_boundary"]["component_writes_authoritative_state"] is not False:
        failures.append("projection granted component write authority")
    leaked = [value for value in frontstage_strings(projected) if BACKSTAGE_RE.search(value)]
    if leaked:
        failures.append("projection leaks backstage terms: " + ", ".join(leaked))
    return failures


def cross_repo_audit(adco_repo: Path) -> tuple[list[str], dict[str, Any]]:
    failures = self_test()
    script = adco_repo / "skill_drafts/ad-creative-orchestrator/scripts/adco_visualization.py"
    if not script.is_file():
        return failures + ["ADCO visualization validator is missing"], {}
    projected = adco_projection(load_document(FIXTURE))
    with tempfile.TemporaryDirectory(prefix="dircreative-adco-visual-") as tmp:
        projected_path = Path(tmp) / "dircreative-provider-projection.json"
        projected_path.write_text(json.dumps(projected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validate_proc = subprocess.run(
            [sys.executable, str(script), "validate", str(projected_path)],
            cwd=adco_repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    self_test_proc = subprocess.run(
        [sys.executable, str(script), "self-test"],
        cwd=adco_repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if validate_proc.returncode != 0:
        failures.append("ADCO rejected DIR provider projection")
    if self_test_proc.returncode != 0:
        failures.append("ADCO visualization self-test is not green")
    return failures, {
        "projection_returncode": validate_proc.returncode,
        "projection_stdout": validate_proc.stdout.strip(),
        "projection_stderr": validate_proc.stderr.strip(),
        "adco_self_test_returncode": self_test_proc.returncode,
        "adco_self_test_stdout": self_test_proc.stdout.strip(),
        "adco_self_test_stderr": self_test_proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative visualization projection into ADCO.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--adco-repo")
    args = parser.parse_args()
    if args.adco_repo:
        failures, evidence = cross_repo_audit(Path(args.adco_repo).expanduser().resolve())
        print("DIRcreative / ADCO Visualization Projection Audit")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        marker = "PASS" if not failures else "FAIL"
        print(f"BILATERAL_VISUALIZATION_COMPATIBILITY: {marker}")
    else:
        failures = self_test()
        marker = "PASS" if not failures else "FAIL"
        print(f"ADCO_VISUALIZATION_PROJECTION_SELF_TEST: {marker}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
