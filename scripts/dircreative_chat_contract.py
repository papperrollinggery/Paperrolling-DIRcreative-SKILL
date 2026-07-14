#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dircreative_validation_harness import load_json_file


CONTRACT_PATH = "docs/film-preproduction/chat-surface-contract.yaml"


@dataclass
class TranscriptCheck:
    id: str
    path: str
    ordered_stages: list[str]
    forbidden_before_generation: list[str]
    customer_preview_stages: list[str]
    required_terms: list[str] = field(default_factory=list)
    required_any_terms: list[list[str]] = field(default_factory=list)
    min_counts: dict[str, int] = field(default_factory=dict)
    simulated_decisions_required: bool = False


def load_contract() -> dict[str, Any]:
    data = load_json_file(CONTRACT_PATH)
    if not isinstance(data, dict):
        raise AssertionError(f"{CONTRACT_PATH} must contain an object")
    return data


def transcript_checks() -> list[TranscriptCheck]:
    data = load_contract()
    checks = data.get("checks", [])
    if not isinstance(checks, list):
        raise AssertionError(f"{CONTRACT_PATH} checks must be a list")
    return [
        TranscriptCheck(
            id=item["id"],
            path=item["path"],
            ordered_stages=list(item.get("ordered_stages", [])),
            forbidden_before_generation=list(item.get("forbidden_before_generation", [])),
            customer_preview_stages=list(item.get("customer_preview_stages", data.get("customer_preview_stages", []))),
            required_terms=list(item.get("required_terms", [])),
            required_any_terms=[list(group) for group in item.get("required_any_terms", [])],
            min_counts={str(key): int(value) for key, value in item.get("min_counts", {}).items()},
            simulated_decisions_required=bool(item.get("simulated_decisions_required", False)),
        )
        for item in checks
    ]


def required_terms_for(check_id: str) -> list[str]:
    return _check_by_id(check_id).required_terms


def ordered_stages_for(check_id: str) -> list[str]:
    return _check_by_id(check_id).ordered_stages


def forbidden_before_generation(check_id: str) -> list[str]:
    return _check_by_id(check_id).forbidden_before_generation


def stage_gate_exempts() -> tuple[tuple[str, ...], tuple[str, ...]]:
    data = load_contract()
    gate = data.get("stage_gate", {})
    return (
        tuple(gate.get("confirm_stage_exempts", [])),
        tuple(gate.get("simulated_decision_stage_exempts", [])),
    )


def _check_by_id(check_id: str) -> TranscriptCheck:
    for check in transcript_checks():
        if check.id == check_id:
            return check
    raise AssertionError(f"unknown chat surface contract check: {check_id}")
