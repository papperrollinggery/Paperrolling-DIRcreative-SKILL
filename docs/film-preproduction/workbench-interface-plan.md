# DIRcreative Workbench Interface Plan

Status: planned

Purpose: define the future interface as a dense preproduction workbench, not a marketing site or generic dashboard.

## Layout Model

```text
left rail: project stages and artifact status
center: current artifact work surface
right inspector: provenance, locks, dependencies, receipts
bottom strip: timeline, validation, checkpoint, run log
```

The first screen should be the active project workspace. No landing hero, no decorative background, no feature tour.

## Navigation

| Stage | View | Primary Artifact |
| --- | --- | --- |
| Intake | Brief editor | idea intake / project brief |
| Director Room | Role board | director room notes, concept options, selected concept |
| Story | Treatment editor | logline, beat sheet, treatment, ad structure |
| Script | Script and breakdown | script, breakdown, asset requirements, audio policy |
| Shots | Shot table | shot list, camera plan, blocking plan |
| Visuals | Visual bible and reference pack | visual bible, reference pack plan, layout spec |
| Images | Image prompt compiler | image prompt manifest, prompt files |
| Video | Model adapter compare | Seedance, Kling, Runway, Veo prompts |
| QA | Failure and retry panel | QA report, retry plan, learning candidates |
| Update | Source and pattern maintenance | model sources, prompt sources, prompt registry |

## Work Surface Patterns

### Brief Editor

- Raw idea field.
- Channel selector: film, ad, short drama, short video, music video, product demo.
- Deliverable chips: duration, aspect ratio, platform, language, audio policy.
- Missing decision panel.
- Output preview: project brief artifact and receipt.

### Director Room Role Board

- One lane per role: producer, creative director, director, screenwriter, cinematographer, production designer, editor, sound designer, model prompt engineer, continuity QA.
- Each lane has recommendation, tradeoff, risk, and decision impact.
- Concept options compare hook, channel fit, production cost, model risk, and story strength.
- Selected concept lock appears next to the concept title.

### Story / Ad Structure Editor

- Narrative projects show logline, beat sheet, treatment, story review.
- Advertising projects show promise, proof, 15s/30s structure, copy, legal note, product proof.
- The workbench should show channel-specific gates so an ad is not judged like a short film.

### Shot Table

Columns:

```text
shot_id
duration
purpose
shot_size
camera_angle
lens
camera_motion
subject_action
blocking
audio
continuity
model_notes
```

Interactions:

- Add, split, merge, reorder, lock shot.
- Mark overloaded shot.
- Show total duration.
- Show downstream prompt impact for changed shots.

### Visual Bible And Reference Pack

- Identity, environment, product/prop, wardrobe, material, light, color, and texture panels.
- Reference role map: identity, environment, prop/product, storyboard, style, first frame.
- Board overload warning when one image tries to serve too many roles.
- Video-model safety indicator for each planned reference image.

### Image Prompt Compiler

- JSON-first editor with rendered sections.
- Pattern picker sourced from `prompt-pattern-registry.json`.
- Art direction policy visible as a locked block.
- Exact labels field.
- Material truth and surface integrity guard field.
- Prompt preview from the JSON source.
- QA flags: role clear, text readable, panels large enough, continuity locks present, video model safe.

### Video Model Adapter Compare

Four-pane comparison:

```text
Seedance | Kling | Runway | Veo
```

Each pane shows:

- best use,
- reference map,
- prompt text,
- audio policy,
- anti-misread clause,
- risk notes,
- retry rules.

The UI must make prompt differences visible. The user should immediately see why Kling gets motion-first wording while Veo gets structured subject/action/scene/camera/audio sections.

### QA And Retry

- Failure taxonomy list.
- Generated run review form.
- Smallest revision target.
- Owner skill.
- Retry instruction.
- Learning candidate toggle.
- Source or pattern update request when a retry creates reusable knowledge.

### Learn / Update / Checkpoint

- Learning viewer from versioned research docs and current-state references; runtime fixtures are test-only.
- Source freshness table from `docs/film-preproduction/sources/`.
- Pattern promotion queue from QA reports.
- Checkpoint create/resume controls.
- Timeline from `.dircreative/state/current.json` and current receipts.

## Fixture Modes

| Fixture | UI Mode |
| --- | --- |
| Cyber Courier | Narrative micro-short mode with treatment, script, shot sequence, cinematic reference pack, and four model adapters |
| RainLock Commuter Shell | Advertising mode with product promise, visible proof, 15s/30s structure, product material board, and product-ad video prompts |

Switching between fixtures should prove that the interface is channel-aware and not overfit to one storytelling format.

## Inspector

The inspector stays visible for every artifact and shows:

- file path,
- artifact ID,
- version,
- status,
- owner skill,
- source artifact IDs,
- downstream dependents,
- lock state,
- last receipt,
- validation state,
- prompt/source provenance when relevant.

## Regeneration UX

Before writing downstream changes, the workbench must show:

- changed input artifact,
- affected downstream artifacts,
- owner skill that will run next,
- locked artifacts that will be preserved,
- proposed output paths,
- validation commands that will run after write.

After write, the workbench must show:

- receipt,
- file diff summary,
- validation result,
- next recommended skill.

## Visual Design Direction

- Dense, calm, production-focused.
- Tables, split panes, tabs, inspectors, and timelines over decorative cards.
- Use cards only for repeated role lanes, concept options, QA findings, and prompt pattern entries.
- Use stable dimensions for shot rows, prompt panes, model tabs, and QA cards.
- Typography should fit operational review, not hero marketing.
- Visual assets appear as generated or selected reference outputs only after the user authorizes generation; until then, the workbench displays prompt previews and reference roles.

## Interface Acceptance

- The first viewport is the workbench, not a landing page.
- Every visible field can trace to an artifact file.
- The user can lock concept, shot list, visual bible, and prompt manifests.
- The user can compare model-specific prompts without opening raw files.
- The user can see why a generation failed and which skill owns the retry.
- The interface can be implemented later without changing the current file contracts.
