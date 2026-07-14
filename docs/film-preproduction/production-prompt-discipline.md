# Production Prompt Discipline

Verified: 2026-06-06

Purpose: keep DIRcreative prompt work disciplined before any image or video generation handoff. This is a platform-neutral production harness, not a dependency on Higgsfield, any MCP server, or any external account.

## Core Rule

DIRcreative separates prompt construction from execution.

Prompt construction is a separate layer from media execution. The construction layer decides whether the prompt is coherent and artifact-backed; the execution layer decides whether a tool can run it.

```text
story / shot / reference truth
-> prompt construction layer
-> pre-delivery harness
-> prompt-only, assisted-generation, or external-generation handoff
-> QA and single-variable retry
```

The prompt construction layer prepares a generation-ready artifact. It does not prove that media exists, that a tool is available, or that the user authorized generation.

Thread history, hidden agent memory, copied prompt windows, and prior model habits are not durable truth. Durable truth stays in artifacts, `.dircreative/runs/`, `skill_run_receipt`, manifests, and validation output.

## Required Prompt Construction Layer

Before an image or video prompt is delivered, the responsible skill must show or record:

- active route: selected skill, current stage, and downstream artifact owner,
- source truth: locked story, script, shot, visual bible, reference pack, and co-creation gate source,
- material selection: the user-facing choice of asset type before prompt compilation, such as character identity reference, scene geography/FOV reference, professional storyboard + motion map, clean frame, style/material board, first test image, full pack, prompt-only export, or stop,
- visual output mode: `prompt_only`, `assisted_generation`, or `external_generation`,
- execution capability and authorization evidence: tool availability and explicit user permission when generation is requested,
- reference bindings: which identity, scene/FOV, storyboard/motion map, clean frame, element, audio, or planning-only asset each prompt uses,
- prompt contract: role, boundaries, inheritance, direct-input policy, and visible handoff text,
- model constraints: current documented model behavior or project registry fact, not guessed platform behavior,
- negative constraints: targeted blockers for the current asset, not a generic artifact dump,
- falsifiable success rubric: what must be true after generation or import for the candidate to pass QA.

When prompt structure changes based on external practice, read `docs/film-preproduction/research/ai-video-prompt-community-lessons.md` first. Adopt structure only, not unverified platform facts. Community recipes from Reddit or X are weak signals unless backed by official docs, source repositories, local policy, or current tool schemas.

## Pre-Delivery Harness

Run this harness before exporting prompt text, prompt files, or generation instructions.

1. **Routing check**: the prompt is being compiled by the correct sub-skill and the next artifact owner is named.
2. **Knowledge check**: only the relevant policy, source registry, schema, and skill docs are loaded.
3. **Lock-order check**: identity/product, scene/FOV, storyboard/motion map, clean frames, and video prompts appear in the approved order for the project type.
4. **Material-selection check**: the user has chosen which material to make next, or goal-mode simulation has explicitly recorded `模拟用户选择` for that material choice.
5. **Mode check**: `visual_output_mode`, `execution_capabilities`, and `asset_output.status` agree.
6. **Authorization check**: assisted image or video generation remains blocked unless the user explicitly authorized it in the live run.
7. **Reference check**: each prompt binds to locked source artifacts and labels planning-only assets as not direct video input.
8. **Structure check**: image prompts include visual decomposition and prompt layers; video prompts use model-specific structure instead of one universal prompt.
9. **Negative check**: avoid lists target the smallest likely failure for this asset and do not contradict the positive prompt.
10. **Prompt-window hygiene check**: remove stale prompt blocks, old references, superseded user decisions, and conflicting model notes before compiling final text.
11. **Success rubric check**: list pass/fail criteria that a reviewer can verify from the generated or imported asset.

If any check fails, stop before generation or external handoff and route to the smallest corrective artifact.

## Video Prompt Structure

Use a model-agnostic five-part discipline for every video prompt:

```text
Model policy -> Camera -> Subject -> Look -> Action
```

- Model: which target model or prompt-only target is being prepared.
- Camera: one motivated camera behavior with start and end target.
- Subject: visible actor, product, prop, or scene owner inherited from source truth.
- Look: lighting, material behavior, palette, style, and surface constraints.
- Action: one primary action that fits the shot duration.

Each model adapter may expand that into its own shape. A six-slot adapter is valid when the model benefits from explicit separation:

```text
camera + subject + action + setting + style + lighting
```

Rules:

- camera must name physical start and end targets or explicitly stay locked-off,
- subject must inherit identity/product locks instead of redesigning them,
- action must fit the shot duration and input frame,
- setting must inherit the scene/FOV source,
- style and lighting must be concrete production constraints, not praise words,
- audio is separate from visual prompting unless the target model supports native audio.

Before finalizing a video prompt, reduce the shot to a micro-scene beat sheet:

- initial visible state,
- trigger or pressure,
- subject action path,
- camera start target,
- camera end target,
- timing beat or pause,
- final visible state,
- sound or silence policy when relevant.

Reject prompts that combine several unrelated actions, multiple camera moves, and a slogan into one shot.

## Image Prompt Structure

Image prompts keep the existing JSON-first DIRcreative contract.

Required layers:

- `evidence_policy`,
- `visual_decomposition`,
- `prompt_layers.director_recreation_prompt`,
- `prompt_layers.prompt_core`,
- `prompt_layers.negative_prompt`,
- `type_treatment`,
- `style_tags`,
- visible pre-generation contract text.

For complex assets, the final prompt must make the role label, title hierarchy, inheritance source, role purity, and direct video input policy readable even if the user copies the prompt into another tool.

## Professional Storyboard And Motion Map Structure

Do not compile a professional storyboard/motion map as a generic 3x3 image prompt.

Before a storyboard/motion map prompt is exported or generated, lock these layers:

- character design: age range, profession, costume, hair, body language, expression baseline, and relationship distance,
- scene layout: stable geography, entrances/exits, hero props, foreground/midground/background, light sources, and continuity positions,
- prop continuity: which object starts where, who touches it, where it ends, and whether it is direct video input or planning-only,
- shot cells: shot id, duration, shot size, camera height, lens feel, camera position, camera movement, subject movement path, blocking, emotional beat, transition logic, and model risk.
- shot-card text: each visible storyboard cell must use professional production language, not thin captions. Include narrative purpose, lens/support/movement, subject blocking/path, continuity, sound/edit cue, and model risk in compact shot-card phrasing.

The user-facing gate must offer material choices before generation, for example:

- character identity reference,
- scene geography + camera FOV reference,
- professional storyboard + motion map,
- selected clean frame,
- style/material board,
- prompt-only export,
- stop.

If the user asks for "the director storyboard image", ask whether they want a planning storyboard/motion map, clean frame, character reference, scene/FOV reference, or full reference pack unless the current context already makes that material choice explicit.

Reject storyboard pages whose text only says generic labels such as `wide`, `close-up`, `slow push`, `conversation`, `hero frame`, or `emotional ending`. Those words are only acceptable when embedded in a complete shot-card summary that explains why the shot exists and how it should be filmed or translated to video models.

## Single-Variable Retry

Retries change one production variable at a time unless a locked upstream decision is wrong.

Change one variable per retry. Broad retries hide which correction fixed or broke the result.

Allowed retry variables:

- subject identity or product silhouette,
- action or blocking,
- camera path or shot size,
- scene/FOV binding,
- style or lighting,
- text/title hierarchy,
- reference upload map,
- output controls such as aspect ratio, duration, or direct-input mode.

Do not rewrite story, shot design, reference pack, prompt text, model adapter, and QA rubric in the same retry. Diagnose the failing layer first, change the smallest artifact, and preserve the rest of the artifact chain.

## Falsifiable Success Rubric

Every generation-ready handoff must define pass/fail criteria before generation or external execution.

Minimum rubric:

- identity/product match: what must remain identical,
- scene/FOV match: route, axis, camera side, and light source,
- action match: what movement must happen and what must not happen,
- camera match: support, start/end target, and stability,
- role purity: whether the asset stayed identity board, scene atlas, storyboard/motion map, clean frame, or video prompt,
- output boundary: no generated media exists in `prompt_only`; assisted candidates are not user-locked until QA passes,
- failure routing: the smallest next retry artifact if the candidate fails.

## Platform Boundaries

Do not write plausible platform facts as if verified.

Do not import platform-specific details unless the source registry and target adapter require them.

Forbidden in this discipline layer:

- adding an MCP dependency,
- installing or connecting an external generator,
- copying platform price, account, model menu, or credit policy into core rules,
- treating community prompt recipes as verified model facts,
- treating a thread, hidden context, or old prompt window as durable state,
- converting goal-mode simulation into live user acceptance.
- overfitting to a public Reddit, X, or prompt-library recipe without converting it into DIRcreative source truth, material role, prompt contract, and falsifiable QA criteria.

## Goal And Thread Boundary

Goal mode may drive implementation and dry-run simulation. Codex worker threads may research, review, or validate in parallel.

They must remain coordination tools only:

- Codex worker threads are not production truth.
- `.dircreative/runs/`, artifact manifests, and `skill_run_receipt` remain the durable source of truth.
- Goal-mode simulation must not create live acceptance receipts or mark real user approval.
- Useful thread findings must be converted into docs, artifacts, manifests, or receipts before they guide production.

## Thread Execution Protocol

Use a main-controller thread to guard lifecycle decisions and reconcile durable project truth. Worker threads may help only when their role, write scope, and cleanup rule are explicit before they start.

Read `docs/film-preproduction/thread-orchestration-protocol.md` for the complete thread lifecycle, worker role, failed worktree initialization, reconciliation, and completion rules.

Required thread rules:

- Substantive production, implementation, documentation, and professional-role work defaults to worker Threads.
- The main-controller thread may write only run receipts, adoption records, merge or rollback actions, validation evidence, cleanup records, and user-facing status.
- A worker that may edit files must run in an isolated worktree and return a patch summary, validation output, and changed-file list before the main-controller thread adopts anything.
- A same-directory worker is read-only by default and may only inspect, summarize, or review. If it writes files, discard its output as untrusted until the main-controller thread rechecks the worktree and removes duplicates.
- A failed worktree initialization is not a worker result. Record it as an infrastructure failure, archive or clear the failed thread/pending worker when visible, and continue from the main-controller thread.
- Do not keep stale workers open after their result is consumed or rejected. Archive completed, failed, duplicate, and superseded worker threads to avoid thread pileup.
- Do not mark a Goal complete merely because a subtask validation passed. Goal completion must match the active project acceptance standard.
- If `dircreative_objective_audit.py` reports `OBJECTIVE_COMPLETE: NO`, the project is not complete; the Goal may only be closed if its objective was explicitly scoped to a narrower subtask and that narrower scope is stated in the final report.

The discipline layer should improve how DIRcreative writes, checks, and retries prompts. It must not expand scope into generation, publishing, frontend work, or external platform integration.
