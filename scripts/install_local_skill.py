#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from typing import Callable
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
from dircreative_verify_release import (
    ArchiveManifestEntry,
    PinnedDirectory,
    VerifiedRelease,
    archive_manifest_digest,
    assert_tree_matches_manifest,
    directory_open_flags,
    inode_identity,
    open_pinned_directory,
    regular_file_open_flags,
    stable_entry_identity,
    strict_tree_manifest,
    strict_tree_manifest_from_fd,
    verify_release_detailed,
)
import dircreative_dependency_bundle as dependency_bundle
import dircreative_jingzao_updater as jingzao_updater


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / ".codex" / "dev-skills" / "dircreative"
FORMAL_INSTALL_TARGETS = (
    Path.home() / ".skillshub" / "dircreative",
    Path.home() / ".codex" / "skills" / "dircreative",
)
INTERNAL_SKILL_FILE = "INTERNAL_SKILL.md"
LICENSED_DEPENDENCY_MANIFEST = ROOT / "dependency-bundles" / "humanizer-zh" / "manifest.json"


def root_skill_source(base: Path = ROOT) -> Path:
    source_layout = base / "skills" / "dircreative" / "SKILL.md"
    if source_layout.exists():
        return source_layout
    installed_layout = base / "SKILL.md"
    if installed_layout.exists():
        return installed_layout
    raise SystemExit("missing root DIRcreative SKILL.md")


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
    if allow_formal:
        raise ValueError(
            "formal DIRcreative installation requires a verified artifact; "
            "call formal_install with the complete provenance arguments"
        )
    validate_install_target(target, allow_formal=False)
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


def validate_formal_source(reproducible_source: Path) -> Path:
    expanded = reproducible_source.expanduser()
    absolute = Path(os.path.abspath(expanded))
    try:
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"formal reproducible source is unavailable: {absolute}: {exc}") from exc
    if resolved != ROOT:
        raise ValueError(
            "formal installer must run from the exact reproducible source repository; "
            f"expected {ROOT}, got {absolute}"
        )
    return resolved


def validate_formal_request(expected_commit: str, expected_tag: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit) is None:
        raise ValueError("--expected-commit must be one full lowercase 40-character commit SHA")
    if re.fullmatch(r"v\d+\.\d+\.\d+", expected_tag) is None:
        raise ValueError("--expected-tag must be a canonical v<semantic-version> tag")


FORMAL_REQUIRED_OPTIONS = (
    "artifact",
    "checksums",
    "expected_commit",
    "expected_tag",
    "reproducible_source",
)


def missing_formal_options(namespace: argparse.Namespace) -> list[str]:
    return [
        f"--{name.replace('_', '-')}"
        for name in FORMAL_REQUIRED_OPTIONS
        if not getattr(namespace, name, None)
    ]


def create_unique_directory_at(
    parent: PinnedDirectory,
    *,
    prefix: str,
) -> tuple[str, int, tuple[int, int]]:
    for _attempt in range(128):
        name = f"{prefix}{uuid.uuid4().hex}"
        try:
            os.mkdir(name, 0o700, dir_fd=parent.fd)
        except FileExistsError:
            continue
        before = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        descriptor = os.open(name, directory_open_flags(), dir_fd=parent.fd)
        opened = os.fstat(descriptor)
        after = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        if (
            inode_identity(before) != inode_identity(opened)
            or inode_identity(after) != inode_identity(opened)
        ):
            os.close(descriptor)
            raise ValueError("new private installation directory changed while opening")
        return name, descriptor, inode_identity(opened)
    raise ValueError("cannot allocate a unique private installation directory")


def stat_entry_at(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def remove_tree_contents_fd(directory_fd: int) -> None:
    os.fchmod(directory_fd, 0o700)
    for name in sorted(os.listdir(directory_fd)):
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(before.st_mode):
            child_fd = os.open(name, directory_open_flags(), dir_fd=directory_fd)
            try:
                opened = os.fstat(child_fd)
                if inode_identity(before) != inode_identity(opened):
                    raise ValueError("cleanup directory changed while opening")
                remove_tree_contents_fd(child_fd)
                linked = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if inode_identity(linked) != inode_identity(opened):
                    raise ValueError("cleanup directory binding changed")
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        else:
            os.unlink(name, dir_fd=directory_fd)


def remove_expected_directory_at(
    parent_fd: int,
    name: str,
    expected_identity: tuple[int, int],
) -> bool:
    linked = stat_entry_at(parent_fd, name)
    if linked is None:
        return False
    if not stat.S_ISDIR(linked.st_mode) or inode_identity(linked) != expected_identity:
        raise ValueError(f"refusing to remove an unexpected installation entry: {name}")
    descriptor = os.open(name, directory_open_flags(), dir_fd=parent_fd)
    try:
        opened = os.fstat(descriptor)
        if inode_identity(opened) != expected_identity:
            raise ValueError(f"installation entry changed while opening for cleanup: {name}")
        remove_tree_contents_fd(descriptor)
        linked_after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if inode_identity(linked_after) != expected_identity:
            raise ValueError(f"installation entry changed before cleanup: {name}")
    finally:
        os.close(descriptor)
    os.rmdir(name, dir_fd=parent_fd)
    return True


def copy_verified_tree(
    source: Path,
    target: Path,
    manifest: tuple[ArchiveManifestEntry, ...],
    *,
    race_hook: Callable[[str, str], None] | None = None,
    source_root_fd: int | None = None,
    target_root_fd: int | None = None,
) -> None:
    if source_root_fd is None:
        assert_tree_matches_manifest(source, manifest, label="verified extraction before copy")
    elif strict_tree_manifest_from_fd(source_root_fd) != manifest:
        raise ValueError("verified extraction before copy does not match archive manifest")
    by_path = {entry.path: entry for entry in manifest}
    if len(by_path) != len(manifest) or "." not in by_path:
        raise ValueError("verified archive manifest has duplicate paths or no root entry")
    root_entry = by_path["."]
    if root_entry.kind != "directory":
        raise ValueError("verified archive manifest root must be a directory")

    directories = sorted(
        (entry for entry in manifest if entry.path != "." and entry.kind == "directory"),
        key=lambda entry: (len(Path(entry.path).parts), entry.path),
    )
    files = sorted(
        (entry for entry in manifest if entry.kind == "file"),
        key=lambda entry: entry.path,
    )
    if len(directories) + len(files) + 1 != len(manifest):
        raise ValueError("verified archive manifest contains an unsupported entry kind")

    target_context = (
        open_pinned_directory(target)
        if target_root_fd is None
        else nullcontext(None)
    )
    source_context = (
        open_pinned_directory(source)
        if source_root_fd is None
        else nullcontext(None)
    )
    with source_context as opened_source_root, target_context as opened_target_root:
        effective_source_fd = (
            opened_source_root.fd
            if opened_source_root is not None
            else source_root_fd
        )
        effective_target_fd = (
            opened_target_root.fd
            if opened_target_root is not None
            else target_root_fd
        )
        if effective_source_fd is None or not stat.S_ISDIR(os.fstat(effective_source_fd).st_mode):
            raise ValueError("verified extraction descriptor must reference a directory")
        if effective_target_fd is None or not stat.S_ISDIR(os.fstat(effective_target_fd).st_mode):
            raise ValueError("formal install target descriptor must reference a directory")
        source_directories: dict[str, int] = {".": effective_source_fd}
        target_directories: dict[str, int] = {".": effective_target_fd}
        source_bindings: list[tuple[int, str, tuple[int, int], int]] = []
        target_bindings: list[tuple[int, str, tuple[int, int], int]] = []
        try:
            for entry in directories:
                relative = PurePosixPath(entry.path)
                parent = relative.parent.as_posix()
                source_parent_fd = source_directories[parent]
                source_before = os.stat(
                    relative.name,
                    dir_fd=source_parent_fd,
                    follow_symlinks=False,
                )
                if race_hook is not None:
                    race_hook("source_child_lstat", entry.path)
                source_fd = os.open(
                    relative.name,
                    directory_open_flags(),
                    dir_fd=source_parent_fd,
                )
                source_opened = os.fstat(source_fd)
                source_linked = os.stat(
                    relative.name,
                    dir_fd=source_parent_fd,
                    follow_symlinks=False,
                )
                if (
                    stable_entry_identity(source_before) != stable_entry_identity(source_opened)
                    or stable_entry_identity(source_linked) != stable_entry_identity(source_opened)
                ):
                    os.close(source_fd)
                    raise ValueError(
                        f"verified extraction directory changed while opening: {entry.path}"
                    )
                source_directories[entry.path] = source_fd
                source_bindings.append(
                    (source_parent_fd, relative.name, inode_identity(source_opened), source_fd)
                )

                target_parent_fd = target_directories[parent]
                os.mkdir(relative.name, 0o700, dir_fd=target_parent_fd)
                target_before = os.stat(
                    relative.name,
                    dir_fd=target_parent_fd,
                    follow_symlinks=False,
                )
                target_fd = os.open(
                    relative.name,
                    directory_open_flags(),
                    dir_fd=target_parent_fd,
                )
                target_opened = os.fstat(target_fd)
                if inode_identity(target_before) != inode_identity(target_opened):
                    os.close(target_fd)
                    raise ValueError(
                        f"formal install directory changed while opening: {entry.path}"
                    )
                target_directories[entry.path] = target_fd
                target_bindings.append(
                    (target_parent_fd, relative.name, inode_identity(target_opened), target_fd)
                )
                if race_hook is not None:
                    race_hook("destination_directory_created", entry.path)

            for entry in files:
                relative = PurePosixPath(entry.path)
                parent = relative.parent.as_posix()
                source_parent_fd = source_directories[parent]
                source_before = os.stat(
                    relative.name,
                    dir_fd=source_parent_fd,
                    follow_symlinks=False,
                )
                if race_hook is not None:
                    race_hook("source_child_lstat", entry.path)
                try:
                    source_fd = os.open(
                        relative.name,
                        regular_file_open_flags(),
                        dir_fd=source_parent_fd,
                    )
                except OSError as exc:
                    raise ValueError(
                        f"cannot open verified extraction file {entry.path}: {exc}"
                    ) from exc
                source_opened = os.fstat(source_fd)
                if stable_entry_identity(source_before) != stable_entry_identity(source_opened):
                    os.close(source_fd)
                    raise ValueError(
                        f"verified extraction file changed while opening: {entry.path}"
                    )
                target_parent_fd = target_directories[parent]
                try:
                    destination_fd = os.open(
                        relative.name,
                        regular_file_open_flags(write=True, create=True),
                        0o600,
                        dir_fd=target_parent_fd,
                    )
                except BaseException:
                    os.close(source_fd)
                    raise
                digest = hashlib.sha256()
                total = 0
                with (
                    os.fdopen(source_fd, "rb", closefd=True) as source_handle,
                    os.fdopen(destination_fd, "wb", closefd=True) as destination_handle,
                ):
                    destination_opened = os.fstat(destination_handle.fileno())
                    if (
                        not stat.S_ISREG(source_opened.st_mode)
                        or source_opened.st_nlink != 1
                        or not stat.S_ISREG(destination_opened.st_mode)
                        or destination_opened.st_nlink != 1
                    ):
                        raise ValueError(
                            f"formal copy requires single-link regular files: {entry.path}"
                        )
                    while True:
                        chunk = source_handle.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        digest.update(chunk)
                        destination_handle.write(chunk)
                    destination_handle.flush()
                    os.fsync(destination_handle.fileno())
                    os.fchmod(destination_handle.fileno(), entry.mode)
                    source_after = os.fstat(source_handle.fileno())
                    destination_after = os.fstat(destination_handle.fileno())
                source_linked = os.stat(
                    relative.name,
                    dir_fd=source_parent_fd,
                    follow_symlinks=False,
                )
                destination_linked = os.stat(
                    relative.name,
                    dir_fd=target_parent_fd,
                    follow_symlinks=False,
                )
                if (
                    stable_entry_identity(source_opened) != stable_entry_identity(source_after)
                    or stable_entry_identity(source_after) != stable_entry_identity(source_linked)
                ):
                    raise ValueError(f"verified extraction file changed during copy: {entry.path}")
                if (
                    inode_identity(destination_after) != inode_identity(destination_linked)
                    or destination_after.st_size != entry.size
                ):
                    raise ValueError(f"formal install file changed during copy: {entry.path}")
                if total != entry.size or digest.hexdigest() != entry.sha256:
                    raise ValueError(f"verified extraction file content changed: {entry.path}")

            for entry in reversed(directories):
                os.fchmod(target_directories[entry.path], entry.mode)
            os.fchmod(effective_target_fd, root_entry.mode)

            for parent_fd, name, expected_identity, descriptor in source_bindings:
                linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    inode_identity(linked) != expected_identity
                    or inode_identity(os.fstat(descriptor)) != expected_identity
                ):
                    raise ValueError("verified extraction directory binding changed during copy")
            for parent_fd, name, expected_identity, descriptor in target_bindings:
                linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    inode_identity(linked) != expected_identity
                    or inode_identity(os.fstat(descriptor)) != expected_identity
                ):
                    raise ValueError("formal install directory binding changed during copy")

            staged_manifest = strict_tree_manifest_from_fd(effective_target_fd)
            if staged_manifest != manifest:
                raise ValueError("formal install staging tree does not match verified archive manifest")
            source_manifest = strict_tree_manifest_from_fd(effective_source_fd)
            if source_manifest != manifest:
                raise ValueError("verified extraction changed during formal copy")
            if opened_source_root is not None:
                opened_source_root.revalidate(label="verified extraction after copy")
            if opened_target_root is not None:
                opened_target_root.revalidate(label="formal install staging after copy")
        finally:
            for descriptor in reversed(
                [value for key, value in source_directories.items() if key != "."]
            ):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            for descriptor in reversed(
                [value for key, value in target_directories.items() if key != "."]
            ):
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def install_verified_tree(
    target: Path,
    verified: VerifiedRelease,
    *,
    after_staging: Callable[[Path], None] | None = None,
    after_swap: Callable[[Path], None] | None = None,
    copy_race_hook: Callable[[str, str], None] | None = None,
    verified_root_fd: int | None = None,
) -> None:
    if verified.extracted_root is None:
        raise ValueError("formal install requires a verifier-owned extracted release tree")
    if archive_manifest_digest(verified.archive_manifest) != verified.archive_manifest_sha256:
        raise ValueError("formal install archive manifest digest mismatch")
    validate_install_target(target, allow_formal=True)
    with open_pinned_directory(target.parent, create=True) as target_parent:
        staging_name, staging_fd, staging_identity = create_unique_directory_at(
            target_parent,
            prefix=f".{target.name}.verified-staging-",
        )
        staging = target_parent.path / staging_name
        backup_name = f".{target.name}.backup-{uuid.uuid4().hex}"
        backup = target_parent.path / backup_name
        backup_identity: tuple[int, int] | None = None
        moved_existing = False
        restored_existing = False
        swapped = False
        completed = False
        try:
            linked_staging = os.stat(
                staging_name,
                dir_fd=target_parent.fd,
                follow_symlinks=False,
            )
            if inode_identity(linked_staging) != staging_identity:
                raise ValueError("formal install staging binding changed before copy")
            copy_verified_tree(
                verified.extracted_root,
                staging,
                verified.archive_manifest,
                race_hook=copy_race_hook,
                source_root_fd=verified_root_fd,
                target_root_fd=staging_fd,
            )
            linked_staging = os.stat(
                staging_name,
                dir_fd=target_parent.fd,
                follow_symlinks=False,
            )
            if inode_identity(linked_staging) != staging_identity:
                raise ValueError("formal install staging binding changed during copy")
            if after_staging is not None:
                after_staging(staging)
            if strict_tree_manifest_from_fd(staging_fd) != verified.archive_manifest:
                raise ValueError(
                    "formal install staging pre-swap tree does not match verified archive manifest"
                )
            target_parent.revalidate(label="formal install parent before swap")
            current_target = stat_entry_at(target_parent.fd, target.name)
            if current_target is not None:
                if not stat.S_ISDIR(current_target.st_mode):
                    raise ValueError("formal install target must be a real directory")
                current_fd = os.open(
                    target.name,
                    directory_open_flags(),
                    dir_fd=target_parent.fd,
                )
                try:
                    opened_target = os.fstat(current_fd)
                    if inode_identity(opened_target) != inode_identity(current_target):
                        raise ValueError("formal install target changed while preserving it")
                    backup_identity = inode_identity(opened_target)
                finally:
                    os.close(current_fd)
                os.replace(
                    target.name,
                    backup_name,
                    src_dir_fd=target_parent.fd,
                    dst_dir_fd=target_parent.fd,
                )
                moved_existing = True
                preserved = os.stat(
                    backup_name,
                    dir_fd=target_parent.fd,
                    follow_symlinks=False,
                )
                if inode_identity(preserved) != backup_identity:
                    raise ValueError("preserved formal install identity changed during backup")
            linked_staging = os.stat(
                staging_name,
                dir_fd=target_parent.fd,
                follow_symlinks=False,
            )
            if inode_identity(linked_staging) != staging_identity:
                raise ValueError("formal install staging binding changed before swap")
            os.replace(
                staging_name,
                target.name,
                src_dir_fd=target_parent.fd,
                dst_dir_fd=target_parent.fd,
            )
            swapped = True
            installed = os.stat(
                target.name,
                dir_fd=target_parent.fd,
                follow_symlinks=False,
            )
            if inode_identity(installed) != staging_identity:
                raise ValueError("formal install target identity changed during swap")
            if after_swap is not None:
                after_swap(target_parent.path / target.name)
            if strict_tree_manifest_from_fd(staging_fd) != verified.archive_manifest:
                raise ValueError(
                    "formal install target post-swap tree does not match verified archive manifest"
                )
            installed_after = os.stat(
                target.name,
                dir_fd=target_parent.fd,
                follow_symlinks=False,
            )
            if inode_identity(installed_after) != staging_identity:
                raise ValueError("formal install target binding changed after swap")
            target_parent.revalidate(label="formal install parent after swap")
            completed = True
        except BaseException as install_error:
            try:
                if swapped:
                    current_target = stat_entry_at(target_parent.fd, target.name)
                    if current_target is None or inode_identity(current_target) != staging_identity:
                        raise RuntimeError(
                            "formal install rollback cannot identify the newly installed target"
                        )
                    remove_expected_directory_at(
                        target_parent.fd,
                        target.name,
                        staging_identity,
                    )
                if moved_existing:
                    if backup_identity is None:
                        raise RuntimeError("formal install rollback lost the backup identity")
                    if stat_entry_at(target_parent.fd, target.name) is not None:
                        raise RuntimeError(
                            "formal install rollback cannot restore while the target still exists"
                        )
                    preserved = stat_entry_at(target_parent.fd, backup_name)
                    if preserved is None or inode_identity(preserved) != backup_identity:
                        raise RuntimeError("formal install rollback cannot identify the preserved install")
                    os.replace(
                        backup_name,
                        target.name,
                        src_dir_fd=target_parent.fd,
                        dst_dir_fd=target_parent.fd,
                    )
                    moved_existing = False
                    restored_existing = True
                    restored = os.stat(
                        target.name,
                        dir_fd=target_parent.fd,
                        follow_symlinks=False,
                    )
                    if inode_identity(restored) != backup_identity:
                        raise RuntimeError("formal install rollback restored the wrong target")
                target_parent.revalidate(label="formal install parent after rollback")
            except BaseException as restore_error:
                if restored_existing:
                    recovery_message = (
                        "formal DIRcreative install failed; "
                        f"the previous install was moved back to the target at: {target}, "
                        "but restoration readback did not complete"
                    )
                elif moved_existing:
                    recovery_message = (
                        "formal DIRcreative install failed and automatic restoration also failed; "
                        f"the previous install is retained at: {backup}"
                    )
                else:
                    recovery_message = (
                        "formal DIRcreative install failed and automatic restoration also failed; "
                        "no preserved previous install is available"
                    )
                raise RuntimeError(recovery_message) from restore_error
            raise install_error
        finally:
            failure_in_flight = sys.exc_info()[0] is not None
            try:
                linked_staging = stat_entry_at(target_parent.fd, staging_name)
                if linked_staging is not None:
                    if inode_identity(linked_staging) != staging_identity:
                        if not failure_in_flight:
                            raise ValueError("formal install staging name was replaced")
                    else:
                        remove_expected_directory_at(
                            target_parent.fd,
                            staging_name,
                            staging_identity,
                        )
                if completed and backup_identity is not None:
                    remove_expected_directory_at(
                        target_parent.fd,
                        backup_name,
                        backup_identity,
                    )
            finally:
                os.close(staging_fd)


def formal_install(
    target: Path,
    *,
    artifact: Path,
    checksums: Path,
    expected_commit: str,
    expected_tag: str,
    reproducible_source: Path,
    allow_unpublished: bool = False,
    verifier: Callable[..., VerifiedRelease] | None = None,
    after_staging: Callable[[Path], None] | None = None,
    after_swap: Callable[[Path], None] | None = None,
) -> VerifiedRelease:
    validate_formal_request(expected_commit, expected_tag)
    source = validate_formal_source(reproducible_source)
    validate_install_target(target, allow_formal=True)
    with open_pinned_directory(source) as source_root:
        version_before = os.stat("VERSION", dir_fd=source_root.fd, follow_symlinks=False)
        version_fd = os.open(
            "VERSION",
            regular_file_open_flags(),
            dir_fd=source_root.fd,
        )
        with os.fdopen(version_fd, "rb", closefd=True) as version_handle:
            version_opened = os.fstat(version_handle.fileno())
            if (
                not stat.S_ISREG(version_opened.st_mode)
                or version_opened.st_nlink != 1
                or stable_entry_identity(version_before) != stable_entry_identity(version_opened)
            ):
                raise ValueError("formal installer source VERSION must be a single-link regular file")
            version_bytes = version_handle.read(128)
            version_after = os.fstat(version_handle.fileno())
        version_linked = os.stat("VERSION", dir_fd=source_root.fd, follow_symlinks=False)
        if (
            stable_entry_identity(version_opened) != stable_entry_identity(version_after)
            or stable_entry_identity(version_after) != stable_entry_identity(version_linked)
        ):
            raise ValueError("formal installer source VERSION changed while being read")
        source_root.revalidate(label="formal installer source")
    try:
        expected_version = version_bytes.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("formal installer source VERSION must be UTF-8") from exc
    if expected_tag != f"v{expected_version}":
        raise ValueError("--expected-tag does not match the exact source VERSION")
    verifier_function = verifier or verify_release_detailed
    with open_pinned_directory(target.parent, create=True) as target_parent:
        extract_name, extract_fd, extract_identity = create_unique_directory_at(
            target_parent,
            prefix=f".{target.name}.verified-extract-",
        )
        extract_path = target_parent.path / extract_name
        try:
            verified = verifier_function(
                artifact,
                checksums,
                expected_version=expected_version,
                expected_commit=expected_commit,
                extract_to=extract_path,
                reproducible_source=source,
                expected_tag=expected_tag,
                require_remote_tag=not allow_unpublished,
                extract_root_fd=extract_fd,
            )
            target_parent.revalidate(label="formal verifier extraction parent")
            if verified.commit_sha != expected_commit:
                raise ValueError("verified release commit does not equal the requested exact commit")
            if verified.reproducible_match != "true":
                raise ValueError("formal installer requires an exact reproducible artifact match")
            expected_scope = (
                "local_exact_commit_rebuild_only" if allow_unpublished else "canonical_remote_tag"
            )
            if verified.provenance_scope != expected_scope:
                raise ValueError("verified release provenance scope does not match formal install mode")
            if not allow_unpublished and verified.remote_tag_match != "true":
                raise ValueError("formal installer requires a canonical annotated remote tag")
            if (
                verified.extracted_root is None
                or verified.extracted_root.parent != extract_path
            ):
                raise ValueError("formal verifier returned an extraction outside its pinned root")
            linked_extract = os.stat(
                extract_name,
                dir_fd=target_parent.fd,
                follow_symlinks=False,
            )
            if inode_identity(linked_extract) != extract_identity:
                raise ValueError("formal verifier extraction root binding changed")
            verified_root_name = verified.extracted_root.name
            if (
                PurePosixPath(verified_root_name).name != verified_root_name
                or verified_root_name in {"", ".", ".."}
            ):
                raise ValueError("formal verifier returned an unsafe extraction root name")
            verified_root_before = os.stat(
                verified_root_name,
                dir_fd=extract_fd,
                follow_symlinks=False,
            )
            verified_root_fd = os.open(
                verified_root_name,
                directory_open_flags(),
                dir_fd=extract_fd,
            )
            try:
                verified_root_opened = os.fstat(verified_root_fd)
                if inode_identity(verified_root_before) != inode_identity(verified_root_opened):
                    raise ValueError("formal verifier extraction tree changed while pinning")
                install_verified_tree(
                    target,
                    verified,
                    after_staging=after_staging,
                    after_swap=after_swap,
                    verified_root_fd=verified_root_fd,
                )
                verified_root_linked = os.stat(
                    verified_root_name,
                    dir_fd=extract_fd,
                    follow_symlinks=False,
                )
                if inode_identity(verified_root_linked) != inode_identity(verified_root_opened):
                    raise ValueError("formal verifier extraction tree binding changed during install")
            finally:
                os.close(verified_root_fd)
            return verified
        finally:
            try:
                remove_expected_directory_at(
                    target_parent.fd,
                    extract_name,
                    extract_identity,
                )
            finally:
                os.close(extract_fd)


def self_test() -> int:
    current_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    current_tag = f"v{current_version}"
    unicode_escape_sample = b'if "\\\\u003c/script\\\\u003e" not in hostile_fragment:\n'
    if sanitize_package_bytes("scripts/escape-sample.py", unicode_escape_sample, {}) != unicode_escape_sample:
        raise AssertionError("package sanitizer modified JSON unicode escape evidence")
    regex_escape_sample = b'"pattern": "^(?!/)(?!.*(?:^|/)\\\\.\\\\.(?:/|$)).+$"\n'
    if sanitize_package_bytes("schemas/relative-path.json", regex_escape_sample, {}) != regex_escape_sample:
        raise AssertionError("package sanitizer modified relative-path regex evidence")
    for commit, tag, expected_error in (
        ("not-a-commit", "v0.5.0", "--expected-commit"),
        ("a" * 40, "0.5.0", "--expected-tag"),
        ("a" * 40, "vnext", "--expected-tag"),
    ):
        try:
            validate_formal_request(commit, tag)
        except ValueError as exc:
            if expected_error not in str(exc):
                raise
        else:
            raise AssertionError("formal installer accepted invalid commit/tag input")
    with tempfile.TemporaryDirectory(prefix="dircreative-installer-self-test-") as raw:
        root = Path(raw).resolve()
        source_fixture = root / "source-safety"
        for item in PACKAGE_ITEMS:
            path = source_fixture / item
            if item in {"README.md", "llms.txt", "VERSION", "CHANGELOG.md"}:
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
                "runtime/visual-asset-plan.schema.json",
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

    missing = missing_formal_options(
        argparse.Namespace(
            artifact=None,
            checksums=None,
            expected_commit=None,
            expected_tag=None,
            reproducible_source=None,
        )
    )
    if missing != [
        "--artifact",
        "--checksums",
        "--expected-commit",
        "--expected-tag",
        "--reproducible-source",
    ]:
        raise AssertionError(f"formal installer missing-argument gate drifted: {missing}")

    with tempfile.TemporaryDirectory(prefix="dircreative-formal-installer-self-test-") as raw:
        formal_root = Path(raw).resolve()
        extracted = formal_root / "verified-extraction"
        extracted.mkdir(mode=0o755)
        (extracted / "SKILL.md").write_text("# verified fixture\n", encoding="utf-8")
        (extracted / "SKILL.md").chmod(0o644)
        empty_directory = extracted / "empty"
        empty_directory.mkdir(mode=0o755)
        nested_directory = extracted / "nested"
        nested_directory.mkdir(mode=0o750)
        nested_payload = nested_directory / "payload.txt"
        nested_payload.write_text("verified nested payload\n", encoding="utf-8")
        nested_payload.chmod(0o640)
        manifest = strict_tree_manifest(extracted)
        verified = VerifiedRelease(
            version="0.5.0",
            commit_sha="a" * 40,
            artifact_sha256="b" * 64,
            reproducible_match="true",
            remote_tag_match="not_requested",
            provenance_scope="local_exact_commit_rebuild_only",
            extracted_root=extracted,
            archive_manifest=manifest,
            archive_manifest_sha256=archive_manifest_digest(manifest),
        )
        formal_target = formal_root / "formal-target"
        formal_target.mkdir()
        prior = formal_target / "previous-install.txt"
        prior.write_text("preserve\n", encoding="utf-8")

        real_stat = os.stat
        backup_readback_injected = False

        def fail_preserved_backup_readback(
            path: os.PathLike[str] | str | int,
            *args: object,
            **kwargs: object,
        ) -> os.stat_result:
            nonlocal backup_readback_injected
            if (
                not backup_readback_injected
                and isinstance(path, str)
                and path.startswith(f".{formal_target.name}.backup-")
                and kwargs.get("dir_fd") is not None
                and kwargs.get("follow_symlinks") is False
            ):
                backup_readback_injected = True
                raise OSError("injected preserved-backup readback failure")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(os, "stat", side_effect=fail_preserved_backup_readback):
            try:
                install_verified_tree(formal_target, verified)
            except OSError as exc:
                if "injected preserved-backup readback failure" not in str(exc):
                    raise
            else:
                raise AssertionError("formal installer accepted a failed backup readback")
        if not backup_readback_injected:
            raise AssertionError("formal backup-readback failure hook did not execute")
        if prior.read_text(encoding="utf-8") != "preserve\n":
            raise AssertionError("backup readback failure did not restore the previous install")
        if list(formal_root.glob(".formal-target.backup-*")):
            raise AssertionError("backup readback failure left a hidden recovery backup")

        real_replace = os.replace
        restore_move_completed = False
        restore_readback_injected = False

        def observe_restore_move(
            source: os.PathLike[str] | str,
            destination: os.PathLike[str] | str,
            *args: object,
            **kwargs: object,
        ) -> None:
            nonlocal restore_move_completed
            real_replace(source, destination, *args, **kwargs)
            if (
                isinstance(source, str)
                and source.startswith(f".{formal_target.name}.backup-")
                and destination == formal_target.name
            ):
                restore_move_completed = True

        def fail_restored_target_readback(
            path: os.PathLike[str] | str | int,
            *args: object,
            **kwargs: object,
        ) -> os.stat_result:
            nonlocal restore_readback_injected
            if (
                restore_move_completed
                and not restore_readback_injected
                and path == formal_target.name
                and kwargs.get("dir_fd") is not None
                and kwargs.get("follow_symlinks") is False
            ):
                restore_readback_injected = True
                raise OSError("injected restored-target readback failure")
            return real_stat(path, *args, **kwargs)

        def force_post_swap_rollback(_installed: Path) -> None:
            raise ValueError("injected post-swap failure requiring rollback")

        with (
            mock.patch.object(os, "replace", side_effect=observe_restore_move),
            mock.patch.object(os, "stat", side_effect=fail_restored_target_readback),
        ):
            try:
                install_verified_tree(
                    formal_target,
                    verified,
                    after_swap=force_post_swap_rollback,
                )
            except RuntimeError as exc:
                if (
                    "was moved back to the target" not in str(exc)
                    or "restoration readback did not complete" not in str(exc)
                    or "retained at" in str(exc)
                ):
                    raise
            else:
                raise AssertionError("formal installer hid a restored-target readback failure")
        if not restore_move_completed or not restore_readback_injected:
            raise AssertionError("formal restored-target readback failure hook did not execute")
        if prior.read_text(encoding="utf-8") != "preserve\n":
            raise AssertionError("restore readback failure lost the previous installation")
        if list(formal_root.glob(".formal-target.backup-*")):
            raise AssertionError("restore readback failure reported a non-existent recovery backup")

        manifest_race_parent = formal_root / "manifest-race"
        manifest_race_parent.mkdir()
        manifest_race_tree = manifest_race_parent / "tree"
        manifest_race_tree.mkdir()
        (manifest_race_tree / "child.txt").write_text("pinned tree\n", encoding="utf-8")
        manifest_race_outside = manifest_race_parent / "outside"
        manifest_race_outside.mkdir()
        outside_manifest_file = manifest_race_outside / "child.txt"
        outside_manifest_file.write_text("outside tree\n", encoding="utf-8")
        outside_manifest_mode = stat.S_IMODE(manifest_race_outside.stat().st_mode)
        detached_manifest_tree = manifest_race_parent / "tree-detached"
        manifest_race_fired = False

        def swap_manifest_ancestor(event: str, relative: str) -> None:
            nonlocal manifest_race_fired
            if manifest_race_fired or event != "child_lstat" or relative != "child.txt":
                return
            manifest_race_fired = True
            manifest_race_tree.rename(detached_manifest_tree)
            manifest_race_tree.symlink_to(manifest_race_outside, target_is_directory=True)

        try:
            strict_tree_manifest(manifest_race_tree, race_hook=swap_manifest_ancestor)
        except ValueError as exc:
            if "changed" not in str(exc):
                raise
        else:
            raise AssertionError("strict manifest accepted an ancestor swap after child lstat")
        if not manifest_race_fired:
            raise AssertionError("strict manifest ancestor-swap hook did not execute")
        if (
            outside_manifest_file.read_text(encoding="utf-8") != "outside tree\n"
            or stat.S_IMODE(manifest_race_outside.stat().st_mode) != outside_manifest_mode
        ):
            raise AssertionError("strict manifest ancestor race modified the outside tree")
        manifest_race_tree.unlink()
        detached_manifest_tree.rename(manifest_race_tree)

        source_race_parent = formal_root / "source-copy-race"
        source_race_parent.mkdir()
        source_race_tree = source_race_parent / "source"
        shutil.copytree(extracted, source_race_tree)
        source_race_manifest = strict_tree_manifest(source_race_tree)
        source_race_outside = source_race_parent / "outside"
        source_race_outside.mkdir()
        outside_source_file = source_race_outside / "SKILL.md"
        outside_source_file.write_text("outside source\n", encoding="utf-8")
        outside_source_mode = stat.S_IMODE(source_race_outside.stat().st_mode)
        source_race_target = source_race_parent / "target"
        source_race_target.mkdir()
        detached_source_tree = source_race_parent / "source-detached"
        source_race_fired = False

        def swap_source_ancestor(event: str, relative: str) -> None:
            nonlocal source_race_fired
            if source_race_fired or event != "source_child_lstat" or relative != "SKILL.md":
                return
            source_race_fired = True
            source_race_tree.rename(detached_source_tree)
            source_race_tree.symlink_to(source_race_outside, target_is_directory=True)

        try:
            copy_verified_tree(
                source_race_tree,
                source_race_target,
                source_race_manifest,
                race_hook=swap_source_ancestor,
            )
        except ValueError as exc:
            if "changed" not in str(exc):
                raise
        else:
            raise AssertionError("formal copy accepted a source ancestor swap after child lstat")
        if not source_race_fired:
            raise AssertionError("formal source-copy ancestor-swap hook did not execute")
        if (
            outside_source_file.read_text(encoding="utf-8") != "outside source\n"
            or stat.S_IMODE(source_race_outside.stat().st_mode) != outside_source_mode
        ):
            raise AssertionError("formal source-copy race modified the outside tree")
        source_race_tree.unlink()
        detached_source_tree.rename(source_race_tree)

        destination_race_outside = formal_root / "destination-race-outside"
        destination_race_outside.mkdir(mode=0o711)
        outside_destination_sentinel = destination_race_outside / "sentinel.txt"
        outside_destination_sentinel.write_text("outside destination\n", encoding="utf-8")
        outside_destination_mode = stat.S_IMODE(destination_race_outside.stat().st_mode)
        detached_destination_staging = formal_root / "destination-staging-detached"
        destination_race_fired = False

        def swap_destination_directory(event: str, relative: str) -> None:
            nonlocal destination_race_fired
            if (
                destination_race_fired
                or event != "destination_directory_created"
                or relative != "empty"
            ):
                return
            staging_candidates = list(
                formal_root.glob(".formal-target.verified-staging-*")
            )
            if len(staging_candidates) != 1:
                raise AssertionError("cannot identify the deterministic formal staging tree")
            staging_root = staging_candidates[0]
            staging_root.rename(detached_destination_staging)
            staging_root.symlink_to(destination_race_outside, target_is_directory=True)
            destination_race_fired = True

        try:
            install_verified_tree(
                formal_target,
                verified,
                copy_race_hook=swap_destination_directory,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "formal installer accepted a destination directory swap before child create"
            )
        if not destination_race_fired:
            raise AssertionError("formal destination-copy race hook did not execute")
        if prior.read_text(encoding="utf-8") != "preserve\n":
            raise AssertionError("destination directory race did not preserve the previous install")
        if (
            outside_destination_sentinel.read_text(encoding="utf-8")
            != "outside destination\n"
            or (destination_race_outside / "payload.txt").exists()
            or stat.S_IMODE(destination_race_outside.stat().st_mode)
            != outside_destination_mode
        ):
            raise AssertionError("formal destination-copy race wrote or chmodded the outside tree")
        staging_aliases = list(formal_root.glob(".formal-target.verified-staging-*"))
        if len(staging_aliases) != 1 or not staging_aliases[0].is_symlink():
            raise AssertionError("formal destination-copy race did not retain the replaced name safely")
        staging_aliases[0].unlink()
        shutil.rmtree(detached_destination_staging)

        def tamper_staging(staging: Path) -> None:
            (staging / "unexpected.txt").write_text("tamper\n", encoding="utf-8")

        try:
            install_verified_tree(formal_target, verified, after_staging=tamper_staging)
        except ValueError as exc:
            if "staging pre-swap" not in str(exc):
                raise
        else:
            raise AssertionError("formal installer accepted a tampered staging tree")
        if prior.read_text(encoding="utf-8") != "preserve\n":
            raise AssertionError("staging tamper modified the previous installation")

        def tamper_target(installed: Path) -> None:
            (installed / "SKILL.md").write_text("post-swap tamper\n", encoding="utf-8")

        try:
            install_verified_tree(formal_target, verified, after_swap=tamper_target)
        except ValueError as exc:
            if "target post-swap" not in str(exc):
                raise
        else:
            raise AssertionError("formal installer accepted a tampered post-swap tree")
        if prior.read_text(encoding="utf-8") != "preserve\n":
            raise AssertionError("post-swap tamper did not restore the previous installation")

        install_verified_tree(formal_target, verified)
        if (formal_target / "SKILL.md").read_text(encoding="utf-8") != "# verified fixture\n":
            raise AssertionError("valid verified tree was not installed")
        if not (formal_target / "empty").is_dir():
            raise AssertionError("formal installer lost an empty archive directory")
        if list(formal_root.glob(".formal-target.backup-*")):
            raise AssertionError("successful formal install left a stale recovery backup")

        try:
            validate_formal_source(formal_root)
        except ValueError as exc:
            if "exact reproducible source" not in str(exc):
                raise
        else:
            raise AssertionError("formal installer accepted a different source directory")
        try:
            install(formal_root / "unverified-formal", allow_formal=True)
        except ValueError as exc:
            if "verified artifact" not in str(exc):
                raise
        else:
            raise AssertionError("development installer entered formal mode without an artifact")

        fake_artifact = formal_root / "artifact.tar.gz"
        fake_checksums = formal_root / "SHA256SUMS"

        def remote_tag_missing(*_args: object, **kwargs: object) -> VerifiedRelease:
            if kwargs.get("require_remote_tag") is not True:
                raise AssertionError("published formal install did not require the canonical remote tag")
            raise ValueError("canonical remote tag is not published")

        try:
            formal_install(
                formal_root / "published-target",
                artifact=fake_artifact,
                checksums=fake_checksums,
                expected_commit="a" * 40,
                expected_tag=current_tag,
                reproducible_source=ROOT,
                verifier=remote_tag_missing,
            )
        except ValueError as exc:
            if "not published" not in str(exc):
                raise
        else:
            raise AssertionError("formal installer allowed an unpublished release by default")

        def verified_unpublished(*_args: object, **kwargs: object) -> VerifiedRelease:
            if kwargs.get("require_remote_tag") is not False:
                raise AssertionError("explicit unpublished mode still required a remote tag")
            extract_to = kwargs.get("extract_to")
            if not isinstance(extract_to, Path):
                raise AssertionError("formal installer did not provide verifier-owned extraction")
            if not isinstance(kwargs.get("extract_root_fd"), int):
                raise AssertionError("formal installer did not pin the verifier extraction root")
            verifier_root = extract_to / f"dircreative-{current_version}"
            shutil.copytree(extracted, verifier_root)
            copied_manifest = strict_tree_manifest(verifier_root)
            return VerifiedRelease(
                version=current_version,
                commit_sha="a" * 40,
                artifact_sha256="b" * 64,
                reproducible_match="true",
                remote_tag_match="not_requested",
                provenance_scope="local_exact_commit_rebuild_only",
                extracted_root=verifier_root,
                archive_manifest=copied_manifest,
                archive_manifest_sha256=archive_manifest_digest(copied_manifest),
            )

        unpublished_target = formal_root / "unpublished-target"
        formal_install(
            unpublished_target,
            artifact=fake_artifact,
            checksums=fake_checksums,
            expected_commit="a" * 40,
            expected_tag=current_tag,
            reproducible_source=ROOT,
            allow_unpublished=True,
            verifier=verified_unpublished,
        )
        if not (unpublished_target / "SKILL.md").is_file():
            raise AssertionError("valid explicit unpublished formal install did not complete")
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
        symlink_root = Path(raw).resolve()
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
    parser.add_argument("--target", help="Install target directory.")
    parser.add_argument("--skills-root", type=Path, help="Skills root; installs DIRcreative at <root>/dircreative.")
    parser.add_argument("--with-dependencies", action="store_true", help="Explicitly install licensed local dependencies and sync Jingzao from its official latest stable Release.")
    parser.add_argument(
        "--formal-install",
        action="store_true",
        help="Install only the exact tree from a reproducibly verified release artifact.",
    )
    parser.add_argument("--artifact", help="Release tar.gz to verify and install in formal mode.")
    parser.add_argument("--checksums", help="SHA256SUMS file binding the formal release artifact.")
    parser.add_argument("--expected-commit", help="Exact lowercase 40-character release commit SHA.")
    parser.add_argument("--expected-tag", help="Canonical v<version> release tag.")
    parser.add_argument(
        "--reproducible-source",
        help="Exact clean canonical source repository used for same-process rebuild verification.",
    )
    parser.add_argument(
        "--allow-unpublished",
        action="store_true",
        help="Explicit local-candidate mode: relax only canonical remote tag publication.",
    )
    parser.add_argument("--self-test", action="store_true", help="Exercise atomic replacement and recovery failures.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.target and args.skills_root:
        parser.error("choose either --target or --skills-root")
    if args.with_dependencies and args.skills_root is None:
        parser.error("--with-dependencies requires an explicit --skills-root")
    requested_target = args.target
    if args.skills_root is not None:
        requested_target = str(args.skills_root.expanduser() / "dircreative")
    if requested_target is None:
        requested_target = str(DEFAULT_TARGET)
    expanded_target = Path(requested_target).expanduser()
    absolute_target = Path(os.path.abspath(expanded_target))
    target = absolute_target.parent.resolve(strict=False) / absolute_target.name
    try:
        if args.formal_install:
            missing = missing_formal_options(args)
            if missing:
                parser.error(
                    "--formal-install requires " + ", ".join(missing)
                )
            artifact = Path(os.path.abspath(Path(args.artifact).expanduser()))
            checksums = Path(os.path.abspath(Path(args.checksums).expanduser()))
            reproducible_source = Path(
                os.path.abspath(Path(args.reproducible_source).expanduser())
            )
            verified = formal_install(
                target,
                artifact=artifact,
                checksums=checksums,
                expected_commit=args.expected_commit,
                expected_tag=args.expected_tag,
                reproducible_source=reproducible_source,
                allow_unpublished=args.allow_unpublished,
            )
            print(f"formal_release_commit: {verified.commit_sha}")
            print(f"formal_artifact_sha256: {verified.artifact_sha256}")
            print(f"formal_manifest_sha256: {verified.archive_manifest_sha256}")
            print(
                "FORMAL_INSTALL_MODE: "
                + (
                    "UNPUBLISHED_LOCAL_CANDIDATE"
                    if args.allow_unpublished
                    else "CANONICAL_REMOTE_TAG"
                )
            )
        else:
            supplied_formal_only = [
                f"--{name.replace('_', '-')}"
                for name in FORMAL_REQUIRED_OPTIONS
                if getattr(args, name, None)
            ]
            if args.allow_unpublished:
                supplied_formal_only.append("--allow-unpublished")
            if supplied_formal_only:
                parser.error(
                    "formal release options require --formal-install: "
                    + ", ".join(supplied_formal_only)
                )
            install(target)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"DIRCREATIVE_INSTALL: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"installed DIRcreative skill package: {target}")
    dependency_result: dict[str, object] | None = None
    if args.with_dependencies:
        skills_root = args.skills_root.expanduser()
        offline = dependency_bundle.install_bundle(
            LICENSED_DEPENDENCY_MANIFEST, skills_root,
            source_root=LICENSED_DEPENDENCY_MANIFEST.parent,
        )
        remote = jingzao_updater.sync_jingzao(skills_root)
        dependency_result = {"licensed_offline": offline, "jingzao": remote}
        print(json.dumps({"dependencies": dependency_result}, ensure_ascii=False, indent=2, sort_keys=True))
    print("verify with:")
    print(f"  cd {target}")
    validation_flags = "--installed-package"
    if not args.formal_install:
        validation_flags += " --allow-development-install"
    print(f"  python3 scripts/validate_project.py {validation_flags}")
    if dependency_result is not None and any(
        value.get("status") != "ok" for value in dependency_result.values() if isinstance(value, dict)
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
