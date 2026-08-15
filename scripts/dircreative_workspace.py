#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


IGNORED_PARTS = {".git", ".adco-local", ".dircreative", ".DS_Store", "__pycache__"}
ROOT_CONTROL_FILES = {
    ".gitignore", "AGENTS.md", "AGENTS.override.md", "CONTEXT.md", "README.md",
    "project.yml",
}
MANAGED_ROOT_NAMES = {"AD-creative"}
MANAGED_ROOT_STEMS = tuple(f"{index:02d}_" for index in range(10))
FILE_EXTENSIONS = {
    ".avif", ".bmp", ".csv", ".docx", ".gif", ".heic", ".heif", ".jpeg",
    ".jpg", ".json", ".m4a", ".m4v", ".md", ".mkv", ".mov", ".mp3",
    ".mp4", ".pdf", ".png", ".pptx", ".srt", ".tif", ".tiff", ".txt",
    ".vtt", ".wav", ".webm", ".webp", ".xlsx", ".yaml", ".yml",
}


class WorkspaceError(Exception):
    pass


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_root(value: str | Path) -> Path:
    root = Path(value).expanduser()
    if root.is_symlink():
        raise WorkspaceError("project root must not be a symlink")
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceError(f"project root is unavailable: {exc}") from exc
    if not root.is_dir():
        raise WorkspaceError("project root must be a directory")
    return root


def is_ignored(path: Path, root: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.relative_to(root).parts)


def is_project_control(path: Path, root: Path) -> bool:
    return (
        (path.parent == root and path.name in ROOT_CONTROL_FILES)
        or path.name in {"AGENTS.md", "AGENTS.override.md", "project.yml"}
    )


def is_protected_delivery(path: Path, root: Path) -> bool:
    for part in path.relative_to(root).parts:
        normalized = re.sub(r"[^a-z0-9]", "", part.casefold())
        if "finaldelivery" in normalized:
            return True
    return False


def classify(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    lowered = relative.as_posix().casefold()
    if is_project_control(path, root):
        return "project_control"
    if is_protected_delivery(path, root):
        return "protected_delivery"
    if path.parent == root and path.name not in ROOT_CONTROL_FILES:
        return "loose_root_material"
    if any(token in lowered for token in ("/cache/", "/tmp/", "/temp/", "__pycache__")):
        return "cache_or_temporary"
    if "contact" in lowered and "sheet" in lowered:
        return "contact_sheet"
    if any(token in lowered for token in ("/preview", "/qa/", "render/", "rendered/")):
        return "qa_or_preview"
    if any(token in lowered for token in ("version_archive", "/archive/", "/archives/")):
        return "archive_copy"
    if any(token in lowered for token in ("/raw/", "/source/", "projectmaterials", "keyassets")):
        return "source_or_key_asset"
    if any(token in lowered for token in ("/selected/", "clientreview", "workinprogress")):
        return "active_work"
    return "other"


def canonical_rank(item: dict[str, Any]) -> tuple[int, int, str]:
    category_order = {
        "source_or_key_asset": 0,
        "active_work": 1,
        "loose_root_material": 2,
        "protected_delivery": 3,
        "other": 4,
        "archive_copy": 5,
        "qa_or_preview": 6,
        "contact_sheet": 7,
        "cache_or_temporary": 8,
        "project_control": 9,
    }
    return (
        category_order.get(str(item["category"]), 9),
        len(Path(str(item["path"])).parts),
        str(item["path"]).casefold(),
    )


def scan_workspace(root_value: str | Path, *, max_groups: int = 50) -> dict[str, Any]:
    root = validate_root(root_value)
    files: list[dict[str, Any]] = []
    skipped_symlinks: list[str] = []
    for path in sorted(root.rglob("*")):
        if is_ignored(path, root):
            continue
        if path.is_symlink():
            skipped_symlinks.append(path.relative_to(root).as_posix())
            continue
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        category = classify(path, root)
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "absolute_path": path,
                "size_bytes": stat.st_size,
                "device": stat.st_dev,
                "inode": stat.st_ino,
                "category": category,
                "protected": category == "protected_delivery",
            }
        )

    by_size: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in files:
        if item["size_bytes"] > 0 and item["category"] != "project_control":
            by_size[int(item["size_bytes"])].append(item)
    by_digest: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        for item in candidates:
            by_digest[(size, sha256_file(Path(item["absolute_path"])))].append(item)

    groups: list[dict[str, Any]] = []
    for (size, digest), items in by_digest.items():
        if len(items) < 2:
            continue
        ordered = sorted(items, key=canonical_rank)
        unique_inodes = {
            (int(item["device"]), int(item["inode"])) for item in ordered
        }
        groups.append(
            {
                "sha256": digest,
                "size_bytes": size,
                "copies": len(ordered),
                "reclaimable_bytes": size * max(0, len(unique_inodes) - 1),
                "hardlinked_paths": len(ordered) - len(unique_inodes),
                "canonical_candidate": ordered[0]["path"],
                "requires_manual_review": any(bool(item["protected"]) for item in ordered),
                "files": [
                    {
                        "path": item["path"],
                        "category": item["category"],
                        "protected": item["protected"],
                    }
                    for item in ordered
                ],
            }
        )
    groups.sort(key=lambda item: (-int(item["reclaimable_bytes"]), str(item["sha256"])))

    loose = [
        item
        for item in files
        if item["category"] == "loose_root_material"
        and Path(str(item["path"])).suffix.casefold() in FILE_EXTENSIONS
    ]
    unorganized_root_entries = []
    for path in sorted(root.iterdir()):
        if path.is_symlink() or path.name.startswith("."):
            continue
        if path.name in ROOT_CONTROL_FILES or path.name in MANAGED_ROOT_NAMES:
            continue
        if is_protected_delivery(path, root):
            continue
        if path.is_dir() and path.name.startswith(MANAGED_ROOT_STEMS):
            continue
        if path.is_dir() or (
            path.is_file() and path.suffix.casefold() in FILE_EXTENSIONS
        ):
            unorganized_root_entries.append(path.relative_to(root).as_posix())
    reclaimable = sum(int(group["reclaimable_bytes"]) for group in groups)
    return {
        "schema_version": "1.0",
        "project_root": ".",
        "read_only": True,
        "files_scanned": len(files),
        "bytes_scanned": sum(int(item["size_bytes"]) for item in files),
        "loose_root_materials": len(loose),
        "loose_root_bytes": sum(int(item["size_bytes"]) for item in loose),
        "unorganized_root_entries": unorganized_root_entries[:100],
        "unorganized_root_entry_count": len(unorganized_root_entries),
        "exact_duplicate_groups": len(groups),
        "duplicate_copies": sum(int(group["copies"]) - 1 for group in groups),
        "hardlinked_paths": sum(int(group["hardlinked_paths"]) for group in groups),
        "reclaimable_bytes": reclaimable,
        "needs_organization": bool(unorganized_root_entries or groups),
        "skipped_symlinks": skipped_symlinks,
        "duplicate_groups": groups[: max(0, max_groups)],
        "duplicate_groups_truncated": max(0, len(groups) - max(0, max_groups)),
        "policy": {
            "default_action": "reference_in_place",
            "move_or_delete_requires_user_confirmation": True,
            "protected_delivery_is_never_auto_modified": True,
            "qa_and_preview_outputs_are_regenerable": True,
        },
    }


def inode_identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def open_pinned_directory(path: Path) -> tuple[int, tuple[int, int]]:
    try:
        before = os.stat(path, follow_symlinks=False)
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        linked = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise WorkspaceError(f"project root binding is unavailable: {exc}") from exc
    if (
        not stat.S_ISDIR(opened.st_mode)
        or inode_identity(before) != inode_identity(opened)
        or inode_identity(linked) != inode_identity(opened)
    ):
        os.close(descriptor)
        raise WorkspaceError("project root binding changed")
    return descriptor, inode_identity(opened)


def directory_binding_matches(path: Path, descriptor: int, identity: tuple[int, int]) -> bool:
    try:
        opened = os.fstat(descriptor)
        linked = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISDIR(opened.st_mode)
        and stat.S_ISDIR(linked.st_mode)
        and inode_identity(opened) == identity
        and inode_identity(linked) == identity
    )


def open_or_create_private_plan_directory(
    root_descriptor: int,
) -> tuple[int, tuple[int, int]]:
    try:
        os.mkdir(".dircreative", mode=0o700, dir_fd=root_descriptor)
    except FileExistsError:
        pass
    except OSError as exc:
        raise WorkspaceError(f"workspace plan directory is unavailable: {exc}") from exc
    try:
        entry = os.stat(".dircreative", dir_fd=root_descriptor, follow_symlinks=False)
        if not stat.S_ISDIR(entry.st_mode):
            raise WorkspaceError("workspace plan directory must be a real directory")
        descriptor = os.open(
            ".dircreative",
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_descriptor,
        )
        opened = os.fstat(descriptor)
    except OSError as exc:
        raise WorkspaceError(f"workspace plan directory is unavailable: {exc}") from exc
    if inode_identity(entry) != inode_identity(opened):
        os.close(descriptor)
        raise WorkspaceError("workspace plan directory binding changed")
    return descriptor, inode_identity(opened)


def plan_directory_binding_matches(
    root_descriptor: int,
    plan_descriptor: int,
    identity: tuple[int, int],
) -> bool:
    try:
        opened = os.fstat(plan_descriptor)
        linked = os.stat(
            ".dircreative", dir_fd=root_descriptor, follow_symlinks=False
        )
    except OSError:
        return False
    return (
        stat.S_ISDIR(opened.st_mode)
        and stat.S_ISDIR(linked.st_mode)
        and inode_identity(opened) == identity
        and inode_identity(linked) == identity
    )


def atomic_write_json_at(
    directory_descriptor: int, name: str, payload: dict[str, Any]
) -> tuple[int, int]:
    try:
        current = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        current = None
    except OSError as exc:
        raise WorkspaceError(f"workspace plan target is unavailable: {exc}") from exc
    if current is not None and (
        not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
    ):
        raise WorkspaceError("workspace plan target must be a single-link regular file")

    temporary_name = f".{name}.{uuid.uuid4().hex}.tmp"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    descriptor = -1
    try:
        descriptor = os.open(
            temporary_name,
            flags,
            0o600,
            dir_fd=directory_descriptor,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name,
            name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        os.fsync(directory_descriptor)
        published = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        if not stat.S_ISREG(published.st_mode) or published.st_nlink != 1:
            raise WorkspaceError("workspace plan publication is not a regular file")
        published_identity = inode_identity(published)
    except OSError as exc:
        raise WorkspaceError(f"workspace plan write failed: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory_descriptor)
        except FileNotFoundError:
            pass
        except OSError:
            pass
    return published_identity


def remove_owned_plan(
    directory_descriptor: int, name: str, identity: tuple[int, int]
) -> None:
    try:
        current = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        if (
            stat.S_ISREG(current.st_mode)
            and inode_identity(current) == identity
        ):
            os.unlink(name, dir_fd=directory_descriptor)
            os.fsync(directory_descriptor)
    except OSError:
        pass


def write_plan(
    root_value: str | Path,
    *,
    max_groups: int = 50,
    _race_hook: Callable[[], None] | None = None,
    _plan_dir_race_hook: Callable[[], None] | None = None,
) -> tuple[Path, dict[str, Any]]:
    root = validate_root(root_value)
    root_descriptor, root_identity = open_pinned_directory(root)
    try:
        if not directory_binding_matches(root, root_descriptor, root_identity):
            raise WorkspaceError("project root binding changed before scan")
        report = scan_workspace(root, max_groups=max_groups)
        plan = {
            **report,
            "plan_status": "review_only",
            "physical_changes": [],
            "next_action": "ask_user_once_before_any_move_or_delete",
        }
        if _race_hook is not None:
            _race_hook()
        if not directory_binding_matches(root, root_descriptor, root_identity):
            raise WorkspaceError("project root binding changed before plan write")
        plan_descriptor, plan_identity = open_or_create_private_plan_directory(
            root_descriptor
        )
        try:
            if _plan_dir_race_hook is not None:
                _plan_dir_race_hook()
            if not directory_binding_matches(root, root_descriptor, root_identity):
                raise WorkspaceError("project root binding changed during plan write")
            if not plan_directory_binding_matches(
                root_descriptor, plan_descriptor, plan_identity
            ):
                raise WorkspaceError("workspace plan directory binding changed before write")
            published_identity = atomic_write_json_at(
                plan_descriptor, "workspace-plan.json", plan
            )
            if (
                not directory_binding_matches(root, root_descriptor, root_identity)
                or not plan_directory_binding_matches(
                    root_descriptor, plan_descriptor, plan_identity
                )
            ):
                remove_owned_plan(
                    plan_descriptor, "workspace-plan.json", published_identity
                )
                raise WorkspaceError("workspace plan directory binding changed after write")
        finally:
            os.close(plan_descriptor)
    finally:
        os.close(root_descriptor)
    return root / ".dircreative" / "workspace-plan.json", plan


def human_summary(report: dict[str, Any]) -> str:
    gib = int(report["reclaimable_bytes"]) / (1024**3)
    return "\n".join(
        [
            "DIRCREATIVE_WORKSPACE_AUDIT: PASS",
            "READ_ONLY=1",
            f"FILES={report['files_scanned']}",
            f"LOOSE_ROOT_MATERIALS={report['loose_root_materials']}",
            f"UNORGANIZED_ROOT_ENTRIES={report['unorganized_root_entry_count']}",
            f"DUPLICATE_GROUPS={report['exact_duplicate_groups']}",
            f"DUPLICATE_COPIES={report['duplicate_copies']}",
            f"HARDLINKED_PATHS={report['hardlinked_paths']}",
            f"RECLAIMABLE_GIB={gib:.3f}",
            f"ORGANIZATION_OFFER={'recommended' if report['needs_organization'] else 'not_needed'}",
        ]
    )


def self_test() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="dircreative-workspace-") as raw:
        root = Path(raw)
        (root / "brief.pdf").write_bytes(b"same-large-source")
        (root / "project.yml").write_text("same-control\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("same-control\n", encoding="utf-8")
        (root / "AGENTS.override.md").write_text("same-control\n", encoding="utf-8")
        (root / ".gitignore").write_text(".dircreative/\n", encoding="utf-8")
        (root / "客户整包资料").mkdir()
        (root / "客户整包资料" / "notes.txt").write_text("facts\n", encoding="utf-8")
        source = root / "00_项目资料_ProjectMaterials"
        source.mkdir()
        nested_controls = source / "nested-controls"
        nested_controls.mkdir()
        (nested_controls / "project.yml").write_text("same-control\n", encoding="utf-8")
        second_controls = source / "nested-controls-two"
        second_controls.mkdir()
        (second_controls / "project.yml").write_text("same-control\n", encoding="utf-8")
        (source / "brief-copy.pdf").write_bytes(b"same-large-source")
        os.link(source / "brief-copy.pdf", source / "brief-hardlink.pdf")
        (source / "empty-a.txt").write_bytes(b"")
        (source / "empty-b.txt").write_bytes(b"")
        final = root / "05_最终交付_FinalDelivery"
        final.mkdir()
        (final / "brief-final.pdf").write_bytes(b"same-large-source")
        cache = root / "work" / "cache"
        cache.mkdir(parents=True)
        (cache / "preview.png").write_bytes(b"preview")

        report = scan_workspace(root)
        if report["loose_root_materials"] != 1:
            failures.append("loose root material was not detected")
        if report["unorganized_root_entry_count"] != 3:
            failures.append("loose root file or directory was not detected")
        for control_file in ("project.yml", "AGENTS.md", "AGENTS.override.md", ".gitignore"):
            if control_file in report["unorganized_root_entries"]:
                failures.append(f"project control file was misclassified as material: {control_file}")
        if report["exact_duplicate_groups"] != 1 or report["duplicate_copies"] != 3:
            failures.append("exact duplicate group was not detected")
        group = report["duplicate_groups"][0]
        if group["canonical_candidate"] != "00_项目资料_ProjectMaterials/brief-copy.pdf":
            failures.append("source material was not preferred as canonical candidate")
        if group["requires_manual_review"] is not True:
            failures.append("protected delivery duplicate did not require manual review")
        if group["hardlinked_paths"] != 1:
            failures.append("hardlinked duplicate path was counted as reclaimable bytes")
        if group["reclaimable_bytes"] != len(b"same-large-source") * 2:
            failures.append("physical reclaimable bytes did not exclude the hardlink")
        if any(int(item["size_bytes"]) == 0 for item in report["duplicate_groups"]):
            failures.append("zero-byte files were counted as reclaimable duplicates")
        if any(
            item["category"] == "project_control"
            for duplicate in report["duplicate_groups"]
            for item in duplicate["files"]
        ):
            failures.append("project control files were counted as reclaimable duplicates")
        if classify(nested_controls / "project.yml", root) != "project_control":
            failures.append("nested project.yml was not classified as project control")
        for protected_name in ("finaldelivery", "FINALDELIVERY", "05_FinalDelivery_v2"):
            if classify(root / protected_name / "delivery.pdf", root) != "protected_delivery":
                failures.append(f"FinalDelivery variant was not protected: {protected_name}")

        first_path, _ = write_plan(root)
        second_path, _ = write_plan(root)
        if first_path != second_path or not first_path.is_file():
            failures.append("replace-current workspace plan was not stable")
        if len(list((root / ".dircreative").glob("workspace-plan*.json"))) != 1:
            failures.append("workspace plan accumulated versions")
        if str(root).encode() in first_path.read_bytes():
            failures.append("workspace plan persisted a private absolute project path")

    with tempfile.TemporaryDirectory(prefix="dircreative-workspace-swap-") as raw:
        base = Path(raw)
        authorized = base / "authorized"
        authorized.mkdir()
        (authorized / "brief.txt").write_text("brief\n", encoding="utf-8")
        original = base / "authorized-original"
        victim = base / "victim"
        victim.mkdir()

        def swap_root() -> None:
            authorized.rename(original)
            authorized.symlink_to(victim, target_is_directory=True)

        try:
            write_plan(authorized, _race_hook=swap_root)
            failures.append("workspace plan accepted a swapped project root")
        except WorkspaceError:
            pass
        if (victim / ".dircreative" / "workspace-plan.json").exists():
            failures.append("workspace plan escaped into a symlink-swapped directory")

    with tempfile.TemporaryDirectory(prefix="dircreative-plan-dir-swap-") as raw:
        base = Path(raw)
        authorized = base / "authorized"
        authorized.mkdir()
        (authorized / "brief.txt").write_text("brief\n", encoding="utf-8")
        escaped = base / "escaped-dircreative"

        def swap_plan_directory() -> None:
            (authorized / ".dircreative").rename(escaped)
            (authorized / ".dircreative").mkdir()

        try:
            write_plan(authorized, _plan_dir_race_hook=swap_plan_directory)
            failures.append("workspace plan accepted a swapped plan directory")
        except WorkspaceError:
            pass
        if (escaped / "workspace-plan.json").exists():
            failures.append("workspace plan was written into a moved-out plan directory")
        if (authorized / ".dircreative" / "workspace-plan.json").exists():
            failures.append("workspace plan was written after plan directory substitution")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only DIRcreative project storage audit.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("project")
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--max-groups", type=int, default=50)
    plan = subparsers.add_parser("plan")
    plan.add_argument("project")
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--max-groups", type=int, default=50)
    subparsers.add_parser("self-test")
    args = parser.parse_args()

    if args.command == "self-test":
        failures = self_test()
        print(f"DIRCREATIVE_WORKSPACE_SELF_TEST: {'PASS' if not failures else 'FAIL'}")
        for failure in failures:
            print(f"- {failure}")
        return 0 if not failures else 1

    try:
        if args.command == "plan":
            output, report = write_plan(args.project, max_groups=args.max_groups)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(human_summary(report))
                print(f"PLAN={output}")
            return 0
        report = scan_workspace(args.project, max_groups=args.max_groups)
    except (OSError, WorkspaceError) as exc:
        print("DIRCREATIVE_WORKSPACE_AUDIT: FAIL")
        print(f"- {exc}")
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(human_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
