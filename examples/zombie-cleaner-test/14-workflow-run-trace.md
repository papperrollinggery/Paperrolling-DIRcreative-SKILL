# Workflow Run Trace

artifact:
  artifact_id: zombie-cleaner-workflow-run-trace-v1
  version: 1.0.0
  status: approved
  owner_skill: checkpoint

## What This Shows

This file makes the hidden file-based workflow visible.

The run did not generate images or videos. It ran in `prompt_only` mode and produced production artifacts that a later generation-capable agent or external tool can consume.

## Run Mode

```yaml
project: Wasteland Sanitation Route
target_duration_sec: 180
longform_generation_mode: hybrid
visual_output_mode: prompt_only
image_generation: unavailable
video_generation: unavailable
media_generated: false
```

## Step Trace

| Step | Skill | Input | Output | What Happened |
| --- | --- | --- | --- | --- |
| 0 | source research | user reference to online `Zombie Scavenger` | `00-source-study.md` | Captured public benchmark traits and originality boundary. |
| 1 | idea-intake | source study | `01-idea-intake.md` | Turned the reference idea into an original project brief. |
| 2 | director-room | idea intake | `02-director-room-notes.md` | Simulated producer, director, writer, cinematographer, editor, sound, model prompt, and QA roles. |
| 3 | story-development | director room | `03-concept-options.md` | Proposed three directions and selected the strongest one. |
| 4 | story-development | selected direction | `04-selected-concept.md`, `05-story-package.md` | Locked logline, story engine, beat sheet, and treatment. |
| 5 | script-treatment | story package | `06-script.md` | Converted treatment into screen action and audio policy. |
| 6 | shot-design | script | `07-shot-list.yaml` | Built twelve 15-second shots with lens, camera, blocking, action, and audio. |
| 7 | sequence-planner | shot list | `08-sequence-plan.yaml` | Split 180s into twelve model-safe 15s sequence units. |
| 8 | visual-bible | sequence plan | `09-visual-bible.md` | Locked identity, vehicle, prop, palette, camera grammar, material rules, and avoid rules. |
| 9 | reference-image-planner | visual bible + sequence plan | `10-reference-pack-plan.yaml` | Planned global boards, dense-board policy, direct input policy, and clean frame requirements. |
| 10 | image-prompt-compiler | reference pack | `11-image-prompt-manifest.yaml` | Wrote JSON-first image prompts and external generation instructions. |
| 11 | longform-reference-planner | sequence plan + image prompt manifest | `12-longform-reference-pack.yaml` | Built global pack plus two executable sequence pack examples. |
| 12 | video-model-adapter | shot list + reference pack | `13-video-prompt-manifest.yaml` | Exported Seedance, Kling, Runway, and Veo prompt strategies. |
| 13 | checkpoint | all artifacts | `14-workflow-run-trace.md` | Made the workflow operation process readable. |
| 14 | co-creation-gate-runtime | workflow trace | `15-co-creation-run.yaml` | Marked fixture choices as simulated, kept live co-creation unverified, and blocked media generation pending user choices. |

## User Co-Creation Gates

These are the points where the workflow should normally stop and ask the user:

```text
concept_options_gate
-> selected Option A: Wasteland Sanitation Route

sequence_plan_gate
-> approved 12 x 15s hybrid structure

global_reference_pack_gate
-> approved worker, vehicle, barrel, route, palette, audio anchors

sequence_reference_pack_gate
-> zc-seq-01 approved, zc-seq-10 pending example, remaining sequences pending

clean_frame_gate
-> all direct I2V clean frames are external_pending

video_prompt_gate
-> model prompts are prompt_ready, no generation run yet
```

## Gate Runtime Check

```text
python3 scripts/dircreative_run.py status --example examples/zombie-cleaner-test
```

Expected status:

```text
RUN_TYPE: dry_run_fixture
REAL_USER_CO_CREATION_VERIFIED: False
clean_frame_gate: pending [pending] BLOCKS_MEDIA
video_prompt_gate: pending [pending] BLOCKS_MEDIA
```

This means the fixture proves the file workflow, not a live user-approved session.

## Artifact Chain

```text
00-source-study.md
-> 01-idea-intake.md
-> 02-director-room-notes.md
-> 03-concept-options.md
-> 04-selected-concept.md
-> 05-story-package.md
-> 06-script.md
-> 07-shot-list.yaml
-> 08-sequence-plan.yaml
-> 09-visual-bible.md
-> 10-reference-pack-plan.yaml
-> 11-image-prompt-manifest.yaml
-> 12-longform-reference-pack.yaml
-> 13-video-prompt-manifest.yaml
-> 14-workflow-run-trace.md
-> 15-co-creation-run.yaml
```

## Where The Workflow Is Not Yet Visible

This repo still does not have:

- frontend timeline,
- clickable workbench,
- live multi-agent transcript,
- generated image gallery,
- video generation results,
- side-by-side Seedance/Kling output comparison.

Those belong to a later WYSIWYG/workbench or real media test phase.

## Next Real Test

The next visible test should select one approved unit:

```text
zc-seq-01
```

Then run:

```text
image prompt -> generated worker/vehicle/scene reference images
-> clean first frame
-> Seedance/Kling video prompt
-> generated clip
-> generation QA
-> retry notes
```

That will turn this file-based workflow into an actual media generation run.
