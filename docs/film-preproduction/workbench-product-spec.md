# DIRcreative Workbench Product Spec

Status: planned

Purpose: define the future WYSIWYG workbench for DIRcreative after artifact contracts, skills, fixtures, prompts, QA, and update rules are stable.

The workbench is a production desk for AI video preproduction. It renders structured artifacts as editable creative surfaces, then writes changes back to artifact files with versions, locks, receipts, and provenance.

## Product Outcome

A user can enter one rough idea and move through a visible professional workflow:

```text
rough idea
-> idea intake
-> director room tradeoffs
-> selected concept
-> story / ad structure
-> script / breakdown
-> shot list
-> visual bible
-> reference image plan
-> image prompt manifest
-> model-specific video prompt manifest
-> generation QA and retry plan
-> learning / update / checkpoint
```

The workbench must show the actual artifact state. It must not hide the workflow inside a single prompt box.

## Primary Users

| User | Need | Workbench Support |
| --- | --- | --- |
| Solo creator | Turn an idea into AI-video-ready preproduction files | Guided stage rail, artifact cards, regeneration controls |
| Director / creative lead | Review tradeoffs and lock creative decisions | Director room view, concept comparison, lock controls |
| Prompt director | Compile reference images and model prompts without losing provenance | Pattern IDs, source registry links, adapter-specific prompt panes |
| Producer | Check channel fit, scope, and deliverables | Channel labels, duration gates, fixture comparison |
| QA reviewer | Find generation failures and route retries | Failure taxonomy, retry rules, receipt trail |

## Artifact-To-View Map

| View | Source Artifacts | Write Artifacts | Skill Stage |
| --- | --- | --- | --- |
| Project Intake | raw idea, optional references | `project.yaml` or `01-idea-intake.md` | `idea-intake` |
| Director Room | intake artifact, channel playbooks | `director-room.yaml`, concept options, selected concept | `director-room` |
| Story / Structure | selected concept | logline, beat sheet, treatment, ad structure | `story-development`, `script-treatment` |
| Script Breakdown | script or ad structure | breakdown, asset requirements, audio policy | `script-breakdown` |
| Shot Table | script, breakdown, audio policy | `shot-list.yaml`, camera plan, blocking plan | `shot-design` |
| Visual Bible | shot list, asset requirements | visual bible, reference pack plan, image layout spec | `visual-bible`, `reference-image-planner` |
| Image Prompt Compiler | visual bible, prompt registry, style schema | image prompt manifest and prompt files | `image-prompt-compiler` |
| Video Model Adapter | shot list, reference pack, image manifest, audio policy | video prompt manifest and model prompt files | `video-model-adapter` |
| Generation QA | generated run notes, prompt manifests | QA report, retry plan, learning candidates | `generation-qa`, `learn` |
| Update / Checkpoint | source registries, learning log, timeline | source freshness report, checkpoint, revision requests | `update`, `checkpoint` |

## Fixture Coverage

| Fixture | Channel Proof | Key Artifacts |
| --- | --- | --- |
| `examples/cyber-courier/` | Cinematic micro-short | story package, script, shot plan, visual bible, five image prompts, four model prompts, generation QA template |
| `examples/product-ad-raincoat/` | Advertising / product proof | idea intake, director-room notes, concept options, selected concept, 15s/30s ad structure, shot list, reference pack plan, image manifest, video manifest |

## Required WYSIWYG Behavior

- Render artifact fields as editable production surfaces: tables for shots, side-by-side cards for director-room roles, structured panes for JSON prompt configs, and model-specific prompt tabs.
- Every visible field must map to a file path, artifact ID, version, owner skill, and downstream dependency.
- A locked artifact can be read downstream but not silently rewritten.
- Regeneration must show what will change before writing files.
- Prompt provenance must stay visible: selected pattern IDs, source registry entries, reference map, model adapter, and skill receipt.
- Video prompt comparison must show why Seedance, Kling, Runway, and Veo differ.
- Generation QA must route failures to retry rules instead of asking the user to diagnose model behavior from scratch.

## Core Screens

| Screen | Purpose | Must Show |
| --- | --- | --- |
| Workflow Rail | Navigate from idea to QA | stage status, artifact count, lock state, validation state |
| Artifact Canvas | Edit the current production artifact | rendered fields, raw artifact toggle, version metadata |
| Inspector | Explain provenance and downstream impact | source files, owner skill, receipts, dependencies, lock button |
| Comparison Pane | Compare choices or model outputs | concept options, shot variants, model prompt differences |
| QA Drawer | Review problems and retry actions | failure type, owner skill, smallest revision target, retry rule |
| Timeline | Resume work safely | `.dircreative/state/current.json`, current checkpoints, and current run receipts |

## Regeneration Contract

When a user edits an upstream artifact:

1. Mark downstream artifacts as `stale` in the workbench view, not on disk until a write is confirmed.
2. Show affected artifacts and owner skills.
3. Offer scoped regeneration from the next dependent skill.
4. Write a `skill_run_receipt` with changed inputs, outputs, decisions, unresolved questions, QA gate, and next skill.
5. Preserve locked artifacts and create a revision request if a locked upstream decision blocks quality.

## Non-Goals

- Do not implement the frontend in this phase.
- Do not add a database.
- Do not generate images or videos.
- Do not turn the product into a landing page.
- Do not hide artifact files behind an opaque chat transcript.

## Acceptance

- Every planned view maps to artifact files and skill stages.
- Cyber Courier and RainLock both fit the workbench model.
- Locks, versions, receipts, and provenance are visible workflow concepts.
- Regeneration is scoped and auditable.
- The workbench can be implemented later without changing the current artifact contracts.
