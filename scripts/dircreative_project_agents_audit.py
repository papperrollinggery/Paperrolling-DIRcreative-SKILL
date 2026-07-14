#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dircreative_project_agents import ROOT, audit_repo, audit_target, print_audit


sys.dont_write_bytecode = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only DIRcreative project AGENTS.md audit wrapper.")
    parser.add_argument("--target", help="Target project directory to audit.")
    parser.add_argument("--require-active", action="store_true", help="Fail when active AGENTS.md DIRcreative rules are absent or incomplete.")
    parser.add_argument(
        "--require-dircreative-agents",
        action="store_true",
        help="Alias for --require-active.",
    )
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to audit when --target is omitted.")
    parser.add_argument(
        "--implementation-script",
        default="scripts/dircreative_project_agents.py",
        help="Implementation script path relative to repo root.",
    )
    args = parser.parse_args()

    if args.target:
        return print_audit(
            "PROJECT_AGENTS_AUDIT",
            audit_target(Path(args.target), require_active=args.require_active or args.require_dircreative_agents),
        )
    return print_audit("PROJECT_AGENTS_AUDIT", audit_repo(Path(args.repo_root), args.implementation_script))


if __name__ == "__main__":
    raise SystemExit(main())
