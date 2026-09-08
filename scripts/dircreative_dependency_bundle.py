#!/usr/bin/env python3
"""Install a verified, local Skill dependency bundle without running providers.

The manifest is JSON.  Each skill declares a source directory relative to the
manifest (or ``--source-root``), a destination ``relative_directory``, and the
complete set of regular files that may be installed.  For example::

  {"schema_version": 1, "bundle_id": "example", "skills": [{
    "skill_id": "example-skill", "version": "1.0.0",
    "source": {"directory": "bundle/example-skill", "reference": "local"},
    "relative_directory": "example-skill",
    "files": [{"path": "SKILL.md", "sha256": "...", "executable": false}]
  }]}

Receipts are kept under the supplied skills root, never inside a Skill.  This
module deliberately has no network, provider, scheduler, or credential code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable


SCHEMA_VERSION = 1
CONTROL_DIRECTORY = ".dircreative-dependency-bundles"
RECEIPT_VERSION = 1
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class BundleError(ValueError):
    """Raised when a bundle manifest or its local source is unsafe or invalid."""


def _safe_relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BundleError(f"{label}_invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise BundleError(f"{label}_unsafe")
    if "\\" in value:
        raise BundleError(f"{label}_unsafe")
    return path.as_posix()


def _require_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise BundleError(f"{label}_invalid")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _regular(path: Path, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except FileNotFoundError as exc:
        raise BundleError(f"{label}_missing") from exc
    if stat.S_ISLNK(details.st_mode):
        raise BundleError(f"{label}_symlink")
    if not stat.S_ISREG(details.st_mode):
        raise BundleError(f"{label}_not_regular")
    return details


def _directory(path: Path, label: str, *, create: bool = False) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    try:
        details = path.lstat()
    except FileNotFoundError as exc:
        raise BundleError(f"{label}_missing") from exc
    if stat.S_ISLNK(details.st_mode):
        raise BundleError(f"{label}_symlink")
    if not stat.S_ISDIR(details.st_mode):
        raise BundleError(f"{label}_not_directory")


def _child(root: Path, relative: str, label: str) -> Path:
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        # An absent leaf is handled by the caller; every existing parent must be real.
        if current.exists() or current.is_symlink():
            details = current.lstat()
            if stat.S_ISLNK(details.st_mode):
                raise BundleError(f"{label}_symlink")
    return current


def _source_directory(entry: dict[str, Any]) -> str:
    source = entry.get("source")
    if isinstance(source, str):
        return _safe_relative(source, "source_directory")
    if isinstance(source, dict):
        return _safe_relative(source.get("directory"), "source_directory")
    return _safe_relative(entry.get("source_directory"), "source_directory")


def _overlaps(left: str, right: str) -> bool:
    left_parts = PurePosixPath(left).parts
    right_parts = PurePosixPath(right).parts
    return left_parts[:len(right_parts)] == right_parts or right_parts[:len(left_parts)] == left_parts


def _semver(value: str) -> tuple[int, int, int, tuple[tuple[int, int | str], ...] | None] | None:
    match = SEMVER_RE.fullmatch(value)
    if not match:
        return None
    prerelease = match.group(4)
    if prerelease is None:
        parts = None
    else:
        parsed: list[tuple[int, int | str]] = []
        for part in prerelease.split("."):
            if part.isdigit():
                if len(part) > 1 and part.startswith("0"):
                    return None
                parsed.append((0, int(part)))
            else:
                parsed.append((1, part))
        parts = tuple(parsed)
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), parts


def _compare_semver(left: str, right: str) -> int | None:
    """Return comparison of two standard SemVer versions, or None if either is unknown."""
    first, second = _semver(left), _semver(right)
    if first is None or second is None:
        return None
    if first[:3] != second[:3]:
        return 1 if first[:3] > second[:3] else -1
    if first[3] is None or second[3] is None:
        if first[3] is second[3]:
            return 0
        return 1 if first[3] is None else -1
    for a, b in zip(first[3], second[3]):
        if a == b:
            continue
        if a[0] != b[0]:
            return -1 if a[0] == 0 else 1
        return 1 if a[1] > b[1] else -1
    if len(first[3]) == len(second[3]):
        return 0
    return 1 if len(first[3]) > len(second[3]) else -1


def load_manifest(manifest_path: Path | str) -> dict[str, Any]:
    """Read and normalize a manifest, rejecting unsafe paths before installation."""
    path = Path(manifest_path)
    _regular(path, "manifest")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError("manifest_invalid") from exc
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise BundleError("manifest_schema_invalid")
    bundle_id = _require_identifier(document.get("bundle_id"), "bundle_id")
    raw_skills = document.get("skills")
    if not isinstance(raw_skills, list) or not raw_skills:
        raise BundleError("skills_invalid")
    skills: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_destinations: set[str] = set()
    for raw in raw_skills:
        if not isinstance(raw, dict):
            raise BundleError("skill_invalid")
        skill_id = _require_identifier(raw.get("skill_id"), "skill_id")
        if skill_id in seen_ids:
            raise BundleError("skill_id_duplicate")
        seen_ids.add(skill_id)
        version = raw.get("version")
        if not isinstance(version, str) or not version:
            raise BundleError("version_invalid")
        destination = _safe_relative(raw.get("relative_directory"), "relative_directory")
        if _overlaps(destination, CONTROL_DIRECTORY):
            raise BundleError("relative_directory_reserved")
        if destination != skill_id:
            raise BundleError("skill_id_relative_directory_mismatch")
        if destination in seen_destinations:
            raise BundleError("relative_directory_duplicate")
        if any(_overlaps(destination, existing) for existing in seen_destinations):
            raise BundleError("relative_directory_overlap")
        seen_destinations.add(destination)
        source_directory = _source_directory(raw)
        files = raw.get("files")
        if not isinstance(files, list) or not files:
            raise BundleError("files_invalid")
        normalized_files: list[dict[str, Any]] = []
        seen_files: set[str] = set()
        for file in files:
            if not isinstance(file, dict):
                raise BundleError("file_invalid")
            relative = _safe_relative(file.get("path"), "file_path")
            digest = file.get("sha256")
            if relative in seen_files or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                raise BundleError("file_invalid")
            if not isinstance(file.get("executable"), bool):
                raise BundleError("file_executable_invalid")
            seen_files.add(relative)
            normalized = {"path": relative, "sha256": digest, "executable": file["executable"]}
            if "source_path" in file:
                normalized["source_path"] = _safe_relative(file["source_path"], "source_path")
            normalized_files.append(normalized)
        skills.append({
            "skill_id": skill_id, "version": version, "source_directory": source_directory,
            "relative_directory": destination, "files": sorted(normalized_files, key=lambda item: item["path"]),
        })
    return {"schema_version": SCHEMA_VERSION, "bundle_id": bundle_id, "skills": skills}


def _verify_source(entry: dict[str, Any], source_root: Path) -> None:
    _directory(source_root, "source_root")
    source = _child(source_root, entry["source_directory"], "source_directory")
    _directory(source, "source_directory")
    for item in entry["files"]:
        candidate = _child(source, item.get("source_path", item["path"]), "source_file")
        details = _regular(candidate, "source_file")
        if _sha256(candidate) != item["sha256"]:
            raise BundleError(f"source_hash_mismatch:{entry['skill_id']}:{item['path']}")
        if bool(details.st_mode & stat.S_IXUSR) != item["executable"]:
            raise BundleError(f"source_executable_mismatch:{entry['skill_id']}:{item['path']}")


def _receipt_path(control: Path, skill_id: str) -> Path:
    return control / "receipts" / f"{skill_id}.json"


def _receipt(entry: dict[str, Any], bundle_id: str) -> dict[str, Any]:
    return {"receipt_version": RECEIPT_VERSION, "bundle_id": bundle_id, **entry}


def _read_receipt(control: Path, entry: dict[str, Any]) -> dict[str, Any] | None:
    path = _receipt_path(control, entry["skill_id"])
    if not path.exists() and not path.is_symlink():
        return None
    _regular(path, "receipt")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise BundleError("receipt_invalid")
    if not isinstance(receipt, dict) or receipt.get("receipt_version") != RECEIPT_VERSION:
        raise BundleError("receipt_invalid")
    required = ("bundle_id", "skill_id", "version", "source_directory", "relative_directory", "files")
    if any(key not in receipt for key in required) or receipt["skill_id"] != entry["skill_id"]:
        raise BundleError("receipt_invalid")
    try:
        # Validate receipt with the same structural rules, without requiring a source tree.
        validated = load_manifest_data({"schema_version": SCHEMA_VERSION, "bundle_id": receipt["bundle_id"], "skills": [receipt]})
    except BundleError as exc:
        raise BundleError("receipt_invalid") from exc
    return {"receipt_version": RECEIPT_VERSION, "bundle_id": validated["bundle_id"], **validated["skills"][0]}


def load_manifest_data(document: dict[str, Any]) -> dict[str, Any]:
    """Validate already-loaded data; primarily useful for receipt validation."""
    with tempfile.TemporaryDirectory(prefix="dircreative-bundle-manifest-") as raw:
        path = Path(raw) / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return load_manifest(path)


def _inventory(directory: Path) -> list[dict[str, Any]]:
    _directory(directory, "installed_directory")
    files: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        details = path.lstat()
        if stat.S_ISLNK(details.st_mode):
            raise BundleError("installed_directory_symlink")
        if stat.S_ISDIR(details.st_mode):
            continue
        if not stat.S_ISREG(details.st_mode):
            raise BundleError("installed_directory_unexpected_file")
        files.append({"path": relative, "sha256": _sha256(path), "executable": bool(details.st_mode & stat.S_IXUSR)})
    return sorted(files, key=lambda item: item["path"])


def _matches(directory: Path, receipt: dict[str, Any]) -> bool:
    try:
        return _inventory(directory) == [{key: file[key] for key in ("path", "sha256", "executable")} for file in receipt["files"]]
    except BundleError:
        return False


def _prepare_root(skills_root: Path) -> Path:
    _directory(skills_root, "skills_root", create=True)
    control = skills_root / CONTROL_DIRECTORY
    _directory(control, "control_directory", create=True)
    _directory(control / "receipts", "receipt_directory", create=True)
    return control


def _state(entry: dict[str, Any], bundle_id: str, skills_root: Path, control: Path) -> tuple[str, str | None, dict[str, Any] | None]:
    try:
        target = _child(skills_root, entry["relative_directory"], "target_directory")
    except BundleError as exc:
        return "conflict", str(exc), None
    if not target.exists() and not target.is_symlink():
        return "install", None, None
    try:
        _directory(target, "target_directory")
    except BundleError:
        return "conflict", "target_not_directory_or_symlink", None
    try:
        old = _read_receipt(control, entry)
    except BundleError:
        return "conflict", "receipt_invalid", None
    if old is None:
        return "preserved", "unmanaged_existing_directory", None
    if old["bundle_id"] != bundle_id or old["relative_directory"] != entry["relative_directory"]:
        return "conflict", "receipt_does_not_own_target", old
    if not _matches(target, old):
        return "conflict", "local_edits_or_unexpected_files", old
    if old == _receipt(entry, bundle_id):
        return "up_to_date", None, old
    comparison = _compare_semver(old["version"], entry["version"])
    if comparison is None:
        return "preserved", "unknown_version_order", old
    if comparison > 0:
        return "preserved", "managed_newer_version", old
    return "update", None, old


def _stage(entry: dict[str, Any], source_root: Path, stage_root: Path) -> Path:
    staged = stage_root / entry["skill_id"]
    staged.mkdir()
    source = source_root / entry["source_directory"]
    for item in entry["files"]:
        source_file = _child(source, item.get("source_path", item["path"]), "source_file")
        details = _regular(source_file, "source_file")
        if _sha256(source_file) != item["sha256"]:
            raise BundleError(f"source_hash_mismatch:{entry['skill_id']}:{item['path']}")
        if bool(details.st_mode & stat.S_IXUSR) != item["executable"]:
            raise BundleError(f"source_executable_mismatch:{entry['skill_id']}:{item['path']}")
        destination = staged / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, destination)
        destination.chmod(0o755 if item["executable"] else 0o644)
        if _sha256(destination) != item["sha256"]:
            raise BundleError(f"staged_hash_mismatch:{entry['skill_id']}:{item['path']}")
    return staged


def _write_receipt(control: Path, entry: dict[str, Any], bundle_id: str, replace: Callable[[str | bytes | os.PathLike[str] | os.PathLike[bytes], str | bytes | os.PathLike[str] | os.PathLike[bytes]], Any]) -> None:
    destination = _receipt_path(control, entry["skill_id"])
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, prefix=".receipt-", delete=False) as handle:
        temp = Path(handle.name)
        json.dump(_receipt(entry, bundle_id), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    try:
        replace(temp, destination)
    finally:
        if temp.exists() or temp.is_symlink():
            temp.unlink()


def _remove_published_directory(path: Path) -> None:
    """Remove only a directory this transaction has already published."""
    details = path.lstat()
    if not stat.S_ISDIR(details.st_mode) or stat.S_ISLNK(details.st_mode):
        raise BundleError("published_target_invalid")
    shutil.rmtree(path)


def _replace_one(staged: Path, target: Path, old: dict[str, Any] | None, control: Path, entry: dict[str, Any], bundle_id: str, replace: Callable[..., Any]) -> None:
    backup = target.with_name(f".{target.name}.bundle-backup-{next(tempfile._get_candidate_names())}")
    moved_old = False
    published_new = False
    try:
        if old is not None:
            if _read_receipt(control, entry) != old or not _matches(target, old):
                raise BundleError("target_changed_before_update")
            replace(target, backup)
            moved_old = True
            if not _matches(backup, old):
                raise BundleError("target_changed_during_update")
        elif target.exists() or target.is_symlink():
            raise BundleError("target_appeared_before_install")
        replace(staged, target)
        published_new = True
        _write_receipt(control, entry, bundle_id, replace)
    except Exception:
        if published_new and (target.exists() or target.is_symlink()):
            _remove_published_directory(target)
        if moved_old and backup.exists():
            replace(backup, target)
        raise
    else:
        if moved_old and backup.exists():
            shutil.rmtree(backup)


def _report(kind: str, entry: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
    result = {"skill_id": entry["skill_id"], "version": entry["version"], "status": kind}
    if reason:
        result["reason"] = reason
    return result


def _blocked(error: Exception) -> dict[str, Any]:
    reason = str(error) if isinstance(error, BundleError) else f"internal_error:{type(error).__name__}"
    return {"status": "blocked", "error": reason, "skills": []}


def install_bundle(manifest_path: Path | str, skills_root: Path | str, *, source_root: Path | str | None = None, replace: Callable[..., Any] = os.replace) -> dict[str, Any]:
    """Install only verified local content and return a per-skill JSON-safe report."""
    try:
        manifest_file = Path(manifest_path)
        manifest = load_manifest(manifest_file)
        source = Path(source_root) if source_root is not None else manifest_file.parent
        for entry in manifest["skills"]:
            _verify_source(entry, source)
        root = Path(skills_root)
        control = _prepare_root(root)
    except Exception as exc:
        return _blocked(exc)

    plan: list[tuple[dict[str, Any], str, dict[str, Any] | None]] = []
    report: list[dict[str, Any]] = []
    for entry in manifest["skills"]:
        try:
            kind, reason, old = _state(entry, manifest["bundle_id"], root, control)
        except Exception as exc:
            report.append(_report("conflict", entry, f"state_failed:{type(exc).__name__}"))
            continue
        if kind in ("up_to_date", "preserved", "conflict"):
            report.append(_report(kind, entry, reason))
        else:
            plan.append((entry, kind, old))

    if plan:
        try:
            with tempfile.TemporaryDirectory(prefix="staging-", dir=control) as raw:
                stage_root = Path(raw)
                staged = {entry["skill_id"]: _stage(entry, source, stage_root) for entry, _, _ in plan}
                for entry, kind, old in plan:
                    target = root / entry["relative_directory"]
                    try:
                        _replace_one(staged[entry["skill_id"]], target, old, control, entry, manifest["bundle_id"], replace)
                        report.append(_report("installed", entry))
                    except Exception as exc:  # rollback is performed inside _replace_one
                        report.append(_report("conflict", entry, f"replacement_failed:{type(exc).__name__}"))
        except Exception as exc:
            return {"status": "blocked", "error": f"staging_failed:{type(exc).__name__}", "skills": report}

    report.sort(key=lambda row: row["skill_id"])
    status = "ok" if all(row["status"] in ("installed", "up_to_date") for row in report) else "attention"
    return {"status": status, "bundle_id": manifest["bundle_id"], "skills": report}


def check_bundle(manifest_path: Path | str, skills_root: Path | str, *, source_root: Path | str | None = None) -> dict[str, Any]:
    """Validate a local bundle and report whether its requested snapshot is installed."""
    try:
        manifest_file = Path(manifest_path)
        manifest = load_manifest(manifest_file)
        source = Path(source_root) if source_root is not None else manifest_file.parent
        for entry in manifest["skills"]:
            _verify_source(entry, source)
        root = Path(skills_root)
        if root.exists() or root.is_symlink():
            _directory(root, "skills_root")
        control = root / CONTROL_DIRECTORY
        if control.exists() or control.is_symlink():
            _directory(control, "control_directory")
            receipts = control / "receipts"
            if receipts.exists() or receipts.is_symlink():
                _directory(receipts, "receipt_directory")
    except Exception as exc:
        return _blocked(exc)
    report: list[dict[str, Any]] = []
    for entry in manifest["skills"]:
        try:
            kind, reason, _ = _state(entry, manifest["bundle_id"], root, control)
        except Exception as exc:
            report.append(_report("conflict", entry, f"state_failed:{type(exc).__name__}"))
            continue
        if kind == "install":
            report.append(_report("missing", entry, "not_installed"))
        elif kind == "update":
            report.append(_report("conflict", entry, "managed_snapshot_differs"))
        else:
            report.append(_report(kind, entry, reason))
    report.sort(key=lambda row: row["skill_id"])
    status = "ok" if all(row["status"] == "up_to_date" for row in report) else "attention"
    return {"status": status, "bundle_id": manifest["bundle_id"], "skills": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "check"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--skills-root", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    result = (install_bundle if args.command == "install" else check_bundle)(
        args.manifest, args.skills_root, source_root=args.source_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else (1 if result["status"] == "blocked" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
