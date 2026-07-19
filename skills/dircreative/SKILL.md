---
name: dircreative
description: Use only after the user explicitly invokes $dircreative for film preproduction: story, script, storyboard, shot planning, visual systems, reference-image planning, and model-specific video prompts. ADCO mode accepts only a validated Specialist Exchange handoff. Do not use for maintaining, debugging, refactoring, testing, or evaluating the DIRcreative source repository; maintaining ADCO; ordinary code work; factual questions; or generic advertising requests without an explicit $dircreative invocation.
---

# DIRcreative

DIRcreative is a film-preproduction router. It selects one execution context, one
mode, one Route Card, and the smallest task-specific file set before calling a
sub-capability.

## Invocation Boundary

Start only when either condition is true:

- the user explicitly writes `$dircreative`; or
- a validated `adco.specialist-exchange` handoff selects
  `dircreative.film-preproduction`.

Never activate for repository maintenance, ADCO maintenance, ordinary code work,
fact questions, or generic advertising language without `$dircreative`.

## Router Contract

1. Run `python3 scripts/dircreative_route.py "<request>"`. For an exchange, pass
   `--handoff <path>` instead of copying the handoff into prose.
2. Accept only the stable JSON fields `execution_context`, `mode`, `route`,
   `required_files`, `optional_files`, `external_user_gate`, `action`,
   `first_response_contract`, `reuse_known_brief`, `state_persistence`,
   `threads_allowed`, `full_receipt_required`, and `reason_codes`.
3. If the route is `source_maintenance` or the handoff is invalid, stop Skill
   execution and return the reason code.
4. Read exactly one selected Route Card:
   - `fast` -> `skills/dircreative/routes/fast-task.md`
   - `studio` -> `skills/dircreative/routes/studio-development.md`
   - `delivery` -> `skills/dircreative/routes/delivery-audit.md`
5. Read only `required_files`; read an optional file only when current evidence
   shows it is needed. Never expand a file reference into a general preflight.

## Startup Reads

- There are zero unconditional protocol reads.
- The router selects one Route Card before any task contract is opened.
- Route Card references are terminal for routing; do not follow a second routing
  chain.

## Execution Context

`standalone_chat` owns the visible response and any local compact state.

`orchestrated_worker` exists only after a valid exchange handoff. ADCO remains the
controller and owns Current Truth, versions, adoption, client visibility,
readiness, completion, and cleanup. Specialist Exchange v2 executes inline,
forbids nested dispatch, and returns only domain outputs, domain QA, status, and
`open_questions`; it does not emit readiness claims. Read-only v1 receipts retain
their six false client/PPT/final/send/project/control-plane claims.

Repository maintenance is outside Skill runtime.

## Modes

### Fast

Use for one bounded copy, shot, storyboard, prompt, or existing-artifact change.
Fast uses one agent, zero Threads, zero Director Room, no full project state, no
full receipt, no staged confirmation sequence, and at most three task files.
Return the revised result directly. No file write means no receipt.

### Studio

Use for a complete concept, story plus script, script plus storyboard,
multi-output preproduction, a 15-180 second project, or a complex visual system.
Studio uses one controller, at most three dynamic professional perspectives, at
most one independent critical pass, and zero Threads by default. It does not
manufacture conflict or expose role-card ceremony before the work.

### Delivery

Use only for real generation authorization, formal assets or versions,
client-visible delivery, final prompt or asset handoff, or a valid Specialist
Exchange handoff. Only Delivery may use full receipts, hashes, authorization, and
strict audit.

## External User Gates

The only v2 external gates are:

- `concept_lock` for incompatible creative directions;
- `generation_authorization` before real generation; and
- `client_delivery_approval` before client-visible delivery.

Story, script, shot, visual, reference, prompt, and QA states are reversible
internal state. “Continue” continues when no real blocker exists. A bounded edit
never returns to idea intake. A complete supplied brief is not re-asked. When the
user requests an artifact, the first response contains useful artifact content.

## Compact State

Use `skills/dircreative/runtime/state-snapshot.schema.json`.

- Fast keeps state in memory and normally writes nothing.
- Studio persists only for pause, cross-session resume, or multi-file output.
- Delivery persists.
- Run the full state audit only for resume, handoff, Delivery, or a completion
  claim.

## Sub-Capability Dispatch

Invoke only the capability selected by `route` and `required_files`. Do not enter
adjacent stages speculatively. Preserve locked facts, mark changed downstream
outputs stale, and make the smallest valid edit.

Prompt compilation keeps Prompt IR model-neutral and uses exactly one selected
model adapter. Media generation is outside prompt compilation.

## Result Contract

Lead with the requested creative result. Add only the professional judgment that
changes the decision, then assumptions, limitations, or one blocking question.
Do not put meetings, role lists, gates, receipts, or terminal logs before the
artifact.

Stop when the selected Route Card's output is delivered, a declared external gate
is reached, a required input is missing, or validation fails. Never claim work,
generation, client approval, external execution, or completion without current
evidence.

## Compatibility

Legacy v1 project, Director Room, gate, state, and exchange records are read-only
compatible. New runs use v2 routing, dynamic perspectives, three external gates,
compact state, model adapters, and version-selected exchange validation.

The canonical owner index is
`docs/film-preproduction/runtime-contracts.md`. Supporting guides never override
the machine-readable owners listed there.
