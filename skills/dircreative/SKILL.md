---
name: dircreative
description: "Use only after the user explicitly invokes $dircreative for film preproduction: story, script, storyboard, shot planning, visual systems, reference-image planning, and model-specific video prompts. ADCO mode accepts only a validated Specialist Exchange handoff. Do not use for maintaining, debugging, refactoring, testing, or evaluating the DIRcreative source repository; maintaining ADCO; ordinary code work; factual questions; or generic advertising requests without an explicit $dircreative invocation."
---

# DIRcreative

Make the film work better across story, image, sound, performance, continuity,
and model behavior; keep control machinery subordinate to the result.

## Invocation Boundary

Start only for explicit `$dircreative` or validated `adco.specialist-exchange`
selecting `dircreative.film-preproduction`; real ADCO uses
`adco specialist-handoff` and `adco specialist-adopt`. Misrouted DIR/ADCO
maintenance becomes `source_maintenance` and stops Skill execution.

## Router Contract

Choose an obvious standalone route directly; do not run a script before useful
creative work:

| Request | Mode / route | Route Card | One task reference |
| --- | --- | --- | --- |
| bounded copy or script change | Fast / `copy_revision` | `routes/fast-task.md` | `references/copy-script.md` |
| one shot or a few storyboard frames | Fast / `shot_optimization` or `storyboard_review` | `routes/fast-task.md` | `references/shot-storyboard.md` |
| bounded model prompt change | Fast / `prompt_revision` | `routes/fast-task.md` | `references/prompt-model.md` |
| other bounded revision | Fast / `bounded_revision` | `routes/fast-task.md` | none |
| analyze or distill a reference video / local clip into AI filmmaking methods | Studio / `video_distillation` | `routes/studio-development.md` | `references/video-distillation.md` |
| recurring character, costume master sheet, headless derivative, or garment detail board | Studio / `film_development` | `routes/studio-development.md` | `references/character-master-sheet.md` |
| complete or multi-output film work, including its visual asset plan | Studio / `film_development` | `routes/studio-development.md` | `references/film-development.md` |
| real generation or client delivery | Delivery / `generation_authorization` or `client_delivery` | `routes/delivery-audit.md` | `references/generation-delivery.md` |
| fully validated ADCO handoff | Delivery / `adco_specialist_exchange` | `routes/delivery-audit.md` | `references/specialist-exchange.md` plus the descriptor schema |

Run `python3 scripts/dircreative_route.py --handoff <file> --project-root <dir>`
only to validate an ADCO handoff, or use text routing for genuine mode ambiguity.
A schema-only handoff fails closed; verify its descriptor, locked hashes, brief,
capabilities, exchange index, snapshot, and isolated output/receipt scope. It is
not a mandatory creative preflight.

Read exactly one selected Route Card, then only the task reference in the table.
Do not follow references from that card into another protocol chain. Optional
model/source evidence is fetched only when a current claim or real execution
depends on it.

For an explicit project directory, new materials, or multi-file Studio output,
also read `references/project-hygiene.md` after the first useful artifact. It is
an operational reference, not a craft reference.

## Startup Reads

There are zero unconditional protocol reads. An obvious Fast or Studio request needs no router tool call
before the result and uses one Route Card and one task reference.

## Intelligent Skill Stack

Select by the current deliverable stage; reselect when that stage changes.
Use one advisory stack: one craft owner, non-overlapping
collaborators, at most one validator, and an execution adapter only for an
authorized side effect. DIR or valid-handoff ADCO retains artifact/state.
Fast/Studio/Delivery load at most 1/3/1 bodies inside 14/20/30KB. Prefer the host
catalog; scan only when absent, never run discovered code or expose paths.
Liu/Sophia are explicit overlays; `ai-visual-production-director` is reference-
only. Show the artifact first. Only the host may say “已用” after full body and
hash verification. Only primary-route evidence authorizes ADCO handoff or gates.
Read `references/visual-skill-stack.md` only for ambiguity or audit.

## Execution Context

`standalone_chat` owns response/state. `orchestrated_worker` requires a valid
exchange; ADCO owns host truth, adoption, versions, client visibility, and
cleanup. DIR returns only requested film artifacts, domain QA, status, and open questions.
Nested dispatch is forbidden.

## Modes

### Fast

Make one bounded change with zero Threads or Director Room. Preserve facts
outside the edit and return the revised artifact immediately.

### Studio

Develop connected preproduction artifacts with one controller, at most three dynamic professional perspectives,
one critical pass, and zero Threads by default. Lock the
audience change, core action, brand role, start-action-end, physical/media rules,
continuity, and sound/edit logic. Client stories stop at narrative; nine-grid
storyboards are narrative beats. Only explicit technical/full-preproduction
scope proceeds to shot and asset matrices. Whole-film work derives scene,
identity, per-shot board, director-board, and model-input coverage before
generation; representative images are never the whole film.
Repeated assets use the staged `asset_foundation` pass; only a hash-bound,
fully covered pass plus scoped stress verdict may enter Seedance compilation.

### Delivery

Use strict evidence only when a real side effect, formal handoff, version, or
client-visible asset is in scope, and bind it to the current artifact.

## External User Gates

The only v2 gates are `concept_lock` for incompatible directions,
`generation_authorization` for unapproved real generation, and
`client_delivery_approval` for unapproved client-visible action. An explicit
instruction for that action satisfies its gate; do not ask twice.

Story, script, shot, visual, reference, prompt, and QA states are reversible
internal work. Reuse supplied brief facts. “Continue” continues. A bounded edit
never returns to intake.

## Compact State

Use `runtime/state-snapshot.schema.json` only when state must survive the answer.
Fast stays in memory; Studio persists for pause/resume or multi-file output;
Delivery persists for an actual handoff or execution record.

## Project Files

Use supplied materials in place with one physical owner for identical bytes.
For project or multi-file scope, follow `references/project-hygiene.md`; moving,
deleting, renaming, replacing, or writing target `AGENTS.md` still requires the
trusted host's scoped authority. Runtime prompts or receipts never grant it.

## Chat Visualization

Use visualization only when clearer than prose or a small table. Verify the
current surface and visible render; otherwise provide a complete table, Mermaid,
image, or prose fallback. Offline render PASS or a file path does not prove host
mounting; report `USER_VISIBLE=UNVERIFIED` until visible.

## Sub-Capability Dispatch

Use the selected task reference as craft guidance, not as a checklist to expose.
Do not enter adjacent stages speculatively. Preserve locked facts, mark only
affected downstream material stale, and make the smallest complete change.

Audience-facing story, script, PPT, README and report prose uses a source-derived
voice before delivery. Preserve names, coined terms, character diction, genre
register and intentional poetic rhythm. Route explicit “说人话 / 去 AI 味 /
自然一点” requests, or drafts that still read like a template, through
`human_language_revision`; natural language is not casual-language flattening.

Prompt work keeps Prompt IR model-neutral and applies one model surface at a
time. Verify volatile model claims from current official evidence only when they
affect the answer or execution.
Record only final generation candidates in `ai-film-production-ledger`; runtime
state remains project truth and the Ledger never executes or approves media.

## Result Contract

Lead with the requested artifact or recommendation, then only decision-changing
judgment, assumptions, limits, or one indispensable question. Fast/Studio do not narrate
routes, Git, receipts, gates, validation, or role meetings unless requested.
Validate the task and direct dependencies; unrelated debt cannot downgrade it.

Whole-film completeness binds every scene/shot to exact time, action, sound,
continuity, entities, generation unit, and dependencies. A sample is never the
whole film. `visual_assets_complete` also needs canonical, decodable,
aspect-correct PNG evidence, bound visual review, and separate trusted host
adoption/readback. Payload reviewer labels, IDs, hashes, and locks do not bypass it, and
it never means master, client, or broadcaster approval.

Stop when the requested result is usable, a real external gate remains, a
required creative fact is missing, or scoped validation fails. Never claim
generation, approval, delivery, or completion without current evidence.
