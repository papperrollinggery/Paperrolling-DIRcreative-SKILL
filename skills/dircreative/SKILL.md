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

After mode and deliverable selection, use the host catalog for one advisory
stack: one craft owner, non-overlapping collaborators, at most one validator,
and an adapter only for an authorized side effect. DIR, or valid-handoff ADCO,
keeps final artifact/state ownership. Fast/Studio/Delivery load at most 1/3/1
provider bodies inside 14/20/30KB. Scan an authorized root only when the catalog
is absent; never execute discovered code or expose paths. Liu/Sophia are explicit
overlays; `ai-visual-production-director` is reference-only. Put the artifact
before the compact Skill card. The selector never claims “已用”; only the host may
do so after independently reading the selected body and verifying its hash. ADCO handoff and execution gates come only from
the validated primary route, never request fields. Read
`references/visual-skill-stack.md` only for ambiguity or audit.

## Execution Context

`standalone_chat` owns response/state. `orchestrated_worker` requires a valid
exchange; ADCO owns host truth, versions, adoption, client visibility, readiness,
completion, and cleanup. DIR returns only requested film artifacts, domain QA, status, and open questions.
Nested dispatch is forbidden.

## Modes

### Fast

Make one bounded change with one agent, zero Threads, zero Director Room, zero
full-project audits, and no specialized receipt. Preserve facts outside the edit
and return the revised artifact immediately.

### Studio

Develop a complete concept or multiple connected preproduction artifacts with
one controller. Use at most three dynamic professional perspectives and at most
one critical pass, integrated into the work rather than shown as meeting
ceremony. Threads default to zero. First lock audience state change, one core
action, brand causal role, start-action-end, physical/media rules, continuity,
and sound/edit logic. A one-to-two-page client story stops at that narrative
layer; a nine-grid storyboard is narrative beats by default, not a technical
shot list. Only an explicit technical/full-preproduction request proceeds to
the shot and asset matrix. For whole-film scope, derive the scene,
identity, per-shot storyboard, director-board, and model-input asset coverage
before generation; do not treat a few representative images as the full film.

### Delivery

Use strict evidence only when a real side effect, formal handoff, version, or
client-visible asset is in scope. Bind evidence to the current artifact and its
dependencies, not to unrelated project history.

## External User Gates

The only v2 gates are `concept_lock` for incompatible creative directions,
`generation_authorization` before an unapproved real generation, and
`client_delivery_approval` before an unapproved client-visible action. An
explicit instruction to perform the same action may satisfy its gate; do not ask
the user to approve twice.

Story, script, shot, visual, reference, prompt, and QA states are reversible
internal work. Reuse supplied brief facts. “Continue” continues. A bounded edit
never returns to intake.

## Compact State

Use `skills/dircreative/runtime/state-snapshot.schema.json` only when state must
survive the answer. Fast stays in memory. Studio persists for pause,
cross-session resume, or multi-file output. Delivery persists when an actual
handoff or execution record exists.

## Project Files

Use supplied materials in place and keep one physical owner for identical
bytes. For project or multi-file scope, scan read-only and offer one organization
action after useful work; moving, deleting, renaming, or replacing files still
needs approval. Keep one replace-current plan. Normal Director Room, storyboard,
prompt, Goal, worker, and live acceptance never writes target `AGENTS.md`. Only
the trusted host controller may apply a user-authorized scoped patch after
reading the hierarchy and preserving child rules; runtime proposals, receipts,
prompts, and worker assertions never authorize a write.

## Chat Visualization

Use a visualization only when clearer than prose or a small table. Confirm the
current surface exposes OpenAI Visualizations / `@Visualize` and verify it is
visible; otherwise return a complete table, Mermaid, image, or prose fallback.
Bundled renderers are offline verification, not host integration. Keep one
replace-current HTML preview. A file, cache path, renderer PASS, or browser audit
does not prove mounting; report `USER_VISIBLE=UNVERIFIED` until visibly rendered,
and never print a private directive as delivery.

## Sub-Capability Dispatch

Use the selected task reference as craft guidance, not as a checklist to expose.
Do not enter adjacent stages speculatively. Preserve locked facts, mark only
affected downstream material stale, and make the smallest complete change.

Prompt work keeps Prompt IR model-neutral and applies one model surface at a
time. Verify volatile model claims from current official evidence only when they
affect the answer or execution.

## Result Contract

Lead with the requested artifact or recommendation. Then include only judgment
that changes a creative or production decision, followed by assumptions,
limitations, or one indispensable question.

For Fast and Studio, do not narrate routes, paths, Git, receipts, hashes, gates,
state files, validation commands, or role meetings unless the user requested
that operational information. A complete brief must yield useful content in the
first response.

Validate the current task and its direct dependencies. Unrelated historical or
project-wide debt may be reported separately, but it cannot block or downgrade a
scoped result that does not depend on it.

Whole-film completeness binds every scene/shot to exact time, action, sound,
continuity, entities, generation unit, and dependencies. A sample is never the
whole film. `visual_assets_complete` also needs canonical, decodable,
aspect-correct PNG evidence, bound visual review, and separate trusted host
adoption/readback. Payload reviewer labels, IDs, hashes, and locks do not bypass it, and
it never means master, client, or broadcaster approval.

Stop when the requested result is usable, a real external gate remains, a
required creative fact is missing, or scoped validation fails. Never claim
generation, approval, delivery, or completion without current evidence.

## Compatibility

Legacy v1 role, gate, state, Thread, and exchange records remain read-only. They
are not active templates. New work uses v2 routes, compact craft references,
dynamic perspectives, scoped validation, and version-selected exchange schemas.
