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
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_bytes(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.decode("utf-8", errors="replace").strip())
    return proc.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remove_release_outputs(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def candidate_still_valid(
    candidate: str,
    preflight_cmd: list[str],
    *,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = run,
    git_reader: Callable[..., bytes] = git_bytes,
) -> tuple[bool, str]:
    postflight = runner(preflight_cmd)
    diagnostics = postflight.stdout + postflight.stderr
    if postflight.returncode != 0:
        return False, diagnostics
    try:
        current_head = git_reader("rev-parse", "HEAD").decode().strip()
    except (ValueError, UnicodeDecodeError) as exc:
        return False, diagnostics + f"post-build HEAD capture failed: {exc}\n"
    if current_head != candidate:
        return False, diagnostics + "post-build HEAD differs from sealed commit\n"
    return True, diagnostics


def sealed_candidate(expected_commit: str | None, current_head: str) -> str:
    expected = (expected_commit or "").strip()
    if expected and not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ValueError("--expected-commit must be one full lowercase 40-character commit SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", current_head):
        raise ValueError("HEAD is not one full lowercase commit SHA")
    candidate = expected or current_head
    if current_head != candidate:
        raise ValueError("HEAD changed before build or does not equal --expected-commit")
    return candidate


def resolve_release_status(
    *,
    require_tag: bool,
    allow_unpublished: bool,
) -> str:
    if require_tag == allow_unpublished:
        raise ValueError(
            "choose exactly one release mode: --require-tag or --allow-unpublished"
        )
    return "CANONICAL_REMOTE_TAG" if require_tag else "UNPUBLISHED_LOCAL_CANDIDATE"


def self_test() -> int:
    candidate = "a" * 40
    swapped = "b" * 40
    passed = subprocess.CompletedProcess(["preflight"], 0, "RELEASE_PREFLIGHT: PASS\n", "")
    valid, _ = candidate_still_valid(
        candidate,
        ["preflight"],
        runner=lambda _cmd: passed,
        git_reader=lambda *_args: f"{swapped}\n".encode(),
    )
    if valid:
        print("RELEASE_BUILD_SELF_TEST: FAIL_HEAD_SWAP_ACCEPTED")
        return 1
    failed = subprocess.CompletedProcess(["preflight"], 1, "RELEASE_PREFLIGHT: FAIL\n", "")
    valid, _ = candidate_still_valid(
        candidate,
        ["preflight"],
        runner=lambda _cmd: failed,
        git_reader=lambda *_args: f"{candidate}\n".encode(),
    )
    if valid:
        print("RELEASE_BUILD_SELF_TEST: FAIL_POSTFLIGHT_ACCEPTED")
        return 1
    try:
        sealed_candidate(candidate, swapped)
    except ValueError:
        pass
    else:
        print("RELEASE_BUILD_SELF_TEST: FAIL_EXPECTED_COMMIT_SWAP_ACCEPTED")
        return 1
    try:
        sealed_candidate("A" * 40, candidate)
    except ValueError:
        pass
    else:
        print("RELEASE_BUILD_SELF_TEST: FAIL_NONCANONICAL_COMMIT_ACCEPTED")
        return 1
    mode_cases = (
        (False, False, None),
        (True, True, None),
        (False, True, "UNPUBLISHED_LOCAL_CANDIDATE"),
        (True, False, "CANONICAL_REMOTE_TAG"),
    )
    for require_tag, allow_unpublished, expected in mode_cases:
        try:
            actual = resolve_release_status(
                require_tag=require_tag,
                allow_unpublished=allow_unpublished,
            )
        except ValueError:
            actual = None
        if actual != expected:
            print("RELEASE_BUILD_SELF_TEST: FAIL_RELEASE_MODE_CONTRACT")
            return 1
    with tempfile.TemporaryDirectory(prefix="dircreative-build-self-test-") as raw:
        artifact = Path(raw) / "artifact.tar.gz"
        checksums = Path(raw) / "SHA256SUMS"
        artifact.write_bytes(b"artifact")
        checksums.write_text("checksum\n", encoding="utf-8")
        remove_release_outputs(artifact, checksums)
        if artifact.exists() or checksums.exists():
            print("RELEASE_BUILD_SELF_TEST: FAIL_STALE_OUTPUTS")
            return 1
    print("RELEASE_BUILD_SELF_TEST: PASS")
    return 0


def safe_extract(archive: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve(strict=False)
            try:
                target.relative_to(destination.resolve())
            except ValueError as exc:
                raise ValueError(f"git archive member escapes extraction root: {member.name}") from exc
            if member.issym() or member.islnk():
                raise ValueError(f"git archive link is not allowed in release source: {member.name}")
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"git archive member type is not allowed: {member.name}")
        for member in tar.getmembers():
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(0o755)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise ValueError(f"cannot read git archive member: {member.name}")
            with target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o755 if member.mode & 0o111 else 0o644)


def add_tree_to_tar(tar: tarfile.TarFile, root: Path, arc_root: str, mtime: int) -> None:
    paths = [root, *sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())]
    for path in paths:
        relative = path.relative_to(root)
        arcname = arc_root if not relative.parts else f"{arc_root}/{relative.as_posix()}"
        info = tar.gettarinfo(str(path), arcname=arcname)
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mtime = mtime
        info.mode = 0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644
        if path.is_file():
            with path.open("rb") as handle:
                tar.addfile(info, handle)
        else:
            tar.addfile(info)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a reproducible DIRcreative release package from one sealed commit.")
    parser.add_argument("--output-dir", default="dist", help="Output directory, relative to repository root by default.")
    parser.add_argument("--require-tag", action="store_true", help="Require v<VERSION> to point to the sealed commit.")
    parser.add_argument("--allow-unpublished", action="store_true", help="CI only: skip main/origin equality, but still require a clean tree.")
    parser.add_argument(
        "--expected-commit",
        help="Full lowercase commit SHA sealed by the caller; HEAD must match before and after build.",
    )
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    try:
        release_status = resolve_release_status(
            require_tag=args.require_tag,
            allow_unpublished=args.allow_unpublished,
        )
    except ValueError as exc:
        print(f"RELEASE_BUILD: FAIL_MODE ({exc})")
        return 1

    try:
        current_head = git_bytes("rev-parse", "HEAD").decode().strip()
        candidate = sealed_candidate(args.expected_commit, current_head)
    except (ValueError, UnicodeDecodeError) as exc:
        print(f"RELEASE_BUILD: FAIL_CANDIDATE ({exc})")
        return 1

    preflight_cmd = [
        "python3",
        "scripts/dircreative_release_preflight.py",
        "--expected-commit",
        candidate,
    ]
    if args.require_tag:
        preflight_cmd.append("--require-tag")
    if args.allow_unpublished:
        preflight_cmd.append("--allow-unpublished")
    preflight = run(preflight_cmd)
    if preflight.returncode != 0:
        print(preflight.stdout, end="")
        print(preflight.stderr, end="")
        print("RELEASE_BUILD: FAIL_PRECHECK")
        return 1

    try:
        version = git_bytes("show", f"{candidate}:VERSION").decode().strip()
        commit_timestamp = int(git_bytes("show", "-s", "--format=%ct", candidate).decode().strip())
    except (ValueError, UnicodeDecodeError) as exc:
        print(f"RELEASE_BUILD: FAIL_SEALED_METADATA ({exc})")
        return 1
    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"dircreative-{version}.tar.gz"
    checksums = output_dir / "SHA256SUMS"
    remove_release_outputs(artifact, checksums)

    with tempfile.TemporaryDirectory(prefix="dircreative-release-") as raw:
        temporary = Path(raw)
        snapshot = temporary / "snapshot"
        payload = temporary / f"dircreative-{version}"
        snapshot.mkdir()
        safe_extract(git_bytes("archive", "--format=tar", candidate), snapshot)

        installed = run(
            ["python3", "scripts/install_local_skill.py", "--target", str(payload)],
            cwd=snapshot,
        )
        if installed.returncode != 0:
            remove_release_outputs(artifact, checksums)
            print(installed.stdout, end="")
            print(installed.stderr, end="")
            print("RELEASE_BUILD: FAIL_INSTALL_LAYOUT")
            return 1

        parity = run(
            ["python3", "scripts/dircreative_install_parity.py", "--target", str(payload)],
            cwd=snapshot,
        )
        if parity.returncode != 0:
            remove_release_outputs(artifact, checksums)
            print(parity.stdout, end="")
            print(parity.stderr, end="")
            print("RELEASE_BUILD: FAIL_PARITY")
            return 1

        root_skill_hash = sha256(payload / "SKILL.md")
        metadata = {
            "schema_version": "1.1.0",
            "product": "DIRcreative",
            "version": version,
            "tag": f"v{version}",
            "commit_sha": candidate,
            "commit_timestamp": datetime.fromtimestamp(commit_timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "root_skill_sha256": root_skill_hash,
            "source": "git archive of exact commit",
            "release_status": release_status,
        }
        (payload / "RELEASE-METADATA.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (payload / "RELEASE-METADATA.json").chmod(0o644)

        if artifact.exists():
            artifact.unlink()
        with tempfile.TemporaryFile(mode="w+b") as raw_tar:
            with tarfile.open(
                fileobj=raw_tar,
                mode="w",
                format=tarfile.USTAR_FORMAT,
            ) as tar:
                add_tree_to_tar(tar, payload, payload.name, commit_timestamp)
            raw_tar.seek(0)
            with artifact.open("wb") as raw_output:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=raw_output,
                    compresslevel=0,
                    mtime=commit_timestamp,
                ) as compressed:
                    for chunk in iter(lambda: raw_tar.read(1024 * 1024), b""):
                        compressed.write(chunk)

    artifact_hash = sha256(artifact)
    checksums.write_text(f"{artifact_hash}  {artifact.name}\n", encoding="utf-8")
    valid, diagnostics = candidate_still_valid(candidate, preflight_cmd)
    if not valid:
        remove_release_outputs(artifact, checksums)
        print(diagnostics, end="")
        print("RELEASE_BUILD: FAIL_POSTCHECK")
        return 1
    print("DIRcreative Release Build")
    print("=" * 72)
    print(f"version: {version}")
    print(f"commit_sha: {candidate}")
    print(f"artifact: {artifact}")
    print(f"artifact_sha256: {artifact_hash}")
    print(f"checksums: {checksums}")
    print("release_source: exact_git_archive")
    print("RELEASE_BUILD: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
