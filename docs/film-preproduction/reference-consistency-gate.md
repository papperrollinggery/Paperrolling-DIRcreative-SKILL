# Reference Consistency Gate

Verified: 2026-05-16

Purpose: prevent reference packs from creating character drift, scene drift, and duplicated visual contradictions.

## Core Rule

Character consistency and scene consistency are mandatory gates.

Do not generate multiple boards or clean frames that independently reinterpret the same character, costume, prop, vehicle, or location. More images are allowed only when they have separate jobs and inherit the locked visual truth.

## Lock Order

Default assisted-generation order:

```text
character_identity_lock
-> scene_geography_camera_lock
-> storyboard_motion_density_lock
-> selected clean frames
-> model-specific video prompts
```

Do not batch-generate all assets before the character and scene anchors are reviewed.

## Character Identity Lock

The character identity reference is the single source of truth for:

- face,
- body proportion,
- wardrobe silhouette,
- costume color and material,
- protective gear,
- recurring props held or worn by the character.

Required board label:

```text
CHARACTER IDENTITY REFERENCE / 人物参考图 / NOT DIRECT VIDEO INPUT
```

This role label must be the dominant page title. The project title may appear only as smaller metadata, for example `Project: Fog Route Cleaner`.

Never make the film title larger than the asset role. A reference image is a production tool first, not a poster.

The identity board must include only enough views to lock identity. It must not redesign the scene, final shot composition, or storyboard rhythm.

Any later image that shows the character must declare:

```yaml
inherits_character_identity_from: <asset_id>
must_not_reinterpret:
  - face
  - body proportion
  - wardrobe silhouette
  - costume color
  - protective gear
```

If a generated later image changes these features, reject it as `character_identity_reference_drift`.

## Scene Geography And Camera Lock

The scene reference is the single source of truth for:

- location geography,
- route direction,
- entrances and exits,
- vehicle positions,
- background landmarks,
- lighting source positions,
- shot camera positions,
- camera field of view per shot.

Default scene asset:

```text
SCENE GEOGRAPHY + CAMERA FOV REFERENCE / 场景空间+镜头视场参考图 / PLANNING ONLY
```

This role label must be the dominant page title. The project title and sequence name are secondary metadata.

For complex action, use one detailed scene atlas instead of several competing environment boards:

- one 360-degree or wide panoramic environment strip,
- one top-down route/floor plan,
- shot positions marked as `S01`, `S02`, etc.,
- field-of-view wedges for each shot,
- subject path and vehicle path,
- no alternate versions of the same street unless the story changes location.

The scene atlas is planning-only unless a model strategy explicitly allows all-reference input with anti-misread warnings.

Any later clean frame must declare:

```yaml
inherits_scene_geography_from: <asset_id>
fov_source_shot_id: <shot_id>
must_match:
  - route direction
  - vehicle position
  - light source direction
  - foreground/midground/background layout
```

If a generated later image changes the route, vehicle position, or camera axis, reject it as `scene_geography_reference_drift`.

## Duplication Policy

Repeating a subject across multiple images is allowed only when repetition has a controlled job.

Allowed repetition:

- a small locked identity inset copied for continuity,
- a scene atlas crop used to explain a shot field of view,
- the same prop repeated for material detail,
- the same shot ID repeated across storyboard, prompt manifest, and video prompt.

Forbidden repetition:

- character appears in several boards with different face, body, costume, or gear,
- location appears in several boards with different street geometry,
- storyboard panels invent new camera positions not present in the scene atlas,
- clean frames create a new version of the character or scene.

If repetition creates new visual facts, reject it as `reference_asset_duplicate_conflict`.

## Minimal V2 Pack

For a 15-second film with consistency risk, prefer this pack:

1. `character_identity_reference`: one board, identity only.
2. `scene_geography_camera_fov_reference`: one scene atlas, 360/wide view plus top-down/FOV marks.
3. `professional_storyboard_motion_map`: one high-density storyboard/motion board, using shot IDs from the scene atlas.
4. `clean_first_frame` and `clean_end_frame`: optional, generated only after identity and scene anchors pass user review.

Do not add separate style, lighting, environment, and storyboard boards if they repeat and contradict the same character or scene. Put style/material rules into the manifest unless they need a dedicated visual proof.

## Storyboard Motion Density

The storyboard/motion board must not be a simple mood strip.

Each shot cell must include:

- shot ID and timecode,
- duration,
- shot size,
- lens,
- camera angle,
- camera support,
- camera movement start and end,
- subject blocking start and end,
- foreground/midground/background,
- lighting cue,
- sound cue,
- transition,
- model risk or split rule.

Required board label:

```text
PROFESSIONAL STORYBOARD + MOTION MAP / 详细分镜头+镜头运动图 / PLANNING ONLY
```

This role label must be the dominant page title. The film title is secondary because the user must immediately know this is the professional storyboard page.

If this density is absent, reject it as `storyboard_information_density_too_low`.

## QA Gate

No generated asset can be locked unless:

- character identity source is singular and referenced by downstream assets,
- scene geography source is singular and referenced by downstream assets,
- duplicated content does not introduce new visual facts,
- every board has a visible role label or manifest role label,
- the visible role label is the dominant title, not subordinate to the film title,
- storyboard/motion board includes production shot-card density,
- clean frames match both character identity and scene/FOV anchors.

## Pre-Generation Spec Gate

The assistant must validate a machine-readable pre-generation contract before calling any image generation tool.

The image prompt is not allowed to rely on prose intent alone. It must declare the exact asset role, title hierarchy, inheritance, role boundaries, and model safety policy before generation.

This applies to prompt-only and external-generation handoffs too. If the user copies only the prompt text into Image2, Image Gen, or another tool, the prompt itself must still say the role label, title hierarchy, project metadata hierarchy, and direct video input policy.

Required contract:

```yaml
pre_generation_contract:
  status: pass | fail
  asset_id:
  asset_role:
  dominant_title:
  secondary_project_metadata:
  title_hierarchy:
    role_label_largest: true
    project_title_secondary: true
    forbidden_largest_text:
      - film title
      - project title
  role_purity:
    primary_job:
    must_not_do: []
  inheritance:
    character_identity_source:
    scene_geography_source:
  direct_video_input_policy:
    allowed: false
    reason:
  prompt_lint:
    exact_role_label_present: true
    title_hierarchy_instruction_present: true
    forbidden_poster_hierarchy_present: true
    no_unowned_scene_or_character_redesign: true
```

If `pre_generation_contract.status` is not `pass`, do not call the image generation tool.

For the character identity reference, the prompt must explicitly say:

```text
Largest title on the page: 人物身份参考图 / CHARACTER IDENTITY REFERENCE
Smaller metadata only: Project: Fog Route Cleaner
Do not make FOG ROUTE CLEANER the largest title.
```

For the scene/FOV reference, the prompt must explicitly say:

```text
Largest title on the page: 场景空间+镜头视场参考图 / SCENE GEOGRAPHY + CAMERA FOV REFERENCE
Smaller metadata only: Project: Fog Route Cleaner
Do not make FOG ROUTE CLEANER the largest title.
```

For the professional storyboard page, the prompt must explicitly say:

```text
Largest title on the page: 详细分镜头+镜头运动图 / PROFESSIONAL STORYBOARD + MOTION MAP
Smaller metadata only: Project: Fog Route Cleaner
Do not make FOG ROUTE CLEANER the largest title.
```

This gate exists because correcting the model after generation wastes time and lets bad assets reach the user. The correct place to prevent title hierarchy, role confusion, and duplicated visual truth is before generation.

## Post-Generation Self-QA

After any image is generated or imported, the assistant must still inspect it before asking the user to lock it.

The user should not be the first QA pass.

Required self-QA checks:

- role label exists,
- role label is the dominant page title,
- project or film title is smaller metadata,
- asset role is pure and not mixed with unrelated jobs,
- character identity stays consistent with the locked source,
- scene geography stays consistent with the locked source,
- repeated content does not introduce new visual facts,
- storyboard/motion pages include professional shot-card density,
- clean frames contain no labels, arrows, panels, or board layout,
- direct video input policy is still valid,
- material artifact guard passes.

If any required check fails:

```yaml
self_qa:
  status: fail
  failure_ids: []
  user_lock_request_allowed: false
  next_action: regenerate_or_replan
```

Do not ask the user to approve or lock a failed candidate. Report the failure, record it in `.dircreative/runs/`, and regenerate only after the prompt or plan is corrected.

If a UI or image tool automatically displays the generated file, the assistant still must immediately run self-QA and mark the candidate as pass or fail before asking the user for any creative decision.
