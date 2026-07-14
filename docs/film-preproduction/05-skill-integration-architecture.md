# Skill Integration Architecture

Verified: 2026-05-14

Purpose: define how `Paperrolling-DIRcreative-SKILL` becomes a professional AI video preproduction skill pack, not a loose collection of prompt notes.

This plan is the execution bridge for Goal mode, gstack-style skill execution, and future Codex subagent orchestration.

## Target Outcome

The finished skill pack must help a user move from one rough idea to:

- strong story concept,
- channel-aware creative direction,
- professional treatment and script,
- shot list with camera, blocking, pacing, and sound,
- reference image pack plan,
- JSON-first image prompts for production boards,
- model-specific video prompts for Seedance, Kling, Runway, and Veo,
- QA and retry instructions after generation failures.

It must not behave like a single mega prompt. It must behave like a small film preproduction department with structured handoffs.

## Design Premises

1. Story quality comes before prompt quality.
2. Reference images are production artifacts, not decoration.
3. Video prompts are model adapters, not universal prose.
4. Every skill reads structured artifacts and writes structured artifacts.
5. Every role receives only the knowledge it needs.
6. Prompt patterns must be searchable, sourced, versioned, and tested before promotion.
7. The system must keep improving through a registry and learning loop, not by rewriting the core prompt every time.
8. Codex can run this as a single structured workflow or as parallel role passes when subagents are explicitly authorized.
9. DIRcreative uses a two-level delegation boundary: Codex Threads are first-level durable workers; temporary stateless subagents are second-level local tools inside an explicitly authorized worker.

## Research Distilled Into Reusable Rules

### Image Prompt System

From the character-design prompt, the reusable mechanism is the art-direction control layer:

```json
{
  "art_direction_policy": {
    "non_negotiables": [
      "do not use a generic layout",
      "do not use evenly distributed grids unless a technical sub-section requires it",
      "do not make the layout symmetrical only for symmetry",
      "composition must feel art-directed, intentional, and slightly asymmetric",
      "every section must feel carefully placed, not automatically generated"
    ]
  }
}
```

This applies to character boards, environment boards, prop boards, storyboard boards, lighting boards, and complete production boards.

The rule is not "always asymmetric." The rule is: hierarchy must explain placement. Technical grids are allowed inside a sub-section, but the full board must not look like an unconsidered template.

### Fish-Scale And Material Artifact Guard

The second prompt becomes a targeted surface guard:

```json
{
  "surface_integrity_guard": {
    "required": [
      "clean natural materials",
      "smooth and coherent surface texture",
      "main subject remains clear",
      "background depth layers remain distinct",
      "complete object geometry"
    ],
    "avoid": [
      "fish-scale texture",
      "excessive sharpening",
      "color speckles",
      "random noise",
      "cracks",
      "collapsed surfaces",
      "distorted geometry",
      "broken material continuity"
    ]
  }
}
```

Use this as a targeted retry pattern. Do not globally force transparent backgrounds unless the requested artifact is a cutout or alpha-ready asset.

### Prompt Website / Gallery Pattern

Prompt gallery and prompt-search sites are useful because they separate discovery from compilation:

```text
search examples
-> classify pattern
-> extract reusable mechanism
-> record source
-> test against fixture
-> promote to registry
-> compile project-specific JSON
```

This project should not copy viral prompts wholesale. It should extract patterns such as:

- art-directed asymmetry,
- multi-panel identity lock,
- reference-map prompts,
- exact quoted text,
- motion-focused video prompts,
- material artifact guards,
- model-specific negative phrasing rules.

### GPT Image / Image2 Pattern

For complex boards, use JSON-first authoring:

- canvas and layout before subject detail,
- separate visual systems,
- exact text labels in quotes,
- reference images named by role,
- invariants declared explicitly,
- targeted avoid lines,
- compact final prompt generated from the JSON source.

The JSON is the source of truth. Natural language is a compiled view.

### Video Model Pattern

Video prompts must be adapted by model:

- Seedance: reference map + chronological shot flow + continuity locks + audio section.
- Kling: subject movement + background movement + camera movement; avoid contradicting the input image.
- Runway: high-quality input image + simple positive motion prompt; avoid long negative prompt chains.
- Veo: subject + action + context + camera + lighting + style + audio, with audio written as its own section.

The same shot list should produce different prompts for different models.

### gstack Pattern

The reusable gstack idea is a skill operating system:

- root skill preamble,
- update check,
- session state,
- routing rules,
- sub-skills with narrow responsibilities,
- generated skill docs from templates,
- project learnings,
- timeline/checkpoints,
- health and QA gates,
- changelog and upgrade path.

DIRcreative should copy this architecture pattern, not the browser tooling.

## Two-Level Delegation Contract

First-level Codex Threads own durable execution: `thread_id`, `thread_class`, read/write scope, worktree, receipt, adoption or rejection, validation, and cleanup. Any work that creates repository files, accepted professional output, validation evidence, or durable project truth must stay at this level.

Second-level stateless subagents may be used only as local tools inside an authorized first-level worker. They are appropriate for narrow read-only assistance such as prompt decomposition, reference checks, risk inventory, source triage, and candidate ranking. They are not appropriate for live acceptance, final user judgment, cleanup verification, repository writes, or Goal/objective completion.

The first-level worker must reconcile every second-level output into its own receipt before the result affects production. Required fields are subagent id or `TOOL_BLOCKED`, input question, output summary, close status, adoption decision, adopted artifact path, `durable_truth: false`, `may_write_live_acceptance: false`, and `may_mark_goal_complete: false`.

## Skill Pack Shape

Root package name:

```text
dircreative
```

Repo name can remain:

```text
Paperrolling-DIRcreative-SKILL
```

Root skill responsibility:

- read project state,
- run preflight,
- route to sub-skill,
- enforce phase contract,
- load relevant knowledge packs,
- write artifacts,
- run QA gates,
- record learning and source provenance.

Sub-skills:

```text
dircreative/idea-intake
dircreative/director-room
dircreative/channel-strategy
dircreative/story-development
dircreative/script-treatment
dircreative/script-breakdown
dircreative/shot-design
dircreative/visual-bible
dircreative/reference-image-planner
dircreative/image-prompt-compiler
dircreative/video-model-adapter
dircreative/generation-qa
dircreative/learn
dircreative/update
dircreative/checkpoint
```

Each sub-skill must define:

- inputs,
- outputs,
- knowledge packs,
- allowed edits,
- QA gate,
- next skill,
- failure recovery.

## Skill-To-Skill Contract

No skill reads the whole conversation as its main input.

Every skill reads artifact files:

```text
project.yaml
director-room.yaml
story-package.yaml
script-breakdown.yaml
shot-list.yaml
visual-bible.yaml
image-prompt-manifest.yaml
video-prompt-manifest.yaml
qa-report.yaml
```

Every artifact needs:

```yaml
artifact_id:
version:
source_artifact_ids: []
status: draft | reviewed | approved | locked | deprecated
owner_skill:
created_at:
updated_at:
locked_by_user: false
notes:
```

Downstream skills may read locked upstream artifacts, but must not silently rewrite them. If a downstream issue requires upstream change, write a `revision_request` instead.

## Director Room Mode

Director room is the front-end decision engine. It should produce creative disagreement, not just agreement.

Default core room:

| Role | Purpose | Required Knowledge |
|------|---------|--------------------|
| Producer | channel, scope, production feasibility | channel playbooks, constraints, deliverable map |
| Creative Director | concept, theme, hook, visual metaphor | channel playbooks, reference analysis |
| Director | story-to-screen translation | film glossary, shot grammar, performance notes |
| Screenwriter | logline, conflict, treatment, script | story schema, channel structure |
| Cinematographer | framing, lens, light, camera motion | film glossary, shot list schema |
| Production Designer | world, props, wardrobe, material logic | visual bible schema, image prompt style system |
| Editor | pacing, shot count, transition logic | channel timing, shot duration rules |
| Sound Designer | dialogue, VO, SFX, music, silence | audio design notes, model adapter notes |
| Model Prompt Engineer | reference images and model prompts | image prompt system, video model adapter notes |
| Continuity QA | contradictions, drift, missing assets | all locked artifacts, QA taxonomy |

Execution modes:

```text
single-agent mode:
  one Codex session runs every role sequentially and writes director-room.yaml

parallel-agent mode:
  if explicitly authorized, spawn separate agents for Producer, Creative Director,
  Director/Cinematographer, Screenwriter, and Model Prompt Engineer, then merge
  through Continuity QA
```

Conflict rule:

The director room must preserve disagreements when they matter. Example:

- Producer says the idea is too broad for 15 seconds.
- Director wants a slow reveal.
- Editor says the hook must happen in 2 seconds for short video.

The decision artifact must record the tradeoff and the selected route.

## Canvas Graph Mode

TapNow-style canvas workflows are useful as an interface pattern for DIRcreative.

DIRcreative should be able to express the workflow as a visible graph:

```text
idea -> director room -> story -> script -> shot list -> visual bible
     -> reference boards -> clean frames -> image prompts -> video prompts -> QA
```

Graph rules:

- Each node records role, source artifacts, user gate, and output status.
- Edges record whether an asset is planning-only, reference-only, or direct video input.
- The graph never bypasses required gates.
- Dense storyboard boards stay planning-only unless converted into clean text-free frames.
- Future UI/workbench layers can render this graph without changing the skill contracts.

## Knowledge Pack Loading

Each role gets a minimal knowledge bundle:

```yaml
producer:
  - research/channel-playbooks.md
  - schemas/project.yaml

creative_director:
  - research/channel-playbooks.md
  - research/storyboard-reference-analysis.md

director:
  - research/film-production-glossary.md
  - schemas/shot-list.yaml

screenwriter:
  - schemas/story-package.yaml
  - research/channel-playbooks.md

cinematographer:
  - research/film-production-glossary.md
  - schemas/shot-list.yaml

production_designer:
  - schemas/visual-bible.yaml
  - research/image-prompt-style-system.md
  - prompt-pattern-registry.json

sound_designer:
  - research/audio-design-notes.md
  - research/model-adapter-notes.md

model_prompt_engineer:
  - schemas/image-prompt-manifest.yaml
  - schemas/video-prompt-manifest.yaml
  - schemas/image-prompt-style-config.schema.json
  - templates/image-prompt-style-config.template.json
  - prompt-pattern-registry.json
  - research/model-adapter-notes.md

continuity_qa:
  - schemas/qa-report.yaml
  - all current project artifacts
```

This prevents the "every role has every document" failure mode.

## Professional Output Gates

### Story Creativity Gate

A story package is acceptable only if it has:

- clear subject of desire,
- obstacle or tension,
- emotional turn,
- channel-appropriate hook,
- feasible duration,
- visualizable beats,
- no empty "cinematic" filler.

For ads, product/brand memory must be explicit. For short drama, conflict escalation and cliffhanger must be explicit. For MV, music structure must drive the visual structure.

### Reference Image Gate

A reference pack is acceptable only if:

- each image has one production role,
- boards are not overloaded,
- text is readable,
- layout hierarchy is intentional,
- material behavior is described,
- identity and prop continuity are locked,
- downstream video model will not mistake the board itself for the scene.

### Image Prompt Gate

Every image prompt must include:

- JSON style config,
- selected pattern ids,
- canvas and layout,
- production audience,
- visual systems,
- art-directed layout policy,
- material truth,
- consistency locks,
- exact labels,
- targeted avoid list,
- surface integrity guard when needed.

### Video Prompt Gate

Every model-specific video prompt must include:

- reference map,
- shot goal,
- subject action,
- camera action,
- background motion,
- duration,
- continuity locks,
- audio policy,
- anti-misread clause for boards,
- retry rule for common failures.

It must be rewritten per model. A copied universal prompt fails this gate.

## Self-Update System

DIRcreative needs three update channels.

### Source Refresh

Files:

```text
docs/film-preproduction/sources/model-sources.yaml
docs/film-preproduction/sources/prompt-sources.yaml
```

Each source record:

```yaml
source_id:
url:
source_type: official | github | paper | internal_eval | user_pattern
last_verified:
stable_facts: []
inferred_behavior: []
refresh_trigger:
adapter_impact:
status: active | watch | deprecated
```

### Pattern Registry Update

Existing file:

```text
docs/film-preproduction/prompt-pattern-registry.json
```

Update rule:

```text
new source or output failure
-> extract pattern
-> add source
-> test on fixture
-> promote only after QA improvement
-> deprecate after repeated failure
```

No unsourced prompt pattern becomes active.

### Skill Docs Generation

Use gstack's template idea:

```text
SKILL.md.tmpl
-> scripts/generate-skill-docs
-> SKILL.md
-> validation checks generated sections are fresh
```

Generated sections:

- sub-skill list,
- schema references,
- current model adapter support,
- registry pattern ids,
- verification commands,
- routing table.

Human-written sections:

- role voice,
- workflow philosophy,
- QA standards,
- failure handling.

## Inter-Skill Collaboration Protocol

Every sub-skill writes a receipt using the canonical `skill_run_receipt` defined in:

```text
docs/film-preproduction/schemas/skill-orchestration.yaml
```

Skills communicate through:

- artifact files,
- receipts,
- revision requests,
- QA reports,
- prompt-pattern registry,
- project learnings.

They do not communicate through hidden conversation memory.

### External Orchestrator Adapter

Resolve one execution context before applying chat, thread, or adoption rules:

```text
standalone_chat
orchestrated_worker
```

In `standalone_chat`, DIRcreative is the product harness and owns the outer user gate, thread plan, adoption, validation, cleanup, and session completion boundary.

In `orchestrated_worker`, the caller owns the outer control loop. For ADCO, use `docs/film-preproduction/adco-integration-contract.md`, protocol `adco.specialist-exchange` v1, and profile `dircreative.film-preproduction`. ADCO owns current truth, requirements, worker assignment, client interaction, artifact adoption, project gates, versions, exports, FinalDelivery, and cleanup. DIRcreative owns only the assigned film-preproduction work, scoped provider artifacts, domain QA, bounded retry, structured questions, and adoption recommendation.

The ADCO adapter uses a provider descriptor and capability negotiation instead of a hard-coded ADCO package version or DIR runtime path. An unsupported protocol/version, unverified descriptor, missing capability, stale input hash, invalid worker identity, unsafe scope, authority escalation, or incomplete provider receipt blocks execution. Never fall back to standalone controller behavior inside a failed ADCO handoff.

The assigned worker identity is evidence-bearing only for `execution.mode: codex_thread`: the receipt `execution_evidence.thread_id` must equal the native handoff thread id. `inline` is the native default and must not invent a thread id. A mismatch is `invalid_worker_thread_id` and the result is rejected evidence.

ADCO may supply `worktree`, `isolated_workspace`, or `read_only`. This allows non-git advertising material projects to use `AD-creative/workspaces/<work_id>/` without pretending a git worktree exists. Exact caller-owned paths and write scope remain mandatory; `read_only` may grant only the exact receipt path and no output root.

Native provider receipts bind descriptor and handoff hashes, consumed input hashes, project-relative output paths and hashes, QA, outcome, questions, recommendation, execution evidence, the negotiated domain extension, and all six false client/PPT/final/send/project/control-plane claims. ADCO writes the separate adoption record and closes the handoff host-scope baseline. ADCO must not depend on DIR repository paths, package versions, `.dircreative/runs`, or internal validators. After adoption, both sides must verify target hashes and ADCO project validation before any gate advance is treated as durable evidence.

## Harness And Loop Engineering Contract

The root `dircreative` skill is the product harness. Sub-skills provide professional production capability. In `standalone_chat`, the root harness owns routing, typed stage gates, receipts, retry loops, stop conditions, session persistence, council/cold-review, Goal autorun dry-run boundary, and live acceptance boundary. In `orchestrated_worker`, DIRcreative owns the bounded domain loop while the validated caller owns the outer loop, user gate, adoption, cleanup, and completion decision.

### Typed Stage Gate

Every stage that can change creative truth or generation readiness must declare a typed gate before work continues:

```yaml
stage_gate:
  id:
  type: idea | story | script | shot | visual | reference | image_prompt | video_prompt | generation_qa | retry | acceptance | checkpoint
  status: pass | fail | needs_user | blocked | simulated
  decision_owner: user | simulated_fixture | controller | worker
  source_truth_refs: []
  input_locks: []
  output_artifacts: []
  next_allowed_stage:
  stop_condition:
```

Rules:

- `needs_user` stops live execution and shows one customer-facing decision question.
- `simulated` is valid only for Goal autorun or fixture tests and must name `decision_owner: simulated_fixture`.
- `pass` allows downstream work only for the artifacts listed in `output_artifacts`.
- `fail` must route to the retry loop with one failure id and one corrected layer.
- `blocked` must name the real blocker: user decision, external account/API access, media authorization, unsafe repo state, or live acceptance boundary.

### Receipt And Session Persistence

`skill_run_receipt` is the durable session record. It must be updated after every material stage, worker adoption, retry, checkpoint, and stop.

Minimum receipt fields:

```yaml
skill_run_receipt:
  receipt_version: "1.0"
  run_id:
  skill_id:
  execution_context:
    mode: standalone_chat | orchestrated_worker
    controller_skill:
  orchestrator_context:
    contract_name:
    contract_version:
    caller_skill:
    caller_run_id:
    handoff_id:
    goal_id:
    work_id:
    lane_id:
    lane_run_id:
    target_gate_id:
    absolute_deadline_at:
    adoption_owner:
    skill_sha256:
  worker_identity:
    thread_id:
    source_thread_id:
    assigned_worker_thread_id:
    reporting_thread_id:
  stage_gate:
  input_artifacts: []
  output_artifacts: []
  decisions: []
  unresolved_questions: []
  retry_loop:
    failure_id:
    corrected_layer:
    unchanged_locks: []
    next_smallest_artifact:
  qa_gate:
    status: pass | fail | needs_user
    reasons: []
  session_state:
    checkpoint_path:
    source_truth_refs: []
    stale_artifacts: []
  domain_delivery:
    domain_verdict: domain_accepted | draft_accepted_with_limitations | needs_user | needs_revision | blocked
    discussion_ready: false
    specialist_handoff_ready: false
    generation_ready: false
    client_ready: false
    final_export_allowed: false
    hard_blockers: []
    evidence_refs: []
    dirty_state_impact:
    worker_recommendation:
    loop_state:
    qa_gate_status:
    manifest_index_updates_needed: []
    recurrence_guard:
    cleanup_actions: []
    adoption_recommendation: adopt_as_internal_draft | adopt_for_next_gate | reject | defer
  next_recommended_skill:
```

Session persistence must not depend on chat history. Durable state lives in artifacts, manifests, `.dircreative/runs/`, checkpoint files, dispatch records, adoption records, QA output, and receipts.

In `orchestrated_worker`, `client_ready`, `final_export_allowed`, and `generation_ready` remain false in the v1 specialist receipt. The current profile is prompt-only; real media requires a separately negotiated profile with work/asset/hash-bound authorization and pre-generation evidence. ADCO writes the adoption decision after receiving the DIRcreative recommendation.

### Retry Loop

Retry is an engineering loop, not a rewrite pass:

```text
failure id
-> corrected layer
-> unchanged locks
-> one smallest artifact
-> falsifiable expected improvement
-> QA check
-> receipt update
```

Do not change story, reference identity, camera logic, style, model adapter, and output controls in one retry. If the failure touches multiple layers, stop and route upstream to the earliest owning stage.

### Council And Cold Review

Use `docs/film-preproduction/council-adversarial-review.md` when a stage could pass validation while still failing the user. Use cold review after non-trivial harness, thread, retry, acceptance, or generation-boundary changes.

Council/cold-review output is advisory until reconciled into a repo doc, skill rule, artifact, receipt, failure taxonomy, retry rule, validation script, or adoption record. It cannot mark a Goal complete.

### Goal Autorun And Live Acceptance Boundaries

Goal autorun is a dry-run harness. It may prove loop coverage for rough idea, complete idea, product ad, Creative Production preflight, QA, and retry, but it cannot prove live acceptance.

Hard boundary:

- no real image/video generation in Goal autorun,
- no `live-user-acceptance.yaml` in Goal autorun,
- no `real_user_co_creation_verified: true` from simulated choices,
- no `update_goal` from dry-run evidence,
- no `OBJECTIVE_COMPLETE` claim from validation, worker approval, council approval, generated media, or prompt-only export.

Live acceptance requires the live chat acceptance runbook and an explicit real user acceptance statement before `.dircreative/runs/live-user-acceptance.yaml` is written.

## Project Learning

DIRcreative keeps one canonical current-state file. Historical JSONL samples are read-only regression fixtures with no live authority:

```text
.dircreative/state/current.json
.dircreative/checkpoints/
.dircreative/runs/
tests/fixtures/runtime/history/  # fixture only; never resume from here
```

Learning schema:

```json
{
  "ts": "2026-05-14T00:00:00Z",
  "skill": "image-prompt-compiler",
  "type": "pattern",
  "key": "art-directed-asymmetric-layout",
  "insight": "Use layout hierarchy and section placement logic to prevent generic equal-grid boards.",
  "confidence": 8,
  "source": "user-stated",
  "artifact_refs": []
}
```

Learning types:

```text
pattern
pitfall
preference
model_behavior
channel_rule
qa_failure
prompt_fix
```

## WYSIWYG Workbench Thinking

The future frontend should not expose only prompts.

It should expose the production state:

```text
Idea Board
Director Room
Story Package
Script Breakdown
Shot Table
Visual Bible
Reference Pack
Prompt Manifest
Generation QA
Pattern Registry
```

Key interaction principles:

- users lock approved artifacts,
- downstream regeneration shows what will change,
- reference images map to shot IDs,
- model prompts show differences side by side,
- generated outputs are scored against gates,
- failed outputs create retry instructions and registry candidates.

Website inspiration to reuse:

- searchable prompt library,
- category filters,
- example-to-pattern extraction,
- remix mode,
- refresh schedule,
- curated results instead of infinite prompt dump.

## Codex Execution Strategy

Codex-native implementation should start file-driven.

First implementation layer:

- Markdown docs,
- YAML/JSON schemas,
- fixtures,
- verification commands,
- phase contracts,
- local skill folders.

Second implementation layer:

- scripts for validation,
- generated skill docs,
- registry search,
- source refresh checks,
- artifact receipts.

Third implementation layer:

- optional browser/workbench,
- optional image/video API adapters,
- optional multi-agent parallel execution.

Subagent policy:

- use role simulation in normal execution,
- use real parallel agents only when the user explicitly authorizes subagents,
- split agents by non-overlapping artifact ownership,
- merge through Continuity QA.

## Execution Roadmap To Skill Pack

### Stage 1: Contract Completion

Add:

- artifact metadata fields,
- skill orchestration schema,
- source registry schema,
- run receipt schema.

Done when a downstream worker can tell exactly which skill owns each artifact.

### Stage 2: Fixture Completion

Complete `cyber-courier` through:

- story package,
- script,
- script breakdown,
- shot list,
- visual bible,
- reference image plan,
- image prompt manifest,
- video prompt manifest,
- QA report.

Done when the same idea produces distinct outputs for film, ad, short drama, short video, and MV constraints.

### Stage 3: Skill Drafts

Create local draft skills:

```text
skills/dircreative/SKILL.md
skills/dircreative/director-room/SKILL.md
skills/dircreative/story-development/SKILL.md
skills/dircreative/shot-design/SKILL.md
skills/dircreative/image-prompt-compiler/SKILL.md
skills/dircreative/video-model-adapter/SKILL.md
skills/dircreative/generation-qa/SKILL.md
```

Done when each skill has one clear input/output boundary.

### Stage 4: Update And Learning Infrastructure

Add:

- `.dircreative/` run state,
- source registries,
- prompt pattern registry search,
- learning log,
- generated SKILL docs,
- validation script.

Done when a new source can be added without editing the root skill by hand.

### Stage 5: Workbench Plan

Design the frontend around artifacts and locks, not prompts.

Done when every UI surface maps to artifact IDs and versioned source dependencies.

## gstack-Ready Execution Standard

A future gstack/Goal worker should be able to run:

```text
Read README.md.
Read docs/film-preproduction/04-goal-mode-handoff.md.
Read docs/film-preproduction/05-skill-integration-architecture.md.
Read docs/film-preproduction/phase-contracts.yaml.
Execute only the active phase.
Write artifacts only inside allowed edits.
Run verification.
Commit.
Report STATUS, PHASE, CHANGED, VERIFIED, NEXT.
```

Quality bar:

- no phase skips,
- no prompt generation before story/shot/reference artifacts exist,
- no unverified source claims,
- no single universal video prompt,
- no copied prompt-library dumps,
- no hidden state as the only handoff,
- no generated image/video without explicit phase permission.

## Sources Used

- OpenAI GPT Image prompting guide: https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide
- wuyoscar GPT Image 2 skill: https://github.com/wuyoscar/gpt_image_2_skill
- YouMind GPT Image 2 prompt search skill: https://github.com/YouMind-OpenLab/gpt-image-2-prompts-search
- Runway Gen-4 Video Prompting Guide: https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide
- Kling Image-to-Video Guide: https://kling.ai/quickstart/image-to-video-guide
- Google Veo video prompt guide: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide
- Seedance 2.0 paper: https://arxiv.org/abs/2604.14148
- Private local gstack architecture reference used during design review; not distributed with this repository.
- Private local gstack self-learning reference used during design review; not distributed with this repository.
