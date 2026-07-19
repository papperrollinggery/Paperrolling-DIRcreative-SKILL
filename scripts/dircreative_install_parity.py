#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from dircreative_package_layout import (
    PACKAGE_ITEMS,
    PACKAGE_RUNTIME_FILES,
    ROOT_SKILL_RUNTIME_DIRS,
    runtime_source_bytes,
    sanitize_package_bytes,
    should_ignore,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / ".codex" / "dev-skills" / "dircreative"
FORMAL_INSTALL_TARGETS = (
    Path.home() / ".codex" / "skills" / "dircreative",
    Path.home() / ".skillshub" / "dircreative",
)
RELEASE_METADATA_NAME = "RELEASE-METADATA.json"
INTERNAL_SKILL_FILE = "INTERNAL_SKILL.md"
IGNORED_TARGET_DIR_NAMES = {"__pycache__"}
IGNORED_TARGET_FILE_NAMES = {".DS_Store"}
IGNORED_TARGET_EXTENSIONS = {".pyc", ".pyo"}


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


def source_commit_sha() -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


def validate_external_release_metadata(target: Path) -> tuple[set[str], list[str]]:
    """Allow only a current, hash-bound release metadata sidecar on a source checkout."""
    source_metadata = ROOT / RELEASE_METADATA_NAME
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

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    expected_commit = source_commit_sha()
    expected_root_hash = file_hash(target / "SKILL.md") if (target / "SKILL.md").is_file() else None
    required = {
        "schema_version": "1.0.0",
        "product": "DIRcreative",
        "version": version,
        "tag": f"v{version}",
        "source": "git archive of exact commit",
    }
    failures: list[str] = []
    for key, expected in required.items():
        if payload.get(key) != expected:
            failures.append(f"invalid installed release metadata: {key} mismatch")
    if expected_commit is None or payload.get("commit_sha") != expected_commit:
        failures.append("invalid installed release metadata: commit_sha does not match source HEAD")
    if expected_root_hash is None or payload.get("root_skill_sha256") != expected_root_hash:
        failures.append("invalid installed release metadata: root_skill_sha256 does not match installed SKILL.md")
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
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    source_manifest = expected_manifest(ROOT)
    target_manifest, invalid_entries = collect_target_manifest(target)
    failures: list[str] = []
    metadata_extras, metadata_failures = validate_external_release_metadata(target)
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

    source_root_skill = root_skill_source(ROOT)
    installed_root_skill = target / "SKILL.md"
    if not installed_root_skill.exists():
        failures.append("missing installed root SKILL.md")
    elif bytes_hash(
        source_root_skill.read_bytes()
        if installed_layout(ROOT)
        else sanitize_package_bytes("SKILL.md", source_root_skill.read_bytes(), {})
    ) != file_hash(installed_root_skill):
        failures.append("installed root SKILL.md differs from source root DIRcreative SKILL.md")

    print("DIRcreative Install Parity")
    print("=" * 72)
    print(f"source: {ROOT}")
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
