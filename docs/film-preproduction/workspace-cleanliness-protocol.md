# Workspace Cleanliness Protocol

Verified: 2026-06-19

Purpose: keep DIRcreative Codex Thread work from polluting the user's repository, local worktrees, or execution environment.

## Core Rule

The main-controller thread owns workspace hygiene. Worker threads may inspect or produce scoped outputs, but they must not leave untracked caches, stale worktrees, duplicate checkouts, hidden receipts, or unexplained dirty files.

## Preflight

Before non-trivial edits, thread dispatch, release gates, or validation runs, the main-controller must inspect:

```bash
git status --short
git worktree list --porcelain
```

Classify dirty files before acting:

- `user_owned_dirty`: existed before the current task; do not overwrite or clean.
- `task_owned_dirty`: created by the current task and must be explained, adopted, or removed.
- `generated_cache`: `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, coverage files, or temporary local pages.
- `worker_residue`: unintended worktree checkout, failed pending worktree, duplicate worker output, or stale thread receipt.

If the worktree is already dirty, prefer read-only workers and narrow edits. Do not ask a worker to write into the same directory unless the writable file list is exact and the controller can inspect the diff immediately.

## During Execution

Use clean subprocess defaults for local validation and release commands:

```text
PYTHONDONTWRITEBYTECODE=1
```

Python validation, readiness, visual dogfood, and release gate runners should pass this environment variable to child Python commands. Do not rely on `.gitignore` to hide avoidable cache churn.

Rules:

- Same-directory Codex workers are read-only.
- Isolated edit workers must use a separate worktree and exact write scope.
- The controller adopts worker output only after reading the diff and running validation.
- Temporary generated files must go to `/tmp` or a declared output path.
- Do not copy generated media into `examples/`.
- Do not leave raw worker notes as project truth.

## Cleanup

Before reporting readiness, the controller must:

1. Remove task-owned generated caches such as `scripts/__pycache__/` if they were created by this run.
2. Leave user-owned dirty files untouched.
3. Archive completed, failed, duplicate, and superseded disposable worker threads when visible.
4. Check `git worktree list --porcelain` for unintended worktrees.
5. Check `git status --short` and make sure every remaining dirty file is intentional and reported.
6. Record cleanup evidence in `.dircreative/runs/` when Codex Threads were used.

Do not run broad cleanup commands that can delete user work. Safe cleanup is scoped to task-owned caches and worker residue.

## Verification

A clean DIRcreative thread-backed run should end with:

```bash
git diff --check
git worktree list --porcelain
python3 scripts/dircreative_thread_audit.py --dispatch-record <record>
python3 scripts/validate_project.py
git status --short
```

The final status may show intentional modified files. It must not show unexplained caches, failed worktree residue, or worker-created files that were not adopted into the task.

## Failure Signals

Treat these as `thread_control_incomplete` or workspace cleanup failures:

- a worker says the worktree is dirty but the controller has not classified the dirt,
- `__pycache__/` or similar caches appear after validation,
- an isolated worker leaves a worktree after adoption or rejection,
- a dispatch record claims cleanup but `git worktree list --porcelain` shows unintended worktrees,
- final status includes untracked files not listed in the final report,
- a worker result is used without being reconciled into repo docs, receipts, manifests, or validation output.
