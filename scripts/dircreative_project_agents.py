#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


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
    "film-craft provider only",
    "AD-creative/AGENTS.md",
]
ACTIVE_WRITE_MODES = {"create", "append-section", "replace-section"}
AGENTS_FILENAMES = {"AGENTS.md", "AGENTS.override.md"}
ACTIVE_WRITE_BLOCK = "active_agents_write_requires_host_controller_scoped_patch_only"
CONFLICT_PATTERNS = (
    re.compile(r"\bnever\s+(?:use|activate|invoke|run)\s+dircreative\b", re.IGNORECASE),
    re.compile(r"\bdo\s+not\s+(?:use|activate|invoke|run)\s+dircreative\b", re.IGNORECASE),
    re.compile(
        r"\bdircreative\s+(?:must\s+not|may\s+not|shall\s+not|cannot|can't)\s+be\s+"
        r"(?:used|activated|invoked|run)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:the\s+)?use\s+of\s+dircreative\s+is\s+(?:strictly\s+)?prohibited\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:严禁|禁止|不要|不得)\s*(?:使用|启用|调用|运行)\s*DIRcreative", re.IGNORECASE),
)
CONSERVATIVE_DENIAL = re.compile(
    r"\b(?:never|forbidden|prohibited|not\s+allowed|should\s+not|must\s+not|"
    r"may\s+not|shall\s+not|do\s+not|cannot|can't)\b|"
    r"不允许|严禁|禁止|禁用|不得|不要",
    re.IGNORECASE,
)
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
            "- DIRcreative is a film-craft provider only. It does not own client truth, requirements or gaps, version maps, artifact adoption, PPT, FinalDelivery, Client Pack, asset authorization, send readiness, or project completion.",
            "- Do not create, replace, or supersede `AD-creative/AGENTS.md`; child rules keep precedence and ADCO retains ownership inside `AD-creative/`.",
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


def read_agents_hierarchy(target: Path) -> list[Path]:
    """Read every applicable parent and child policy file before any proposal or patch."""
    target = target.resolve(strict=True)
    candidates: set[Path] = set()
    for directory in [target, *target.parents]:
        for filename in AGENTS_FILENAMES:
            path = directory / filename
            if path.exists():
                candidates.add(path)
    for path in target.rglob("*"):
        if path.name in AGENTS_FILENAMES and path.exists():
            candidates.add(path)
    ordered = sorted(candidates, key=lambda path: (len(path.parts), path.as_posix().casefold()))
    for path in ordered:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"invalid_agents_hierarchy_entry:{path}")
        path.read_text(encoding="utf-8")
    return ordered


def hierarchy_snapshot(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256(path) for path in paths}


def hierarchy_conflict(paths: list[Path]) -> Path | None:
    """Detect an explicit DIRcreative prohibition before producing policy text."""
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in CONFLICT_PATTERNS):
            return path
        for segment in re.split(r"[.!?。！？；;\n]", text):
            if "dircreative" in segment.casefold() and CONSERVATIVE_DENIAL.search(segment):
                return path
    return None


def render_proposal(existing: str | None) -> str:
    notice = (
        "<!-- INACTIVE PROPOSAL: a trusted host controller must apply any scoped "
        "AGENTS.md patch after direct current-user authorization and hierarchy review. -->"
    )
    if existing is None:
        candidate = render_agents_md()
    else:
        replaced = replace_marked_section(existing, render_dircreative_section())
        candidate = replaced if replaced is not None else append_marked_section(
            existing, render_dircreative_section()
        )
    return notice + "\n\n" + candidate


def inode_identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def stable_file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
    )


def open_pinned_directory(path: Path) -> tuple[int, tuple[int, int]]:
    before = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError("target_project_must_be_directory")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        linked = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or inode_identity(before) != inode_identity(opened)
            or inode_identity(linked) != inode_identity(opened)
        ):
            raise ValueError("target_project_binding_changed")
        return descriptor, inode_identity(opened)
    except BaseException:
        os.close(descriptor)
        raise


def directory_binding_matches(
    path: Path,
    descriptor: int,
    expected_identity: tuple[int, int],
) -> bool:
    try:
        opened = os.fstat(descriptor)
        linked = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISDIR(opened.st_mode)
        and stat.S_ISDIR(linked.st_mode)
        and inode_identity(opened) == expected_identity
        and inode_identity(linked) == expected_identity
    )


def stat_entry_at(directory_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def read_optional_regular_text_at(directory_fd: int, name: str) -> str | None:
    before = stat_entry_at(directory_fd, name)
    if before is None:
        return None
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"invalid_target_policy_entry:{name}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        opened = os.fstat(descriptor)
        if stable_file_identity(before) != stable_file_identity(opened):
            raise ValueError(f"target_policy_entry_changed:{name}")
        with os.fdopen(descriptor, "r", encoding="utf-8", closefd=False) as handle:
            text = handle.read()
        after = os.fstat(descriptor)
        linked = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            stable_file_identity(opened) != stable_file_identity(after)
            or stable_file_identity(after) != stable_file_identity(linked)
        ):
            raise ValueError(f"target_policy_entry_changed:{name}")
        return text
    finally:
        os.close(descriptor)


def atomic_write_text_at(
    directory_fd: int,
    directory_path: Path,
    directory_identity: tuple[int, int],
    name: str,
    text: str,
) -> tuple[int, int]:
    existing = stat_entry_at(directory_fd, name)
    if existing is not None and (
        not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1
    ):
        raise ValueError(f"invalid_proposal_entry:{name}")
    expected_existing = stable_file_identity(existing) if existing is not None else None
    temporary_name = f".{name}.{uuid.uuid4().hex}.tmp"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(temporary_name, flags, 0o600, dir_fd=directory_fd)
    temporary_identity: tuple[int, int] | None = None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            if existing is not None:
                os.fchmod(handle.fileno(), existing.st_mode & 0o777)
            temporary_identity = inode_identity(os.fstat(handle.fileno()))
        temporary = os.stat(temporary_name, dir_fd=directory_fd, follow_symlinks=False)
        if temporary_identity != inode_identity(temporary) or not stat.S_ISREG(temporary.st_mode):
            raise ValueError("proposal_temporary_binding_changed")
        current = stat_entry_at(directory_fd, name)
        current_identity = stable_file_identity(current) if current is not None else None
        if current_identity != expected_existing:
            raise ValueError("proposal_destination_changed")
        if not directory_binding_matches(directory_path, directory_fd, directory_identity):
            raise ValueError("target_project_binding_changed")
        os.replace(
            temporary_name,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        installed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if temporary_identity != inode_identity(installed) or not stat.S_ISREG(installed.st_mode):
            raise ValueError("proposal_install_binding_changed")
        os.fsync(directory_fd)
        return inode_identity(installed)
    finally:
        temporary = stat_entry_at(directory_fd, temporary_name)
        if (
            temporary is not None
            and temporary_identity is not None
            and inode_identity(temporary) == temporary_identity
        ):
            os.unlink(temporary_name, dir_fd=directory_fd)


def remove_owned_entry_at(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
) -> None:
    current = stat_entry_at(directory_fd, name)
    if current is None:
        return
    if inode_identity(current) != expected_identity or not stat.S_ISREG(current.st_mode):
        raise ValueError("refusing_to_remove_unowned_proposal")
    os.unlink(name, dir_fd=directory_fd)
    os.fsync(directory_fd)


def write_generate(
    target: Path,
    mode: str,
    *,
    authorization_receipt: str | None = None,
    authorization_text: str | None = None,
    _race_hook: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    if mode == "auto":
        mode = "propose"
    raw_target = target.expanduser()
    if raw_target.is_symlink():
        return False, "target_project_symlink_refused"
    try:
        target = raw_target.resolve(strict=True)
    except FileNotFoundError:
        return False, "target_project_must_exist"
    if not target.is_dir():
        return False, "target_project_must_be_directory"
    try:
        target_fd, target_identity = open_pinned_directory(target)
    except (OSError, ValueError) as exc:
        return False, f"target_project_open_failed:{exc}"
    try:
        hierarchy = read_agents_hierarchy(target)
        hierarchy_before = hierarchy_snapshot(hierarchy)
        conflict = hierarchy_conflict(hierarchy)
        if conflict is not None:
            return False, f"agents_hierarchy_conflict:{conflict}"
        if mode in ACTIVE_WRITE_MODES:
            # A local JSON/string/receipt is caller-controlled and cannot prove the
            # current user's instruction. Runtime remains proposal-only; the trusted
            # host controller applies a normal scoped patch when authorized.
            return False, ACTIVE_WRITE_BLOCK

        agents_path = target / "AGENTS.md"
        proposed_path = target / PROPOSED_NAME

        def unchanged_hierarchy() -> bool:
            if not directory_binding_matches(target, target_fd, target_identity):
                return False
            try:
                current = read_agents_hierarchy(target)
                return hierarchy_snapshot(current) == hierarchy_before
            except (OSError, UnicodeDecodeError, ValueError):
                return False

        if mode == "propose":
            existing = read_optional_regular_text_at(target_fd, "AGENTS.md")
            proposal_text = render_proposal(existing)
            if _race_hook is not None:
                _race_hook("before_proposal_write")
            if not unchanged_hierarchy():
                return False, "agents_hierarchy_changed_before_proposal"
            proposal_identity = atomic_write_text_at(
                target_fd,
                target,
                target_identity,
                PROPOSED_NAME,
                proposal_text,
            )
            if _race_hook is not None:
                _race_hook("after_proposal_write")
            if not unchanged_hierarchy():
                remove_owned_entry_at(target_fd, PROPOSED_NAME, proposal_identity)
                return False, "agents_hierarchy_changed_during_proposal"
            return True, f"wrote {proposed_path} hierarchy_read={len(hierarchy)}"

        return False, f"unknown_mode:{mode}"
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return False, f"agents_hierarchy_write_failed:{exc}"
    finally:
        os.close(target_fd)


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
        child_path = target / "AD-creative" / "AGENTS.md"
        child_path.parent.mkdir()
        child_path.write_text("# ADCO child rules\n\nkeep child precedence\n", encoding="utf-8")
        child_before = sha256(child_path)
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
        if ok or message != ACTIVE_WRITE_BLOCK:
            return False, "test:detect-accidental-agents-overwrite"
        if sha256(agents_path) != before:
            return False, "test:detect-accidental-agents-overwrite"
        forged = '{"explicit_user_authorization":true,"source":"current_user_request"}'
        for mode in sorted(ACTIVE_WRITE_MODES):
            ok, message = write_generate(target, mode, authorization_text=forged)
            if ok or message != ACTIVE_WRITE_BLOCK:
                return False, f"caller_forged_authorization_must_be_rejected:{mode}"
        proposal = (target / PROPOSED_NAME).read_text(encoding="utf-8")
        if "keep this sentinel" not in proposal or BEGIN_MARKER not in proposal:
            return False, "proposal_must_preserve_existing_policy"
        if agents_path.read_text(encoding="utf-8") != original:
            return False, "proposal_changed_active_root_policy"
        if sha256(child_path) != child_before:
            return False, "scoped_patch_changed_child_policy"
        conflict_rules = (
            "Never use DIRcreative here.",
            "DIRcreative must not be used in this project.",
            "The use of DIRcreative is prohibited.",
            "本项目严禁使用 DIRcreative。",
            "DIRcreative is forbidden in this project.",
            "DIRcreative should not be used in this project.",
            "本项目不允许使用 DIRcreative。",
        )
        for index, rule in enumerate(conflict_rules, start=1):
            conflict_target = Path(tmp) / f"conflict-{index}"
            conflict_target.mkdir()
            conflict_agents = conflict_target / "AGENTS.md"
            conflict_agents.write_text(f"# Policy\n\n{rule}\n", encoding="utf-8")
            conflict_before = sha256(conflict_agents)
            ok, message = write_generate(conflict_target, "propose")
            if ok or not message.startswith("agents_hierarchy_conflict:"):
                return False, f"explicit_hierarchy_conflict_must_stop_proposal:{index}"
            if sha256(conflict_agents) != conflict_before or (conflict_target / PROPOSED_NAME).exists():
                return False, f"conflict_check_must_not_write:{index}"

        swap_target = Path(tmp) / "target-swap"
        swap_target.mkdir()
        (swap_target / "AGENTS.md").write_text("# Original policy\n", encoding="utf-8")
        swap_original = Path(tmp) / "target-swap-original"
        swap_victim = Path(tmp) / "target-swap-victim"
        swap_victim.mkdir()

        def swap_target_hook(stage: str) -> None:
            if stage != "before_proposal_write":
                return
            os.replace(swap_target, swap_original)
            swap_target.symlink_to(swap_victim, target_is_directory=True)

        ok, message = write_generate(
            swap_target,
            "propose",
            _race_hook=swap_target_hook,
        )
        if ok or "changed_before_proposal" not in message:
            return False, "target_directory_swap_must_stop_proposal"
        if (swap_victim / PROPOSED_NAME).exists() or (swap_original / PROPOSED_NAME).exists():
            return False, "target_directory_swap_escaped_proposal_root"
        swap_target.unlink()

        root_race_target = Path(tmp) / "root-policy-race"
        root_race_target.mkdir()
        root_race_agents = root_race_target / "AGENTS.md"
        root_race_agents.write_text("# Original policy\n", encoding="utf-8")

        def root_policy_hook(stage: str) -> None:
            if stage == "before_proposal_write":
                root_race_agents.write_text("# Changed policy\n", encoding="utf-8")

        ok, message = write_generate(
            root_race_target,
            "propose",
            _race_hook=root_policy_hook,
        )
        if ok or "changed_before_proposal" not in message:
            return False, "root_policy_change_must_stop_proposal"
        if (root_race_target / PROPOSED_NAME).exists():
            return False, "root_policy_change_left_stale_proposal"
        if list(target.glob(".AGENTS.md.*.tmp")):
            return False, "atomic_write_temporary_file_leaked"
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
    parser = argparse.ArgumentParser(description="Render/propose/audit DIRcreative project AGENTS.md rules; runtime active writes fail closed.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="Render DIRcreative AGENTS.md content to stdout.")
    render.add_argument("--proposed", action="store_true", help="Render the inactive proposal variant.")

    generate = subparsers.add_parser("generate", help="Write AGENTS.md or AGENTS.dircreative.proposed.md for a target project.")
    generate.add_argument("target", help="Target project directory.")
    generate.add_argument(
        "--mode",
        choices=["auto", "propose", "create", "append-section", "replace-section"],
        default="propose",
        help="Default writes an inactive proposal; active modes are retained only to fail closed for a trusted host-controller patch.",
    )
    generate.add_argument("--authorization-receipt", help="Deprecated and never trusted by this proposal-only runtime.")
    generate.add_argument("--authorization-text", help="Deprecated and never trusted by this proposal-only runtime.")

    install = subparsers.add_parser("install", help="Fail-closed compatibility command; active patches require the trusted host controller.")
    install.add_argument("target", help="Target project directory.")
    install.add_argument(
        "--mode",
        choices=["create", "append-section", "replace-section"],
        required=True,
        help="Install mode. Existing AGENTS.md requires append-section or replace-section.",
    )
    install.add_argument("--authorization-receipt", help="Deprecated and never trusted by this proposal-only runtime.")
    install.add_argument("--authorization-text", help="Deprecated and never trusted by this proposal-only runtime.")

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
