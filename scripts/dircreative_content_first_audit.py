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
SHOT_LINE_RE = re.compile(
    r"^\s*(?:\|\s*|[-*]\s*|#{1,6}\s*)?(?:\*\*)?"
    r"(?P<shot>S?[0-9]{2})(?:\*\*)?(?=\s*(?:[|·:\-–—]|$))(?P<body>[^\n]*)",
    flags=re.MULTILINE,
)
LINE_TIMECODE_RE = re.compile(
    r"(?P<start>[0-9]{2,}:[0-5][0-9](?:\.[0-9]+)?)\s*[\-–—]\s*"
    r"(?P<end>[0-9]{2,}:[0-5][0-9](?:\.[0-9]+)?)"
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


def timecode_seconds(value: str) -> float:
    minutes, seconds = value.split(":", 1)
    return int(minutes) * 60 + float(seconds)


def audit_shot_structure(answer: str, contract: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    expected_count = int(contract["shot_count"])
    expected_ids = [f"S{index:02d}" for index in range(1, expected_count + 1)]
    entries: list[tuple[str, float, float, int]] = []
    for match in SHOT_LINE_RE.finditer(answer):
        raw_shot_id = match.group("shot")
        shot_id = raw_shot_id if raw_shot_id.startswith("S") else f"S{raw_shot_id}"
        body = match.group("body")
        timecode = LINE_TIMECODE_RE.search(body)
        if timecode is None:
            continue
        entries.append(
            (
                shot_id,
                timecode_seconds(timecode.group("start")),
                timecode_seconds(timecode.group("end")),
                len(body.strip()),
            )
        )

    shot_ids = [item[0] for item in entries]
    if shot_ids != expected_ids:
        missing = [shot_id for shot_id in expected_ids if shot_id not in shot_ids]
        duplicates = sorted({shot_id for shot_id in shot_ids if shot_ids.count(shot_id) > 1})
        errors.append(
            "shot_structure_coverage:"
            f"expected={expected_count}:found={len(shot_ids)}:"
            f"missing={','.join(missing)}:duplicates={','.join(duplicates)}"
        )

    minimum_detail = int(contract.get("minimum_shot_line_chars", 60))
    sparse = [shot_id for shot_id, _, _, length in entries if length < minimum_detail]
    if sparse:
        errors.append("shot_structure_too_sparse:" + ",".join(sparse))

    expected_start = 0.0
    timeline_ok = len(entries) == expected_count
    for shot_id, start, end, _ in entries:
        if abs(start - expected_start) > 0.001 or end <= start:
            timeline_ok = False
            errors.append(
                f"shot_timeline_discontinuous:{shot_id}:expected={expected_start:.3f}:start={start:.3f}:end={end:.3f}"
            )
            break
        expected_start = end
    expected_duration = float(contract["duration_seconds"])
    if not timeline_ok or abs(expected_start - expected_duration) > 0.001:
        errors.append(
            f"shot_timeline_duration:expected={expected_duration:.3f}:actual={expected_start:.3f}"
        )
    return {
        "formal_shot_lines": len(entries),
        "unique_formal_shots": len(set(shot_ids)),
        "timeline_end_seconds": round(expected_start, 3),
        "timeline_continuous": timeline_ok and abs(expected_start - expected_duration) <= 0.001,
    }, errors


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

    structural_metrics: dict[str, Any] = {}
    structural_contract = case.get("structural_contract")
    if isinstance(structural_contract, dict):
        structural_metrics, structural_errors = audit_shot_structure(answer, structural_contract)
        errors.extend(structural_errors)

    metrics = {
        "answer_bytes": answer_bytes,
        "concepts_passed": sum(concept_hits),
        "concepts_total": len(concept_hits),
        "first_line": first_line[:100],
        "process_narration_ratio": round(process_ratio, 4),
        "useful_content_ratio": round(useful_ratio, 4),
        "questions": question_count,
        **structural_metrics,
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
    studio_case = next(case for case in payload["cases"] if case["id"] == "studio_film_live")
    padded_single_shot = (
        "# 60 秒 16:9 方案\n"
        "| S01 · 00:00.0-01:00.0 | 24 个镜头、场景地理 Camera-FOV、逐镜分镜、"
        "导演故事板、clean_first_frame、声音、澄川冷萃 |\n"
        + "视觉与声音细节。" * 500
    )
    _, padded_errors = audit_answer(
        padded_single_shot,
        studio_case,
        payload["process_terms"],
    )
    padded_negative_control = any(
        error.startswith("shot_structure_coverage:") for error in padded_errors
    )
    if not padded_negative_control:
        failures.append("single-shot keyword-padded TVC negative control was accepted")

    def compact_timecode(seconds: float) -> str:
        minutes = int(seconds // 60)
        remainder = seconds - minutes * 60
        return f"{minutes:02d}:{remainder:04.1f}"

    alternate_table = "\n".join(
        (
            f"| **{index:02d}** | {compact_timecode((index - 1) * 2.5)}"
            f"–{compact_timecode(index * 2.5)} | "
            + "specific image, performance, camera, sound, edit, continuity and model-risk detail "
            + "for this formal shot row |"
        )
        for index in range(1, 25)
    )
    alternate_metrics, alternate_errors = audit_shot_structure(
        alternate_table,
        studio_case["structural_contract"],
    )
    alternate_table_control = not alternate_errors
    if not alternate_table_control:
        failures.append(
            "valid bold numeric/en-dash shot table was rejected: "
            + ";".join(alternate_errors)
        )
    return {
        "status": "PASS" if not failures else "FAIL",
        "baseline_answers": results,
        "negative_control_rejected": negative_control,
        "negative_control_metrics": negative_metrics,
        "single_shot_padded_negative_control_rejected": padded_negative_control,
        "bold_numeric_en_dash_table_control": alternate_table_control,
        "bold_numeric_en_dash_table_metrics": alternate_metrics,
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
