#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from dircreative_package_layout import (
    IGNORE_NAMES,
    HOST_USER_PATH_RE,
    PACKAGE_ITEMS,
    PACKAGE_RUNTIME_FILES,
    ROOT_SKILL_RUNTIME_DIRS,
    THREAD_ID_RE,
    runtime_source_bytes,
    sanitize_package_bytes,
    validate_package_sources,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / ".codex" / "dev-skills" / "dircreative"
FORMAL_INSTALL_TARGETS = (
    Path.home() / ".skillshub" / "dircreative",
    Path.home() / ".codex" / "skills" / "dircreative",
)
INTERNAL_SKILL_FILE = "INTERNAL_SKILL.md"


def root_skill_source(base: Path = ROOT) -> Path:
    source_layout = base / "skills" / "dircreative" / "SKILL.md"
    if source_layout.exists():
        return source_layout
    installed_layout = base / "SKILL.md"
    if installed_layout.exists():
        return installed_layout
    raise SystemExit("missing root DIRcreative SKILL.md")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_release_metadata(base: Path = ROOT) -> dict[str, str]:
    metadata_path = base / "RELEASE-METADATA.json"
    version_path = base / "VERSION"
    skill_path = root_skill_source(base)
    for label, path in (
        ("release metadata", metadata_path),
        ("VERSION", version_path),
        ("root SKILL.md", skill_path),
    ):
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError(f"formal install requires a regular, single-link {label}")
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid release metadata: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid release metadata: expected an object")
    required_fields = {
        "schema_version",
        "product",
        "version",
        "tag",
        "commit_sha",
        "commit_timestamp",
        "root_skill_sha256",
        "source",
    }
    if set(payload) != required_fields:
        raise ValueError("invalid release metadata: field set mismatch")
    version = version_path.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"\d+\.\d+\.\d+", version) is None:
        raise ValueError("invalid release metadata: VERSION must be semantic x.y.z")
    expected = {
        "schema_version": "1.0.0",
        "product": "DIRcreative",
        "version": version,
        "tag": f"v{version}",
        "root_skill_sha256": sha256(skill_path),
        "source": "git archive of exact commit",
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"invalid release metadata: {field} mismatch")
    commit_sha = payload.get("commit_sha")
    if not isinstance(commit_sha, str) or re.fullmatch(r"[0-9a-f]{40}", commit_sha) is None:
        raise ValueError("invalid release metadata: commit_sha must be one exact Git commit")
    timestamp = payload.get("commit_timestamp")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise ValueError("invalid release metadata: commit_timestamp must be UTC")
    return {key: str(value) for key, value in payload.items()}


def copy_item(source: Path, target: Path) -> None:
    if source.is_dir():
        ignore = shutil.ignore_patterns(*sorted(IGNORE_NAMES), "*.pyc", "*.pyo")
        shutil.copytree(source, target, ignore=ignore)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def sanitize_copied_item(source: Path, target: Path, package_key: str, thread_ids: dict[str, str]) -> None:
    if source.is_file():
        target.write_bytes(sanitize_package_bytes(package_key, source.read_bytes(), thread_ids))
        return
    for source_path in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = source_path.relative_to(source)
        if any(part in IGNORE_NAMES for part in relative.parts) or relative.suffix in {".pyc", ".pyo"}:
            continue
        target_path = target / relative
        target_path.write_bytes(
            sanitize_package_bytes(f"{package_key}/{relative.as_posix()}", source_path.read_bytes(), thread_ids)
        )


def populate(target: Path) -> None:
    thread_ids: dict[str, str] = {}
    for item in PACKAGE_ITEMS:
        source = ROOT / item
        copy_item(source, target / item)
        sanitize_copied_item(source, target / item, item, thread_ids)

    for relative in sorted(PACKAGE_RUNTIME_FILES):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = runtime_source_bytes(ROOT, relative, thread_ids)
        destination.write_bytes(data)
        shutil.copymode(ROOT / relative, destination)

    root_skill = root_skill_source()
    copy_item(root_skill, target / "SKILL.md")
    (target / "SKILL.md").write_bytes(
        sanitize_package_bytes("SKILL.md", root_skill.read_bytes(), thread_ids)
    )
    skill_agent_metadata = root_skill.parent / "agents"
    if skill_agent_metadata.is_dir():
        copy_item(skill_agent_metadata, target / "agents")
        sanitize_copied_item(skill_agent_metadata, target / "agents", "agents", thread_ids)
    for directory in ROOT_SKILL_RUNTIME_DIRS:
        source = root_skill.parent / directory
        if not source.is_dir():
            continue
        destination = target / directory
        copy_item(source, destination)
        sanitize_copied_item(source, destination, directory, thread_ids)
    release_metadata = ROOT / "RELEASE-METADATA.json"
    if release_metadata.exists():
        copy_item(release_metadata, target / "RELEASE-METADATA.json")
    hide_internal_skill_entries(target)

    packaged_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in target.rglob("*")
        if path.is_file()
    )
    if HOST_USER_PATH_RE.search(packaged_text) or THREAD_ID_RE.search(packaged_text):
        raise ValueError("sanitized package still contains host-specific paths or thread IDs")


def path_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def remove_path_entry(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path_entry_exists(path):
        path.unlink()


def normalized_parts(path: Path, *, resolve_links: bool) -> tuple[str, ...]:
    expanded = path.expanduser()
    normalized = expanded.resolve(strict=False) if resolve_links else Path(os.path.abspath(expanded))
    return tuple(part.casefold() for part in normalized.parts)


def path_part_variants(path: Path) -> set[tuple[str, ...]]:
    return {
        normalized_parts(path, resolve_links=False),
        normalized_parts(path, resolve_links=True),
    }


def same_location(left: Path, right: Path) -> bool:
    if path_part_variants(left).intersection(path_part_variants(right)):
        return True
    if path_entry_exists(left) and path_entry_exists(right):
        try:
            return os.path.samefile(left, right)
        except OSError:
            return False
    return False


def paths_overlap(left: Path, right: Path) -> bool:
    for left_parts in path_part_variants(left):
        for right_parts in path_part_variants(right):
            shortest = min(len(left_parts), len(right_parts))
            if left_parts[:shortest] == right_parts[:shortest]:
                return True
    return False


def validate_install_target(target: Path, *, allow_formal: bool) -> None:
    if target.is_symlink():
        raise ValueError(
            "install target must not be a symlink; use the canonical directory path explicitly"
        )
    if paths_overlap(target, ROOT):
        raise ValueError(f"install target must not be the source repository or its parent/child: {target}")
    exact_formal = any(same_location(target, formal) for formal in FORMAL_INSTALL_TARGETS)
    overlaps_formal = any(paths_overlap(target, formal) for formal in FORMAL_INSTALL_TARGETS)
    if exact_formal:
        if not allow_formal:
            raise ValueError(
                "formal DIRcreative installation requires explicit --formal-install authorization"
            )
        return
    if overlaps_formal:
        raise ValueError(
            "install target may not be a parent or child of a formal DIRcreative installation"
        )


def install(target: Path, *, allow_formal: bool = False) -> None:
    validate_install_target(target, allow_formal=allow_formal)
    if allow_formal:
        validate_release_metadata(ROOT)
    validate_package_sources(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
    moved_existing = False
    install_completed = False
    try:
        populate(staging)
        if path_entry_exists(target):
            os.replace(target, backup)
            moved_existing = True
        os.replace(staging, target)
        install_completed = True
    except BaseException as install_error:
        if moved_existing and path_entry_exists(backup):
            if path_entry_exists(target):
                raise RuntimeError(
                    "DIRcreative install failed after preserving the previous install; "
                    f"both the target and recovery backup require manual reconciliation: {backup}"
                ) from install_error
            try:
                os.replace(backup, target)
            except Exception as restore_error:
                raise RuntimeError(
                    "DIRcreative install failed and automatic restoration also failed; "
                    f"the previous install is retained at: {backup}"
                ) from restore_error
        raise
    finally:
        failure_in_flight = sys.exc_info()[0] is not None
        if path_entry_exists(staging):
            try:
                remove_path_entry(staging)
            except OSError:
                if not failure_in_flight:
                    raise
        if install_completed and path_entry_exists(backup):
            remove_path_entry(backup)


def self_test() -> int:
    unicode_escape_sample = b'if "\\\\u003c/script\\\\u003e" not in hostile_fragment:\n'
    if sanitize_package_bytes("scripts/escape-sample.py", unicode_escape_sample, {}) != unicode_escape_sample:
        raise AssertionError("package sanitizer modified JSON unicode escape evidence")
    regex_escape_sample = b'"pattern": "^(?!/)(?!.*(?:^|/)\\\\.\\\\.(?:/|$)).+$"\n'
    if sanitize_package_bytes("schemas/relative-path.json", regex_escape_sample, {}) != regex_escape_sample:
        raise AssertionError("package sanitizer modified relative-path regex evidence")
    with tempfile.TemporaryDirectory(prefix="dircreative-installer-metadata-") as raw:
        release_root = Path(raw)
        (release_root / "VERSION").write_text("9.8.7\n", encoding="utf-8")
        (release_root / "SKILL.md").write_text("# Isolated release fixture\n", encoding="utf-8")
        metadata = {
            "schema_version": "1.0.0",
            "product": "DIRcreative",
            "version": "9.8.7",
            "tag": "v9.8.7",
            "commit_sha": "a" * 40,
            "commit_timestamp": "2026-07-21T00:00:00Z",
            "root_skill_sha256": sha256(release_root / "SKILL.md"),
            "source": "git archive of exact commit",
        }
        metadata_path = release_root / "RELEASE-METADATA.json"
        metadata_path.write_text(json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8")
        validate_release_metadata(release_root)
        metadata["commit_sha"] = "not-a-commit"
        metadata_path.write_text(json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8")
        try:
            validate_release_metadata(release_root)
        except ValueError as exc:
            if "commit_sha" not in str(exc):
                raise
        else:
            raise AssertionError("formal installer accepted unbound release metadata")
    with tempfile.TemporaryDirectory(prefix="dircreative-installer-self-test-") as raw:
        root = Path(raw)
        source_fixture = root / "source-safety"
        for item in PACKAGE_ITEMS:
            path = source_fixture / item
            if item in {"README.md", "VERSION", "CHANGELOG.md"}:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
        for relative in PACKAGE_RUNTIME_FILES:
            path = source_fixture / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")
        safe_source = source_fixture / "docs/safe.txt"
        safe_source.write_text("safe\n", encoding="utf-8")
        validate_package_sources(source_fixture)

        symlink_source = source_fixture / "docs/external-link.txt"
        try:
            symlink_source.symlink_to(Path("/etc/hosts"))
        except (NotImplementedError, OSError):
            pass
        else:
            try:
                validate_package_sources(source_fixture)
            except ValueError as exc:
                if "symbolic link" not in str(exc):
                    raise
            else:
                raise AssertionError("package source validation accepted a symbolic link")
            symlink_source.unlink()

        hardlink_source = source_fixture / "docs/hardlink-source.txt"
        hardlink_alias = source_fixture / "docs/hardlink-alias.txt"
        hardlink_source.write_text("hardlink\n", encoding="utf-8")
        os.link(hardlink_source, hardlink_alias)
        try:
            validate_package_sources(source_fixture)
        except ValueError as exc:
            if "hardlinked" not in str(exc):
                raise
        else:
            raise AssertionError("package source validation accepted a hardlink")
        hardlink_alias.unlink()
        hardlink_source.unlink()

        if hasattr(os, "mkfifo"):
            special_source = source_fixture / "docs/special-source"
            os.mkfifo(special_source)
            try:
                validate_package_sources(source_fixture)
            except ValueError as exc:
                if "regular file or directory" not in str(exc):
                    raise
            else:
                raise AssertionError("package source validation accepted a special file")
            special_source.unlink()

        for layout in (
            Path(".codex/dev-skills/dircreative"),
            Path(".codex/skills/dircreative"),
            Path(".skillshub/dircreative"),
        ):
            layout_target = root / layout
            populate(layout_target)
            policy = layout_target / "agents/openai.yaml"
            if not policy.is_file() or "allow_implicit_invocation: false" not in policy.read_text(encoding="utf-8"):
                raise AssertionError(f"activation policy missing from isolated install layout: {layout}")
            for relative in (
                "routes/fast-task.md",
                "routes/studio-development.md",
                "routes/delivery-audit.md",
                "references/copy-script.md",
                "references/film-development.md",
                "references/generation-delivery.md",
                "runtime/routing-policy.yaml",
            ):
                if not (layout_target / relative).is_file():
                    raise AssertionError(f"root runtime file missing from isolated install layout: {layout}/{relative}")
        target = root / "dircreative"
        target.mkdir()
        sentinel = target / "previous-install.txt"
        sentinel.write_text("keep me\n", encoding="utf-8")
        real_replace = os.replace
        calls = 0

        def fail_install_swap(source: os.PathLike[str] | str, destination: os.PathLike[str] | str) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected install swap failure")
            real_replace(source, destination)

        with mock.patch.object(os, "replace", side_effect=fail_install_swap):
            try:
                install(target)
            except OSError as exc:
                if "injected install swap failure" not in str(exc):
                    raise
            else:
                raise AssertionError("installer must surface an injected install swap failure")
        if sentinel.read_text(encoding="utf-8") != "keep me\n":
            raise AssertionError("installer did not restore the previous installation")
        if list(root.glob(".dircreative.backup-*")):
            raise AssertionError("successful restoration left a stale recovery backup")

        calls = 0

        def fail_install_and_restore(
            source: os.PathLike[str] | str,
            destination: os.PathLike[str] | str,
        ) -> None:
            nonlocal calls
            calls += 1
            if calls in {2, 3}:
                raise OSError(f"injected replace failure {calls}")
            real_replace(source, destination)

        with mock.patch.object(os, "replace", side_effect=fail_install_and_restore):
            try:
                install(target)
            except RuntimeError as exc:
                if "previous install is retained at" not in str(exc):
                    raise
            else:
                raise AssertionError("installer must fail closed when restoration fails")
        backups = list(root.glob(".dircreative.backup-*"))
        if len(backups) != 1 or not (backups[0] / "previous-install.txt").is_file():
            raise AssertionError("failed restoration did not retain one recoverable backup")
    unsafe_targets = [
        ROOT,
        ROOT.parent,
        ROOT / "nested-install",
        Path.home(),
        Path.home() / ".codex",
        Path.home() / ".codex" / "skills",
        Path.home() / ".skillshub",
        Path.home() / ".skillshub" / "dircreative" / "nested-install",
    ]
    for unsafe_target in unsafe_targets:
        try:
            validate_install_target(unsafe_target, allow_formal=True)
        except ValueError:
            pass
        else:
            raise AssertionError(f"installer accepted unsafe overlapping target: {unsafe_target}")
    for formal_target in FORMAL_INSTALL_TARGETS:
        try:
            validate_install_target(formal_target, allow_formal=False)
        except ValueError:
            pass
        else:
            raise AssertionError(f"installer accepted formal target without authorization: {formal_target}")
        if formal_target.is_symlink():
            try:
                validate_install_target(formal_target, allow_formal=True)
            except ValueError:
                pass
            else:
                raise AssertionError(f"installer accepted formal symlink target: {formal_target}")
        elif paths_overlap(formal_target, ROOT):
            try:
                validate_install_target(formal_target, allow_formal=True)
            except ValueError:
                pass
            else:
                raise AssertionError(f"installer accepted the current source root as an install target: {formal_target}")
        else:
            validate_install_target(formal_target, allow_formal=True)
    case_alias = Path.home() / ".skillshub" / "DIRCREATIVE"
    try:
        validate_install_target(case_alias, allow_formal=False)
    except ValueError:
        pass
    else:
        raise AssertionError("installer accepted a case-insensitive formal target alias")
    with tempfile.TemporaryDirectory(prefix="dircreative-installer-symlink-") as raw:
        symlink_root = Path(raw)
        victim = symlink_root / "victim"
        victim.mkdir()
        sentinel = victim / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        alias = symlink_root / "alias"
        alias.symlink_to(victim, target_is_directory=True)
        try:
            install(alias)
        except ValueError:
            pass
        else:
            raise AssertionError("installer accepted a symlink target")
        if sentinel.read_text(encoding="utf-8") != "preserve\n" or not alias.is_symlink():
            raise AssertionError("symlink target rejection modified its destination")
    print("DIRCREATIVE_INSTALLER_SELF_TEST: PASS")
    return 0


def hide_internal_skill_entries(target: Path) -> None:
    for path in sorted((target / "skills").rglob("SKILL.md")):
        internal_path = path.with_name(INTERNAL_SKILL_FILE)
        path.rename(internal_path)
        strip_skill_frontmatter(internal_path)


def strip_skill_frontmatter(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return
    end = text.find("\n---\n", 4)
    if end == -1:
        return
    path.write_text(text[end + len("\n---\n") :].lstrip("\n"), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install DIRcreative as a local Codex skill package.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Install target directory.")
    parser.add_argument(
        "--formal-install",
        action="store_true",
        help="Authorize replacing the canonical SkillHub/Codex installation from a verified release artifact.",
    )
    parser.add_argument("--self-test", action="store_true", help="Exercise atomic replacement and recovery failures.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    expanded_target = Path(args.target).expanduser()
    absolute_target = Path(os.path.abspath(expanded_target))
    target = absolute_target.parent.resolve(strict=False) / absolute_target.name
    try:
        install(target, allow_formal=args.formal_install)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"DIRCREATIVE_INSTALL: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"installed DIRcreative skill package: {target}")
    print("verify with:")
    print(f"  cd {target}")
    print("  python3 scripts/validate_project.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
