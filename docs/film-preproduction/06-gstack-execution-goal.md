# GStack Execution Goal

Status: release-candidate; keep goal active until live user acceptance

Repository: `<repo-root>`

Objective: execute the project until `dircreative` becomes a practically usable, professional AI video preproduction skill pack.

This is not a one-phase planning task. It is a staged execution goal. Continue phase by phase, commit after each verified phase, update `phase-contracts.yaml`, and keep going until the final acceptance standard below is met or a real blocker is reached.

## One-Line Goal

Build `dircreative` into a local skill pack that can take one rough idea and produce professional creative development, script/treatment, shot plan, reference image prompts, model-specific video prompts, QA/retry guidance, and reusable learning/update behavior.

Current state: the local release gate now installs and validates the skill package. The remaining completion blocker is not packaging; it is proving the live chat experience satisfies the user.

## Read First

Read in order:

1. `README.md`
2. `docs/film-preproduction/04-goal-mode-handoff.md`
3. `docs/film-preproduction/05-skill-integration-architecture.md`
4. `docs/film-preproduction/phase-contracts.yaml`
5. `docs/film-preproduction/schemas/skill-orchestration.yaml`
6. `docs/film-preproduction/research/*`
7. `docs/film-preproduction/schemas/*`
8. `docs/film-preproduction/prompt-pattern-registry.json`

## Execution Rules

- Start from `project.active_phase` in `docs/film-preproduction/phase-contracts.yaml`.
- Execute phases in order. Do not skip phases.
- After each phase passes verification, commit the result and update the next phase to active.
- Keep prior completed foundation inserts intact.
- Do not generate real images or videos unless a later explicit phase and user authorization allows it.
- Do not collapse the project into one giant prompt.
- Do not copy prompt galleries wholesale. Extract reusable patterns with sources.
- Do not use one universal video prompt for all models.
- Do not call the project complete until the final acceptance standard passes.

## Harness Loop Rule

Run each phase as a bounded engineering loop, not a one-shot prompt pass:

```text
typed stage gate
-> scoped production action
-> artifact and receipt
-> QA or council/cold-review
-> smallest retry if needed
-> checkpoint/session state
-> stop at needs_user, blocked, dry-run boundary, or live acceptance boundary
```

Loop contract:

- Every phase must name its typed stage gate, source truth, output artifact, QA status, stop condition, and next allowed skill.
- Every retry must use one failure id, one corrected layer, visible unchanged locks, one smallest artifact, and a falsifiable next QA check.
- Codex Thread worker output is advisory until the main-controller records adoption or rejection and validates the accepted diff.
- Temporary stateless subagents may assist an explicitly authorized worker only as second-level local tools; the first-level worker still owns the receipt, adoption record, cleanup evidence, and all durable truth.
- Goal autorun dry-runs, generated media, council approval, release-gate PASS, worker PASS, and prompt-only exports cannot produce `OBJECTIVE_COMPLETE: YES`.
- Live completion still requires the live chat acceptance runbook and a real user acceptance receipt.

## Long-Run Phase Target

Complete these phases in order:

```text
Phase B: Story fixture completion
Phase C: Script and breakdown fixture
Phase D: Shot design fixture
Phase E: Visual bible and reference pack
Phase F: Image prompt compiler design
Phase G: Video model adapters
Phase H: Skill packaging
Phase I: WYSIWYG workbench plan
```

If phase contracts are missing required detail, improve the contract first, then execute.

## Required Execution Depth

### 1. Finish The Cyber Courier End-To-End Fixture

Produce a full professional fixture from the existing rough idea:

```text
idea intake
director room
concept selection
logline
beat sheet
treatment
script
script breakdown
asset requirements
audio policy
shot list
camera plan
blocking plan
shot QA
visual bible
reference pack plan
image layout spec
image prompt manifest
image prompt files
video prompt manifest
Seedance prompt
Kling prompt
Runway prompt
Veo prompt
model adapter risk notes
generation QA report template
```

This fixture is the proof that the workflow can turn one idea into professional AI-video-ready preproduction assets.

### 2. Add A Second Channel-Specific Fixture

Add one smaller second fixture to prove the system is not overfit to a cinematic short.

Recommended:

```text
examples/product-ad-raincoat/
```

Minimum output:

- idea intake,
- director room notes,
- concept options,
- selected concept,
- 15s/30s ad structure,
- shot list,
- reference pack plan,
- image prompt manifest,
- video prompt manifest.

This fixture must prove the system can handle advertising/product logic, not only narrative film logic.

### 3. Package Local Skills

Create the local skill pack:

```text
skills/dircreative/SKILL.md
skills/dircreative/idea-intake/SKILL.md
skills/dircreative/director-room/SKILL.md
skills/dircreative/story-development/SKILL.md
skills/dircreative/script-treatment/SKILL.md
skills/dircreative/script-breakdown/SKILL.md
skills/dircreative/shot-design/SKILL.md
skills/dircreative/visual-bible/SKILL.md
skills/dircreative/reference-image-planner/SKILL.md
skills/dircreative/image-prompt-compiler/SKILL.md
skills/dircreative/video-model-adapter/SKILL.md
skills/dircreative/generation-qa/SKILL.md
skills/dircreative/learn/SKILL.md
skills/dircreative/update/SKILL.md
skills/dircreative/checkpoint/SKILL.md
```

Root skill must:

- run preflight,
- read phase contracts,
- route to sub-skills,
- load only relevant knowledge packs,
- enforce artifact handoffs,
- write `skill_run_receipt`,
- reconcile `.dircreative/state/current.json`; keep `tests/fixtures/runtime/history/` read-only and non-authoritative,
- support update/checkpoint behavior.

### 4. Add Validation And QA Scripts

Add local validation commands, preferably under:

```text
scripts/
```

Required checks:

- YAML parse,
- JSON parse,
- required artifact existence,
- prompt manifest structure,
- video prompt manifest structure,
- prompt pattern registry references,
- no placeholder markers,
- no universal-model video prompt duplication,
- skill files cite their required schemas/research files.

### 5. Add Professional Quality Gates

Create or complete:

```text
docs/film-preproduction/qa/qa-checklist.md
docs/film-preproduction/qa/failure-taxonomy.yaml
docs/film-preproduction/qa/retry-rules.md
```

Must cover:

- weak story idea,
- generic script,
- vague visual direction,
- overloaded shot,
- unusable reference image plan,
- generic grid board layout,
- fish-scale/material artifact,
- image prompt missing JSON style config,
- storyboard board misread by video model,
- same video prompt copied across models,
- missing audio policy,
- model-specific motion failure.

### 6. Add Self-Update Infrastructure

Create source registries:

```text
docs/film-preproduction/sources/model-sources.yaml
docs/film-preproduction/sources/prompt-sources.yaml
```

Create update guidance:

```text
skills/dircreative/update/SKILL.md
```

The update skill must:

- check source freshness,
- distinguish official facts from inferred behavior,
- update model adapter notes when sources change,
- propose prompt pattern candidates,
- promote patterns only after fixture QA improvement,
- record deprecated patterns and failure reasons.

## Professional Acceptance Standard

The project is not done until all conditions are true:

- A user can start with one vague idea and run the local workflow to produce a coherent creative package.
- The director-room stage produces real tradeoffs across producer, creative director, director, writer, cinematographer, production designer, editor, sound designer, model prompt engineer, and continuity QA.
- Story output is not generic: it has conflict, emotional turn, channel fit, and visualizable beats.
- Shot output is usable: each shot has duration, purpose, shot size, camera angle, lens, camera motion, subject action, blocking, and audio fields.
- Reference pack output is usable: each image has a clear role and avoids overloaded boards.
- Image prompts use JSON-first style configs, selected pattern ids, art-directed layout policy, material truth, consistency locks, exact labels, and targeted artifact guards.
- Video prompts are materially different for Seedance, Kling, Runway, and Veo.
- Video prompts include reference maps, anti-misread clauses, audio policy, and retry rules.
- The skill pack has root skill plus sub-skills with narrow input/output contracts.
- Skill collaboration uses artifact files and receipts, not hidden conversation state.
- There is a repeatable validation command.
- There is at least one narrative fixture and one advertising/product fixture.
- The repo is clean after commit.

## Verification Commands

Run at minimum:

```bash
ruby -e 'require "yaml"; Dir["docs/film-preproduction/**/*.yaml"].each { |f| YAML.load_file(f); puts "ok #{f}" }'
python3 -m json.tool docs/film-preproduction/prompt-pattern-registry.json >/tmp/prompt-pattern-registry.json.out
python3 -m json.tool docs/film-preproduction/schemas/image-prompt-style-config.schema.json >/tmp/image-prompt-style-config.schema.json.out
python3 -m json.tool docs/film-preproduction/templates/image-prompt-style-config.template.json >/tmp/image-prompt-style-config.template.json.out
rg -n 'TB[D]|TO[D]O|待[定]|占[位]|x[x]x|FIX[ME]' .
git diff --check
git status --short
```

Add stronger project-specific validation scripts as implementation progresses.

## Stop Conditions

Stop only if:

- required user decision blocks the next phase,
- source research conflicts with existing assumptions and needs user judgment,
- external API access or account login is required,
- generating real images/videos becomes necessary and user has not authorized it,
- repo state becomes unsafe to continue.

If stopped, write:

```text
STATUS: BLOCKED
BLOCKER:
LAST_COMPLETED_PHASE:
FILES_CHANGED:
VERIFIED:
NEXT_EXACT_ACTION:
```

## Completion Report

When the full execution goal is met, report:

```text
STATUS: DONE
FINAL_STATE: practical professional DIRcreative skill pack ready for local use
COMMITS:
FIXTURES:
SKILLS:
VALIDATION:
KNOWN_LIMITS:
NEXT_OPTIONAL_WORK:
```

## Copy-Paste Goal For GStack

```text
Work in `<repo-root>`.

Read docs/film-preproduction/06-gstack-execution-goal.md first.
Then read README.md, docs/film-preproduction/04-goal-mode-handoff.md, docs/film-preproduction/05-skill-integration-architecture.md, docs/film-preproduction/phase-contracts.yaml, and docs/film-preproduction/schemas/skill-orchestration.yaml.

Execute the project phase by phase until dircreative becomes a practically usable professional AI video preproduction skill pack.

Start from the active phase in phase-contracts.yaml. Complete each phase, verify it, commit it, update phase-contracts.yaml to the next phase, and continue. Do not stop after a single phase unless blocked by a real user decision, external account/API requirement, or explicit image/video generation authorization boundary.

The final standard is not "docs exist." The final standard is that a user can provide one vague idea and the local skill workflow can produce professional story development, script/treatment, shot plan, reference image prompts, model-specific video prompts, QA/retry guidance, and skill-to-skill coordination through artifacts and receipts.

Do not generate real images or videos. Do not make one universal video prompt. Do not copy prompt libraries wholesale. Use sourced pattern extraction, JSON-first image prompt configs, model-specific video adapters, and professional QA gates.

Commit after every verified phase. Keep git status clean. Report STATUS, completed phases, commits, changed files, verification commands, remaining blockers, and next exact action.
```
