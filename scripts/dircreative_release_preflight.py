#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ORIGIN_SLUG = "papperrollinggery/paperrolling-dircreative-skill"


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def github_slug(remote_url: str) -> str | None:
    value = remote_url.strip().rstrip("/")
    if value.startswith("git@github.com:"):
        path = value.removeprefix("git@github.com:")
    else:
        parsed = urlparse(value)
        if (parsed.hostname or "").lower() != "github.com":
            return None
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not re.fullmatch(r"[^/]+/[^/]+", path):
        return None
    return path.lower()


def remote_tag_target(tag: str) -> tuple[str, bool]:
    tag_ref = f"refs/tags/{tag}"
    peeled_ref = f"{tag_ref}^{{}}"
    output = git("ls-remote", "--exit-code", "origin", tag_ref, peeled_ref)
    refs = {
        ref: sha
        for line in output.splitlines()
        if len((parts := line.split())) == 2
        for sha, ref in [parts]
    }
    return refs.get(peeled_ref, ""), tag_ref in refs and peeled_ref in refs


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind a DIRcreative release gate to one clean, published commit.")
    parser.add_argument("--require-tag", action="store_true", help="Require v<VERSION> to resolve to the sealed commit.")
    parser.add_argument("--allow-unpublished", action="store_true", help="CI/development only: skip branch and origin/main equality.")
    parser.add_argument(
        "--expected-commit",
        help="Full commit SHA selected by the caller; HEAD must remain equal to it throughout preflight.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    expected_commit = (args.expected_commit or "").strip().lower()
    if expected_commit and not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        failures.append("--expected-commit must be one full lowercase 40-character commit SHA")
        expected_commit = ""

    head = ""
    sealed_commit = ""
    version = "invalid"
    readme = ""
    branch = ""
    status = ""
    worktrees: list[str] = []
    hidden_index_entries: list[str] = []
    sparse_checkout = False
    try:
        head = git("rev-parse", "HEAD")
        sealed_commit = expected_commit or head
        resolved_commit = git("rev-parse", "--verify", f"{sealed_commit}^{{commit}}")
        if resolved_commit != sealed_commit:
            failures.append("sealed commit does not resolve to the exact requested commit")
        if head != sealed_commit:
            failures.append("HEAD changed before preflight or does not equal --expected-commit")
        version = git("show", f"{sealed_commit}:VERSION").strip()
        readme = git("show", f"{sealed_commit}:README.md")
        branch = git("branch", "--show-current")
    except ValueError as exc:
        failures.append(str(exc))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        failures.append("VERSION at the sealed commit must contain one semantic version")
    if version != "invalid" and f"v{version}" not in readme:
        failures.append(f"README at the sealed commit does not declare v{version}")

    if not args.allow_unpublished:
        if branch != "main":
            failures.append(f"release branch must be main, got {branch or 'detached'}")
        try:
            origin_url = git("remote", "get-url", "origin")
            origin_slug = github_slug(origin_url)
            if origin_slug != EXPECTED_ORIGIN_SLUG:
                raise ValueError(
                    "origin must be the canonical DIRcreative repository "
                    f"({EXPECTED_ORIGIN_SLUG}), got {origin_slug or origin_url}"
                )
            origin_push_url = git("remote", "get-url", "--push", "origin")
            origin_push_slug = github_slug(origin_push_url)
            if origin_push_slug != EXPECTED_ORIGIN_SLUG:
                raise ValueError(
                    "origin push URL must be the canonical DIRcreative repository "
                    f"({EXPECTED_ORIGIN_SLUG}), got {origin_push_slug or origin_push_url}"
                )
            git(
                "fetch",
                "--quiet",
                "--prune",
                "--tags",
                "origin",
                "refs/heads/main:refs/remotes/origin/main",
            )
            remote_head = git("rev-parse", "origin/main")
        except ValueError as exc:
            failures.append(str(exc))
            origin_url = "unavailable"
            origin_slug = "unavailable"
            origin_push_url = "unavailable"
            origin_push_slug = "unavailable"
            remote_head = ""
        if sealed_commit and remote_head and sealed_commit != remote_head:
            failures.append("sealed commit does not equal origin/main")
    else:
        origin_url = "not_required"
        origin_slug = "not_required"
        origin_push_url = "not_required"
        origin_push_slug = "not_required"
        remote_head = "not_required"

    tag = f"v{version}"
    tag_head = "not_required"
    remote_tag_head = "not_required"
    remote_tag_annotated = "not_required"
    if args.require_tag:
        try:
            tag_head = git("rev-parse", f"refs/tags/{tag}^{{commit}}")
            tag_type = git("cat-file", "-t", f"refs/tags/{tag}")
        except ValueError:
            failures.append(f"missing release tag: {tag}")
            tag_head = ""
            tag_type = ""
        if sealed_commit and tag_head and tag_head != sealed_commit:
            failures.append(f"{tag} does not point to the sealed commit")
        if tag_type and tag_type != "tag":
            failures.append(f"{tag} must be an annotated tag")
        if not args.allow_unpublished and origin_slug == EXPECTED_ORIGIN_SLUG:
            try:
                remote_tag_head, remote_is_annotated = remote_tag_target(tag)
                remote_tag_annotated = str(remote_is_annotated).lower()
            except ValueError as exc:
                failures.append(f"remote release tag is missing or unreadable: {exc}")
                remote_tag_head = ""
                remote_is_annotated = False
                remote_tag_annotated = "false"
            if not remote_is_annotated:
                failures.append(f"origin {tag} must be an annotated tag")
            if sealed_commit and remote_tag_head and remote_tag_head != sealed_commit:
                failures.append(f"origin {tag} does not point to the sealed commit")
        elif not args.allow_unpublished:
            remote_tag_head = "unavailable"
            remote_tag_annotated = "false"
    else:
        tag_type = "not_required"

    # Capture all mutable local release state again after remote/tag checks. The
    # caller may package only the sealed commit, and a ref/index/worktree change
    # during preflight must fail closed.
    try:
        final_head = git("rev-parse", "HEAD")
        branch = git("branch", "--show-current")
        status = git("status", "--porcelain", "--untracked-files=all")
        worktrees = [line for line in git("worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
        hidden_index_entries = [
            line
            for line in git("ls-files", "-v").splitlines()
            if line and line[0] != "H"
        ]
        try:
            sparse_checkout = git("config", "--bool", "core.sparseCheckout").lower() == "true"
        except ValueError:
            sparse_checkout = False
        if sealed_commit and final_head != sealed_commit:
            failures.append("HEAD changed during release preflight")
    except ValueError as exc:
        failures.append(f"final local-state capture failed: {exc}")
        final_head = ""

    if status:
        failures.append("release worktree is not clean")
    if hidden_index_entries:
        failures.append("release worktree contains assume-unchanged, skip-worktree, or nonstandard index flags")
    if sparse_checkout:
        failures.append("release worktree must not use sparse checkout")
    if len(worktrees) != 1:
        failures.append(f"release requires exactly one git worktree, found {len(worktrees)}")
    if not args.allow_unpublished and branch != "main":
        failures.append(f"release branch changed during preflight, got {branch or 'detached'}")

    print("DIRcreative Release Preflight")
    print("=" * 72)
    print(f"version: {version}")
    print(f"head: {head}")
    print(f"sealed_commit: {sealed_commit}")
    print(f"final_head: {final_head}")
    print(f"branch: {branch}")
    print(f"origin_url: {origin_url}")
    print(f"origin_slug: {origin_slug}")
    print(f"origin_push_url: {origin_push_url}")
    print(f"origin_push_slug: {origin_push_slug}")
    print(f"origin_main: {remote_head}")
    print(f"tag: {tag}")
    print(f"tag_head: {tag_head}")
    print(f"tag_type: {tag_type}")
    print(f"remote_tag_head: {remote_tag_head}")
    print(f"remote_tag_annotated: {remote_tag_annotated}")
    print(f"git_worktree_count: {len(worktrees)}")
    print(f"hidden_index_entry_count: {len(hidden_index_entries)}")
    print(f"sparse_checkout: {str(sparse_checkout).lower()}")
    if failures:
        print("RELEASE_PREFLIGHT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("RELEASE_PREFLIGHT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
