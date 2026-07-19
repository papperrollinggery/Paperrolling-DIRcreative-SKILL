#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests/fixtures/content-first/cases.json"
PROCESS_OPENERS = (
    "我会先",
    "我将先",
    "首先需要",
    "先进入",
    "已进入",
    "当前阶段",
    "执行流程",
    "路由结果",
    "阶段：",
    "阶段:",
)


def load_payload() -> dict[str, Any]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload.get("cases"), list) or not payload["cases"]:
        raise ValueError("content-first fixture must contain cases")
    return payload


def case_map() -> dict[str, dict[str, Any]]:
    cases = load_payload()["cases"]
    mapped = {case["id"]: case for case in cases}
    if len(mapped) != len(cases):
        raise ValueError("content-first case ids must be unique")
    return mapped


def substantive_line(answer: str) -> str:
    for raw in answer.splitlines():
        line = re.sub(r"^[\s#>*_`-]+", "", raw).strip()
        if line:
            return line
    return ""


def user_question_count(answer: str) -> int:
    count = 0
    for raw in answer.splitlines():
        line = raw.strip()
        if not line or line.startswith((">", "|")):
            continue
        if "用户确认点" in line or re.match(r"^(?:请确认|请选择|是否|需要你|你需要)", line):
            count += 1
            continue
        if line.endswith(("?", "？")) and not re.match(r"^[\"“'‘].*[\"”'’][?？]?$", line):
            count += 1
    return count


def audit_answer(answer: str, case: dict[str, Any], process_terms: list[str]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    stripped = answer.strip()
    if not stripped:
        return {"answer_bytes": 0}, ["answer_missing"]
    if stripped.startswith("{") and stripped.endswith("}"):
        errors.append("route_metadata_returned_instead_of_answer")

    answer_bytes = len(answer.encode("utf-8"))
    if answer_bytes < int(case["minimum_answer_bytes"]):
        errors.append(f"answer_too_short:{answer_bytes}")

    folded = answer.casefold()
    concept_hits: list[bool] = []
    for alternatives in case.get("required_concepts", []):
        hit = any(str(term).casefold() in folded for term in alternatives)
        concept_hits.append(hit)
        if not hit:
            errors.append("missing_concept:" + "|".join(alternatives))
    for term in case.get("forbidden_contains", []):
        if str(term).casefold() in folded:
            errors.append(f"forbidden_content:{term}")

    nonblank = [line.strip() for line in answer.splitlines() if line.strip()]
    total_chars = sum(len(line) for line in nonblank) or 1
    process_lines = [
        line
        for line in nonblank
        if any(term.casefold() in line.casefold() for term in process_terms)
    ]
    process_chars = sum(len(line) for line in process_lines)
    process_ratio = process_chars / total_chars
    useful_ratio = (total_chars - process_chars) / total_chars
    if process_ratio > float(case["maximum_process_narration_ratio"]):
        errors.append(f"process_narration_ratio:{process_ratio:.3f}")
    if useful_ratio < float(case["minimum_useful_content_ratio"]):
        errors.append(f"useful_content_ratio:{useful_ratio:.3f}")

    first_line = substantive_line(answer)
    if any(first_line.startswith(opener) for opener in PROCESS_OPENERS):
        errors.append(f"process_first_opener:{first_line[:40]}")
    question_count = user_question_count(answer)
    if question_count > int(case["maximum_questions"]):
        errors.append(f"too_many_questions:{question_count}")

    metrics = {
        "answer_bytes": answer_bytes,
        "concepts_passed": sum(concept_hits),
        "concepts_total": len(concept_hits),
        "first_line": first_line[:100],
        "process_narration_ratio": round(process_ratio, 4),
        "useful_content_ratio": round(useful_ratio, 4),
        "questions": question_count,
    }
    return metrics, errors


def audit_baselines() -> tuple[dict[str, Any], list[str]]:
    payload = load_payload()
    failures: list[str] = []
    results: dict[str, Any] = {}
    for case in payload["cases"]:
        snapshot = case.get("baseline_snapshot")
        if not snapshot:
            continue
        answer = (ROOT / snapshot).read_text(encoding="utf-8")
        metrics, errors = audit_answer(answer, case, payload["process_terms"])
        results[case["id"]] = metrics
        failures.extend(f"{case['id']}: {error}" for error in errors)

    negative = "我会先运行 dircreative_route.py，再执行 git status 和 validate_project.py。"
    negative_metrics, negative_errors = audit_answer(negative, payload["cases"][0], payload["process_terms"])
    negative_control = bool(negative_errors)
    if not negative_control:
        failures.append("process-only negative control was accepted")
    return {
        "status": "PASS" if not failures else "FAIL",
        "baseline_answers": results,
        "negative_control_rejected": negative_control,
        "negative_control_metrics": negative_metrics,
    }, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative answers for content-first behavior.")
    parser.add_argument(
        "--answer",
        action="append",
        default=[],
        metavar="CASE_ID=PATH",
        help="Audit one live answer file; repeat for multiple cases.",
    )
    args = parser.parse_args()
    try:
        payload = load_payload()
        cases = case_map()
        if not args.answer:
            report, failures = audit_baselines()
        else:
            failures = []
            results: dict[str, Any] = {}
            for binding in args.answer:
                case_id, separator, raw_path = binding.partition("=")
                if not separator or case_id not in cases:
                    raise ValueError(f"invalid answer binding: {binding}")
                path = Path(raw_path).expanduser().resolve()
                answer = path.read_text(encoding="utf-8")
                metrics, errors = audit_answer(answer, cases[case_id], payload["process_terms"])
                results[case_id] = {**metrics, "answer_path": str(path)}
                failures.extend(f"{case_id}: {error}" for error in errors)
            report = {"status": "PASS" if not failures else "FAIL", "live_answers": results}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        print("DIRCREATIVE_CONTENT_FIRST_AUDIT: FAIL")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        for failure in failures:
            print(f"- {failure}")
        print("DIRCREATIVE_CONTENT_FIRST_AUDIT: FAIL")
        return 1
    print("DIRCREATIVE_CONTENT_FIRST_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
