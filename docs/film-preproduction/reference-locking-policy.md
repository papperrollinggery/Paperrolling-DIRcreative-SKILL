# Reference Locking Policy

Verified: 2026-07-10

Purpose: lock visual truth, rights, and model-safe reference roles without embedding volatile provider facts in the core workflow.

For assisted generation, also apply `docs/film-preproduction/reference-consistency-gate.md`.

## Principle

Text describes intent. Locked references carry visual truth. Capability cards decide how a specific version and surface may consume those references.

```text
approved source artifacts
-> rights gate
-> selected references
-> explicit reference map
-> exact capability-card direct input policy
-> QA and retry
```

## User Co-Creation Gates

| Gate | User decision | DIRcreative responsibility |
| --- | --- | --- |
| `visual_direction_selection` | Choose or mix visual directions | Present distinct options and tradeoffs |
| `reference_pack_plan_approval` | Confirm boards and clean frames | Propose the smallest readable pack |
| `character_identity_lock` | Lock character identity | Reject face, body, wardrobe, or likeness drift |
| `identity_product_lock` | Lock product/brand identity | Reject silhouette, material, logo, or product-claim drift |
| `scene_geography_camera_lock` | Lock scene geography and camera FOV | Keep one spatial source of truth |
| `professional_storyboard_page_lock` | Lock shot order and motion plan | Require professional shot-card density |
| `clean_first_frame_lock` | Select clean direct-input frames | Reject text, panels, arrows, and board layouts |
| `model_strategy_selection` | Choose exact card(s), not a family alias | Show status, version, surface, reference modes, and failure modes |
| `rights_gate` | Confirm source, likeness, voice, brand, character, and music authorization | Block generation when evidence is absent |
| `visual_output_mode_gate` | Confirm `prompt_only`, `assisted_generation`, or `external_generation` | Record execution capability and authorization |
| `sequence_plan_gate` | Confirm duration and decomposition | Derive generation units from exact cards |
| `sequence_reference_pack_gate` | Approve one sequence pack | Preserve global locks while limiting rework |

`simulated_fixture` decisions never create a live lock. A `real_user` decision is required for live visual truth.

## Reference Status

```text
candidate -> selected -> locked -> superseded
```

- `candidate`: planned, generated, or imported but not approved.
- `selected`: direction is preferred; downstream prompts still warn it is not final.
- `locked`: rights and self-QA pass; downstream prompts may treat it as visual truth.
- `superseded`: retained for provenance, never used by the active prompt chain.

Reference status and `asset_output.status` are separate. File existence does not prove a lock.

## Asset Roles

Each reference asset has exactly one primary role:

```text
master_reference_board
identity_product_board
character_identity_reference
environment_camera_board
scene_geography_camera_fov_reference
storyboard_motion_board
professional_storyboard_motion_map
style_material_board
clean_first_frame
clean_key_frame
clean_end_frame
motion_reference_video
audio_reference
element_reference
```

Secondary jobs belong in `supports`. They must not introduce a second visual source of truth.

## Direct Input Policy

Direct input is resolved per asset and exact capability card:

```yaml
direct_input_policy:
  capability_card_id: ""
  version: ""
  provider_surface: ""
  reference_mode: "planning_only | first_frame | last_frame | asset_reference | style_reference | element_reference | audio_reference | motion_reference"
  allowed: false
  source_field: "reference_modes"
  anti_misread_required: false
  reason: ""
```

Stable defaults:

- `professional_storyboard_motion_map`, `storyboard_motion_board`, floor plans, and text-dense boards are `planning_only`.
- `clean_first_frame`, `clean_key_frame`, and `clean_end_frame` may become direct inputs only when the exact card supports the selected mode.
- An element, character, style, asset, motion, video, or audio reference uses only the matching card mode.
- `conditional` is not an approval; it requires an explicit risk note and anti-misread clause.
- A workflow/canvas card cannot authorize a model input by itself.

## Storyboard / Clean-Frame Separation

A professional storyboard/motion map must contain a shot image region, timecode, duration, detailed frame description, shot size, focal length, camera position, camera movement, subject blocking, sound, transition, and model risk.

Its dominant page title must be the role label. The film title is smaller metadata. A pre-generation contract must make the role and hierarchy visible.

A clean frame contains only one cinematic state:

- no title,
- no production label,
- no shot-card text,
- no arrow or motion path,
- no panel border,
- no floor plan,
- no table or palette strip.

A clean frame is a separate asset or separate prompt. It is never an implied crop from a board.

## Rights Lock

Every reference records:

```yaml
rights:
  status: "verified | conditional | unverified | blocked"
  owner_or_license_basis: ""
  likeness_authorization: "not_applicable | verified | unverified | blocked"
  voice_authorization: "not_applicable | verified | unverified | blocked"
  brand_character_music_authorization: "not_applicable | verified | unverified | blocked"
  provider_restrictions_checked_against_card: false
  evidence_refs: []
```

An unverified/blocked reference may remain a planning placeholder but cannot enter `assisted_generation`, direct external upload, edit, or extension.

## Edit Preserve / Change Lock

When an existing image, video, clean frame, character, product, or scene is edited:

```yaml
operation: edit
source_references: []
transformation_contract:
  preserve: []
  change: []
  forbidden_change: []
  overlap_check: "pass | fail"
```

Preserve identity, geometry, shot state, light, text, or camera only when those fields are explicitly listed. `preserve` and `change` cannot contain the same field, both must be non-empty for an edit, and an image edit must name its concrete source/reference.

## Visual Output Status

Use `asset_output.status`:

```text
prompt_ready
generated_candidate
user_locked
external_pending
external_imported
rejected
```

- `prompt_ready` is the default without generation.
- `generated_candidate` is never final visual truth.
- `external_pending` means instructions exist but media does not.
- `external_imported` still needs rights and self-QA before lock.
- `rejected` remains in provenance but cannot feed downstream prompts.

## Stale Downstream Artifacts

| Changed lock | Mark stale |
| --- | --- |
| character/product identity or rights | image prompts, video prompts, edit prompts, QA |
| scene geography/camera FOV | shot-to-reference map, clean frames, image/video prompts |
| storyboard/motion | video prompts, generation-unit plan, edit assembly |
| style/material | image prompts, video prompts, generated candidates |
| clean first/end frame | every direct-input binding that references it |
| capability card/version/surface | duration, reference, audio, edit, extension, and rights routing |

Do not silently rewrite a locked upstream artifact. Write a revision request and identify the smallest stale set.

## Longform Locking

```text
sequence_plan_gate
-> global_visual_lock_gate
-> rights_gate
-> sequence_reference_pack_gate
-> clean_frame_gate
-> video_prompt_gate
-> edit_assembly_gate
```

`hybrid` remains the default longform_generation_mode: plan the full arc and global locks, then approve one sequence pack at a time.

## Anti-Misread Clause

Use for any direct card mode that conditionally accepts a board:

```text
This reference is production guidance only.
Use only the declared identity, product, scene geography, shot order, camera path, light, or style role.
Do not show, animate, copy, or recreate labels, arrows, panel borders, floor-plan marks, tables, shot-card text, or board layout.
```

## QA Gate

A reference pack is not ready unless:

- the user decision gate is resolved by a real user when live,
- character consistency and scene consistency each have one locked source of truth,
- every asset has one primary role and visible role label,
- rights evidence is verified for every direct input,
- every direct binding names an exact current capability card and source field,
- storyboard/motion maps remain planning-only unless an explicit card mode permits otherwise,
- every direct first/last-frame binding uses a separate clean frame,
- dense boards carry anti-misread text when conditionally bound,
- `visual_output_mode` and execution capabilities are explicit,
- every asset has `asset_output.status`,
- stale downstream artifacts are marked after any lock or capability change,
- `clean_frame_gate` and `video_prompt_gate` pass before direct generation.
