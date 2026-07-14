#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRESS_FILE = ROOT / "docs" / "film-preproduction" / "current-project-progress.md"


def git_output(args: list[str], default_empty: str = "unknown") -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return "unknown"
    return proc.stdout.strip() or default_empty


def read_progress() -> dict[str, str]:
    progress: dict[str, str] = {}
    for line in PROGRESS_FILE.read_text(encoding="utf-8").splitlines():
        if ":" not in line or line.startswith("#"):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key:
            progress[key] = value
    return progress


def main() -> int:
    progress = read_progress()
    latest_commit = git_output(["rev-parse", "--short", "HEAD"])
    branch = git_output(["branch", "--show-current"])
    status = git_output(["status", "--short"], default_empty="")
    worktree_state = "dirty" if status else "clean"

    print("DIRcreative Progress Report")
    print("=" * 72)
    print(f"completion_estimate_percent: {progress.get('completion_estimate_percent', 'unknown')}")
    print(f"technical_readiness: {progress.get('technical_readiness', 'unknown')}")
    print(f"objective_complete: {progress.get('objective_complete', 'unknown')}")
    print(f"remaining_blocker: {progress.get('remaining_blocker', 'unknown')}")
    print(f"estimated_remaining_time: {progress.get('estimated_remaining_time', 'unknown')}")
    print(f"latest_commit: {latest_commit}")
    print(f"branch: {branch}")
    print(f"worktree_state: {worktree_state}")
    print("next_required_action: run a real chat acceptance pass; do not treat goal-mode simulation as user approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
