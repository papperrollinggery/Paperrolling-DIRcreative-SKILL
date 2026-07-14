#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
PROPOSED_NAME = "AGENTS.dircreative.proposed.md"
BEGIN_MARKER = "<!-- DIRcreative:BEGIN project-rules -->"
END_MARKER = "<!-- DIRcreative:END project-rules -->"
DEFAULT_IMPLEMENTATION_SCRIPT = "scripts/dircreative_project_agents.py"
DOC_EXTENSIONS = {".md", ".txt", ".rst"}
REQUIRED_TERMS = [
    "DIRcreative",
    ".dircreative/runs",
    "skill_run_receipt",
    "pre_generation_contract.status: pass",
    "idea intake -> director room -> story -> script -> script breakdown -> shot design -> visual bible -> reference pack -> image prompt -> video model adapter -> QA/retry",
    "Source of truth",
    "worker thread output is advisory",
    "中文优先、简洁、先给结论",
    "THREAD_DISPATCH_RECEIPT",
    "target project-bound worker",
    "cos_main_overexecution",
    "rejected_evidence",
    "live-user-acceptance.yaml",
    "Validation commands",
]
ACTIVE_WRITE_MODES = {"create", "append-section", "replace-section"}
DOC_GENERATION_ACTION_TERMS = [
    "generation",
    "generate",
    "propose",
    "proposal",
    "create",
    "append",
    "install",
    "project-level",
    "project agents",
    "dircreative_project_agents.py",
]

# Validation contract strings:
# mode:propose-agents-md
# mode:create-agents-md
# mode:append-dircreative-section
# mode:replace-dircreative-section
# audit:missing-active-agents
# audit:missing-required-dircreative-terms
# audit:docs-mention-generation-without-implementation
# audit:informational-by-default
# auth:authorization-required-for-active-agents-write
# test:detect-accidental-agents-overwrite


@dataclass
class AuditResult:
    ok: bool
    failures: list[str]
    details: list[str]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_project_requires_agents(target: Path) -> bool:
    return (target / ".dircreative").exists()


def render_dircreative_section() -> str:
    return "\n".join(
        [
            BEGIN_MARKER,
            "## DIRcreative Project Rules",
            "",
            "- Use DIRcreative for AI video, film preproduction, image prompt, video prompt, reference pack, and QA/retry work in this project.",
            "- Do not jump directly to image generation, video generation, or prompt handoff.",
            "- Creative lock order: idea intake -> director room -> story -> script -> script breakdown -> shot design -> visual bible -> reference pack -> image prompt -> video model adapter -> QA/retry.",
            "- Source of truth: project artifacts, `.dircreative/runs/`, prompt manifests, `skill_run_receipt`, and validation output.",
            "- Do not treat hidden chat history, unadopted worker notes, temporary screenshots, widget pages, local URLs, or generated candidates as project truth.",
            "- Before image or video generation, require locked story/script/shot/reference inputs plus `pre_generation_contract.status: pass` and explicit user authorization for that media action.",
            "- Codex worker thread output is advisory until the controller adopts it into project files, `.dircreative/runs/`, manifests, receipts, or validation output.",
            "- Same-directory workers are read-only; writable workers must use isolated worktrees and cannot mark the Goal complete.",
            "- If a Chief-of-Staff workflow is triggered, keep user-visible output 中文优先、简洁、先给结论; for real dispatch, show a Chinese dispatch summary before the `THREAD_DISPATCH_RECEIPT` machine credential.",
            "- Chief-of-Staff controller threads are not execution surfaces: they must not run target project tests/gates, clean processes, edit files, or implement code directly.",
            "- Cross-project work must execute in the target project's main COS or a target project-bound worker; a source COS must not enter another project and treat its own commands as completion evidence.",
            "- If a main COS over-executes, record `cos_main_overexecution` and `adoption_status: rejected_evidence`; its commands, diffs, cleanup, tests, or gate output are clues only until rerun/adopted by a project-bound worker.",
            "- Do not create `.dircreative/runs/live-user-acceptance.yaml`, set real-user acceptance, or claim completion from validation, simulation, widgets, generated media, or `AGENTS.md` edits.",
            "- Validation commands: run the target project validation documented in its README/CONTEXT/AGENTS plus DIRcreative audits relevant to the run.",
            END_MARKER,
            "",
        ]
    )


def render_agents_md(*, proposed: bool = False) -> str:
    header = [
        "# Agent Instructions",
        "",
    ]
    if proposed:
        header.extend(
            [
                "This file is a DIRcreative proposal and is not active until copied into `AGENTS.md`.",
                "",
            ]
        )
    header.append(render_dircreative_section().rstrip())
    header.append("")
    return "\n".join(header)


def replace_marked_section(existing: str, section: str) -> str | None:
    begin = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)
    if begin == -1 or end == -1 or end < begin:
        return None
    end += len(END_MARKER)
    replacement = section.rstrip()
    prefix = existing[:begin].rstrip()
    suffix = existing[end:].lstrip()
    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(replacement)
    if suffix:
        parts.append(suffix.rstrip())
    return "\n\n".join(parts).rstrip() + "\n"


def append_marked_section(existing: str, section: str) -> str:
    text = existing.rstrip()
    if not text:
        return section.rstrip() + "\n"
    return text + "\n\n" + section.rstrip() + "\n"


def authorization_evidence(authorization_receipt: str | None, authorization_text: str | None) -> str | None:
    if authorization_text and authorization_text.strip():
        return "authorization_text"
    if authorization_receipt:
        receipt_path = Path(authorization_receipt).expanduser()
        if receipt_path.exists() and receipt_path.is_file():
            try:
                if receipt_path.read_text(encoding="utf-8").strip():
                    return f"authorization_receipt:{receipt_path}"
            except UnicodeDecodeError:
                if receipt_path.read_bytes():
                    return f"authorization_receipt:{receipt_path}"
    return None


def write_generate(
    target: Path,
    mode: str,
    *,
    authorization_receipt: str | None = None,
    authorization_text: str | None = None,
) -> tuple[bool, str]:
    if mode == "auto":
        mode = "propose"
    if mode in ACTIVE_WRITE_MODES and not authorization_evidence(authorization_receipt, authorization_text):
        return False, "authorization_required_for_active_agents_write"

    target = target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    agents_path = target / "AGENTS.md"
    proposed_path = target / PROPOSED_NAME
    section = render_dircreative_section()

    if mode == "propose":
        proposed_path.write_text(render_agents_md(proposed=True), encoding="utf-8")
        return True, f"wrote {proposed_path}"

    if mode == "create":
        if agents_path.exists():
            return False, "overwrite_risk_existing_agents_md"
        agents_path.write_text(render_agents_md(), encoding="utf-8")
        return True, f"wrote {agents_path}"

    if mode == "append-section":
        if not agents_path.exists():
            return False, "append_requires_existing_agents_md"
        existing = agents_path.read_text(encoding="utf-8")
        if BEGIN_MARKER in existing or END_MARKER in existing:
            return False, "append_refuses_existing_dircreative_section_use_replace_section"
        before = sha256(agents_path)
        agents_path.write_text(append_marked_section(existing, section), encoding="utf-8")
        after = sha256(agents_path)
        return True, f"updated {agents_path} hash_before={before} hash_after={after}"

    if mode == "replace-section":
        if not agents_path.exists():
            return False, "replace_requires_existing_agents_md"
        existing = agents_path.read_text(encoding="utf-8")
        replaced = replace_marked_section(existing, section)
        if replaced is None:
            return False, "replace_requires_marked_dircreative_section"
        before = sha256(agents_path)
        agents_path.write_text(replaced, encoding="utf-8")
        after = sha256(agents_path)
        return True, f"updated {agents_path} hash_before={before} hash_after={after}"

    return False, f"unknown_mode:{mode}"


def audit_target(target: Path, *, require_active: bool = False) -> AuditResult:
    target = target.expanduser().resolve()
    failures: list[str] = []
    details: list[str] = [f"target: {target}"]
    agents_path = target / "AGENTS.md"
    details.append(f"dircreative_project_detected: {str(target_project_requires_agents(target)).lower()}")
    details.append(f"require_active: {str(require_active).lower()}")

    if not agents_path.exists():
        details.append("active_agents: absent")
        if require_active:
            failures.append("target_project_needs_agents_missing_active_rules")
        return AuditResult(not failures, failures, details)

    findings: list[str] = []
    text = agents_path.read_text(encoding="utf-8")
    missing = [term for term in REQUIRED_TERMS if term not in text]
    if missing:
        findings.append("active_agents_missing_required_dircreative_terms: " + ", ".join(missing))
    if BEGIN_MARKER in text or END_MARKER in text:
        if BEGIN_MARKER not in text or END_MARKER not in text:
            findings.append("active_agents_incomplete_dircreative_marked_section")
        elif text.find(END_MARKER) < text.find(BEGIN_MARKER):
            findings.append("active_agents_incomplete_dircreative_marked_section")
    if require_active:
        failures.extend(findings)
    elif findings:
        details.extend("informational_" + finding for finding in findings)
    details.append("active_agents: present")
    return AuditResult(not failures, failures, details)


def docs_mention_agents_generation(repo_root: Path) -> bool:
    search_roots = [repo_root / "README.md", repo_root / "docs", repo_root / "skills" / "dircreative" / "SKILL.md"]
    for root in search_roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        for path in paths:
            if path.suffix not in DOC_EXTENSIONS:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            lowered = text.lower()
            if "agents.md" in lowered and any(term in lowered for term in DOC_GENERATION_ACTION_TERMS):
                return True
    return False


def overwrite_guard_self_test() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "target"
        target.mkdir()
        agents_path = target / "AGENTS.md"
        original = "# Existing Rules\n\nkeep this sentinel\n"
        agents_path.write_text(original, encoding="utf-8")
        before = sha256(agents_path)
        ok, message = write_generate(target, "propose")
        after = sha256(agents_path)
        if not ok:
            return False, f"proposal_failed:{message}"
        if before != after or agents_path.read_text(encoding="utf-8") != original:
            return False, "test:detect-accidental-agents-overwrite"
        ok, message = write_generate(target, "create")
        if ok or message != "authorization_required_for_active_agents_write":
            return False, "test:detect-accidental-agents-overwrite"
        if sha256(agents_path) != before:
            return False, "test:detect-accidental-agents-overwrite"
    return True, "test:detect-accidental-agents-overwrite passed"


def audit_repo(repo_root: Path, implementation_script: str) -> AuditResult:
    repo_root = repo_root.expanduser().resolve()
    failures: list[str] = []
    details: list[str] = [f"repo_root: {repo_root}"]
    implementation_path = repo_root / implementation_script
    mentions_generation = docs_mention_agents_generation(repo_root)
    details.append(f"docs_mention_agents_generation: {str(mentions_generation).lower()}")
    details.append(f"implementation_script: {implementation_path}")

    if mentions_generation and not implementation_path.exists():
        failures.append("docs_mention_agents_generation_but_implementation_missing")

    ok, message = overwrite_guard_self_test()
    details.append(message)
    if not ok:
        failures.append(message)

    return AuditResult(not failures, failures, details)


def print_audit(name: str, result: AuditResult) -> int:
    print("DIRcreative Project AGENTS Audit")
    print("=" * 72)
    for detail in result.details:
        print(detail)
    if result.failures:
        print(f"{name}: FAIL")
        for failure in result.failures:
            print(f"- {failure}")
        return 1
    print(f"{name}: PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render, install, propose, and audit DIRcreative project AGENTS.md rules.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="Render DIRcreative AGENTS.md content to stdout.")
    render.add_argument("--proposed", action="store_true", help="Render the inactive proposal variant.")

    generate = subparsers.add_parser("generate", help="Write AGENTS.md or AGENTS.dircreative.proposed.md for a target project.")
    generate.add_argument("target", help="Target project directory.")
    generate.add_argument(
        "--mode",
        choices=["auto", "propose", "create", "append-section", "replace-section"],
        default="propose",
        help="Write mode. Default writes an inactive proposal; active AGENTS.md writes require an explicit mode.",
    )
    generate.add_argument("--authorization-receipt", help="Non-empty authorization receipt required for active writes.")
    generate.add_argument("--authorization-text", help="Inline authorization evidence required for active writes.")

    install = subparsers.add_parser("install", help="Explicitly install active DIRcreative rules into target AGENTS.md.")
    install.add_argument("target", help="Target project directory.")
    install.add_argument(
        "--mode",
        choices=["create", "append-section", "replace-section"],
        required=True,
        help="Install mode. Existing AGENTS.md requires append-section or replace-section.",
    )
    install.add_argument("--authorization-receipt", help="Non-empty authorization receipt required for active writes.")
    install.add_argument("--authorization-text", help="Inline authorization evidence required for active writes.")

    audit = subparsers.add_parser("audit", help="Read-only audit for a target project.")
    audit.add_argument("target", help="Target project directory.")
    audit.add_argument("--require-active", action="store_true", help="Fail when active AGENTS.md DIRcreative rules are absent or incomplete.")
    audit.add_argument(
        "--require-dircreative-agents",
        action="store_true",
        help="Alias for --require-active.",
    )

    repo_audit = subparsers.add_parser("audit-repo", help="Read-only audit for this implementation.")
    repo_audit.add_argument("--repo-root", default=str(ROOT), help="Repository root to audit.")
    repo_audit.add_argument(
        "--implementation-script",
        default=DEFAULT_IMPLEMENTATION_SCRIPT,
        help="Implementation script path relative to repo root.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "render":
        print(render_agents_md(proposed=args.proposed), end="")
        return 0

    if args.command == "generate":
        ok, message = write_generate(
            Path(args.target),
            args.mode,
            authorization_receipt=args.authorization_receipt,
            authorization_text=args.authorization_text,
        )
        print(message)
        return 0 if ok else 1

    if args.command == "install":
        ok, message = write_generate(
            Path(args.target),
            args.mode,
            authorization_receipt=args.authorization_receipt,
            authorization_text=args.authorization_text,
        )
        print(message)
        return 0 if ok else 1

    if args.command == "audit":
        return print_audit(
            "PROJECT_AGENTS_AUDIT",
            audit_target(Path(args.target), require_active=args.require_active or args.require_dircreative_agents),
        )

    if args.command == "audit-repo":
        return print_audit("PROJECT_AGENTS_AUDIT", audit_repo(Path(args.repo_root), args.implementation_script))

    parser.error("unreachable")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
