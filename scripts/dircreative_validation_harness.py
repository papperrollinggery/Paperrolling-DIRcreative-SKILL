#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    label: str
    ok: bool
    evidence: str


@dataclass
class Requirement:
    label: str
    status: str
    evidence: str
    reason: str = ""


def read(path: str, *, missing_ok: bool = False) -> str:
    target = ROOT / path
    if not target.exists() and path.startswith("skills/") and path.endswith("/SKILL.md"):
        target = target.with_name("INTERNAL_SKILL.md")
    if not target.exists():
        if missing_ok:
            return ""
        raise AssertionError(f"missing {path}")
    return target.read_text(encoding="utf-8")


def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_output(cmd: list[str], cwd: Path = ROOT) -> str:
    proc = run(cmd, cwd)
    if proc.returncode != 0:
        raise AssertionError(f"{' '.join(cmd)} failed:\n{proc.stderr}\n{proc.stdout}")
    return proc.stdout


def has_terms(text: str, terms: list[str], *, case_sensitive: bool = True) -> bool:
    return not missing_terms(text, terms, case_sensitive=case_sensitive)


def missing_terms(text: str, terms: list[str], *, case_sensitive: bool = True) -> list[str]:
    if case_sensitive:
        return [term for term in terms if term not in text]
    lowered = text.lower()
    return [term for term in terms if term.lower() not in lowered]


def require_terms(text: str, terms: list[str], source: str, *, case_sensitive: bool = True) -> None:
    missing = missing_terms(text, terms, case_sensitive=case_sensitive)
    if missing:
        raise AssertionError(f"{source} missing terms: {missing}")


def add_check(checks: list[Check], label: str, evidence: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - audit should aggregate all failures.
        checks.append(Check(label, False, f"{evidence}; failure: {exc}"))
    else:
        checks.append(Check(label, True, evidence))


def load_json_file(path: str) -> Any:
    return json.loads(read(path))


def check_status(ok: bool) -> str:
    return "PASS" if ok else "MISSING"
