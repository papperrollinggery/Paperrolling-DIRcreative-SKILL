# DIRcreative Workbench Data Flow

Status: planned

Purpose: define how the future workbench reads, displays, edits, regenerates, and verifies artifact files.

## Data Principle

The file artifact is the source of truth.

The workbench renders artifacts into UI state, but it does not invent a separate hidden workflow model. Every edit must map back to a file path, artifact ID, version, owner skill, and receipt.

## Artifact Graph

```text
project brief
  -> director room
  -> selected concept
  -> story package or ad structure
  -> script / breakdown / audio policy
  -> shot list / camera plan / blocking plan
  -> visual bible / reference pack plan / image layout spec
  -> image prompt manifest / image prompt files
  -> video prompt manifest / model prompt files
  -> generation QA / retry plan
  -> learning log / source update / checkpoint
```

## Core Records

| Record | Location | Purpose |
| --- | --- | --- |
| Artifact metadata | top of each artifact file | identity, version, status, owner, source artifact IDs |
| Skill receipt | artifact footer or `.dircreative/runs/` | execution decisions, inputs, outputs, QA, next skill |
| Timeline entry | `.dircreative/state/current.json` plus current receipts | phase and run history |
| Learning entry | versioned research docs or prompt registry, referenced by current state | reusable prompt/model/process finding |
| Checkpoint | `.dircreative/checkpoints/` | resumable snapshot of stage, locks, and next action |
| Source registry | `docs/film-preproduction/sources/` | model and prompt source freshness |
| Prompt registry | `docs/film-preproduction/prompt-pattern-registry.json` | active prompt mechanisms and QA gates |

## Status Model

Artifact status values:

```text
draft -> reviewed -> approved -> locked
```

Additional workbench-only display states:

```text
stale
blocked_by_lock
needs_user
needs_generation_review
deprecated
```

Workbench-only states are not written over artifact status unless the user confirms an artifact revision.

## Versioning Rules

- Every artifact has `artifact_id`, `version`, `source_artifact_ids`, `status`, `owner_skill`, `created_at`, `updated_at`, `locked_by_user`, and `notes` when the schema supports it.
- Patch edits that do not change downstream meaning keep the same major version.
- Edits that change creative direction, shot order, reference roles, image prompts, or model prompts create a new minor version.
- Locked artifacts cannot be overwritten by downstream regeneration.
- If a downstream skill detects a locked upstream problem, it writes a `revision_request` entry instead of changing the locked file.

## Edit Flow

```text
user edits field
-> workbench validates local field shape
-> dependency graph marks downstream artifacts as stale in UI
-> user chooses regenerate or save-only
-> selected skill reads current artifacts
-> skill writes new artifact or revision request
-> validation command runs
-> receipt and timeline update
```

## Lock Flow

| Action | Effect |
| --- | --- |
| Lock concept | Downstream story, script, shot, and prompt stages read the concept as stable input. |
| Lock shot list | Prompt compiler cannot change shot order; it can request shot revision. |
| Lock visual bible | Image prompt compiler preserves identity, material, palette, and reference roles. |
| Lock prompt manifest | Video adapter reads prompts and reference map without rewriting image prompt strategy. |
| Unlock | Requires explicit user action and creates a receipt note. |

## Provenance Flow

Image prompt provenance must show:

- source artifact IDs,
- selected prompt pattern IDs,
- style schema path,
- prompt registry path,
- exact text labels,
- reference roles,
- material and artifact guards,
- QA flags.

Video prompt provenance must show:

- shot list source,
- reference pack source,
- image prompt manifest source,
- audio policy source,
- model adapter source,
- reference map,
- anti-misread clause,
- model-specific risk notes,
- retry rules.

## Regeneration Scope

| Changed Artifact | First Affected Skill | Downstream Impact |
| --- | --- | --- |
| Project intake | `director-room` | concept, story, script, shots, visuals, prompts, QA |
| Selected concept | `story-development` | story/ad structure, script, shots, visuals, prompts, QA |
| Script or ad structure | `script-breakdown` | breakdown, shots, visuals, prompts, QA |
| Shot list | `visual-bible` | reference plan, image prompts, video prompts, QA |
| Visual bible | `reference-image-planner` | image prompts, video prompts, QA |
| Image prompt manifest | `video-model-adapter` | reference map, model prompts, QA |
| Video prompt manifest | `generation-qa` | retry plan, learn/update candidates |

## Validation Flow

The workbench should expose the same checks that the repository uses:

```bash
python3 scripts/validate_project.py
ruby -e 'require "yaml"; Dir["docs/film-preproduction/**/*.yaml", "examples/**/*.yaml"].each { |f| YAML.load_file(f); puts "ok #{f}" }'
python3 -m json.tool docs/film-preproduction/prompt-pattern-registry.json
rg -n 'TB[D]|TO[D]O|待[定]|占[位]|x[x]x|FIX[ME]' .
git diff --check
```

Validation output should attach to the current run receipt, not disappear into terminal history.

## Storage Boundaries

- No database in the planned first implementation.
- No generated image or video files during this phase.
- No account/API credentials in artifact files.
- Local files remain portable and reviewable by another Codex or gstack worker.

## Data Flow Acceptance

- Every screen can resolve its displayed data to concrete artifact files.
- Every edit can identify downstream stale artifacts before writing.
- Every regeneration can produce a receipt.
- Prompt provenance can be reconstructed from files alone.
- The validation command covers the required final docs, fixtures, skills, manifests, registries, and QA gates.
