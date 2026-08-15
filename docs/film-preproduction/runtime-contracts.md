# DIRcreative Runtime Contracts

Verified: 2026-07-19

Status: canonical index for the active v2 source runtime. This index names one
owner for each executable contract; linked guides explain presentation or legacy
compatibility but do not redefine behavior.

## Contract Ownership

| Contract | Canonical owner | Supporting guide |
| --- | --- | --- |
| Invocation | `skills/dircreative/agents/openai.yaml` | root `SKILL.md` invocation boundary |
| Route, mode, and post-route Skill Stack selection | `skills/dircreative/runtime/routing-policy.yaml` | root `SKILL.md` plus conditional `references/visual-skill-stack.md` |
| Fast execution | `skills/dircreative/routes/fast-task.md` | none |
| Studio execution | `skills/dircreative/routes/studio-development.md` | none |
| Delivery execution | `skills/dircreative/routes/delivery-audit.md` | none |
| Adaptive perspective selection | `docs/film-preproduction/director-room-routing.md` | machine mirror in `schemas/director-role-harness.yaml` |
| External gates and persistence policy | `skills/dircreative/runtime/routing-policy.yaml` | chat/start/integrity presentation guides |
| Compact working state | `skills/dircreative/runtime/state-snapshot.schema.json` | `runtime-state-governance.md` only at durable audit boundaries |
| Whole-film visual asset coverage | `skills/dircreative/runtime/visual-asset-plan.schema.json` | compact craft rules in `references/film-development.md` and `references/generation-delivery.md` |
| Prompt IR | `docs/film-preproduction/schemas/prompt-ir.schema.json` | prompt authoring and QA guides |
| Model adapter interface | `scripts/dircreative_adapters/base.py` | one module per provider adapter |
| Specialist Exchange | `docs/film-preproduction/schemas/adco-specialist-descriptor.json` and versioned handoff/receipt schemas | `adco-integration-contract.md` |
| Legacy Thread evidence | `docs/film-preproduction/thread-orchestration-protocol.md` | read-only v1 compatibility only |

`docs/film-preproduction/phase-contracts.yaml` is a repository fixture plan. It
does not own chat runtime routing, gates, state, or completion.

## Active Flow

```text
explicit $dircreative or validated ADCO handoff
  -> direct route judgment for obvious standalone work
  -> exactly one mode, one Route Card, and at most one craft card
  -> optional bounded advisory Skill Stack after mode/deliverable selection
  -> deterministic router only for ambiguity or handoff validation
  -> useful artifact first
  -> optional compact state or one real external gate
```

The active modes are:

- Fast: bounded copy, shot, storyboard, prompt, or existing-artifact revision;
  zero Threads, zero Director Room, no full receipt or full-project validation.
- Studio: complete or multi-output film development; one controller, zero
  Threads by default, at most three adaptive perspectives and one critic. A
  whole-film scope also emits a visual asset matrix covering every scene and
  shot before generation.
- Delivery: generation authorization, formal handoff, client delivery, or a
  validated Specialist Exchange; full audit is allowed here only.

New runs may stop only at `concept_lock`, `generation_authorization`, or
`client_delivery_approval`. Story, script, shot, visual, reference, prompt, and
QA progress are reversible internal state. A known brief is reused. A bounded
edit never reopens intake. A current request that explicitly authorizes the same
generation or delivery action satisfies its gate; the runtime does not ask twice.

## Context Boundary

- Startup has no unconditional protocol read and no mandatory router command.
- Obvious Fast and Studio requests go directly to one Route Card and one compact
  craft card under `skills/dircreative/references/`.
- The host catalog may supply a bounded advisory Skill Stack after that route.
  Discovery is read-only and conditional; it is never a startup preflight.
- The deterministic router is a machine mirror for ambiguous requests, ADCO
  validation, and tests; it is not a creative preflight.
- Fast never loads ADCO, Thread, Goal, Delivery, or FinalDelivery contracts.
- Studio never loads FinalDelivery contracts.
- Active v2 routes never load the legacy nested subskills, professional voice
  standard, ten-role harness, client hard-gate document, or full capability
  policy. Those remain available for legacy reads and focused engineering tests.
- Full state audit runs only for resume, handoff, Delivery, or a completion claim.

## Content-First Budgets

Loaded context means root `SKILL.md` plus the selected Route Card and required
task references. `dircreative_context_budget_audit.py` calculates it from the
actual routing policy on every validation run.

| Mode | Context | Files | Runtime behavior |
| --- | ---: | ---: | --- |
| Fast | <= 14,000 bytes | <= 4 | one task reference, <= 1 provider body, zero routing/audit preflight, >= 75% useful content |
| Studio | <= 20,000 bytes | <= 6 | one task reference, <= 3 provider bodies/perspectives, >= 70% useful content |
| Delivery | <= 30,000 bytes | <= 5 | <= 2 task references, <= 1 provider body, evidence only for the real action |

Fast and Studio do not run whole-project validation. Current output and direct
dependencies define the scoped result. Unrelated historical/control-plane debt
is reported separately and cannot downgrade an independent scoped pass. A scoped
pass also never implies that the whole project is client-ready.

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
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_content_first_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_live_model_eval.py --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visual_asset_plan.py --self-test
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

Visual asset plan v2.2 binds the plan to a colocated source inventory, the
approved shot-card file, full per-shot creative truth, and their canonical
SHA-256 values. Shot-card ranges must be continuous, agree with declared
durations, end at the film duration, and land on the selected frame rate.
`--stamp-evidence` accepts dependency-free canonical PNG evidence, full-decodes
each required raster under one normalization profile, checks scene/style/shot
and clean-input frames against the delivery aspect, records file and pixel
hashes, and emits only a bound technical receipt; the decoder name is diagnostic
and does not make the receipt environment-specific. It never grants visual QA.
JPEG/WebP may remain source or preview media but must be normalized to canonical
PNG before completion. Every completion-path asset,
including `user_locked` and `reused_locked`, needs a role-specific review entry
in a separate package-local review manifest read as one hash-bound byte snapshot,
and a receipt bound to that file's SHA-256. Generated paths must remain relative
to the plan directory. These
local receipts are content-bound attestations, not cryptographic signatures or
client/broadcaster acceptance.

```bash
python3 scripts/dircreative_visual_asset_plan.py \
  --plan /path/to/package/visual-asset-plan.json \
  --stamp-evidence \
  --output /path/to/package/visual-asset-plan.json
```

For a real model-level forward test, install the source package into an isolated
repo-local `.agents/skills/dircreative` target and run:

```bash
python3 scripts/dircreative_live_model_eval.py \
  --model gpt-5.6-sol \
  --codex-home <isolated-authenticated-codex-home> \
  --output-dir <temporary-output-dir>
```

The live harness uses read-only, ephemeral `codex exec`, disables plugins/apps/
multi-agent behavior, preserves no session, and rejects process-only answers,
router/audit/Git preflights, missing craft concepts, excess questions, and tool
calls over the per-case budget. It never updates a global Skill directory.
