#!/usr/bin/env python3
"""Explicitly check or install Jingzao from an official public GitHub tag.

This command is intentionally separate from DIRcreative runtime.  It downloads
an archive only for an explicit ``sync`` invocation, never executes content
from that archive, and hands its verified local staging directory to the
dependency-bundle installer.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import dircreative_dependency_bundle as bundles


REPOSITORY = "papperrollinggery/jingzao-image-forge"
SKILL_ID = "jingzao-image-forge"
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


class JingzaoUpdateError(ValueError):
    pass


def _compare_tag(left: str, right: str) -> int:
    a, b = TAG_RE.fullmatch(left), TAG_RE.fullmatch(right)
    if a is None or b is None:
        raise JingzaoUpdateError("official_tag_invalid")
    av, bv = tuple(map(int, a.groups())), tuple(map(int, b.groups()))
    return (av > bv) - (av < bv)


def latest_stable_tag(*, runner: Callable[..., Any] = subprocess.run,
                      opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, str]:
    """Resolve GitHub's latest published stable release to its exact commit."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "DIRcreative-dependency-updater"},
    )
    try:
        release = json.loads(_download(request, opener=opener))
    except (ValueError, UnicodeDecodeError) as exc:
        raise JingzaoUpdateError("official_release_invalid") from exc
    if (not isinstance(release, dict) or release.get("draft") is not False
            or release.get("prerelease") is not False
            or not isinstance(release.get("tag_name"), str)
            or not TAG_RE.fullmatch(release["tag_name"])):
        raise JingzaoUpdateError("official_stable_release_invalid")
    tag = release["tag_name"]
    ref = f"refs/tags/{tag}"
    try:
        result = runner(
            ["git", "ls-remote", "--tags", f"https://github.com/{REPOSITORY}.git", ref, ref + "^{}"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise JingzaoUpdateError("official_tag_lookup_failed") from exc
    if result.returncode != 0:
        raise JingzaoUpdateError("official_tag_lookup_failed")
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2 or parts[1] not in (ref, ref + "^{}"):
            continue
        if not re.fullmatch(r"[0-9a-f]{40}", parts[0]) or parts[1] in refs:
            raise JingzaoUpdateError("official_tag_revision_invalid")
        refs[parts[1]] = parts[0]
    if ref not in refs:
        raise JingzaoUpdateError("official_release_tag_missing")
    return {"repository": REPOSITORY, "tag": tag,
            "revision": refs.get(ref + "^{}", refs[ref])}


def _download(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen) -> bytes:
    try:
        with opener(url, timeout=30) as response:
            data = response.read()
    except OSError as exc:
        raise JingzaoUpdateError("official_archive_download_failed") from exc
    if not data:
        raise JingzaoUpdateError("official_archive_empty")
    return data


def _safe_extract(archive: bytes, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
                    raise JingzaoUpdateError("official_archive_path_unsafe")
                if member.issym() or member.islnk() or member.isdev():
                    raise JingzaoUpdateError("official_archive_link_or_device")
                if not (member.isdir() or member.isfile()):
                    raise JingzaoUpdateError("official_archive_entry_invalid")
            # Extract only prevalidated regular files and directories; compatible
            # with every supported Python 3.10 patch version.
            for member in members:
                output = destination.joinpath(*PurePosixPath(member.name).parts)
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    handle = tar.extractfile(member)
                    if handle is None:
                        raise JingzaoUpdateError("official_archive_file_missing")
                    with handle, output.open("xb") as writer:
                        shutil.copyfileobj(handle, writer)
                    output.chmod(0o755 if member.mode & 0o111 else 0o644)
    except (tarfile.TarError, OSError) as exc:
        raise JingzaoUpdateError("official_archive_invalid") from exc
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1 or not (roots[0] / "SKILL.md").is_file():
        raise JingzaoUpdateError("official_archive_skill_root_invalid")
    return roots[0]


def _manifest_for_tree(source: Path, tag: str, destination: Path) -> Path:
    files: list[dict[str, Any]] = []
    for path in sorted(source.rglob("*")):
        details = path.lstat()
        if stat.S_ISLNK(details.st_mode):
            raise JingzaoUpdateError("official_archive_symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            raise JingzaoUpdateError("official_archive_entry_invalid")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": path.relative_to(source).as_posix(), "sha256": digest,
                      "executable": bool(details.st_mode & stat.S_IXUSR)})
    if not files:
        raise JingzaoUpdateError("official_archive_empty")
    source_parent = destination / "bundle-source"
    if source_parent.exists():
        shutil.rmtree(source_parent)
    shutil.copytree(source, source_parent)
    manifest = {"schema_version": 1, "bundle_id": "dircreative-jingzao-official",
                "skills": [{"skill_id": SKILL_ID, "version": tag.removeprefix("v"),
                            "source": {"directory": "bundle-source", "reference": f"GitHub {REPOSITORY} {tag}"},
                            "relative_directory": SKILL_ID, "files": files}]}
    path = destination / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _local_state(skills_root: Path) -> dict[str, Any]:
    target = skills_root / SKILL_ID
    if not target.exists() and not target.is_symlink():
        return {"status": "missing"}
    if target.is_symlink() or not target.is_dir():
        return {"status": "conflict", "reason": "target_not_real_directory"}
    control = skills_root / bundles.CONTROL_DIRECTORY
    try:
        if control.exists() or control.is_symlink():
            bundles._directory(control, "control_directory")
            bundles._directory(control / "receipts", "receipt_directory")
        document = bundles._read_receipt(control, {"skill_id": SKILL_ID})
        if document is None:
            return {"status": "preserved", "reason": "unmanaged_or_local_install"}
        if document["bundle_id"] != "dircreative-jingzao-official" or document["relative_directory"] != SKILL_ID:
            return {"status": "conflict", "reason": "receipt_does_not_own_target"}
        if not bundles._matches(target, document):
            return {"status": "conflict", "reason": "local_edits_or_unexpected_files"}
    except (OSError, bundles.BundleError):
        return {"status": "conflict", "reason": "receipt_invalid"}
    return {"status": "managed", "version": document["version"], "bundle_id": document["bundle_id"]}


def check_jingzao(skills_root: Path | str, *, runner: Callable[..., Any] = subprocess.run,
                  opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    root = Path(skills_root)
    try:
        official = latest_stable_tag(runner=runner, opener=opener)
    except JingzaoUpdateError as exc:
        return {"status": "blocked", "error": str(exc), "local": _local_state(root)}
    return {"status": "ok", "official": official, "local": _local_state(root)}


def sync_jingzao(skills_root: Path | str, *, runner: Callable[..., Any] = subprocess.run,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    root = Path(skills_root)
    try:
        official = latest_stable_tag(runner=runner, opener=opener)
        archive = _download(f"https://github.com/{REPOSITORY}/archive/{official['revision']}.tar.gz", opener=opener)
        with tempfile.TemporaryDirectory(prefix="dircreative-jingzao-") as raw:
            extracted = _safe_extract(archive, Path(raw) / "extract")
            manifest = _manifest_for_tree(extracted, official["tag"], Path(raw))
            installed = bundles.install_bundle(manifest, root, source_root=Path(raw))
    except (JingzaoUpdateError, OSError, bundles.BundleError) as exc:
        return {"status": "blocked", "error": str(exc), "local": _local_state(root)}
    return {"status": installed["status"], "official": official, "local": _local_state(root), "install": installed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "sync"))
    parser.add_argument("--skills-root", required=True, type=Path)
    args = parser.parse_args()
    result = check_jingzao(args.skills_root) if args.command == "check" else sync_jingzao(args.skills_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else (1 if result["status"] == "blocked" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
