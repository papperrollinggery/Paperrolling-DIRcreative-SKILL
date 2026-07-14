# Thread Orchestration Community Lessons

Verified: 2026-06-06

Purpose: capture platform-neutral lessons from public agent/thread/worktree practice and map them into DIRcreative without making thread state the source of truth.

## Sources Checked

- OpenAI Codex docs: https://developers.openai.com/codex/ — used for the public pattern that Codex exposes worktrees, subagents, workflows, review, and local environments as first-class concepts.
- OpenAI Agents SDK docs: https://openai.github.io/openai-agents-python/ — used for the harness pattern of agents, handoffs, guardrails, tools, and tracing as visible control surfaces.
- Claude Code workflow docs: https://code.claude.com/docs/en/common-workflows — used as adjacent community practice for explicit workflows around multi-step agent coding work.
- Git worktree docs: https://git-scm.com/docs/git-worktree — used as the source for worktree semantics and why isolated edit workers require cleanup.
- Community worktree/parallel-agent discussions from GitHub/Reddit/X search: used only as weak signal that parallel agents need isolation, narrow ownership, and explicit merge/review.

Do not copy platform-specific UI, pricing, hidden queue behavior, or private prompts into DIRcreative. Treat these sources as operating patterns only.

## Adopted Patterns

### Control Thread

Use one pinned main-controller thread for the live user conversation, active Goal, final writes, validation, cleanup, and completion judgment.

Why: public agent practice separates orchestration from execution. A controller keeps the user's intent and acceptance standard stable while workers gather evidence or draft isolated changes.

### Disposable Workers

Use disposable read-only workers for council dissent, source review, consistency review, and validation critique.

Rules:

- one worker, one role,
- narrow source list,
- explicit output shape,
- no writes in same-directory mode,
- archive immediately after findings are consumed or rejected.

Why: community parallel-agent practice repeatedly warns that broad, long-lived workers accumulate stale context and conflicting assumptions.

### Isolated Worktree Workers

Use isolated worktree workers only when implementation work is separable and worth merge overhead.

Rules:

- one worktree worker, one implementation slice,
- return changed files, patch summary, validation output, and unresolved risks,
- main-controller inspects and adopts/rejects the diff,
- cleanup worktree residue after adoption/rejection.

Why: worktrees are good for concurrent coding, but they are a liability for small review tasks or when multiple workers edit the same files.

### Reusable Research Threads

Reuse a research thread only when the same external research domain will be revisited across sessions.

Rules:

- read-only,
- not user-facing unless explicitly pinned for the user,
- findings must be summarized into repository docs before they affect production,
- archive when the durable research note exists.

Why: reusable context helps research continuity, but it must not become hidden project truth.

## Anti-Patterns

- Multiple pinned threads for one active user-facing DIRcreative task.
- Same-directory worker writes.
- Workers that keep running after their result was consumed.
- Treating failed worktree initialization as a valid worker result.
- Treating worker confidence, generated images, or green checks as real user acceptance.
- Letting a reusable research thread override current repository artifacts.

## DIRcreative Mapping

Thread orchestration is useful only when it improves one of these project outcomes:

- stronger council dissent,
- safer isolated implementation,
- independent validation critique,
- recovery after context compaction,
- visible cleanup discipline.

Thread orchestration is not useful when it adds ceremony to a small chat-stage correction or when the main-controller can directly inspect and fix the issue faster.

## Required Evidence After Thread Use

Every meaningful thread session should leave at least one durable trace:

- repository doc update,
- `.dircreative/runs/*.yaml` receipt,
- `skill_run_receipt`,
- validation script update,
- accepted/rejected worker finding summary,
- cleanup evidence showing disposable workers archived and worktrees absent.

If no durable trace exists, the thread result is advisory only and must not guide production.
