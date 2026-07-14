#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from dircreative_package_layout import HOST_USER_PATH_RE, THREAD_ID_RE
from dircreative_release_preflight import EXPECTED_ORIGIN_SLUG, github_slug


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MEMBERS = {
    "SKILL.md",
    "VERSION",
    "CHANGELOG.md",
    "RELEASE-METADATA.json",
    "scripts/validate_project.py",
}


@dataclass(frozen=True)
class ArchiveLimits:
    max_archive_bytes: int = 64 * 1024 * 1024
    max_checksum_bytes: int = 64 * 1024
    max_members: int = 4096
    max_member_bytes: int = 32 * 1024 * 1024
    max_total_file_bytes: int = 256 * 1024 * 1024
    max_tar_stream_bytes: int = 320 * 1024 * 1024
    max_member_path_bytes: int = 1024


DEFAULT_LIMITS = ArchiveLimits()
COPY_CHUNK_BYTES = 1024 * 1024
WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_head() -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_at(source: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=source,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or f"git {' '.join(args)} failed in reproducible source")
    return proc.stdout.strip()


def verify_canonical_remote_tag(source: Path, tag: str, expected_commit: str) -> None:
    tag_ref = f"refs/tags/{tag}"
    peeled_ref = f"{tag_ref}^{{}}"
    output = git_at(source, "ls-remote", "--exit-code", "origin", tag_ref, peeled_ref)
    refs = {
        ref: sha
        for line in output.splitlines()
        if len((parts := line.split())) == 2
        for sha, ref in [parts]
    }
    if tag_ref not in refs or peeled_ref not in refs:
        raise ValueError(f"canonical remote tag must be annotated and peelable: {tag}")
    if refs[peeled_ref] != expected_commit:
        raise ValueError(f"canonical remote tag {tag} does not equal expected commit")


def reject_hidden_index_state(source: Path) -> None:
    flagged = [
        line
        for line in git_at(source, "ls-files", "-v").splitlines()
        if line and line[0] != "H"
    ]
    if flagged:
        raise ValueError("reproducible source contains assume-unchanged, skip-worktree, or nonstandard index flags")
    sparse = subprocess.run(
        ["git", "config", "--bool", "core.sparseCheckout"],
        cwd=source,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if sparse.returncode == 0 and sparse.stdout.strip().lower() == "true":
        raise ValueError("reproducible source must not use sparse checkout")


def verify_reproducible_build(
    source: Path,
    artifact: Path,
    *,
    version: str,
    expected_commit: str,
    expected_hash: str,
    expected_tag: str | None,
    require_remote_tag: bool,
) -> None:
    if not source.is_dir():
        raise ValueError(f"reproducible source is not a directory: {source}")
    source_head = git_at(source, "rev-parse", "HEAD")
    if source_head != expected_commit:
        raise ValueError("reproducible source HEAD does not equal expected commit")
    if git_at(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("reproducible source worktree is not clean")
    reject_hidden_index_state(source)
    origin_url = git_at(source, "remote", "get-url", "origin")
    origin_push_url = git_at(source, "remote", "get-url", "--push", "origin")
    if github_slug(origin_url) != EXPECTED_ORIGIN_SLUG:
        raise ValueError("reproducible source origin is not the canonical DIRcreative repository")
    if github_slug(origin_push_url) != EXPECTED_ORIGIN_SLUG:
        raise ValueError("reproducible source push URL is not the canonical DIRcreative repository")
    if require_remote_tag:
        if not expected_tag:
            raise ValueError("canonical remote tag verification requires an expected tag")
        verify_canonical_remote_tag(source, expected_tag, expected_commit)
    with tempfile.TemporaryDirectory(prefix="dircreative-reproducible-build-") as raw:
        sealed_source = Path(raw) / "source"
        clone = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--no-checkout",
                str(source),
                str(sealed_source),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if clone.returncode != 0:
            raise ValueError("cannot create sealed exact-commit rebuild source: " + clone.stderr.strip())
        git_at(sealed_source, "checkout", "--quiet", "--detach", expected_commit)
        if git_at(sealed_source, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("sealed exact-commit rebuild source is not clean")
        builder = sealed_source / "scripts" / "dircreative_build_release.py"
        if not builder.is_file():
            raise ValueError("sealed exact-commit source is missing the release builder")
        output_dir = Path(raw) / "dist"
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [
                sys.executable,
                str(builder),
                "--allow-unpublished",
                "--output-dir",
                str(output_dir),
            ],
            cwd=sealed_source,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise ValueError(
                "reproducible source build failed: "
                + (proc.stderr.strip() or proc.stdout.strip())
            )
        rebuilt = output_dir / f"dircreative-{version}.tar.gz"
        if not rebuilt.is_file():
            raise ValueError("reproducible source build did not create the expected artifact")
        rebuilt_hash = sha256_file(rebuilt)
        if rebuilt_hash != expected_hash or rebuilt.name != artifact.name:
            raise ValueError("release artifact does not match the reproducible exact-commit build")


def checksum_for(checksum_bytes: bytes, artifact_name: str) -> str:
    matches: list[str] = []
    for raw_line in checksum_bytes.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", line)
        if match and Path(match.group(2)).name == artifact_name:
            matches.append(match.group(1).lower())
    if len(matches) != 1:
        raise ValueError(f"SHA256SUMS must contain exactly one entry for {artifact_name}")
    return matches[0]


def copy_regular_file_once(
    path: Path,
    destination: io.BufferedRandom,
    *,
    max_bytes: int,
    label: str,
) -> tuple[str, int]:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"cannot open {label}: {path}: {exc}") from exc
    digest = hashlib.sha256()
    total = 0
    with os.fdopen(descriptor, "rb", closefd=True) as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file")
        if before.st_nlink != 1:
            raise ValueError(f"{label} must not be hardlinked")
        if before.st_size > max_bytes:
            raise ValueError(f"{label} exceeds size limit ({max_bytes})")
        while True:
            chunk = source.read(COPY_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"{label} exceeds size limit ({max_bytes})")
            digest.update(chunk)
            destination.write(chunk)
        after = os.fstat(source.fileno())
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    if identity_before != identity_after or total != before.st_size:
        raise ValueError(f"{label} changed while it was being sealed")
    destination.flush()
    destination.seek(0)
    return digest.hexdigest(), total


def read_regular_file_once(path: Path, *, max_bytes: int, label: str) -> bytes:
    with tempfile.TemporaryFile(mode="w+b") as sealed:
        copy_regular_file_once(path, sealed, max_bytes=max_bytes, label=label)
        return sealed.read()


def validated_members(
    tar: tarfile.TarFile,
    expected_version: str | None,
    limits: ArchiveLimits,
) -> tuple[str, str, dict[str, tarfile.TarInfo]]:
    members: dict[str, tarfile.TarInfo] = {}
    seen_paths: set[str] = set()
    seen_casefold_paths: dict[str, str] = {}
    roots: set[str] = set()
    member_count = 0
    total_file_bytes = 0
    for member in tar:
        member_count += 1
        if member_count > limits.max_members:
            raise ValueError(f"release artifact exceeds member count limit ({limits.max_members})")
        if len(member.name.encode("utf-8")) > limits.max_member_path_bytes:
            raise ValueError(f"release member path exceeds size limit: {member.name}")
        if "\\" in member.name or "\x00" in member.name:
            raise ValueError(f"unsafe release member path syntax: {member.name}")
        if tar.pax_headers or member.pax_headers or member.offset_data != member.offset + tarfile.BLOCKSIZE:
            raise ValueError(f"release member uses forbidden extended metadata: {member.name}")
        if getattr(member, "sparse", None):
            raise ValueError(f"release member uses forbidden sparse metadata: {member.name}")
        posix = PurePosixPath(member.name)
        if posix.is_absolute() or ".." in posix.parts or not posix.parts:
            raise ValueError(f"unsafe release member path: {member.name}")
        if any(":" in part or part.endswith((".", " ")) for part in posix.parts):
            raise ValueError(f"unsafe cross-platform release member path: {member.name}")
        normalized = posix.as_posix()
        if normalized in seen_paths:
            raise ValueError(f"duplicate release member: {normalized}")
        seen_paths.add(normalized)
        portable_parts: list[str] = []
        for part in posix.parts:
            portable = unicodedata.normalize("NFC", part).casefold().rstrip(". ")
            base_name = portable.split(".", 1)[0]
            if not portable or base_name in WINDOWS_RESERVED_NAMES:
                raise ValueError(f"release member uses a reserved cross-platform path: {member.name}")
            portable_parts.append(portable)
        folded = "/".join(portable_parts)
        if folded in seen_casefold_paths:
            raise ValueError(
                "case-insensitive release member collision: "
                f"{seen_casefold_paths[folded]} and {normalized}"
            )
        seen_casefold_paths[folded] = normalized
        roots.add(posix.parts[0])
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"release member type is not allowed: {member.name}")
        if member.size < 0:
            raise ValueError(f"release member declares a negative size: {member.name}")
        if member.isfile():
            if member.size > limits.max_member_bytes:
                raise ValueError(f"release member exceeds size limit: {member.name}")
            total_file_bytes += member.size
            if total_file_bytes > limits.max_total_file_bytes:
                raise ValueError(
                    f"release artifact exceeds total expanded size limit ({limits.max_total_file_bytes})"
                )

    if len(roots) != 1:
        raise ValueError("release artifact must contain exactly one top-level directory")
    root_name = next(iter(roots))
    if not root_name.startswith("dircreative-"):
        raise ValueError("release artifact has a non-canonical top-level directory")
    version = root_name.removeprefix("dircreative-")
    if expected_version is not None and version != expected_version:
        raise ValueError(f"release root version {version} does not equal expected {expected_version}")

    for member in tar.getmembers():
        posix = PurePosixPath(member.name)
        if posix.parts[0] != root_name:
            raise ValueError(f"release member is outside canonical root {root_name}: {member.name}")
        relative = PurePosixPath(*posix.parts[1:]).as_posix()
        if relative:
            members[relative] = member
        elif not member.isdir():
            raise ValueError(f"release canonical root entry must be a directory: {member.name}")
    for relative, member in members.items():
        for parent in PurePosixPath(relative).parents:
            parent_name = parent.as_posix()
            if parent_name == ".":
                break
            if parent_name in members and members[parent_name].isfile():
                raise ValueError(
                    f"release member path conflicts with a file parent: {parent_name} -> {relative}"
                )
    missing = sorted(REQUIRED_MEMBERS - set(members))
    if missing:
        raise ValueError("release artifact missing required members: " + ", ".join(missing))
    validate_ustar_layout(tar)
    return root_name, version, members


def validate_ustar_layout(tar: tarfile.TarFile) -> None:
    fileobj = tar.fileobj
    original_position = fileobj.tell()
    logical_end = 0
    try:
        for member in tar.getmembers():
            fileobj.seek(member.offset + 257)
            if fileobj.read(8) != b"ustar\x0000":
                raise ValueError(f"release member is not canonical USTAR: {member.name}")
            padded_size = ((member.size + tarfile.BLOCKSIZE - 1) // tarfile.BLOCKSIZE) * tarfile.BLOCKSIZE
            logical_end = max(logical_end, member.offset_data + padded_size)
        fileobj.seek(logical_end)
        trailer_size = 0
        while True:
            chunk = fileobj.read(COPY_CHUNK_BYTES)
            if not chunk:
                break
            trailer_size += len(chunk)
            if any(chunk):
                raise ValueError("release tar contains non-zero trailing data")
        if trailer_size < tarfile.BLOCKSIZE * 2 or (logical_end + trailer_size) % tarfile.BLOCKSIZE:
            raise ValueError("release tar is missing canonical zero-block termination")
    finally:
        fileobj.seek(original_position)


def read_member(tar: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    if not member.isfile():
        raise ValueError(f"required release member is not a file: {member.name}")
    handle = tar.extractfile(member)
    if handle is None:
        raise ValueError(f"cannot read release member: {member.name}")
    data = handle.read(member.size + 1)
    if len(data) != member.size:
        raise ValueError(f"release member size does not match header: {member.name}")
    return data


def extract_validated(
    tar: tarfile.TarFile,
    root_name: str,
    members: dict[str, tarfile.TarInfo],
    destination: Path,
) -> Path:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"extract destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    root = destination / root_name
    for relative, member in sorted(members.items()):
        target = root / relative
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = tar.extractfile(member)
        if source is None:
            raise ValueError(f"cannot extract release member: {member.name}")
        with target.open("xb") as output:
            remaining = member.size
            while remaining:
                chunk = source.read(min(COPY_CHUNK_BYTES, remaining))
                if not chunk:
                    raise ValueError(f"release member ended before declared size: {member.name}")
                output.write(chunk)
                remaining -= len(chunk)
            if source.read(1):
                raise ValueError(f"release member exceeds declared size: {member.name}")
        os.chmod(target, member.mode & 0o777)
    return root


def decompress_archive_bounded(
    artifact: io.BufferedRandom,
    destination: io.BufferedRandom,
    limit: int,
) -> None:
    total = 0
    artifact.seek(0)
    with gzip.GzipFile(fileobj=artifact, mode="rb") as compressed:
        while True:
            chunk = compressed.read(COPY_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise ValueError(f"release artifact exceeds decompressed tar size limit ({limit})")
            destination.write(chunk)
    destination.flush()
    destination.seek(0)


def verify_release(
    artifact: Path,
    checksums: Path,
    *,
    expected_version: str | None = None,
    expected_commit: str | None = None,
    extract_to: Path | None = None,
    limits: ArchiveLimits = DEFAULT_LIMITS,
    reproducible_source: Path | None = None,
    expected_tag: str | None = None,
    require_remote_tag: bool = False,
) -> dict[str, str]:
    checksum_bytes = read_regular_file_once(
        checksums,
        max_bytes=limits.max_checksum_bytes,
        label="checksum file",
    )
    with tempfile.TemporaryFile(mode="w+b") as sealed_artifact:
        actual_hash, _ = copy_regular_file_once(
            artifact,
            sealed_artifact,
            max_bytes=limits.max_archive_bytes,
            label="release artifact",
        )
        declared_hash = checksum_for(checksum_bytes, artifact.name)
        if actual_hash != declared_hash:
            raise ValueError("release artifact SHA-256 does not match SHA256SUMS")

        with tempfile.TemporaryFile(mode="w+b") as uncompressed:
            decompress_archive_bounded(sealed_artifact, uncompressed, limits.max_tar_stream_bytes)
            with tarfile.open(fileobj=uncompressed, mode="r:") as tar:
                root_name, version, members = validated_members(tar, expected_version, limits)

                metadata = json.loads(read_member(tar, members["RELEASE-METADATA.json"]))
                if not isinstance(metadata, dict):
                    raise ValueError("RELEASE-METADATA.json must contain an object")
                if metadata.get("schema_version") != "1.0.0":
                    raise ValueError("release metadata schema_version must be 1.0.0")
                if metadata.get("product") != "DIRcreative":
                    raise ValueError("release metadata product mismatch")
                if metadata.get("version") != version or metadata.get("tag") != f"v{version}":
                    raise ValueError("release metadata version/tag mismatch")
                commit = metadata.get("commit_sha")
                if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                    raise ValueError("release metadata commit_sha is invalid")
                if expected_commit is not None and commit != expected_commit:
                    raise ValueError("release metadata commit_sha does not equal expected commit")
                root_skill = read_member(tar, members["SKILL.md"])
                if metadata.get("root_skill_sha256") != sha256_bytes(root_skill):
                    raise ValueError("release metadata root skill hash mismatch")
                if read_member(tar, members["VERSION"]).decode("utf-8").strip() != version:
                    raise ValueError("packaged VERSION does not match release version")

                for relative, member in members.items():
                    if not member.isfile():
                        continue
                    data = read_member(tar, member)
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if HOST_USER_PATH_RE.search(text):
                        raise ValueError(f"release member contains a host user path: {relative}")
                    if THREAD_ID_RE.search(text):
                        raise ValueError(f"release member contains a live Codex thread id: {relative}")

                reproducible_match = "not_requested"
                remote_tag_match = "not_requested"
                provenance_scope = "structural_only"
                if reproducible_source is not None:
                    if expected_commit is None:
                        raise ValueError("reproducible verification requires an explicit expected commit")
                    verify_reproducible_build(
                        reproducible_source,
                        artifact,
                        version=version,
                        expected_commit=expected_commit,
                        expected_hash=actual_hash,
                        expected_tag=expected_tag or f"v{version}",
                        require_remote_tag=require_remote_tag,
                    )
                    reproducible_match = "true"
                    remote_tag_match = "true" if require_remote_tag else "not_requested"
                    provenance_scope = (
                        "canonical_remote_tag"
                        if require_remote_tag
                        else "local_exact_commit_rebuild_only"
                    )

                extracted = "not_requested"
                if extract_to is not None:
                    extracted = str(extract_validated(tar, root_name, members, extract_to))

        return {
            "version": version,
            "commit_sha": commit,
            "artifact_sha256": actual_hash,
            "reproducible_match": reproducible_match,
            "remote_tag_match": remote_tag_match,
            "provenance_scope": provenance_scope,
            "extracted_root": extracted,
        }


TestMember = tuple[str, bytes, bytes, str]


def add_test_member(
    tar: tarfile.TarFile,
    name: str,
    data: bytes,
    member_type: bytes = tarfile.REGTYPE,
    linkname: str = "",
    pax_headers: dict[str, str] | None = None,
) -> None:
    info = tarfile.TarInfo(name)
    info.type = member_type
    info.linkname = linkname
    info.mode = 0o644
    info.pax_headers = pax_headers or {}
    info.size = len(data) if member_type == tarfile.REGTYPE else 0
    tar.addfile(info, io.BytesIO(data) if info.size else None)


def build_test_archive(
    root: Path,
    case: str,
    *,
    overrides: dict[str, bytes | None] | None = None,
    metadata_overrides: dict[str, object] | None = None,
    extra_members: list[TestMember] | None = None,
    pax_comment_size: int = 0,
    tar_format: int | None = None,
) -> tuple[Path, Path]:
    version = "9.9.9"
    root_name = f"dircreative-{version}"
    case_root = root / case
    case_root.mkdir()
    files: dict[str, bytes] = {
        "SKILL.md": b"---\nname: dircreative\ndescription: fixture\n---\n",
        "VERSION": (version + "\n").encode("utf-8"),
        "CHANGELOG.md": b"# Fixture\n",
        "scripts/validate_project.py": b"print('ok')\n",
    }
    for relative, data in (overrides or {}).items():
        if data is None:
            files.pop(relative, None)
        else:
            files[relative] = data
    metadata: dict[str, object] = {
        "schema_version": "1.0.0",
        "product": "DIRcreative",
        "version": version,
        "tag": f"v{version}",
        "commit_sha": "a" * 40,
        "root_skill_sha256": sha256_bytes(files["SKILL.md"]),
    }
    metadata.update(metadata_overrides or {})
    files["RELEASE-METADATA.json"] = (json.dumps(metadata, sort_keys=True) + "\n").encode("utf-8")

    artifact = case_root / f"dircreative-{version}.tar.gz"
    archive_format = tar_format or (tarfile.PAX_FORMAT if pax_comment_size else tarfile.USTAR_FORMAT)
    with tarfile.open(artifact, mode="w:gz", format=archive_format) as tar:
        for index, (relative, data) in enumerate(sorted(files.items())):
            pax_headers = {"comment": "x" * pax_comment_size} if pax_comment_size and index == 0 else None
            add_test_member(tar, f"{root_name}/{relative}", data, pax_headers=pax_headers)
        for name, data, member_type, linkname in extra_members or []:
            add_test_member(tar, name, data, member_type, linkname)
    checksums = case_root / "SHA256SUMS"
    checksums.write_text(f"{sha256_file(artifact)}  {artifact.name}\n", encoding="utf-8")
    return artifact, checksums


def expect_test_failure(
    label: str,
    artifact: Path,
    checksums: Path,
    expected_error: str,
    **kwargs: object,
) -> None:
    try:
        verify_release(artifact, checksums, **kwargs)
    except ValueError as exc:
        if expected_error not in str(exc):
            raise AssertionError(f"{label} failed for wrong reason: {exc}") from exc
    else:
        raise AssertionError(f"{label} was accepted")


def self_test() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="dircreative-release-verify-") as raw:
            root = Path(raw)
            valid_artifact, valid_checksums = build_test_archive(root, "valid")
            result = verify_release(
                valid_artifact,
                valid_checksums,
                expected_version="9.9.9",
                expected_commit="a" * 40,
                extract_to=root / "extract",
            )
            if result["version"] != "9.9.9" or not Path(result["extracted_root"]).is_dir():
                raise AssertionError("valid control did not extract")

            wrong_checksum = root / "wrong-checksum"
            wrong_checksum.mkdir()
            wrong_checksum_file = wrong_checksum / "SHA256SUMS"
            wrong_checksum_file.write_text(
                f"{'0' * 64}  {valid_artifact.name}\n", encoding="utf-8"
            )
            expect_test_failure(
                "tampered checksum",
                valid_artifact,
                wrong_checksum_file,
                "does not match SHA256SUMS",
                expected_version="9.9.9",
            )

            negative_archives = [
                (
                    "traversal",
                    {},
                    {},
                    [("dircreative-9.9.9/../escape", b"x", tarfile.REGTYPE, "")],
                    "unsafe release member path",
                ),
                (
                    "absolute",
                    {},
                    {},
                    [("/absolute/escape", b"x", tarfile.REGTYPE, "")],
                    "unsafe release member path",
                ),
                (
                    "backslash",
                    {},
                    {},
                    [(r"dircreative-9.9.9\\escape", b"x", tarfile.REGTYPE, "")],
                    "unsafe release member path syntax",
                ),
                (
                    "symlink",
                    {},
                    {},
                    [("dircreative-9.9.9/link", b"", tarfile.SYMTYPE, "../../escape")],
                    "member type is not allowed",
                ),
                (
                    "hardlink",
                    {},
                    {},
                    [("dircreative-9.9.9/link", b"", tarfile.LNKTYPE, "dircreative-9.9.9/SKILL.md")],
                    "member type is not allowed",
                ),
                (
                    "duplicate",
                    {},
                    {},
                    [("dircreative-9.9.9/SKILL.md", b"duplicate", tarfile.REGTYPE, "")],
                    "duplicate release member",
                ),
                (
                    "casefold-collision",
                    {},
                    {},
                    [("dircreative-9.9.9/skill.md", b"collision", tarfile.REGTYPE, "")],
                    "case-insensitive release member collision",
                ),
                (
                    "file-parent-conflict",
                    {},
                    {},
                    [("dircreative-9.9.9/scripts", b"not a directory", tarfile.REGTYPE, "")],
                    "path conflicts with a file parent",
                ),
                (
                    "windows-drive-component",
                    {},
                    {},
                    [("dircreative-9.9.9/C:/escape", b"x", tarfile.REGTYPE, "")],
                    "unsafe cross-platform release member path",
                ),
                (
                    "windows-reserved-name",
                    {},
                    {},
                    [("dircreative-9.9.9/CON.txt", b"x", tarfile.REGTYPE, "")],
                    "reserved cross-platform path",
                ),
                (
                    "multiple-roots",
                    {},
                    {},
                    [("other-root/file", b"x", tarfile.REGTYPE, "")],
                    "exactly one top-level directory",
                ),
                (
                    "missing-required",
                    {"CHANGELOG.md": None},
                    {},
                    [],
                    "missing required members",
                ),
                (
                    "root-hash",
                    {},
                    {"root_skill_sha256": "0" * 64},
                    [],
                    "root skill hash mismatch",
                ),
                (
                    "host-path",
                    {
                        "CHANGELOG.md": (
                            "/" + "home" + "/alice/private/client.txt\n"
                        ).encode("utf-8")
                    },
                    {},
                    [],
                    "contains a host user path",
                ),
                (
                    "thread-id",
                    {
                        "CHANGELOG.md": (
                            "019f4d2b" + "-38d4-7ba2-971f-11bfb9b860cf\n"
                        ).encode("utf-8")
                    },
                    {},
                    [],
                    "contains a live Codex thread id",
                ),
            ]
            for label, overrides, metadata_overrides, extra_members, expected_error in negative_archives:
                artifact, checksums = build_test_archive(
                    root,
                    label,
                    overrides=overrides,
                    metadata_overrides=metadata_overrides,
                    extra_members=extra_members,
                )
                expect_test_failure(
                    label,
                    artifact,
                    checksums,
                    expected_error,
                    expected_version="9.9.9",
                    expected_commit="a" * 40,
                )

            pax_artifact, pax_checksums = build_test_archive(
                root,
                "pax-metadata",
                pax_comment_size=20_000,
            )
            expect_test_failure(
                "pax metadata",
                pax_artifact,
                pax_checksums,
                "forbidden extended metadata",
                expected_version="9.9.9",
                limits=replace(DEFAULT_LIMITS, max_total_file_bytes=4096),
            )
            gnu_artifact, gnu_checksums = build_test_archive(
                root,
                "gnu-format",
                tar_format=tarfile.GNU_FORMAT,
            )
            expect_test_failure(
                "gnu format",
                gnu_artifact,
                gnu_checksums,
                "not canonical USTAR",
                expected_version="9.9.9",
            )

            expect_test_failure(
                "wrong expected commit",
                valid_artifact,
                valid_checksums,
                "does not equal expected commit",
                expected_version="9.9.9",
                expected_commit="b" * 40,
            )
            expect_test_failure(
                "empty expected commit",
                valid_artifact,
                valid_checksums,
                "does not equal expected commit",
                expected_version="9.9.9",
                expected_commit="",
            )
            resource_cases = [
                ("compressed size", replace(DEFAULT_LIMITS, max_archive_bytes=valid_artifact.stat().st_size - 1), "release artifact exceeds size limit"),
                ("checksum size", replace(DEFAULT_LIMITS, max_checksum_bytes=valid_checksums.stat().st_size - 1), "checksum file exceeds size limit"),
                ("member count", replace(DEFAULT_LIMITS, max_members=4), "member count limit"),
                ("single member", replace(DEFAULT_LIMITS, max_member_bytes=8), "member exceeds size limit"),
                ("aggregate size", replace(DEFAULT_LIMITS, max_total_file_bytes=8), "total expanded size limit"),
                ("tar stream size", replace(DEFAULT_LIMITS, max_tar_stream_bytes=512), "decompressed tar size limit"),
                ("member path", replace(DEFAULT_LIMITS, max_member_path_bytes=12), "path exceeds size limit"),
            ]
            for label, limits, expected_error in resource_cases:
                expect_test_failure(
                    label,
                    valid_artifact,
                    valid_checksums,
                    expected_error,
                    expected_version="9.9.9",
                    limits=limits,
                )
            symlink_artifact = root / "symlink-artifact.tar.gz"
            symlink_artifact.symlink_to(valid_artifact)
            expect_test_failure(
                "artifact symlink",
                symlink_artifact,
                valid_checksums,
                "release artifact must not be a symlink",
                expected_version="9.9.9",
            )
            hardlink_artifact = root / "hardlink-artifact.tar.gz"
            os.link(valid_artifact, hardlink_artifact)
            expect_test_failure(
                "artifact hardlink",
                hardlink_artifact,
                valid_checksums,
                "release artifact must not be hardlinked",
                expected_version="9.9.9",
            )
            hardlink_artifact.unlink()
    except (AssertionError, OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"RELEASE_ARTIFACT_VERIFY_SELF_TEST: FAIL: {exc}")
        return 1
    print("RELEASE_ARTIFACT_VERIFY_SELF_TEST: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a DIRcreative release artifact and checksum.")
    parser.add_argument("--artifact")
    parser.add_argument("--checksums")
    parser.add_argument("--expected-version")
    parser.add_argument("--expected-commit")
    parser.add_argument("--expected-tag")
    parser.add_argument("--expect-current-head", action="store_true")
    parser.add_argument("--extract-to")
    parser.add_argument("--reproducible-source")
    parser.add_argument("--require-reproducible-match", action="store_true")
    parser.add_argument("--require-remote-tag", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.artifact or not args.checksums:
        parser.error("--artifact and --checksums are required unless --self-test is used")
    expected_version = args.expected_version
    if expected_version is None and (ROOT / "VERSION").is_file():
        expected_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    expected_commit = args.expected_commit
    if expected_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        print("RELEASE_ARTIFACT_VERIFY: FAIL_INVALID_EXPECTED_COMMIT")
        return 1
    if args.expect_current_head:
        head = current_head()
        if not head:
            print("RELEASE_ARTIFACT_VERIFY: FAIL_CURRENT_HEAD")
            return 1
        if expected_commit is not None and expected_commit != head:
            print("RELEASE_ARTIFACT_VERIFY: FAIL_EXPECTED_COMMIT_CONFLICT")
            return 1
        expected_commit = head
    if args.require_reproducible_match and not args.reproducible_source:
        print("RELEASE_ARTIFACT_VERIFY: FAIL_REPRODUCIBLE_SOURCE_REQUIRED")
        return 1
    if args.reproducible_source and expected_commit is None:
        print("RELEASE_ARTIFACT_VERIFY: FAIL_REPRODUCIBLE_EXPECTED_COMMIT_REQUIRED")
        return 1
    if args.require_remote_tag and not args.reproducible_source:
        print("RELEASE_ARTIFACT_VERIFY: FAIL_REMOTE_TAG_REPRODUCIBLE_SOURCE_REQUIRED")
        return 1
    expected_tag = args.expected_tag or (f"v{expected_version}" if expected_version else None)
    if args.require_remote_tag and (
        expected_tag is None or re.fullmatch(r"v\d+\.\d+\.\d+", expected_tag) is None
    ):
        print("RELEASE_ARTIFACT_VERIFY: FAIL_INVALID_EXPECTED_TAG")
        return 1
    try:
        result = verify_release(
            Path(args.artifact).expanduser().resolve(),
            Path(args.checksums).expanduser().resolve(),
            expected_version=expected_version,
            expected_commit=expected_commit,
            extract_to=Path(args.extract_to).expanduser().resolve() if args.extract_to else None,
            reproducible_source=(
                Path(args.reproducible_source).expanduser().resolve()
                if args.reproducible_source
                else None
            ),
            expected_tag=expected_tag,
            require_remote_tag=args.require_remote_tag,
        )
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as exc:
        print("DIRcreative Release Artifact Verification")
        print("=" * 72)
        print(f"RELEASE_ARTIFACT_VERIFY: FAIL: {exc}")
        return 1
    print("DIRcreative Release Artifact Verification")
    print("=" * 72)
    for key, value in result.items():
        print(f"{key}: {value}")
    print("RELEASE_ARTIFACT_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
