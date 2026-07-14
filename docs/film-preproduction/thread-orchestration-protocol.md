# Thread Orchestration Protocol

Verified: 2026-06-06

Purpose: define how DIRcreative uses Codex threads during project execution without letting thread state replace project artifacts, receipts, or validation.

## Core Rule

In `standalone_chat`, DIRcreative uses Codex threads for substantive execution. The DIRcreative main-controller remains responsible for dispatch, the active Goal and acceptance standard, conflict arbitration, worker diff adoption or rejection, final validation, user reporting, archival cleanup, and completion decisions.

Substantive production work, implementation, document changes, and professional role execution default to worker Threads only in `standalone_chat`; an orchestrated worker uses the caller-assigned Thread. The standalone controller may write run receipts, adoption records, merge or rollback actions, validation evidence, and user-facing status. It must not default to doing creative, implementation, or artifact-production details itself.

Thread output is advisory until the controller accepts it into repository files, `.dircreative/runs/`, manifests, receipts, or validation output. Accepted worker output is reconciled into repository files only through an explicit adoption record.

Second-level subagents are local tools inside a first-level Codex Thread worker, not Codex Threads. They may be used only when the worker dispatch explicitly authorizes temporary stateless assistance for a bounded read-only subtask such as prompt decomposition, reference-image checklist review, risk enumeration, candidate ranking, or source triage. A second-level subagent never replaces the worker `thread_id`, `thread_class`, `write_scope`, receipt, cleanup rule, adoption decision, or durable truth record.

When a worker uses a second-level subagent, the worker must summarize the subagent result into its own receipt or adoption record. The record must include the subagent id when available, input question, output summary, close status, whether the worker adopted or rejected the finding, and the durable artifact that received the adopted finding. If the tool is unavailable, record `TOOL_BLOCKED`; do not invent a subagent id or result.

## Orchestrated Worker Boundary

When `execution_context: orchestrated_worker`, the validated caller is the outer controller. For ADCO, follow `docs/film-preproduction/adco-integration-contract.md`.

- Only for `execution.mode: codex_thread`, use the caller-assigned Codex Thread and preserve its verified real thread id in the neutral receipt. The work id, lane id, lane-run id, active ThreadOps registry row, execution-worker class, isolated workspace, and dispatch receipt must all bind the same real id. `inline` and `external_handoff` must not claim a thread id.
- Treat `source_thread_id` as lineage, never as worker execution proof.
- Do not create another controller, update the outer Goal, ask the client directly, decide adoption, archive caller threads, or perform caller cleanup.
- In `adco.specialist-exchange` v1, `inline` is the default. Use `codex_thread` only when ADCO supplies a ThreadOps-verified real worker id; v1 always sets `nested_dispatch_allowed: false`.
- Accept caller-verified `isolated_workspace` for non-git material projects. Exact write scope, caller-owned paths, return receipt path, host-baseline reference, and FinalDelivery lock remain mandatory. `read_only` permits only the receipt path, not an output root.
- Return scoped artifacts, validation evidence, blockers, decision requests, domain verdict, and adoption recommendation to the caller.

If the orchestrator contract is missing or invalid, stop with the corresponding compatibility failure. Do not silently switch to `standalone_chat` inside the assigned worker.

## Codex Thread Execution Layer

In `standalone_chat`, use Codex Threads as the execution layer when work creates durable artifacts, implementation changes, professional role output, review findings, or validation evidence. Do not spawn a worker because a role name exists. Spawn a worker only when the role has a bounded task, explicit sources, a stop condition, and a cleanup rule.

Trigger Codex Thread dispatch for:

- director-room council work that produces professional role output or benefits from isolated viewpoints,
- multi-review or adversarial review before a lockable creative decision,
- substantive artifact, documentation, or implementation work,
- isolated implementation work that can run in a separate worktree,
- validation or cold review after non-trivial changes,
- cleanup or resume work when stale thread state could confuse the project.

Do not dispatch for:

- a small chat-only gate with no durable artifact, professional role execution, or file changes,
- unbounded "many experts" brainstorming,
- replacing user confirmation,
- storing project truth in hidden thread history,
- letting a worker decide `OBJECTIVE_COMPLETE`.

## Controller Operating Loop

The DIRcreative main-controller runs this loop whenever standalone Codex Threads are used. In `orchestrated_worker`, the caller owns this loop and DIRcreative returns evidence into it:

1. Read `docs/film-preproduction/workspace-cleanliness-protocol.md`.
2. State the active Goal, acceptance standard, current worktree state, and whether live-user acceptance exists.
3. Choose the minimal lane roster and keep at most three active worker/reviewer threads by default.
4. Write or update a `thread_dispatch_record` before dispatching any non-trivial worker.
5. Dispatch each worker with a single `professional_identity`, read/write scope, expected output, stop condition, and cleanup rule.
6. Put substantive artifact, documentation, implementation, and professional-role production in worker scope by default.
7. Read worker output, classify each finding or diff as adopted, rejected, or deferred, and record the adoption decision.
8. Merge or apply accepted worker changes, or roll them back/reject them, before treating them as project truth.
9. Run validation after adoption with `PYTHONDONTWRITEBYTECODE=1` for Python subprocesses.
10. Archive completed, failed, duplicate, and superseded workers when visible.
11. Verify `git status --short`, `git worktree list --porcelain`, and task-owned cache cleanup before reporting readiness.

Thread budget:

- `max_active_workers: 3` by default.
- More than three active workers requires a reason in the dispatch record.
- More than five broad council or reviewer threads requires explicit user approval.
- If the user asks for many roles, group roles into professional lanes instead of creating one thread per role.

## Professional Lane Roster

For director-room, council, and multi-review work, use these default Codex Thread lanes before expanding the roster:

- `creative_story_lane`: creative director, director, and screenwriter viewpoints; protects concept, conflict, performance, and story logic.
- `production_image_lane`: producer, cinematographer, production designer, editor, and sound designer viewpoints; protects channel fit, craft feasibility, visual grammar, pacing, and sound.
- `model_continuity_lane`: model prompt engineer and continuity QA viewpoints; protects reference-pack structure, model misread risk, identity/product locks, and downstream QA.
- `validation_lane`: independent read-only reviewer after implementation; protects overreach, hidden state, missing tests, stale worktrees, and completion-boundary errors.

Each lane may contain multiple professional seats, but it is still one bounded Codex Thread with one output contract. If a lane becomes too broad, split it only after the controller records why the split is needed.

## Dispatch Prompt Contract

Every worker prompt must include:

- `thread_class`,
- `professional_identity`,
- `viewpoint`,
- `read_scope`,
- `write_scope`,
- `allowed_actions`,
- `expected_output`,
- `stop_condition`,
- `cleanup_rule`,
- `may_mark_goal_complete: false`,
- `second_level_subagents.authorized` and the allowed local task modes when the worker may use stateless subagents,
- the acceptance standard the worker must not override.

Same-directory workers must be read-only. Workers that write files must use isolated worktrees. Read-only workers are for review, research, and cold review only; they are not the default way to do production work. Validation workers must receive the intended diff scope and validation commands, not hidden main-thread reasoning.

Second-level subagent authorization must be narrower than the worker scope. It can allow read-only exploration, prompt decomposition, reference checks, risk lists, candidate ranking, or local implementation-option comparison. It must not allow file writes, live acceptance writes, user-facing final judgment, dispatch/adoption decisions, cleanup verification, or Goal/objective completion claims.

If a worker may propose or edit a target project `AGENTS.md`, it must also follow `docs/film-preproduction/project-agents-protocol.md`: explicit user authorization, target project path, operation mode, exact write scope, source-of-truth lock order, validation commands, and controller adoption are required before any `AGENTS.md` change becomes project truth.

## Thread Classes

Use only these thread classes.

### Pinned User-Facing Controller

Purpose: the live user conversation, active Goal, dispatch, acceptance standard, conflict arbitration, worker diff adoption or rejection, final validation, cleanup, user reporting, and acceptance judgment.

Rules:

- Keep one pinned main-controller thread per active DIRcreative project task.
- Do not use disposable worker threads as the user-facing thread.
- Do not let old worker threads become the place where project truth lives.
- The pinned controller owns thread cleanup after worker output is consumed.
- The pinned controller may write receipts, adoption records, merge or rollback actions, validation evidence, and user-facing status.
- The pinned controller must not be the default owner of creative, implementation, document, or artifact-production details.

### Disposable Read-Only Worker

Purpose: research, critique, source review, consistency review, cold review, or council dissent.

Rules:

- Same-directory disposable workers are read-only.
- Dispatch with a single role, source list, output shape, and cleanup rule.
- archive after findings are consumed or rejected.
- Do not reuse for a different role; create a fresh worker to avoid stale context.
- Do not use read-only workers as the default production lane for writing artifacts or implementation.

### Isolated Worktree Worker

Purpose: substantive edits, documentation changes, artifact production, professional-role execution that writes files, or parallel implementation when the work is separable and worth merge overhead.

Rules:

- Use an isolated worktree and branch.
- Under a validated ADCO handoff for a non-git material project, use the caller-assigned `isolated_workspace` instead and do not claim git worktree protection.
- One worker owns one issue or one implementation slice.
- Main-controller must inspect diff, run validation, and adopt or reject the changes.
- Archive after adoption/rejection and remove worktree residue when visible.
- May use temporary stateless subagents only when the dispatch record explicitly authorizes them and the worker records their id, input, output summary, close status, and adoption decision in its own receipt.

### Reusable Research Thread

Purpose: long-running external research only when the same research domain will be revisited repeatedly.

Rules:

- Reusable research threads must not write project files.
- Findings must be summarized into repo docs before affecting production.
- Pin only if the user will actively revisit that research thread; otherwise archive when the research conclusion is captured.

## Second-Level Stateless Subagents

Allowed use:

- `prompt_decomposition`: split a prompt, reference pack, or shot requirement into reviewable components.
- `reference_check`: inspect a bounded reference/image/prompt contract and return risks or inconsistencies.
- `risk_inventory`: list failure modes before generation, validation, or retry.
- `candidate_ranking`: rank already generated or proposed options against explicit criteria.
- `source_or_contract_triage`: read specified docs or code and summarize which contract applies.

Forbidden use:

- replacing Codex Thread dispatch for durable work,
- editing files or writing receipts directly,
- changing `write_scope`, cleanup, adoption, or live acceptance state,
- writing `.dircreative/runs/live-user-acceptance.yaml`,
- marking `GOAL_COMPLETE`, `OBJECTIVE_COMPLETE`, or any active goal complete,
- acting as project truth without first-level worker reconciliation.

Class fit:

- `isolated_worktree_worker`: allowed when the worker needs local read-only decomposition, risk checks, or option comparison before making its own scoped diff.
- `disposable_read_only_worker`: allowed for narrower read-only exploration inside a broad review, but the first-level worker still owns the finding list and cleanup.
- `reusable_research_thread`: allowed for bounded source triage only; reusable knowledge must still be captured in repo docs before use.
- `pinned_user_facing_controller`: not a second-level host for production work. The controller dispatches first-level Threads and records adoption, cleanup, validation, and user-facing status.

Receipt requirements:

- `subagent_id` or `TOOL_BLOCKED`,
- `agent_type`,
- `input_question`,
- `output_summary`,
- `closed_status`,
- `adoption_decision`,
- `adopted_into`,
- `durable_truth: false`,
- `may_write_live_acceptance: false`,
- `may_mark_goal_complete: false`.

## Dispatch Checklist

Before creating or forking a worker, the main-controller must state:

- thread class,
- role and viewpoint,
- read/write scope,
- allowed files or sources,
- expected output format,
- cleanup rule,
- acceptance standard the worker must not override.

For any non-trivial thread use, create or update a thread dispatch record using `docs/film-preproduction/schemas/thread-dispatch-record.template.yaml`. The record must use the schema in `docs/film-preproduction/schemas/thread-dispatch-record.yaml` and be saved under `.dircreative/runs/` or the relevant artifact directory.

Minimum dispatch record requirements:

- one pinned main-controller thread,
- every disposable worker marked `archive_after_consumed`,
- every isolated worktree worker tied to a worktree path and adoption/rejection decision,
- every reusable research thread marked read-only and linked to the durable research note,
- `may_mark_goal_complete: false` for all workers,
- completion boundary showing whether live-user acceptance exists,
- worktree audit evidence.

## Main-Controller Duties

In `standalone_chat`, the DIRcreative main-controller must:

- own the active Goal lifecycle,
- name the active acceptance standard before marking progress,
- dispatch workers for substantive production work by default,
- define each worker role, write scope, expected output, and cleanup rule before dispatch,
- arbitrate conflicts between worker outputs,
- adopt or reject worker patches only after review,
- write only run receipts, adoption records, merge or rollback actions, validation evidence, cleanup records, and user-facing status unless the task is a small chat-only gate,
- run validation after adopting worker findings,
- archive completed, failed, duplicate, and superseded workers when visible,
- report failed worktree initialization as infrastructure failure, not as worker analysis,
- keep `OBJECTIVE_COMPLETE: NO` as not complete even when subtasks pass.

## Worker Types

Use only these worker roles.

### Read-Only Review Worker

Use for source research, consistency review, diff review, or critique.

Rules:

- Prefer no worktree.
- Same-directory workers must be read-only.
- If a same-directory worker writes files, treat its output as untrusted and reconcile from the main-controller thread.
- Output must be a short finding list with adopt/reject recommendations.

### Isolated Edit Worker

Use only when parallel implementation is worth the overhead.

Rules:

- Must run in an isolated worktree.
- Must return changed files, patch summary, validation commands, and unresolved risks.
- Main-controller must inspect the diff before adopting anything.
- Worker completion does not prove project completion.

### Validation Worker

Use after implementation for independent QA.

Rules:

- Must receive the intended acceptance standard and current diff scope.
- Must check for overreach, hidden-state dependency, stale references, and whether validation actually covers the requirement.
- Must not write final receipts or mark the Goal complete.

## Failed Worktree Initialization

A failed worktree initialization is not a worker thread result.

Required handling:

- Do not count it as a review, validation, or implementation worker.
- Check `git worktree list --porcelain` and the local worktree root for residue.
- If no real worktree exists, record the failure as UI/task infrastructure state only.
- Archive or clear the failed pending worker when the Codex app exposes a manageable thread id.
- Continue from the main-controller thread.

## Cleanup Checklist

After a worker returns:

- read the worker result,
- classify each finding as adopted, rejected, or deferred,
- classify each second-level subagent finding as adopted, rejected, or deferred inside the first-level worker receipt,
- reconcile adopted findings into durable project truth,
- archive completed, failed, duplicate, and superseded threads,
- remove only task-owned generated caches such as `__pycache__/` created by the current run,
- leave user-owned dirty files untouched,
- run `git status --short` and classify all remaining dirty paths,
- verify `git worktree list --porcelain` shows no unintended worktree,
- verify the local worktree root has no stale worker checkout,
- keep only the main-controller pinned unless a reusable research thread is intentionally active.
- update the thread dispatch record with consumed/rejected/adopted/deferred status, archived/pinned state, adopted artifacts, and worktree audit evidence.

## Reconciliation Rule

Useful worker findings must be converted into durable project truth before they guide production.

Accepted forms:

- repo docs,
- skill rules,
- `.dircreative/runs/*.yaml`,
- prompt manifests,
- `skill_run_receipt`,
- validation scripts,
- release/audit output.

Target project `AGENTS.md` is an accepted form only for stable project-level rules that the user explicitly authorized DIRcreative to persist. It is not a default reconciliation target for worker findings, creative decisions, generation state, or live acceptance evidence.

Rejected forms:

- hidden thread memory,
- copied prompt-window assumptions,
- unarchived stale worker conclusions,
- failed pending worktree UI entries,
- simulation choices used as real user approval.

## Completion Rule

Do not mark a Goal complete because:

- `validate_project.py` passes,
- release gate passes,
- a worker review says the change looks good,
- generated images look acceptable,
- goal-mode simulation passes.

DIRcreative project completion requires the active acceptance standard. For the current project, that means `.dircreative/runs/live-user-acceptance.yaml` exists, passes `scripts/dircreative_goal_audit.py --require-installed`, and `scripts/dircreative_objective_audit.py --require-installed` reports `OBJECTIVE_COMPLETE: YES`.

An `orchestrated_worker` never closes the outer Goal or writes live acceptance for the caller. It stops after returning its domain receipt; the caller owns adoption, project gates, user/client acceptance, cleanup, and completion.

## Research Basis

Read `docs/film-preproduction/research/thread-orchestration-community-lessons.md` when changing thread policy. It captures platform-neutral lessons from public Codex/agent/worktree practice and maps them into DIRcreative's main-controller, disposable worker, isolated worktree worker, reusable research thread, and cleanup rules.
