#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from dircreative_chat_contract import stage_gate_exempts, transcript_checks
from dircreative_validation_harness import ROOT

STAGE_RE = re.compile(r"阶段:\s*([^\n`]+)")


CONFIRM_STAGE_EXEMPTS, SIMULATED_DECISION_STAGE_EXEMPTS = stage_gate_exempts()
INTERNAL_SECTION_HEADERS = (
    "智能体创作内容:",
    "prompt-only产物:",
    "生产状态:",
    "后台证据",
    "pre_generation_contract",
    "direct video input policy",
)


def stage_block(text: str, stage: str) -> tuple[str | None, str]:
    start = text.find(stage)
    if start == -1:
        return None, f"missing stage: {stage}"
    next_start = text.find("阶段:", start + len(stage))
    if next_start == -1:
        next_start = len(text)
    return text[start:next_start], "ok"


def stage_positions(text: str, stages: list[str]) -> tuple[bool, str]:
    cursor = -1
    for stage in stages:
        index = text.find(stage, cursor + 1)
        if index == -1:
            return False, f"missing stage: {stage}"
        if index < cursor:
            return False, f"stage out of order: {stage}"
        cursor = index
    return True, "ok"


def forbidden_before_contract(text: str, forbidden: list[str]) -> tuple[bool, str]:
    contract_index = text.find("阶段: 出图执行建议")
    if contract_index == -1:
        return False, "missing stage: 阶段: 出图执行建议"
    for stage in forbidden:
        index = text.find(stage)
        if index != -1 and index < contract_index:
            return False, f"{stage} appears before 阶段: 出图执行建议"
    return True, "ok"


def content_terms(text: str, required_terms: list[str], required_any_terms: list[list[str]]) -> tuple[bool, str]:
    lower_text = text.lower()
    missing = [term for term in required_terms if term.lower() not in lower_text]
    for group in required_any_terms:
        if not any(term.lower() in lower_text for term in group):
            missing.append(" or ".join(group))
    if missing:
        return False, "missing terms: " + ", ".join(missing)
    if "```yaml" in text or "```yml" in text:
        return False, "contains fenced raw YAML in chat transcript"
    if "真实工具调用: true" in text or "video_generated: true" in text:
        return False, "claims real tool or video generation inside prompt-only chat surface"
    return True, "ok"


def count_terms(text: str, min_counts: dict[str, int]) -> tuple[bool, str]:
    failures = []
    for term, minimum in min_counts.items():
        actual = text.count(term)
        if actual < minimum:
            failures.append(f"{term} count {actual} < {minimum}")
    if failures:
        return False, "; ".join(failures)
    return True, "ok"


def stage_gate_integrity(text: str, simulated_required: bool) -> tuple[bool, str]:
    starts = [match.start() for match in re.finditer("阶段:", text)]
    failures: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        block = text[start:end]
        title = block.splitlines()[0].strip()
        if not any(title.startswith(stage_start) for stage_start in CONFIRM_STAGE_EXEMPTS) and "用户确认点" not in block:
            failures.append(f"{title} missing 用户确认点")
        if (
            simulated_required
            and "用户确认点" in block
            and "模拟用户选择" not in block
            and not any(title.startswith(stage_start) for stage_start in SIMULATED_DECISION_STAGE_EXEMPTS)
        ):
            failures.append(f"{title} missing 模拟用户选择")
    if failures:
        return False, "; ".join(failures)
    return True, "ok"


def customer_preview_integrity(text: str, required_stages: list[str]) -> tuple[bool, str]:
    failures: list[str] = []
    for stage in required_stages:
        block, reason = stage_block(text, stage)
        if block is None:
            failures.append(reason)
            continue
        preview_index = block.find("客户可见预览:")
        if preview_index == -1:
            failures.append(f"{stage} missing 客户可见预览")
            continue
        internal_indexes = [
            block.find(header)
            for header in INTERNAL_SECTION_HEADERS
            if block.find(header) != -1
        ]
        if internal_indexes and min(internal_indexes) < preview_index:
            failures.append(f"{stage} exposes internal production state before 客户可见预览")
        confirmation_index = block.find("用户确认点")
        if confirmation_index != -1 and preview_index > confirmation_index:
            failures.append(f"{stage} shows 客户可见预览 after 用户确认点")
    if failures:
        return False, "; ".join(failures)
    return True, "ok"


def audit_single_stage_gate(path_value: str, simulated_required: bool) -> int:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"STAGE_GATE_INTEGRITY: FAIL")
        print(f"reason: missing file: {path_value}")
        return 1
    text = path.read_text(encoding="utf-8")
    ok, reason = stage_gate_integrity(text, simulated_required)
    print(f"STAGE_GATE_INTEGRITY: {'PASS' if ok else 'FAIL'}")
    print(f"reason: {reason}")
    return 0 if ok else 1


def audit_single_customer_preview(path_value: str, required_stages: list[str]) -> int:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print("CUSTOMER_PREVIEW_INTEGRITY: FAIL")
        print(f"reason: missing file: {path_value}")
        return 1
    text = path.read_text(encoding="utf-8")
    ok, reason = customer_preview_integrity(text, required_stages)
    print(f"CUSTOMER_PREVIEW_INTEGRITY: {'PASS' if ok else 'FAIL'}")
    print(f"reason: {reason}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative chat-facing transcripts.")
    parser.add_argument(
        "--check-stage-gate",
        metavar="PATH",
        help="Check only stage gate integrity for one transcript path.",
    )
    parser.add_argument(
        "--check-customer-preview",
        metavar="PATH",
        help="Check only customer preview ordering for one transcript path.",
    )
    parser.add_argument(
        "--customer-preview-stage",
        action="append",
        default=[],
        help="Stage required by --check-customer-preview. Defaults to 出图执行建议 and 视频生成建议.",
    )
    parser.add_argument(
        "--simulated",
        action="store_true",
        help="Require simulated stages with 用户确认点 to also include 模拟用户选择.",
    )
    args = parser.parse_args()
    if args.check_stage_gate:
        return audit_single_stage_gate(args.check_stage_gate, args.simulated)
    if args.check_customer_preview:
        stages = args.customer_preview_stage or ["阶段: 出图执行建议", "阶段: 视频生成建议"]
        return audit_single_customer_preview(args.check_customer_preview, stages)

    failures: list[str] = []
    print("DIRcreative Chat Surface Audit")
    print("=" * 72)
    for check in transcript_checks():
        path = ROOT / check.path
        if not path.exists():
            failures.append(f"{check.path}: missing file")
            print(f"[FAIL] {check.path}")
            print("       missing file")
            continue
        text = path.read_text(encoding="utf-8")
        ordered_ok, ordered_reason = stage_positions(text, check.ordered_stages)
        contract_ok, contract_reason = forbidden_before_contract(text, check.forbidden_before_generation)
        content_ok, content_reason = content_terms(text, check.required_terms, check.required_any_terms)
        counts_ok, counts_reason = count_terms(text, check.min_counts)
        stage_gate_ok, stage_gate_reason = stage_gate_integrity(text, check.simulated_decisions_required)
        preview_ok, preview_reason = customer_preview_integrity(text, check.customer_preview_stages)
        ok = ordered_ok and contract_ok and content_ok and counts_ok and stage_gate_ok and preview_ok
        print(f"[{'PASS' if ok else 'FAIL'}] {check.path}")
        print(f"       stage_order: {ordered_reason}")
        print(f"       contract_before_prompts: {contract_reason}")
        print(f"       content_terms: {content_reason}")
        print(f"       decision_counts: {counts_reason}")
        print(f"       stage_gate_integrity: {stage_gate_reason}")
        print(f"       customer_preview: {preview_reason}")
        if not ok:
            failures.append(f"{check.path}: {ordered_reason}; {contract_reason}; {content_reason}; {counts_reason}; {stage_gate_reason}; {preview_reason}")
    print(f"CHAT_SURFACE_AUDIT: {'PASS' if not failures else 'FAIL'}")
    if failures:
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
