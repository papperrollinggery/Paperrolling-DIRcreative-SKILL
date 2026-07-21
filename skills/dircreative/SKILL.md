---
name: dircreative
description: Use only after the user explicitly invokes $dircreative for film preproduction: story, script, storyboard, shot planning, visual systems, reference-image planning, and model-specific video prompts. ADCO mode accepts only a validated Specialist Exchange handoff. Do not use for maintaining, debugging, refactoring, testing, or evaluating the DIRcreative source repository; maintaining ADCO; ordinary code work; factual questions; or generic advertising requests without an explicit $dircreative invocation.
---

# DIRcreative

DIRcreative helps make the film work better. Spend attention on story, image,
sound, performance, continuity, and model behavior; keep routing and evidence
machinery subordinate to the requested result.

## Invocation Boundary

Start only when the user explicitly writes `$dircreative`, or when a validated
`adco.specialist-exchange` handoff selects `dircreative.film-preproduction`.

Never activate for this repository's maintenance, ADCO maintenance, ordinary
code work, fact questions, or generic advertising language. If maintenance is
misrouted here, classify it as `source_maintenance` and stop Skill execution.

## Router Contract

Choose an obvious standalone route directly; do not run a script before useful
creative work:

| Request | Mode / route | Route Card | One task reference |
| --- | --- | --- | --- |
| bounded copy or script change | Fast / `copy_revision` | `routes/fast-task.md` | `references/copy-script.md` |
| one shot or a few storyboard frames | Fast / `shot_optimization` or `storyboard_review` | `routes/fast-task.md` | `references/shot-storyboard.md` |
| bounded model prompt change | Fast / `prompt_revision` | `routes/fast-task.md` | `references/prompt-model.md` |
| other bounded revision | Fast / `bounded_revision` | `routes/fast-task.md` | none |
| complete or multi-output film work | Studio / `film_development` | `routes/studio-development.md` | `references/film-development.md` |
| real generation or client delivery | Delivery / `generation_authorization` or `client_delivery` | `routes/delivery-audit.md` | `references/generation-delivery.md` |
| fully validated ADCO handoff | Delivery / `adco_specialist_exchange` | `routes/delivery-audit.md` | `references/specialist-exchange.md` plus the descriptor schema |

Run `python3 scripts/dircreative_route.py --handoff <file> --project-root <dir>`
only to validate an ADCO handoff, or run the router on text when
the request is genuinely ambiguous between modes. A schema-only handoff fails
closed; the ADCO route verifies the descriptor, locked input hashes, brief
binding, capabilities, exact exchange-index registration, descriptor snapshot,
and isolated output/receipt scope. It is not a mandatory creative preflight.

Read exactly one selected Route Card, then only the task reference in the table.
Do not follow references from that card into another protocol chain. Optional
model/source evidence is fetched only when a current claim or real execution
depends on it.

## Startup Reads

- There are zero unconditional protocol reads.
- An obvious Fast or Studio request needs no router tool call before the result.
- One Route Card and one task reference are the normal maximum.

## Execution Context

`standalone_chat` owns the response and any compact working state.

`orchestrated_worker` exists only after a valid exchange handoff. ADCO owns host
truth, versions, adoption, client visibility, readiness, completion, and cleanup.
DIR returns only requested film artifacts, domain QA, status, and open questions.
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
ceremony. Threads default to zero.

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

Stop when the requested result is usable, a real external gate remains, a
required creative fact is missing, or scoped validation fails. Never claim
generation, approval, delivery, or completion without current evidence.

## Compatibility

Legacy v1 role, gate, state, Thread, and exchange records remain read-only. They
are not active templates. New work uses v2 routes, compact craft references,
dynamic perspectives, scoped validation, and version-selected exchange schemas.
