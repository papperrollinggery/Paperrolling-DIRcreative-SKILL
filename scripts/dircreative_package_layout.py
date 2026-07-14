#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ITEMS = [
    "README.md",
    "VERSION",
    "CHANGELOG.md",
    "docs",
    "examples",
    "scripts",
    "skills",
    "tests",
]

PACKAGE_RUNTIME_FILES = [
    ".dircreative/checkpoints/.keep",
    ".dircreative/runs/.keep",
]

IGNORE_NAMES = {".git", "__pycache__", ".DS_Store", "build", "dist"}
IGNORED_EXTENSIONS = {".pyc", ".pyo"}
THREAD_ID_RE = re.compile(
    r"\b019[a-f0-9]{5}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b",
    re.IGNORECASE,
)
_BACKSLASH_RE = re.escape(chr(92))
_SLASH_RE = re.escape("/")
_SEPARATOR_RE = rf"(?:{_BACKSLASH_RE}|{_SLASH_RE})+"
_PATH_COMPONENT_RE = r"[^\x5c/\r\n\"']+"
_UNC_HOST_COMPONENT_RE = r"[A-Za-z0-9][A-Za-z0-9._$ -]*"
_PATH_START_BOUNDARY_RE = r"(?<![A-Za-z0-9._~:/-])"
_WINDOWS_HOME_RE = rf"[A-Za-z]:{_SEPARATOR_RE}Users{_SEPARATOR_RE}{_PATH_COMPONENT_RE}"
_POSIX_HOME_RE = (
    rf"{_PATH_START_BOUNDARY_RE}{_SLASH_RE}(?:Users|home){_SLASH_RE}{_PATH_COMPONENT_RE}"
)
_ROOT_HOME_RE = (
    rf"{_PATH_START_BOUNDARY_RE}{_SLASH_RE}(?:(?:private{_SLASH_RE})?var{_SLASH_RE})?root"
)
_WSL_DRIVE_HOME_RE = (
    rf"{_PATH_START_BOUNDARY_RE}{_SLASH_RE}mnt{_SLASH_RE}[A-Za-z]{_SLASH_RE}"
    rf"Users{_SLASH_RE}{_PATH_COMPONENT_RE}"
)
_WSL_UNC_HOME_RE = (
    rf"(?<!:)(?:{_BACKSLASH_RE}{{2,}}|{_SLASH_RE}{{2,}})"
    rf"(?:wsl\$|wsl\.localhost){_SEPARATOR_RE}{_PATH_COMPONENT_RE}{_SEPARATOR_RE}"
    rf"(?:home{_SEPARATOR_RE}{_PATH_COMPONENT_RE}|root)"
)
_UNC_HOME_RE = (
    rf"(?<!:)(?:{_BACKSLASH_RE}{{2,}}|{_SLASH_RE}{{2,}})"
    rf"(?!u[0-9a-fA-F]{{4}}{_SEPARATOR_RE})"
    rf"{_UNC_HOST_COMPONENT_RE}{_SEPARATOR_RE}{_UNC_HOST_COMPONENT_RE}{_SEPARATOR_RE}"
    rf"(?:Users{_SEPARATOR_RE})?{_PATH_COMPONENT_RE}"
)
HOST_USER_PATH_RE = re.compile(
    rf"(?:{_WINDOWS_HOME_RE}|{_WSL_DRIVE_HOME_RE}|{_WSL_UNC_HOME_RE}|"
    rf"{_POSIX_HOME_RE}|{_ROOT_HOME_RE}|{_UNC_HOME_RE})",
    re.IGNORECASE,
)
USER_HOME_RE = HOST_USER_PATH_RE
SANITIZED_FIXTURE_HEADER = "# Sanitized release fixture; no live acceptance or host-state authority.\n"


def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_NAMES for part in path.parts) or path.suffix in IGNORED_EXTENSIONS


def runtime_source_bytes(
    root: Path,
    relative: str,
    thread_ids: dict[str, str],
) -> bytes:
    data = (root / relative).read_bytes()
    return sanitize_package_bytes(relative, data, thread_ids, runtime_fixture=True)


def sanitize_package_bytes(
    relative: str,
    data: bytes,
    thread_ids: dict[str, str],
    *,
    runtime_fixture: bool = False,
) -> bytes:
    if not data:
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    text = HOST_USER_PATH_RE.sub("/opt/dircreative-fixture", text)

    def replace_thread_id(match: re.Match[str]) -> str:
        value = match.group(0)
        if value not in thread_ids:
            thread_ids[value] = f"00000000-0000-7000-8000-{len(thread_ids) + 1:012x}"
        return thread_ids[value]

    text = THREAD_ID_RE.sub(replace_thread_id, text)
    if runtime_fixture and relative.endswith((".yaml", ".yml")) and not text.startswith(SANITIZED_FIXTURE_HEADER):
        text = SANITIZED_FIXTURE_HEADER + text
    return text.encode("utf-8")


def validate_package_sources(root: Path) -> None:
    missing = [item for item in PACKAGE_ITEMS if not (root / item).exists()]
    missing.extend(relative for relative in PACKAGE_RUNTIME_FILES if not (root / relative).exists())
    if missing:
        raise ValueError("missing package sources: " + ", ".join(missing))
