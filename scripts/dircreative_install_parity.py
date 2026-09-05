#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dircreative_package_layout import (
    PACKAGE_ITEMS,
    PACKAGE_RUNTIME_FILES,
    ROOT_SKILL_RUNTIME_DIRS,
    runtime_source_bytes,
    sanitize_package_bytes,
    should_ignore,
)
from dircreative_release_preflight import EXPECTED_ORIGIN_SLUG, github_slug


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / ".codex" / "dev-skills" / "dircreative"
FORMAL_INSTALL_TARGETS = (
    Path.home() / ".codex" / "skills" / "dircreative",
    Path.home() / ".skillshub" / "dircreative",
)
RELEASE_METADATA_NAME = "RELEASE-METADATA.json"
RELEASE_METADATA_FIELDS = {
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
RELEASE_STATUSES = {"UNPUBLISHED_LOCAL_CANDIDATE", "CANONICAL_REMOTE_TAG"}
INTERNAL_SKILL_FILE = "INTERNAL_SKILL.md"
IGNORED_TARGET_DIR_NAMES = {"__pycache__"}
IGNORED_TARGET_FILE_NAMES = {".DS_Store"}
IGNORED_TARGET_EXTENSIONS = {".pyc", ".pyo"}


@dataclass(frozen=True)
class InstalledRuntimeVerification:
    required: bool
    ok: bool
    source_root: Path | None = None
    install_target: Path | None = None
    errors: tuple[str, ...] = ()
    parity_output: str = ""

    @property
    def evidence(self) -> str:
        if not self.required:
            return "installation verification not requested; global installation was not inspected"
        location = f"{self.install_target} against independent source {self.source_root}"
        return location + ("; " + "; ".join(self.errors) if self.errors else "; identity, activation policy and package parity verified")


def add_installed_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--require-installed", action="store_true", help="Verify the selected installation against independent canonical source.")
    parser.add_argument("--install-target", "--target", dest="install_target", type=Path,
                        help="Installation to verify; defaults to the formal Codex installation only when required.")
    parser.add_argument("--source-root", type=Path,
                        help="Independent source checkout. Required when this command runs from an installed package.")
    parser.add_argument("--verify-remote-tag", action="store_true",
                        help="Explicitly verify canonical remote tag metadata during installed parity.")


def installed_runtime_cli_args(args: argparse.Namespace) -> list[str]:
    if not args.require_installed:
        return []
    flags = ["--require-installed"]
    if args.install_target is not None:
        flags.extend(["--install-target", str(args.install_target.expanduser().resolve())])
    if args.source_root is not None:
        flags.extend(["--source-root", str(args.source_root.expanduser().resolve())])
    if args.verify_remote_tag:
        flags.append("--verify-remote-tag")
    return flags


def _installed_identity_errors(target: Path) -> list[str]:
    """Read actual Skill identity and host activation metadata, not prose headings."""
    try:
        skill = target / "SKILL.md"
        policy = target / "agents/openai.yaml"
        if any(path.is_symlink() or not path.is_file() for path in (skill, policy)):
            return ["installed root Skill and activation policy must be regular files"]
        if skill.stat().st_size > 65536 or policy.stat().st_size > 65536:
            return ["installed identity metadata exceeds its read limit"]
        text = skill.read_text(encoding="utf-8")
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
        if match is None:
            return ["installed root Skill frontmatter is missing"]
        ruby = (
            "require 'yaml'; require 'json'; raw = JSON.parse(STDIN.read); "
            "puts JSON.generate(raw.transform_values { |text| YAML.safe_load(text, permitted_classes: [], aliases: false) })"
        )
        proc = subprocess.run(["ruby", "-e", ruby],
                              input=json.dumps({"skill": match.group(1), "activation": policy.read_text(encoding="utf-8")}),
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            return ["installed identity or activation YAML is invalid"]
        records = json.loads(proc.stdout)
        metadata, activation = records.get("skill"), records.get("activation")
        if not isinstance(metadata, dict) or metadata.get("name") != "dircreative" or not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
            return ["installed Skill identity must be dircreative with a nonempty description"]
        if not isinstance(activation, dict):
            return ["installed activation policy must be a mapping"]
        gate = activation.get("policy", {})
        interface = activation.get("interface", {})
        if not isinstance(gate, dict) or gate.get("allow_implicit_invocation") is not False:
            return ["installed activation policy must disable implicit invocation"]
        prompt = interface.get("default_prompt") if isinstance(interface, dict) else None
        if not isinstance(prompt, str) or re.search(r"\$dircreative(?![A-Za-z0-9_-])", prompt) is None:
            return ["installed default prompt must explicitly invoke $dircreative"]
    except (OSError, UnicodeDecodeError, ValueError):
        return ["installed identity metadata could not be read"]
    return []


def verify_installed_runtime(
    *, required: bool, source_root: Path | None = None, install_target: Path | None = None,
    verify_remote_tag: bool = False, caller_root: Path = ROOT,
) -> InstalledRuntimeVerification:
    # Source-only audits must not probe or validate an unrelated global install.
    if not required:
        return InstalledRuntimeVerification(required=False, ok=True)
    target = (install_target if install_target is not None else Path.home() / ".codex/skills/dircreative").expanduser().resolve()
    source = (source_root if source_root is not None else caller_root).expanduser().resolve()
    if source == target or installed_layout(source):
        return InstalledRuntimeVerification(True, False, source, target,
            ("independent source required: supply --source-root pointing to the canonical source checkout; an installed copy cannot certify itself",))
    if not (source / "skills/dircreative/SKILL.md").is_file():
        return InstalledRuntimeVerification(True, False, source, target,
            ("independent source checkout is missing its root Skill; supply a valid --source-root",))
    verifier = source / "scripts/dircreative_install_parity.py"
    if (source / "scripts").is_symlink() or verifier.is_symlink() or not verifier.is_file():
        return InstalledRuntimeVerification(True, False, source, target,
            ("independent source verifier is missing or not a regular source file",))
    identity_errors = _installed_identity_errors(target)
    if identity_errors:
        return InstalledRuntimeVerification(True, False, source, target, tuple(identity_errors))
    command = [sys.executable, "-B", str(verifier), "--target", str(target), "--source-root", str(source)]
    if verify_remote_tag:
        command.append("--verify-remote-tag")
    try:
        proc = subprocess.run(command, cwd=source, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        return InstalledRuntimeVerification(True, False, source, target, (f"independent parity could not run: {exc}",))
    output = (proc.stdout + "\n" + proc.stderr).strip()
    ok = proc.returncode == 0 and "INSTALL_PARITY: PASS" in output.splitlines()
    errors = () if ok else tuple(["independent installed parity failed", *[line[2:] for line in output.splitlines() if line.startswith("- ")][:3]])
    return InstalledRuntimeVerification(True, ok, source, target, errors, output)


def path_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def resolve_default_target() -> Path:
    for candidate in (*FORMAL_INSTALL_TARGETS, DEFAULT_TARGET):
        if path_entry_exists(candidate):
            return candidate
    return DEFAULT_TARGET


def installed_layout(base: Path) -> bool:
    return (base / "SKILL.md").exists() and not (base / "skills" / "dircreative" / "SKILL.md").exists()


def root_skill_source(base: Path) -> Path:
    source_layout = base / "skills" / "dircreative" / "SKILL.md"
    if source_layout.exists():
        return source_layout
    installed_root = base / "SKILL.md"
    if installed_root.exists():
        return installed_root
    return source_layout


def strip_skill_frontmatter_bytes(data: bytes) -> bytes:
    marker = b"---\n"
    if not data.startswith(marker):
        return data
    end = data.find(b"\n---\n", len(marker))
    if end == -1:
        return data
    return data[end + len(b"\n---\n") :].lstrip(b"\n")


def file_hash(path: Path, *, strip_skill_frontmatter: bool = False) -> str:
    digest = hashlib.sha256()
    data = path.read_bytes()
    if strip_skill_frontmatter:
        data = strip_skill_frontmatter_bytes(data)
    digest.update(data)
    return digest.hexdigest()


def bytes_hash(data: bytes, *, strip_skill_frontmatter: bool = False) -> str:
    if strip_skill_frontmatter:
        data = strip_skill_frontmatter_bytes(data)
    return hashlib.sha256(data).hexdigest()


def installed_manifest_key(item: str, relative_path: Path) -> str:
    parts = relative_path.parts
    if item == "skills" and parts and parts[-1] == INTERNAL_SKILL_FILE:
        relative_path = Path(*parts[:-1], "SKILL.md")
    return f"{item}/{relative_path.as_posix()}"


def collect_files(
    base: Path,
    item: str,
    *,
    installed: bool = False,
    thread_ids: dict[str, str] | None = None,
) -> dict[str, str]:
    root = base / item
    if not root.exists():
        return {}
    if root.is_file():
        mapping = thread_ids if thread_ids is not None else {}
        data = root.read_bytes() if installed else sanitize_package_bytes(item, root.read_bytes(), mapping)
        return {item: bytes_hash(data)}
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not should_ignore(path.relative_to(root)):
            relative_path = path.relative_to(root)
            key = installed_manifest_key(item, relative_path) if installed else f"{item}/{relative_path.as_posix()}"
            strip_frontmatter = item == "skills" and relative_path.name in {"SKILL.md", INTERNAL_SKILL_FILE}
            mapping = thread_ids if thread_ids is not None else {}
            data = path.read_bytes() if installed else sanitize_package_bytes(key, path.read_bytes(), mapping)
            files[key] = bytes_hash(data, strip_skill_frontmatter=strip_frontmatter)
    return files


def package_manifest(
    base: Path,
    *,
    installed: bool = False,
    thread_ids: dict[str, str] | None = None,
) -> dict[str, str]:
    manifest: dict[str, str] = {}
    mapping = thread_ids if thread_ids is not None else {}
    for item in PACKAGE_ITEMS:
        manifest.update(collect_files(base, item, installed=installed, thread_ids=mapping))
    for relative in sorted(PACKAGE_RUNTIME_FILES):
        path = base / relative
        if not path.exists():
            continue
        data = path.read_bytes() if installed else runtime_source_bytes(base, relative, mapping)
        manifest[relative] = bytes_hash(data)
    return manifest


def root_skill_hash(base: Path, thread_ids: dict[str, str] | None = None) -> str:
    source = root_skill_source(base)
    data = source.read_bytes()
    if not installed_layout(base):
        data = sanitize_package_bytes("SKILL.md", data, thread_ids if thread_ids is not None else {})
    return bytes_hash(data)


def root_runtime_manifest(
    base: Path,
    *,
    installed: bool,
    thread_ids: dict[str, str],
) -> dict[str, str]:
    source_root = root_skill_source(base).parent
    manifest: dict[str, str] = {}
    for directory in ROOT_SKILL_RUNTIME_DIRS:
        root = source_root / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or should_ignore(path.relative_to(root)):
                continue
            relative = path.relative_to(root)
            key = f"{directory}/{relative.as_posix()}"
            data = path.read_bytes()
            if not installed:
                data = sanitize_package_bytes(key, data, thread_ids)
            manifest[key] = bytes_hash(data)
    return manifest


def expected_manifest(base: Path) -> dict[str, str]:
    installed = installed_layout(base)
    thread_ids: dict[str, str] = {}
    manifest = package_manifest(base, installed=installed, thread_ids=thread_ids)
    manifest["SKILL.md"] = root_skill_hash(base, thread_ids)
    agent_policy = (
        base / "agents/openai.yaml"
        if installed
        else base / "skills/dircreative/agents/openai.yaml"
    )
    if agent_policy.is_file():
        data = agent_policy.read_bytes()
        if not installed:
            data = sanitize_package_bytes("agents/openai.yaml", data, thread_ids)
        manifest["agents/openai.yaml"] = bytes_hash(data)
    manifest.update(
        root_runtime_manifest(
            base,
            installed=installed,
            thread_ids=thread_ids,
        )
    )
    metadata = base / RELEASE_METADATA_NAME
    if metadata.is_file():
        manifest[RELEASE_METADATA_NAME] = file_hash(metadata)
    return manifest


def source_commit_sha(source_root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


def source_checkout_clean(source_root: Path) -> bool:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(source_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode == 0 and not proc.stdout


def source_commit_timestamp(source_root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(source_root), "show", "-s", "--format=%ct", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip().isdigit():
        return None
    return datetime.fromtimestamp(
        int(proc.stdout.strip()), tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")


def verify_canonical_source_refs(
    source_root: Path, tag: str, commit: str
) -> list[str]:
    failures: list[str] = []
    for arguments, label in (
        (("remote", "get-url", "origin"), "origin"),
        (("remote", "get-url", "--push", "origin"), "origin push URL"),
    ):
        proc = subprocess.run(
            ["git", "-C", str(source_root), *arguments],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0 or github_slug(proc.stdout.strip()) != EXPECTED_ORIGIN_SLUG:
            failures.append(
                f"invalid installed release metadata: {label} is not canonical"
            )
    remote = subprocess.run(
        [
            "git",
            "-C",
            str(source_root),
            "ls-remote",
            "origin",
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if remote.returncode != 0:
        return [
            *failures,
            "invalid installed release metadata: canonical remote refs unavailable",
        ]
    refs: dict[str, str] = {}
    for line in remote.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            refs[parts[1]] = parts[0]
    return [*failures, *validate_canonical_tag_refs(refs, tag, commit)]


def validate_canonical_tag_refs(
    refs: dict[str, str], tag: str, commit: str
) -> list[str]:
    if (
        f"refs/tags/{tag}" not in refs
        or refs.get(f"refs/tags/{tag}^{{}}") != commit
    ):
        return [
            "invalid installed release metadata: annotated canonical remote tag mismatch"
        ]
    return []


def validate_external_release_metadata(
    source_root: Path,
    target: Path,
    *,
    verify_remote_tag: bool = False,
) -> tuple[set[str], list[str]]:
    """Allow only a current, hash-bound release metadata sidecar on a source checkout."""
    source_metadata = source_root / RELEASE_METADATA_NAME
    target_metadata = target / RELEASE_METADATA_NAME
    if path_entry_exists(source_metadata) or not path_entry_exists(target_metadata):
        return set(), []

    allowed = {RELEASE_METADATA_NAME}
    if target_metadata.is_symlink() or not target_metadata.is_file():
        return allowed, ["invalid installed release metadata: must be a regular file"]
    try:
        payload = json.loads(target_metadata.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return allowed, [f"invalid installed release metadata: {exc}"]
    if not isinstance(payload, dict):
        return allowed, ["invalid installed release metadata: expected an object"]

    version = (source_root / "VERSION").read_text(encoding="utf-8").strip()
    expected_commit = source_commit_sha(source_root)
    expected_timestamp = source_commit_timestamp(source_root)
    expected_root_hash = file_hash(target / "SKILL.md") if (target / "SKILL.md").is_file() else None
    required = {
        "schema_version": "1.1.0",
        "product": "DIRcreative",
        "version": version,
        "tag": f"v{version}",
        "source": "git archive of exact commit",
    }
    failures: list[str] = []
    if not source_checkout_clean(source_root):
        failures.append(
            "invalid installed release metadata: source checkout is dirty or not a Git worktree"
        )
    if set(payload) != RELEASE_METADATA_FIELDS:
        failures.append("invalid installed release metadata: field set mismatch")
    for key, expected in required.items():
        if payload.get(key) != expected:
            failures.append(f"invalid installed release metadata: {key} mismatch")
    if expected_commit is None or payload.get("commit_sha") != expected_commit:
        failures.append("invalid installed release metadata: commit_sha does not match source HEAD")
    if expected_root_hash is None or payload.get("root_skill_sha256") != expected_root_hash:
        failures.append("invalid installed release metadata: root_skill_sha256 does not match installed SKILL.md")
    timestamp = payload.get("commit_timestamp")
    if expected_timestamp is None or timestamp != expected_timestamp:
        failures.append(
            "invalid installed release metadata: commit_timestamp does not match source commit"
        )
    if payload.get("release_status") not in RELEASE_STATUSES:
        failures.append("invalid installed release metadata: release_status is invalid")
    elif payload.get("release_status") == "CANONICAL_REMOTE_TAG":
        if not verify_remote_tag:
            failures.append(
                "invalid installed release metadata: CANONICAL_REMOTE_TAG requires remote tag verification"
            )
        elif expected_commit is not None:
            failures.extend(
                verify_canonical_source_refs(
                    source_root, str(payload.get("tag", "")), expected_commit
                )
            )
    return allowed, failures


def ignored_target_path(relative: Path) -> bool:
    return (
        any(part in IGNORED_TARGET_DIR_NAMES for part in relative.parts)
        or relative.name in IGNORED_TARGET_FILE_NAMES
        or relative.suffix in IGNORED_TARGET_EXTENSIONS
    )


def collect_target_manifest(base: Path) -> tuple[dict[str, str], list[str]]:
    manifest: dict[str, str] = {}
    invalid_entries: list[str] = []
    seen_inodes: dict[tuple[int, int], str] = {}
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base)
        label = relative.as_posix()
        if path.is_symlink():
            invalid_entries.append(f"symlink:{label}")
            continue
        if ignored_target_path(relative):
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            invalid_entries.append(f"non_regular:{label}")
            continue
        stat_result = path.stat(follow_symlinks=False)
        if stat_result.st_nlink != 1:
            invalid_entries.append(f"hardlink_or_reused_inode:{label}:nlink={stat_result.st_nlink}")
            continue
        inode = (stat_result.st_dev, stat_result.st_ino)
        if inode in seen_inodes:
            invalid_entries.append(
                f"duplicate_physical_file:{seen_inodes[inode]}:{label}"
            )
            continue
        seen_inodes[inode] = label
        key = (
            relative.as_posix()
            if len(relative.parts) == 1
            else installed_manifest_key(relative.parts[0], Path(*relative.parts[1:]))
        )
        strip_frontmatter = relative.parts[0] == "skills" and relative.name == INTERNAL_SKILL_FILE
        if key in manifest:
            invalid_entries.append(f"duplicate_normalized_path:{key}")
            continue
        manifest[key] = file_hash(path, strip_skill_frontmatter=strip_frontmatter)
    return manifest, invalid_entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify installed DIRcreative skill matches the source package.")
    parser.add_argument(
        "--target",
        default=str(resolve_default_target()),
        help="Installed local skill directory; defaults to the current formal Codex install when present.",
    )
    parser.add_argument(
        "--source-root",
        default=str(ROOT),
        help="Canonical source checkout used as the independent comparison root.",
    )
    parser.add_argument(
        "--verify-remote-tag",
        action="store_true",
        help="For CANONICAL_REMOTE_TAG metadata, verify canonical origin and annotated remote tag.",
    )
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    source_root = Path(args.source_root).expanduser().resolve()
    if source_root == target or installed_layout(source_root):
        print("DIRcreative Install Parity")
        print("=" * 72)
        print(f"source: {source_root}")
        print(f"target: {target}")
        print("INSTALL_PARITY: FAIL")
        print(
            "- independent source required: an installed copy cannot certify itself; "
            "compare against a source checkout or use verified-artifact installation"
        )
        return 1
    source_manifest = expected_manifest(source_root)
    target_manifest, invalid_entries = collect_target_manifest(target)
    failures: list[str] = []
    metadata_extras, metadata_failures = validate_external_release_metadata(
        source_root, target, verify_remote_tag=args.verify_remote_tag
    )
    failures.extend(metadata_failures)

    if invalid_entries:
        failures.append("invalid installed entries: " + ", ".join(invalid_entries[:20]))

    exposed_internal_skills = sorted(
        path.relative_to(target).as_posix()
        for path in (target / "skills").rglob("SKILL.md")
        if path.is_file()
    )
    if exposed_internal_skills:
        failures.append("exposed internal skill files: " + ", ".join(exposed_internal_skills[:20]))

    missing = sorted(set(source_manifest) - set(target_manifest))
    extra = sorted((set(target_manifest) - set(source_manifest)) - metadata_extras)
    changed = sorted(
        path for path in set(source_manifest).intersection(target_manifest) if source_manifest[path] != target_manifest[path]
    )

    if missing:
        failures.append("missing installed files: " + ", ".join(missing[:20]))
    if extra:
        failures.append("extra installed files: " + ", ".join(extra[:20]))
    if changed:
        failures.append("changed installed files: " + ", ".join(changed[:20]))

    source_root_skill = root_skill_source(source_root)
    installed_root_skill = target / "SKILL.md"
    if not installed_root_skill.exists():
        failures.append("missing installed root SKILL.md")
    elif bytes_hash(
        source_root_skill.read_bytes()
        if installed_layout(source_root)
        else sanitize_package_bytes("SKILL.md", source_root_skill.read_bytes(), {})
    ) != file_hash(installed_root_skill):
        failures.append("installed root SKILL.md differs from source root DIRcreative SKILL.md")

    print("DIRcreative Install Parity")
    print("=" * 72)
    print(f"source: {source_root}")
    print(f"target: {target}")
    print(f"source_files: {len(source_manifest)}")
    print(f"target_files: {len(target_manifest)}")
    if failures:
        print("INSTALL_PARITY: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("INSTALL_PARITY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
