# Project AGENTS.md Protocol

Verified: 2026-06-26

Purpose: define when DIRcreative may propose, create, append to, or leave untouched a target project's `AGENTS.md`.

## Core Rule

DIRcreative must not write or overwrite a target project `AGENTS.md` by default.

Use `.dircreative/runs/`, manifests, `skill_run_receipt`, and user-facing summaries as the default durable handoff. Treat `AGENTS.md` as stable project policy, not as a normal run artifact, worker note, creative brief, prompt manifest, or acceptance receipt.

## Authorization Boundary

Allowed without explicit authorization:

- read an existing target project `AGENTS.md`,
- follow its instructions while working in that project,
- identify gaps or conflicts,
- propose a candidate `AGENTS.md` section in chat or a normal report,
- record a recommendation in `.dircreative/runs/` or `skill_run_receipt`.

Requires explicit user authorization:

- create a new target project `AGENTS.md`,
- append to an existing target project `AGENTS.md`,
- edit or delete any existing `AGENTS.md` instruction,
- move project rules between `AGENTS.md`, `CONTEXT.md`, docs, or run receipts.

Authorization must name the target project and the requested operation. Phrases like "continue", "run the workflow", "make the project durable", "save the run", "accept the chat experience", or "worker can handle it" are not authorization to modify `AGENTS.md`.

The bundled `dircreative_project_agents.py` runtime is proposal-only. Inline
JSON, a local receipt file, a prompt field, or a worker assertion is
caller-controlled and cannot prove a current user instruction. Even when the
user has authorized an edit, the trusted host controller must read the complete
hierarchy and apply an ordinary minimal scoped patch itself; the DIRcreative
runtime must not promote its proposal into active policy.

## No Default Overwrite

Never replace a target project's `AGENTS.md` wholesale unless the user explicitly requests a full rewrite of that file.

When writing is authorized:

- preserve existing instructions and ordering unless the user asks to reorganize,
- prefer the smallest append or surgical edit,
- keep subdirectory `AGENTS.md` precedence intact,
- do not remove local commands, test paths, repo boundaries, safety rules, or ownership notes,
- do not write secrets, account identifiers, private contact data, temporary thread state, model outputs, or unverified assumptions.

If the requested edit conflicts with existing instructions, stop and report the conflict before writing.

## Source Of Truth

Use this order when deciding what can govern a target project:

1. Current system, developer, and explicit user instructions.
2. Existing target project `AGENTS.md` files, with child directory rules overriding parent directory rules.
3. Target project domain docs such as root `CONTEXT.md`, `docs/adr/`, README, issue or PRD docs, and validated repo scripts.
4. DIRcreative durable run evidence: `.dircreative/runs/`, manifests, prompt manifests, QA reports, and `skill_run_receipt`.
5. User-facing summaries and accepted chat decisions.
6. Worker thread findings after controller adoption.

Hidden conversation state, worker memory, unarchived thread conclusions, generated candidates, local URLs, screenshots, and simulation choices are not project truth.

## Lock Order

Before proposing or writing `AGENTS.md`, lock these items in order:

1. target project path and intended rule scope,
2. current user authorization status,
3. existing `AGENTS.md` hierarchy and applicable subdirectory precedence,
4. target project source docs and command evidence,
5. stable project-level rule candidate,
6. conflict check against existing instructions and live user requirements,
7. validation commands for the target project and this skill repo,
8. final operation: propose only, create, append, or surgical edit.

Do not skip from a creative output, worker suggestion, or run receipt directly into an `AGENTS.md` write.

Any persisted DIRcreative project-rule block must also preserve the creative lock order future threads need:

```text
idea intake -> director room -> story -> script -> script breakdown -> shot design -> visual bible -> reference pack -> image prompt -> video model adapter -> QA/retry
```

## Pre-Generation Conditions

DIRcreative may draft a candidate `AGENTS.md` block only when:

- the user asked for project rules, agent instructions, repo operating rules, or persistent workflow guidance,
- the target project and rule scope are identified,
- existing project instructions have been read when available,
- the proposed rule is stable beyond the current run,
- the rule belongs in project policy rather than `.dircreative/runs/`, an artifact manifest, README, or chat summary,
- secrets and private identifiers have been excluded,
- unresolved conflicts are called out instead of silently normalized.

If any condition fails, record the issue in a run receipt or summary and do not generate project policy text as if it were ready to persist.

## Operation Modes

### Not Touch

Leave target `AGENTS.md` untouched for normal creative production, prompt-only workflows, image or video generation planning, QA/retry records, goal-mode simulation, live acceptance, worker dispatch, and disposable research.

### Propose

Propose text when the user asks what should be persisted, asks for a review of project rules, or when a repeated stable rule is discovered. The proposal must state that it is not applied yet.

### Create

The trusted host controller may create a new `AGENTS.md` only after direct
explicit authorization and only when no applicable file exists at the intended
scope. The DIRcreative runtime only returns an inactive proposal. The content
must be project-level operating guidance, not a transcript of the DIRcreative
run.

### Append Or Surgical Edit

The trusted host controller may append or surgically edit only after direct
explicit authorization. The patch must cite the source evidence used and keep
existing instructions intact; the DIRcreative runtime never applies it.

### Full Rewrite

Full rewrite requires explicit user wording that requests replacing the target `AGENTS.md`. Without that wording, rewrite is disallowed.

## Thread And Worker Rules

Same-directory workers are read-only and may not edit target `AGENTS.md`.

An isolated worktree worker may draft or patch target `AGENTS.md` only when its dispatch prompt includes:

- explicit user authorization,
- target project path,
- exact write scope,
- operation mode,
- existing source files to read,
- validation commands,
- `may_mark_goal_complete: false`,
- cleanup rule.

The main-controller must inspect the diff, classify adoption or rejection, run validation, and record the decision in `.dircreative/runs/` before the change can become project truth. A worker's completed task is not authorization and is not acceptance.

## COS Project Boundary

If a Chief-of-Staff workflow is triggered, user-visible output must stay Chinese-first, concise, and conclusion-first. Real dispatch reports must show a Chinese dispatch summary before the `THREAD_DISPATCH_RECEIPT` machine credential.

The Chief-of-Staff controller thread is not an execution surface. Except for T0/T1 lightweight status or explicitly user-forbidden worker cases that are read-only, it must not run target project tests/gates, clean processes, edit files, implement code, or perform operations cleanup directly.

Cross-project work must execute in the target project's main COS or a target project-bound worker. A source COS must not enter another project to run gates, change files, clean processes, or treat its own command output as completion evidence.

If a main COS over-executes, record `cos_main_overexecution` and `adoption_status: rejected_evidence`. Its commands, diffs, cleanup, tests, or gate output are clues only until rerun and adopted by a project-bound worker.

## Live User Acceptance Boundary

Live user acceptance of the DIRcreative chat experience does not authorize project `AGENTS.md` edits.

Project `AGENTS.md` edits do not prove live user acceptance. They cannot create `.dircreative/runs/live-user-acceptance.yaml`, set `real_user_co_creation_verified: true`, or mark a Goal complete.

If a live acceptance pass reveals a stable project rule, record it in the acceptance receipt or a separate run receipt first. Persist it to `AGENTS.md` only after the user separately authorizes that project policy edit.

## Relationship To Runs And Receipts

Use `.dircreative/runs/` and `skill_run_receipt` for run-specific evidence:

- active phase,
- worker dispatch and adoption,
- user decisions,
- generated candidate status,
- QA and retry findings,
- validation evidence,
- proposed project-rule candidates.

Use target project `AGENTS.md` only for stable rules future agents must follow in that repository. Do not duplicate full run receipts into `AGENTS.md`; link or summarize only the durable rule if the user authorizes persistence.

## Validation Commands

For this repo after documentation changes:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_project.py
git diff --check
git status --short
```

For a target project `AGENTS.md` edit:

```bash
git status --short
git diff -- AGENTS.md
git diff --check
```

If the target project has documented validation commands in its existing `AGENTS.md`, README, `CONTEXT.md`, or scripts, run the relevant commands too. If validation cannot run, report the exact command and blocker.
