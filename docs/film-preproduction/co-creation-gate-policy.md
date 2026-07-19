# Co-Creation Gate Policy (Legacy V1, Read Only)

Status: frozen fixture-reader contract. New v2 runs use only `concept_lock`,
`generation_authorization`, and `client_delivery_approval` from
`skills/dircreative/runtime/routing-policy.yaml`. The eleven gate types below
must not be created or required by a new run.

Verified: 2026-05-16

Purpose: make DIRcreative distinguish real user-approved creative decisions from dry-run fixture assumptions.

This policy is enforced through chat-facing decisions, not by asking the user to inspect files.

## Principle

Creative choices are not automatically final.

DIRcreative may propose, rank, and explain options. It must not pretend the user chose them unless a run artifact records one of these sources:

```text
real_user
simulated_fixture
pending
system_default
```

## Required Gates

| Gate | Required User Decision | Downstream Lock |
| --- | --- | --- |
| `concept_options_gate` | Choose or mix story/concept direction. | selected concept |
| `story_approval_gate` | Approve logline, beat logic, and story direction. | script treatment |
| `script_approval_gate` | Approve timed script, dialogue/voiceover policy, and audio intent. | script breakdown and shot design |
| `shot_list_approval_gate` | Approve shot count, timing, lens/motion plan, and action structure. | visual bible |
| `visual_direction_gate` | Choose visual style direction. | visual bible |
| `visual_bible_approval_gate` | Approve identity locks, palette, material rules, and avoid list. | reference image plan |
| `sequence_plan_gate` | Approve duration split and sequence functions. | longform sequence plan |
| `global_reference_pack_gate` | Approve reusable identity, product/prop, scene, style, and audio anchors. | global reference pack |
| `sequence_reference_pack_gate` | Approve per-sequence reference pack. | sequence prompt package |
| `clean_frame_gate` | Approve direct I2V clean start/end frames. | model video prompt export |
| `video_prompt_gate` | Approve model-specific prompts before generation. | generation-ready package |

## Decision Sources

```yaml
decision_source: "real_user | simulated_fixture | pending | system_default"
```

Rules:

- `real_user`: a human chose or approved the gate in the current project.
- `simulated_fixture`: allowed only for test fixtures; downstream artifacts must remain marked as fixture evidence, not proof of live UX.
- `pending`: workflow must stop before locked downstream media generation.
- `system_default`: allowed for mechanical defaults only, never for taste, story, visual style, or final reference selection.

## Fixture Rule

Dry-run examples may use simulated choices to prove schema flow.

They must record:

```yaml
run_type: dry_run_fixture
simulated_choices_allowed: true
real_user_co_creation_verified: false
```

This prevents a test fixture from being mistaken for a real co-creation session.

## Live Run Rule

Live project runs must record:

```yaml
run_type: live_user_run
simulated_choices_allowed: false
real_user_co_creation_verified: true
```

If any required creative gate is still `pending`, the next skill may draft options but must not mark downstream artifacts as `locked`.

Live runs must resolve the earliest unresolved creative gate first. A user saying "可以", "继续", or "测试一下" is permission to continue the workflow, not permission to skip story, script, shot list, or visual bible review.

Reference pack, clean-frame, image generation, and video prompt choices stay blocked until story/script/shot/visual bible gates are visible and approved.

## QA Gate

A run is not co-creation-ready unless:

- every required gate exists,
- creative gates cannot use `system_default`,
- fixture decisions are labeled `simulated_fixture`,
- live decisions are labeled `real_user`,
- pending gates block media generation,
- run trace names where the user should be asked.
