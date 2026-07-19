# DIRcreative Runtime Contracts

Verified: 2026-07-19

Status: canonical index for the active v2 source runtime. This index names one
owner for each executable contract; linked guides explain presentation or legacy
compatibility but do not redefine behavior.

## Contract Ownership

| Contract | Canonical owner | Supporting guide |
| --- | --- | --- |
| Invocation | `skills/dircreative/agents/openai.yaml` | root `SKILL.md` invocation boundary |
| Route and mode selection | `skills/dircreative/runtime/routing-policy.yaml` | `skills/dircreative/SKILL.md` |
| Fast execution | `skills/dircreative/routes/fast-task.md` | none |
| Studio execution | `skills/dircreative/routes/studio-development.md` | none |
| Delivery execution | `skills/dircreative/routes/delivery-audit.md` | none |
| Adaptive perspective selection | `docs/film-preproduction/director-room-routing.md` | machine mirror in `schemas/director-role-harness.yaml` |
| External gates and persistence policy | `skills/dircreative/runtime/routing-policy.yaml` | chat/start/integrity presentation guides |
| Compact working state | `skills/dircreative/runtime/state-snapshot.schema.json` | `runtime-state-governance.md` only at durable audit boundaries |
| Prompt IR | `docs/film-preproduction/schemas/prompt-ir.schema.json` | prompt authoring and QA guides |
| Model adapter interface | `scripts/dircreative_adapters/base.py` | one module per provider adapter |
| Specialist Exchange | `docs/film-preproduction/schemas/adco-specialist-descriptor.json` and versioned handoff/receipt schemas | `adco-integration-contract.md` |
| Legacy Thread evidence | `docs/film-preproduction/thread-orchestration-protocol.md` | read-only v1 compatibility only |

`docs/film-preproduction/phase-contracts.yaml` is a repository fixture plan. It
does not own chat runtime routing, gates, state, or completion.

## Active Flow

```text
explicit $dircreative or validated ADCO handoff
  -> source router
  -> exactly one mode and one Route Card
  -> smallest route-specific context
  -> useful artifact first
  -> optional compact state or one real external gate
```

The active modes are:

- Fast: bounded copy, shot, storyboard, prompt, or existing-artifact revision;
  zero Threads, zero Director Room, no full receipt or full-project validation.
- Studio: complete or multi-output film development; one controller, zero
  Threads by default, at most three adaptive perspectives and one critic.
- Delivery: generation authorization, formal handoff, client delivery, or a
  validated Specialist Exchange; full audit is allowed here only.

New runs may stop only at `concept_lock`, `generation_authorization`, or
`client_delivery_approval`. Story, script, shot, visual, reference, prompt, and
QA progress are reversible internal state. A known brief is reused. A bounded
edit never reopens intake.

## Context Boundary

- Startup has no unconditional protocol read.
- The router opens one Route Card; a Route Card does not route again.
- Fast never loads ADCO, Thread, Goal, Delivery, or FinalDelivery contracts.
- Studio never loads FinalDelivery contracts.
- The ADCO integration contract is loaded only for a schema-valid handoff.
- Full state audit runs only for resume, handoff, Delivery, or a completion claim.

## Director Room v2

Fast tasks use direct professional judgment and never enter Director Room.
Studio selects only `narrative_strategy`, `visual_production`, and/or
`model_continuity`, with a maximum of three. There is no fixed seat count, no
minimum disagreement count, and no forced option list. The requested artifact or
recommendation appears before supporting judgments.

The ten v1 role contracts remain a read-only knowledge index. They are not
workers, mandatory passes, or user-visible cards.

## Prompt Adapters

`scripts/dircreative_prompt_compiler.py` remains the compatible CLI and Prompt IR
entry. It selects one adapter module. Each adapter independently owns reference
limits and syntax, timeline and duration rules, camera/audio/look/negative
surface, unsupported capabilities, prompt budget, and compression order.

Over-budget prompts fail with `prompt_budget_exceeded`. Tests cover, for every
adapter, a valid prompt plus invalid reference count, budget, timeline, and
unsupported-capability cases.

## Specialist Exchange

The descriptor advertises ordered support for `1.0` and `2.0`, and the provider
dispatches validation by message version.

- v1 remains readable, including its descriptor/handoff hashes, scoped receipt,
  false readiness claims, and ADCO adoption validation.
- v2 is the default compact write contract. It is inline-only, forbids nested
  dispatch, and does not copy Current Truth, Goal, versions, user confirmations,
  Client Readiness, cleanup, adoption, visibility, or completion state.
- A v2 receipt returns only real domain output file hashes, domain QA, status,
  and open questions. ADCO owns adoption and all host/client state.

Provider fixtures are not bilateral evidence. A current ADCO checkout must pass
the explicit `--adco-repo` audit before claiming cross-repository compatibility.

## Version Compatibility

| Surface | New writes | Existing reads |
| --- | --- | --- |
| Router, gates, compact state | v2 | legacy project/state records read-only |
| Director Room | dynamic v2 perspectives | v1 ten-role artifacts read-only |
| Specialist Exchange | compact v2 | v1 handoff/receipt/adoption compatible |
| Thread records | none by default in active routes | verified legacy v1 evidence only |

Compatibility never turns a legacy record into an active template. Migration
creates a new v2 artifact and preserves the old source unchanged.

## Verification

Focused source audits:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_activation_policy_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_context_budget_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_director_harness_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_prompt_fixture_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_adco_native_exchange.py --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_headless_acceptance_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_project.py
```

The headless audit launches isolated subprocesses and must write non-empty,
human-readable Fast and Studio answers that exactly match reviewed snapshots.
An empty answer or route JSON without an answer fails. Reviewed outputs are:

- `tests/fixtures/headless-runtime/expected/fast-copy-revision.md`
- `tests/fixtures/headless-runtime/expected/studio-complete-film.md`

These deterministic source fixtures prove routing and answer production. They do
not prove external model generation, client approval, a published release, or
live creative acceptance.
