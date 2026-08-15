#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
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
from collections.abc import Callable
from contextlib import nullcontext
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


@dataclass(frozen=True, order=True)
class ArchiveManifestEntry:
    path: str
    kind: str
    mode: int
    size: int
    sha256: str | None


@dataclass(frozen=True)
class VerifiedRelease:
    version: str
    commit_sha: str
    artifact_sha256: str
    reproducible_match: str
    remote_tag_match: str
    provenance_scope: str
    extracted_root: Path | None
    archive_manifest: tuple[ArchiveManifestEntry, ...]
    archive_manifest_sha256: str

    def summary(self) -> dict[str, str]:
        return {
            "version": self.version,
            "commit_sha": self.commit_sha,
            "artifact_sha256": self.artifact_sha256,
            "reproducible_match": self.reproducible_match,
            "remote_tag_match": self.remote_tag_match,
            "provenance_scope": self.provenance_scope,
            "extracted_root": (
                str(self.extracted_root) if self.extracted_root is not None else "not_requested"
            ),
            "archive_manifest_sha256": self.archive_manifest_sha256,
            "archive_manifest_entries": str(len(self.archive_manifest)),
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_manifest_digest(entries: tuple[ArchiveManifestEntry, ...]) -> str:
    payload = [
        {
            "path": entry.path,
            "kind": entry.kind,
            "mode": entry.mode,
            "size": entry.size,
            "sha256": entry.sha256,
        }
        for entry in entries
    ]
    return sha256_bytes(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )


def inode_identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def stable_entry_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def directory_open_flags() -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("secure directory traversal requires O_DIRECTORY and O_NOFOLLOW")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def regular_file_open_flags(*, write: bool = False, create: bool = False) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("secure file traversal requires O_NOFOLLOW")
    flags = (os.O_WRONLY if write else os.O_RDONLY) | os.O_NOFOLLOW
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


@dataclass
class PinnedDirectory:
    path: Path
    fds: list[int]
    names: list[str]
    identities: list[tuple[int, int]]
    closed: bool = False

    @property
    def fd(self) -> int:
        if self.closed:
            raise ValueError(f"pinned directory is already closed: {self.path}")
        return self.fds[-1]

    @property
    def identity(self) -> tuple[int, int]:
        return self.identities[-1]

    def revalidate(self, *, label: str) -> None:
        if self.closed:
            raise ValueError(f"{label} pinned directory is already closed")
        for index, descriptor in enumerate(self.fds):
            current = os.fstat(descriptor)
            if not stat.S_ISDIR(current.st_mode) or inode_identity(current) != self.identities[index]:
                raise ValueError(f"{label} pinned directory identity changed: {self.path}")
            if index == 0:
                continue
            try:
                linked = os.stat(
                    self.names[index - 1],
                    dir_fd=self.fds[index - 1],
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise ValueError(
                    f"{label} directory chain is no longer reachable: {self.path}: {exc}"
                ) from exc
            if not stat.S_ISDIR(linked.st_mode) or inode_identity(linked) != self.identities[index]:
                raise ValueError(f"{label} directory chain identity changed: {self.path}")

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for descriptor in reversed(self.fds):
            try:
                os.close(descriptor)
            except OSError:
                pass

    def __enter__(self) -> PinnedDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def open_pinned_directory(
    path: Path,
    *,
    create: bool = False,
    create_mode: int = 0o777,
) -> PinnedDirectory:
    absolute = Path(os.path.abspath(path.expanduser()))
    if not absolute.is_absolute():
        raise ValueError(f"secure directory traversal requires an absolute path: {path}")
    flags = directory_open_flags()
    root_fd = os.open(os.sep, flags)
    fds = [root_fd]
    names: list[str] = []
    identities = [inode_identity(os.fstat(root_fd))]
    try:
        for component in absolute.parts[1:]:
            if component in {"", ".", ".."} or os.sep in component:
                raise ValueError(f"unsafe directory path component: {component!r}")
            parent_fd = fds[-1]
            try:
                before = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, create_mode, dir_fd=parent_fd)
                before = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise ValueError(f"directory path component is not a real directory: {absolute}")
            descriptor = os.open(component, flags, dir_fd=parent_fd)
            opened = os.fstat(descriptor)
            try:
                after = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            except BaseException:
                os.close(descriptor)
                raise
            if (
                not stat.S_ISDIR(opened.st_mode)
                or inode_identity(before) != inode_identity(opened)
                or inode_identity(after) != inode_identity(opened)
            ):
                os.close(descriptor)
                raise ValueError(f"directory path component changed while opening: {absolute}")
            fds.append(descriptor)
            names.append(component)
            identities.append(inode_identity(opened))
        pinned = PinnedDirectory(absolute, fds, names, identities)
        pinned.revalidate(label="opened")
        return pinned
    except BaseException:
        for descriptor in reversed(fds):
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


def _read_manifest_file_descriptor(descriptor: int, relative: str) -> tuple[int, str, os.stat_result]:
    digest = hashlib.sha256()
    total = 0
    with os.fdopen(descriptor, "rb", closefd=True) as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"installed manifest entry is not a regular file: {relative}")
        if before.st_nlink != 1:
            raise ValueError(f"installed manifest file must be single-link: {relative}")
        for chunk in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
            total += len(chunk)
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if identity_before != identity_after or total != before.st_size:
        raise ValueError(f"installed manifest file changed while being read: {relative}")
    return total, digest.hexdigest(), after


def strict_tree_manifest_from_fd(
    root_fd: int,
    *,
    race_hook: Callable[[str, str], None] | None = None,
) -> tuple[ArchiveManifestEntry, ...]:
    root_before = os.fstat(root_fd)
    if not stat.S_ISDIR(root_before.st_mode):
        raise ValueError("installed manifest root descriptor must reference a directory")
    entries: list[ArchiveManifestEntry] = [
        ArchiveManifestEntry(".", "directory", stat.S_IMODE(root_before.st_mode), 0, None)
    ]

    def visit(directory_fd: int, relative_directory: PurePosixPath) -> None:
        directory_before = os.fstat(directory_fd)
        try:
            child_names = sorted(os.listdir(directory_fd))
        except OSError as exc:
            relative = relative_directory.as_posix()
            raise ValueError(f"cannot scan installed manifest directory {relative}: {exc}") from exc
        folded_names: dict[str, str] = {}
        for child_name in child_names:
            folded = unicodedata.normalize("NFC", child_name).casefold().rstrip(". ")
            if folded in folded_names:
                raise ValueError(
                    "case-insensitive installed manifest collision: "
                    f"{folded_names[folded]} and {child_name}"
                )
            folded_names[folded] = child_name
            relative_path = relative_directory / child_name
            relative = relative_path.as_posix()
            try:
                child_before = os.stat(
                    child_name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise ValueError(f"cannot stat installed manifest entry {relative}: {exc}") from exc
            if race_hook is not None:
                race_hook("child_lstat", relative)
            mode = stat.S_IMODE(child_before.st_mode)
            if stat.S_ISDIR(child_before.st_mode):
                try:
                    child_fd = os.open(child_name, directory_open_flags(), dir_fd=directory_fd)
                except OSError as exc:
                    raise ValueError(
                        f"cannot open installed manifest directory {relative}: {exc}"
                    ) from exc
                try:
                    child_opened = os.fstat(child_fd)
                    if stable_entry_identity(child_before) != stable_entry_identity(child_opened):
                        raise ValueError(
                            f"installed manifest directory changed while opening: {relative}"
                        )
                    entries.append(ArchiveManifestEntry(relative, "directory", mode, 0, None))
                    visit(child_fd, relative_path)
                    child_after = os.fstat(child_fd)
                    linked_after = os.stat(
                        child_name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    if (
                        stable_entry_identity(child_opened) != stable_entry_identity(child_after)
                        or stable_entry_identity(child_after) != stable_entry_identity(linked_after)
                    ):
                        raise ValueError(
                            f"installed manifest directory changed while being read: {relative}"
                        )
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(child_before.st_mode):
                try:
                    child_fd = os.open(
                        child_name,
                        regular_file_open_flags(),
                        dir_fd=directory_fd,
                    )
                except OSError as exc:
                    raise ValueError(f"cannot open installed manifest file {relative}: {exc}") from exc
                child_opened = os.fstat(child_fd)
                if stable_entry_identity(child_before) != stable_entry_identity(child_opened):
                    os.close(child_fd)
                    raise ValueError(f"installed manifest file changed while opening: {relative}")
                size, digest, child_after = _read_manifest_file_descriptor(child_fd, relative)
                linked_after = os.stat(
                    child_name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if stable_entry_identity(child_after) != stable_entry_identity(linked_after):
                    raise ValueError(f"installed manifest file changed after being read: {relative}")
                entries.append(ArchiveManifestEntry(relative, "file", mode, size, digest))
            else:
                raise ValueError(
                    f"installed manifest entry must be a regular file or directory: {relative}"
                )
        if sorted(os.listdir(directory_fd)) != child_names:
            relative = relative_directory.as_posix()
            raise ValueError(f"installed manifest directory changed while being scanned: {relative}")
        directory_after = os.fstat(directory_fd)
        if stable_entry_identity(directory_before) != stable_entry_identity(directory_after):
            relative = relative_directory.as_posix()
            raise ValueError(f"installed manifest directory changed while being scanned: {relative}")

    visit(root_fd, PurePosixPath())
    root_after = os.fstat(root_fd)
    if stable_entry_identity(root_before) != stable_entry_identity(root_after):
        raise ValueError("installed manifest root changed while being scanned")
    return tuple(sorted(entries))


def strict_tree_manifest(
    root: Path,
    *,
    race_hook: Callable[[str, str], None] | None = None,
) -> tuple[ArchiveManifestEntry, ...]:
    try:
        with open_pinned_directory(root) as pinned:
            pinned.revalidate(label="installed manifest before scan")
            entries = strict_tree_manifest_from_fd(pinned.fd, race_hook=race_hook)
            pinned.revalidate(label="installed manifest after scan")
            return entries
    except OSError as exc:
        raise ValueError(f"cannot securely open installed manifest root {root}: {exc}") from exc


def assert_tree_matches_manifest(
    root: Path,
    expected: tuple[ArchiveManifestEntry, ...],
    *,
    label: str,
) -> None:
    actual = strict_tree_manifest(root)
    if actual != expected:
        expected_by_path = {entry.path: entry for entry in expected}
        actual_by_path = {entry.path: entry for entry in actual}
        missing = sorted(set(expected_by_path) - set(actual_by_path))
        extra = sorted(set(actual_by_path) - set(expected_by_path))
        changed = sorted(
            path
            for path in set(expected_by_path).intersection(actual_by_path)
            if expected_by_path[path] != actual_by_path[path]
        )
        details = []
        if missing:
            details.append("missing=" + ",".join(missing[:5]))
        if extra:
            details.append("extra=" + ",".join(extra[:5]))
        if changed:
            details.append("changed=" + ",".join(changed[:5]))
        raise ValueError(f"{label} tree does not match verified archive manifest: {'; '.join(details)}")


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


def canonicalize_rebuilt_release(
    rebuilt: Path,
    output: Path,
) -> None:
    metadata_count = 0
    with tarfile.open(rebuilt, mode="r:gz") as source_tar:
        members = source_tar.getmembers()
        if not members:
            raise ValueError("rebuilt release archive is empty")
        commit_timestamp = int(members[0].mtime)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(mode="w+b") as raw_tar:
            with tarfile.open(
                fileobj=raw_tar,
                mode="w",
                format=tarfile.USTAR_FORMAT,
            ) as target_tar:
                for member in members:
                    info = copy.copy(member)
                    data: bytes | None = None
                    if member.isfile():
                        data = read_member(source_tar, member)
                        if member.name.endswith("/RELEASE-METADATA.json"):
                            metadata_count += 1
                            try:
                                metadata = json.loads(data.decode("utf-8"))
                            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                                raise ValueError(
                                    "rebuilt release metadata is invalid"
                                ) from exc
                            if (
                                not isinstance(metadata, dict)
                                or metadata.get("release_status")
                                != "UNPUBLISHED_LOCAL_CANDIDATE"
                            ):
                                raise ValueError(
                                    "sealed rebuild must start as an unpublished local candidate"
                                )
                            metadata["release_status"] = "CANONICAL_REMOTE_TAG"
                            data = (
                                json.dumps(
                                    metadata,
                                    ensure_ascii=False,
                                    indent=2,
                                    sort_keys=True,
                                )
                                + "\n"
                            ).encode("utf-8")
                        info.size = len(data)
                        target_tar.addfile(info, io.BytesIO(data))
                    else:
                        target_tar.addfile(info)
            if metadata_count != 1:
                raise ValueError(
                    "rebuilt release must contain exactly one release metadata file"
                )
            raw_tar.seek(0)
            with output.open("wb") as raw_output:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=raw_output,
                    compresslevel=0,
                    mtime=commit_timestamp,
                ) as compressed:
                    while True:
                        chunk = raw_tar.read(COPY_CHUNK_BYTES)
                        if not chunk:
                            break
                        compressed.write(chunk)


def verify_reproducible_build(
    source: Path,
    artifact: Path,
    *,
    version: str,
    expected_commit: str,
    expected_hash: str,
    expected_tag: str | None,
    require_remote_tag: bool,
    _remote_tag_verifier: Callable[[Path, str, str], None] = verify_canonical_remote_tag,
    _canonicalizer: Callable[[Path, Path], None] = canonicalize_rebuilt_release,
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
        _remote_tag_verifier(source, expected_tag, expected_commit)
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
        build_command = [
            sys.executable,
            str(builder),
            "--expected-commit",
            expected_commit,
            "--output-dir",
            str(output_dir),
        ]
        build_command.append("--allow-unpublished")
        proc = subprocess.run(
            build_command,
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
        comparable = rebuilt
        if require_remote_tag:
            canonical_dir = output_dir / "canonicalized"
            canonical_dir.mkdir()
            comparable = canonical_dir / rebuilt.name
            _canonicalizer(rebuilt, comparable)
        rebuilt_hash = sha256_file(comparable)
        if rebuilt_hash != expected_hash or comparable.name != artifact.name:
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
) -> tuple[str, str, tarfile.TarInfo, dict[str, tarfile.TarInfo]]:
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
        if member.mode & ~0o777:
            raise ValueError(f"release member uses forbidden permission bits: {member.name}")
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

    root_member: tarfile.TarInfo | None = None
    for member in tar.getmembers():
        posix = PurePosixPath(member.name)
        if posix.parts[0] != root_name:
            raise ValueError(f"release member is outside canonical root {root_name}: {member.name}")
        relative_parts = posix.parts[1:]
        if relative_parts:
            relative = PurePosixPath(*relative_parts).as_posix()
            members[relative] = member
        elif not member.isdir():
            raise ValueError(f"release canonical root entry must be a directory: {member.name}")
        else:
            root_member = member
    if root_member is None:
        raise ValueError("release artifact must contain an explicit canonical root directory")
    for relative, member in members.items():
        for parent in PurePosixPath(relative).parents:
            parent_name = parent.as_posix()
            if parent_name == ".":
                break
            if parent_name not in members:
                raise ValueError(
                    f"release member is missing an explicit directory parent: {parent_name} -> {relative}"
                )
            if members[parent_name].isfile():
                raise ValueError(
                    f"release member path conflicts with a file parent: {parent_name} -> {relative}"
                )
    missing = sorted(REQUIRED_MEMBERS - set(members))
    if missing:
        raise ValueError("release artifact missing required members: " + ", ".join(missing))
    validate_ustar_layout(tar)
    return root_name, version, root_member, members


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
    root_member: tarfile.TarInfo,
    members: dict[str, tarfile.TarInfo],
    destination: Path,
    *,
    destination_root_fd: int | None = None,
) -> Path:
    directory_members = sorted(
        ((relative, member) for relative, member in members.items() if member.isdir()),
        key=lambda item: (len(PurePosixPath(item[0]).parts), item[0]),
    )
    file_members = sorted(
        ((relative, member) for relative, member in members.items() if member.isfile()),
        key=lambda item: item[0],
    )
    destination_context = (
        open_pinned_directory(destination, create=True)
        if destination_root_fd is None
        else nullcontext(None)
    )
    with destination_context as opened_destination_root:
        effective_destination_fd = (
            opened_destination_root.fd
            if opened_destination_root is not None
            else destination_root_fd
        )
        if (
            effective_destination_fd is None
            or not stat.S_ISDIR(os.fstat(effective_destination_fd).st_mode)
        ):
            raise ValueError("release extraction destination descriptor must reference a directory")
        if opened_destination_root is not None:
            opened_destination_root.revalidate(
                label="release extraction destination before create"
            )
        if os.listdir(effective_destination_fd):
            raise ValueError(f"extract destination is not empty: {destination}")
        os.mkdir(root_name, 0o700, dir_fd=effective_destination_fd)
        root_before = os.stat(
            root_name,
            dir_fd=effective_destination_fd,
            follow_symlinks=False,
        )
        root_fd = os.open(root_name, directory_open_flags(), dir_fd=effective_destination_fd)
        root_opened = os.fstat(root_fd)
        if inode_identity(root_before) != inode_identity(root_opened):
            os.close(root_fd)
            raise ValueError("release extraction root changed while opening")
        directory_fds: dict[str, int] = {".": root_fd}
        directory_bindings: list[tuple[int, str, tuple[int, int], int]] = [
            (effective_destination_fd, root_name, inode_identity(root_opened), root_fd)
        ]
        try:
            for relative, _member in directory_members:
                posix = PurePosixPath(relative)
                parent = posix.parent.as_posix()
                parent_fd = directory_fds[parent]
                os.mkdir(posix.name, 0o700, dir_fd=parent_fd)
                before = os.stat(posix.name, dir_fd=parent_fd, follow_symlinks=False)
                descriptor = os.open(posix.name, directory_open_flags(), dir_fd=parent_fd)
                opened = os.fstat(descriptor)
                after = os.stat(posix.name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    inode_identity(before) != inode_identity(opened)
                    or inode_identity(after) != inode_identity(opened)
                ):
                    os.close(descriptor)
                    raise ValueError(
                        f"release extraction directory changed while opening: {relative}"
                    )
                directory_fds[relative] = descriptor
                directory_bindings.append(
                    (parent_fd, posix.name, inode_identity(opened), descriptor)
                )

            for relative, member in file_members:
                posix = PurePosixPath(relative)
                parent_fd = directory_fds[posix.parent.as_posix()]
                source = tar.extractfile(member)
                if source is None:
                    raise ValueError(f"cannot extract release member: {member.name}")
                descriptor = os.open(
                    posix.name,
                    regular_file_open_flags(write=True, create=True),
                    0o600,
                    dir_fd=parent_fd,
                )
                with os.fdopen(descriptor, "wb", closefd=True) as output:
                    opened = os.fstat(output.fileno())
                    if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                        raise ValueError(
                            f"release extraction destination is not a single-link file: {relative}"
                        )
                    remaining = member.size
                    while remaining:
                        chunk = source.read(min(COPY_CHUNK_BYTES, remaining))
                        if not chunk:
                            raise ValueError(
                                f"release member ended before declared size: {member.name}"
                            )
                        output.write(chunk)
                        remaining -= len(chunk)
                    if source.read(1):
                        raise ValueError(f"release member exceeds declared size: {member.name}")
                    output.flush()
                    os.fsync(output.fileno())
                    os.fchmod(output.fileno(), member.mode & 0o777)
                    written = os.fstat(output.fileno())
                    if written.st_size != member.size:
                        raise ValueError(
                            f"release extraction destination size mismatch: {relative}"
                        )
                linked = os.stat(posix.name, dir_fd=parent_fd, follow_symlinks=False)
                if inode_identity(linked) != inode_identity(written):
                    raise ValueError(
                        f"release extraction destination changed after write: {relative}"
                    )

            for relative, member in reversed(directory_members):
                os.fchmod(directory_fds[relative], member.mode & 0o777)
            os.fchmod(root_fd, root_member.mode & 0o777)
            for parent_fd, name, expected_identity, descriptor in directory_bindings:
                linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                current = os.fstat(descriptor)
                if (
                    inode_identity(linked) != expected_identity
                    or inode_identity(current) != expected_identity
                ):
                    raise ValueError("release extraction directory binding changed")
            if opened_destination_root is not None:
                opened_destination_root.revalidate(
                    label="release extraction destination after write"
                )
        finally:
            for descriptor in reversed(list(directory_fds.values())):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
    return destination / root_name


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


def verify_release_detailed(
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
    extract_root_fd: int | None = None,
) -> VerifiedRelease:
    if expected_commit is not None and re.fullmatch(r"[0-9a-f]{40}", expected_commit) is None:
        raise ValueError("expected commit must be one full lowercase 40-character SHA")
    if require_remote_tag and reproducible_source is None:
        raise ValueError("canonical remote tag verification requires a reproducible source")
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
                root_name, version, root_member, members = validated_members(
                    tar, expected_version, limits
                )

                expected_release_tag = f"v{version}"
                if expected_tag is not None and expected_tag != expected_release_tag:
                    raise ValueError(
                        f"expected tag {expected_tag} does not equal packaged tag {expected_release_tag}"
                    )

                required_data: dict[str, bytes] = {}
                manifest_entries: list[ArchiveManifestEntry] = [
                    ArchiveManifestEntry(
                        ".", "directory", root_member.mode & 0o777, 0, None
                    )
                ]
                for relative, member in sorted(members.items()):
                    if member.isdir():
                        manifest_entries.append(
                            ArchiveManifestEntry(
                                relative, "directory", member.mode & 0o777, 0, None
                            )
                        )
                        continue
                    data = read_member(tar, member)
                    manifest_entries.append(
                        ArchiveManifestEntry(
                            relative,
                            "file",
                            member.mode & 0o777,
                            member.size,
                            sha256_bytes(data),
                        )
                    )
                    if relative in REQUIRED_MEMBERS:
                        required_data[relative] = data
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if HOST_USER_PATH_RE.search(text):
                        raise ValueError(f"release member contains a host user path: {relative}")
                    if THREAD_ID_RE.search(text):
                        raise ValueError(f"release member contains a live Codex thread id: {relative}")
                archive_manifest = tuple(sorted(manifest_entries))
                manifest_digest = archive_manifest_digest(archive_manifest)

                metadata = json.loads(required_data["RELEASE-METADATA.json"])
                if not isinstance(metadata, dict):
                    raise ValueError("RELEASE-METADATA.json must contain an object")
                required_metadata_fields = {
                    "schema_version",
                    "product",
                    "version",
                    "tag",
                    "commit_sha",
                    "commit_timestamp",
                    "root_skill_sha256",
                    "source",
                    "release_status",
                }
                if set(metadata) != required_metadata_fields:
                    raise ValueError("release metadata field set mismatch")
                if metadata.get("schema_version") != "1.1.0":
                    raise ValueError("release metadata schema_version must be 1.1.0")
                if metadata.get("product") != "DIRcreative":
                    raise ValueError("release metadata product mismatch")
                if metadata.get("version") != version or metadata.get("tag") != f"v{version}":
                    raise ValueError("release metadata version/tag mismatch")
                commit = metadata.get("commit_sha")
                if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                    raise ValueError("release metadata commit_sha is invalid")
                if expected_commit is not None and commit != expected_commit:
                    raise ValueError("release metadata commit_sha does not equal expected commit")
                if metadata.get("source") != "git archive of exact commit":
                    raise ValueError("release metadata source mismatch")
                release_status = metadata.get("release_status")
                if release_status not in {
                    "UNPUBLISHED_LOCAL_CANDIDATE",
                    "CANONICAL_REMOTE_TAG",
                }:
                    raise ValueError("release metadata release_status is invalid")
                if require_remote_tag and release_status != "CANONICAL_REMOTE_TAG":
                    raise ValueError("remote-tag verification requires CANONICAL_REMOTE_TAG metadata")
                timestamp = metadata.get("commit_timestamp")
                if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
                    raise ValueError("release metadata commit_timestamp must be UTC")
                root_skill = required_data["SKILL.md"]
                if metadata.get("root_skill_sha256") != sha256_bytes(root_skill):
                    raise ValueError("release metadata root skill hash mismatch")
                if required_data["VERSION"].decode("utf-8").strip() != version:
                    raise ValueError("packaged VERSION does not match release version")

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

                extracted: Path | None = None
                if extract_to is not None:
                    extracted = extract_validated(
                        tar,
                        root_name,
                        root_member,
                        members,
                        extract_to,
                        destination_root_fd=extract_root_fd,
                    )
                    assert_tree_matches_manifest(
                        extracted,
                        archive_manifest,
                        label="verified extraction",
                    )

        return VerifiedRelease(
            version=version,
            commit_sha=commit,
            artifact_sha256=actual_hash,
            reproducible_match=reproducible_match,
            remote_tag_match=remote_tag_match,
            provenance_scope=provenance_scope,
            extracted_root=extracted,
            archive_manifest=archive_manifest,
            archive_manifest_sha256=manifest_digest,
        )


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
    return verify_release_detailed(
        artifact,
        checksums,
        expected_version=expected_version,
        expected_commit=expected_commit,
        extract_to=extract_to,
        limits=limits,
        reproducible_source=reproducible_source,
        expected_tag=expected_tag,
        require_remote_tag=require_remote_tag,
    ).summary()


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
    info.mode = 0o755 if member_type == tarfile.DIRTYPE else 0o644
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
        "schema_version": "1.1.0",
        "product": "DIRcreative",
        "version": version,
        "tag": f"v{version}",
        "commit_sha": "a" * 40,
        "commit_timestamp": "2026-07-21T00:00:00Z",
        "root_skill_sha256": sha256_bytes(files["SKILL.md"]),
        "source": "git archive of exact commit",
        "release_status": "CANONICAL_REMOTE_TAG",
    }
    metadata.update(metadata_overrides or {})
    files["RELEASE-METADATA.json"] = (json.dumps(metadata, sort_keys=True) + "\n").encode("utf-8")

    artifact = case_root / f"dircreative-{version}.tar.gz"
    archive_format = tar_format or (tarfile.PAX_FORMAT if pax_comment_size else tarfile.USTAR_FORMAT)
    with tarfile.open(artifact, mode="w:gz", format=archive_format) as tar:
        add_test_member(tar, root_name, b"", tarfile.DIRTYPE)
        parent_directories = sorted(
            {
                parent.as_posix()
                for relative in files
                for parent in PurePosixPath(relative).parents
                if parent.as_posix() != "."
            },
            key=lambda path: (len(PurePosixPath(path).parts), path),
        )
        for relative in parent_directories:
            add_test_member(tar, f"{root_name}/{relative}", b"", tarfile.DIRTYPE)
        for index, (relative, data) in enumerate(sorted(files.items())):
            pax_headers = {"comment": "x" * pax_comment_size} if pax_comment_size and index == 0 else None
            add_test_member(tar, f"{root_name}/{relative}", data, pax_headers=pax_headers)
        for name, data, member_type, linkname in extra_members or []:
            add_test_member(tar, name, data, member_type, linkname)
    checksums = case_root / "SHA256SUMS"
    checksums.write_text(f"{sha256_file(artifact)}  {artifact.name}\n", encoding="utf-8")
    return artifact, checksums


def build_deterministic_status_archive(path: Path, status: str) -> None:
    version = "9.9.9"
    root_name = f"dircreative-{version}"
    files: dict[str, bytes] = {
        "SKILL.md": b"---\nname: dircreative\ndescription: fixture\n---\n",
        "VERSION": (version + "\n").encode("utf-8"),
        "CHANGELOG.md": b"# Fixture\n",
        "scripts/validate_project.py": b"print('ok')\n",
    }
    metadata = {
        "schema_version": "1.1.0",
        "product": "DIRcreative",
        "version": version,
        "tag": f"v{version}",
        "commit_sha": "a" * 40,
        "commit_timestamp": "1970-01-01T00:00:00Z",
        "root_skill_sha256": sha256_bytes(files["SKILL.md"]),
        "source": "git archive of exact commit",
        "release_status": status,
    }
    files["RELEASE-METADATA.json"] = (
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(mode="w+b") as raw_tar:
        with tarfile.open(
            fileobj=raw_tar, mode="w", format=tarfile.USTAR_FORMAT
        ) as tar:
            add_test_member(tar, root_name, b"", tarfile.DIRTYPE)
            add_test_member(tar, f"{root_name}/scripts", b"", tarfile.DIRTYPE)
            for relative, data in sorted(files.items()):
                add_test_member(tar, f"{root_name}/{relative}", data)
        raw_tar.seek(0)
        with path.open("wb") as raw_output:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_output,
                compresslevel=0,
                mtime=0,
            ) as compressed:
                while True:
                    chunk = raw_tar.read(COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    compressed.write(chunk)


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
            root = Path(raw).resolve()
            valid_artifact, valid_checksums = build_test_archive(root, "valid")
            local_artifact, _ = build_test_archive(
                root,
                "local-candidate",
                metadata_overrides={
                    "release_status": "UNPUBLISHED_LOCAL_CANDIDATE"
                },
            )
            canonicalized_artifact = root / "canonicalized" / local_artifact.name
            canonicalize_rebuilt_release(local_artifact, canonicalized_artifact)
            with tarfile.open(canonicalized_artifact, mode="r:gz") as canonical_tar:
                metadata_members = [
                    member
                    for member in canonical_tar.getmembers()
                    if member.name.endswith("/RELEASE-METADATA.json")
                ]
                if len(metadata_members) != 1:
                    raise AssertionError(
                        "canonicalized fixture has invalid metadata member count"
                    )
                canonical_metadata = json.loads(
                    read_member(canonical_tar, metadata_members[0]).decode("utf-8")
                )
            if canonical_metadata.get("release_status") != "CANONICAL_REMOTE_TAG":
                raise AssertionError(
                    "canonical metadata normalization did not set remote-tag status"
                )
            deterministic_local = root / "deterministic" / "local.tar.gz"
            deterministic_direct = root / "deterministic" / "direct.tar.gz"
            deterministic_first = root / "deterministic" / "first.tar.gz"
            deterministic_second = root / "deterministic" / "second.tar.gz"
            build_deterministic_status_archive(
                deterministic_local, "UNPUBLISHED_LOCAL_CANDIDATE"
            )
            build_deterministic_status_archive(
                deterministic_direct, "CANONICAL_REMOTE_TAG"
            )
            canonicalize_rebuilt_release(
                deterministic_local, deterministic_first
            )
            canonicalize_rebuilt_release(
                deterministic_local, deterministic_second
            )
            if not (
                sha256_file(deterministic_first)
                == sha256_file(deterministic_second)
                == sha256_file(deterministic_direct)
            ):
                raise AssertionError(
                    "canonical metadata normalization is not byte-for-byte reproducible"
                )
            try:
                canonicalize_rebuilt_release(
                    deterministic_direct,
                    root / "deterministic" / "invalid-rewrite.tar.gz",
                )
            except ValueError as exc:
                if "must start as an unpublished local candidate" not in str(exc):
                    raise
            else:
                raise AssertionError(
                    "canonical metadata normalization accepted a pre-claimed canonical artifact"
                )
            verified_control = verify_release_detailed(
                valid_artifact,
                valid_checksums,
                expected_version="9.9.9",
                expected_commit="a" * 40,
                extract_to=root / "extract",
            )
            result = verified_control.summary()
            if result["version"] != "9.9.9" or not Path(result["extracted_root"]).is_dir():
                raise AssertionError("valid control did not extract")
            if int(result["archive_manifest_entries"]) < 7:
                raise AssertionError("valid control did not freeze the complete archive tree")
            pinned_extract = root / "pinned-extract"
            pinned_extract.mkdir()
            with open_pinned_directory(pinned_extract) as pinned_extract_root:
                pinned_control = verify_release_detailed(
                    valid_artifact,
                    valid_checksums,
                    expected_version="9.9.9",
                    expected_commit="a" * 40,
                    extract_to=pinned_extract,
                    extract_root_fd=pinned_extract_root.fd,
                )
                pinned_extract_root.revalidate(label="self-test pinned extraction")
            if pinned_control.extracted_root != pinned_extract / "dircreative-9.9.9":
                raise AssertionError("pinned extraction did not return the canonical root")
            assert_tree_matches_manifest(
                pinned_control.extracted_root,
                pinned_control.archive_manifest,
                label="pinned extraction control",
            )
            extracted_control = Path(result["extracted_root"])
            (extracted_control / "unexpected-after-verification.txt").write_text(
                "tamper\n", encoding="utf-8"
            )
            try:
                assert_tree_matches_manifest(
                    extracted_control,
                    verified_control.archive_manifest,
                    label="tampered verified extraction control",
                )
            except ValueError as exc:
                if "unexpected-after-verification.txt" not in str(exc):
                    raise
            else:
                raise AssertionError("verified extraction tamper escaped manifest readback")

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
                    "metadata-extra-field",
                    {},
                    {"untrusted_claim": True},
                    [],
                    "metadata field set mismatch",
                ),
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
                    [
                        (
                            "dircreative-9.9.9/scripts/validate_project.py/child",
                            b"not reachable",
                            tarfile.REGTYPE,
                            "",
                        )
                    ],
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
                "wrong expected tag",
                valid_artifact,
                valid_checksums,
                "does not equal packaged tag",
                expected_version="9.9.9",
                expected_commit="a" * 40,
                expected_tag="v9.9.8",
            )
            expect_test_failure(
                "empty expected commit",
                valid_artifact,
                valid_checksums,
                "expected commit must be one full lowercase 40-character SHA",
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

            reproducible_source = root / "reproducible-source"
            reproducible_source.mkdir()
            git_at(reproducible_source, "init", "--quiet")
            git_at(reproducible_source, "config", "user.name", "DIRcreative Test")
            git_at(reproducible_source, "config", "user.email", "dircreative@example.invalid")
            scripts_directory = reproducible_source / "scripts"
            scripts_directory.mkdir()
            (reproducible_source / "fixture-release.tar.gz").write_bytes(
                b"exact reproducible fixture artifact\n"
            )
            (scripts_directory / "dircreative_build_release.py").write_text(
                """#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--allow-unpublished", action="store_true")
parser.add_argument("--expected-commit", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
output = Path(args.output_dir)
output.mkdir(parents=True, exist_ok=True)
shutil.copyfile(
    Path(__file__).resolve().parents[1] / "fixture-release.tar.gz",
    output / "dircreative-9.9.9.tar.gz",
)
""",
                encoding="utf-8",
            )
            git_at(reproducible_source, "add", ".")
            git_at(reproducible_source, "commit", "--quiet", "-m", "fixture")
            reproducible_commit = git_at(reproducible_source, "rev-parse", "HEAD")
            git_at(
                reproducible_source,
                "tag",
                "-a",
                "v9.9.9",
                "-m",
                "fixture tag",
                reproducible_commit,
            )
            canonical_url = (
                "https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL.git"
            )
            git_at(reproducible_source, "remote", "add", "origin", canonical_url)
            reproducible_artifact_dir = root / "reproducible-artifact"
            reproducible_artifact_dir.mkdir()
            reproducible_artifact = reproducible_artifact_dir / "dircreative-9.9.9.tar.gz"
            shutil.copyfile(
                reproducible_source / "fixture-release.tar.gz", reproducible_artifact
            )
            verify_reproducible_build(
                reproducible_source,
                reproducible_artifact,
                version="9.9.9",
                expected_commit=reproducible_commit,
                expected_hash=sha256_file(reproducible_artifact),
                expected_tag="v9.9.9",
                require_remote_tag=False,
            )
            remote_tag_checks: list[tuple[Path, str, str]] = []

            def record_remote_tag_check(
                checked_source: Path, checked_tag: str, checked_commit: str
            ) -> None:
                remote_tag_checks.append(
                    (checked_source, checked_tag, checked_commit)
                )

            canonicalization_checks: list[tuple[str, str]] = []

            def record_canonicalization(rebuilt: Path, output: Path) -> None:
                canonicalization_checks.append((rebuilt.name, output.name))
                shutil.copyfile(rebuilt, output)

            verify_reproducible_build(
                reproducible_source,
                reproducible_artifact,
                version="9.9.9",
                expected_commit=reproducible_commit,
                expected_hash=sha256_file(reproducible_artifact),
                expected_tag="v9.9.9",
                require_remote_tag=True,
                _remote_tag_verifier=record_remote_tag_check,
                _canonicalizer=record_canonicalization,
            )
            if remote_tag_checks != [
                (reproducible_source, "v9.9.9", reproducible_commit)
            ]:
                raise AssertionError(
                    "canonical reproducible rebuild skipped remote tag verification"
                )
            if canonicalization_checks != [
                ("dircreative-9.9.9.tar.gz", "dircreative-9.9.9.tar.gz")
            ]:
                raise AssertionError(
                    "canonical reproducible rebuild skipped deterministic metadata normalization"
                )
            forged_artifact_dir = root / "forged-artifact"
            forged_artifact_dir.mkdir()
            forged_artifact = forged_artifact_dir / "dircreative-9.9.9.tar.gz"
            forged_artifact.write_bytes(b"forged artifact with a matching attacker checksum\n")
            try:
                verify_reproducible_build(
                    reproducible_source,
                    forged_artifact,
                    version="9.9.9",
                    expected_commit=reproducible_commit,
                    expected_hash=sha256_file(forged_artifact),
                    expected_tag="v9.9.9",
                    require_remote_tag=False,
                )
            except ValueError as exc:
                if "does not match the reproducible exact-commit build" not in str(exc):
                    raise
            else:
                raise AssertionError("forged artifact survived exact-commit rebuild matching")
            (reproducible_source / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            try:
                verify_reproducible_build(
                    reproducible_source,
                    reproducible_artifact,
                    version="9.9.9",
                    expected_commit=reproducible_commit,
                    expected_hash=sha256_file(reproducible_artifact),
                    expected_tag="v9.9.9",
                    require_remote_tag=False,
                )
            except ValueError as exc:
                if "worktree is not clean" not in str(exc):
                    raise
            else:
                raise AssertionError("reproducible verification accepted a dirty source")
            (reproducible_source / "untracked.txt").unlink()
            git_at(reproducible_source, "remote", "set-url", "origin", "https://example.com/other.git")
            try:
                verify_reproducible_build(
                    reproducible_source,
                    reproducible_artifact,
                    version="9.9.9",
                    expected_commit=reproducible_commit,
                    expected_hash=sha256_file(reproducible_artifact),
                    expected_tag="v9.9.9",
                    require_remote_tag=False,
                )
            except ValueError as exc:
                if "origin is not the canonical" not in str(exc):
                    raise
            else:
                raise AssertionError("reproducible verification accepted a noncanonical source")
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
            Path(os.path.abspath(Path(args.artifact).expanduser())),
            Path(os.path.abspath(Path(args.checksums).expanduser())),
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
