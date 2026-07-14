# Reference And Prompt Plan

artifact:
  artifact_id: complete-idea-reference-prompt-plan-v1
  version: 1.0.0
  source_artifact_ids:
    - complete-idea-shot-list-v1
    - complete-idea-director-room-v1
  status: approved
  owner_skill: reference-image-planner

## Reference Strategy

Selected strategy: `hybrid`

Professional judgment:

Fog Route Cleaner should not generate many overlapping boards before identity and scene are locked. Character consistency and scene consistency are mandatory. The smallest safe V2 sequential pack is three core planning images plus optional clean frames after user lock.

Lock order:

```text
character identity reference
-> scene geography + camera FOV reference
-> professional storyboard + motion map
-> optional clean first/end frames
```

## Reference Image Plan

1. `frc_v2_01_character_identity_reference`
   - Role label: `CHARACTER IDENTITY REFERENCE / 人物参考图 / NOT DIRECT VIDEO INPUT`
   - Role: single character identity lock.
   - Contains: same sanitation worker front/side/back/3/4 action view, face shield, reflective jacket, rubber gloves, disinfectant cart handle, nozzle, pressure gauge.
   - Must not include: alternate worker designs, street geography, storyboard panels, or final cinematic composition.
   - Direct video input: no.
   - Downstream rule: all later images inherit this face, body proportion, wardrobe silhouette, protective gear, and cart design.

2. `frc_v2_02_scene_geography_camera_fov_reference`
   - Role label: `SCENE GEOGRAPHY + CAMERA FOV REFERENCE / 场景空间+镜头视场参考图 / PLANNING ONLY`
   - Role: single scene and camera geography lock.
   - Contains: one wide or 360-degree panoramic street strip, top-down route diagram, ambulance position, zombie distance, worker/cart path, S01-S06 camera points, field-of-view wedges, foreground/midground/background zones, light-source direction.
   - Must not include: alternate streets, alternate ambulance positions, new character costume designs, or contradictory mood panels.
   - Direct video input: no for Kling/Runway; planning/reference only.
   - Downstream rule: all storyboards and clean frames inherit this route axis, vehicle position, camera FOV, and lighting direction.

3. `frc_v2_03_professional_storyboard_motion_map`
   - Role label: `PROFESSIONAL STORYBOARD + MOTION MAP / 详细分镜头+镜头运动图 / PLANNING ONLY`
   - Role: dedicated professional storyboard page.
   - Contains: six shot cells. Each cell must include shot ID, timecode, duration, shot image region, detailed frame description, shot size, focal length, camera position, camera movement start/end, subject blocking start/end, foreground/midground/background, lighting cue, sound description, transition, and model risk.
   - Must not include: new character identity, new street geography, or generic one-line captions.
   - Direct video input: no.
   - Warning: this page is not a first frame. It only drives shot review and prompt compilation.

4. `frc_v2_04_clean_first_frame`
   - Role label in manifest: `CLEAN FIRST FRAME FOR I2V / 干净首帧 / DIRECT VIDEO CANDIDATE`
   - Role: optional direct I2V start frame.
   - Generation condition: only after `frc_v2_01` and `frc_v2_02` are user locked.
   - Contains: clean text-free FRC01 route-blocked frame inherited from locked identity and scene.
   - Direct video input: yes, after user approval.
   - Requirements: no labels, no arrows, no panels, no tiny text, no gore.

5. `frc_v2_05_clean_end_frame`
   - Role label in manifest: `CLEAN END FRAME FOR I2V / 干净尾帧 / DIRECT VIDEO CANDIDATE`
   - Role: optional direct I2V end frame.
   - Generation condition: only after `frc_v2_01` and `frc_v2_02` are user locked.
   - Contains: clean text-free FRC06 quiet proof frame inherited from locked identity and scene.
   - Direct video input: yes, after user approval.
   - Requirements: no labels, no arrows, no panels, no tiny text, no victory pose.

## Image Prompt Summaries

All image prompts use JSON-first structure.

Before assisted image generation, each image must pass a `pre_generation_contract`.

For `frc_v2_01_character_identity_reference`, the contract must say:

```yaml
pre_generation_contract:
  status: pass
  asset_id: frc_v2_01_character_identity_reference
  asset_role: character_identity_reference
  dominant_title: "人物身份参考图 / CHARACTER IDENTITY REFERENCE"
  secondary_project_metadata: "Project: Fog Route Cleaner"
  title_hierarchy:
    role_label_largest: true
    project_title_secondary: true
    forbidden_largest_text:
      - "FOG ROUTE CLEANER"
      - "film title"
  role_purity:
    primary_job: "lock one sanitation worker identity"
    must_not_do:
      - "act as film poster"
      - "act as scene reference"
      - "act as storyboard page"
      - "act as direct video frame"
  inheritance:
    character_identity_source: self
    scene_geography_source: none
  direct_video_input_policy:
    allowed: false
    reason: "identity board contains labels and multiple views"
  prompt_lint:
    exact_role_label_present: true
    title_hierarchy_instruction_present: true
    forbidden_poster_hierarchy_present: true
    no_unowned_scene_or_character_redesign: true
  image_generation_allowed: true
```

The fixed surface-integrity macro is optional and defaults off. Activate it only for an observed material/geometry failure or an internal A/B test, and record the failure ID; otherwise use concise failure-specific constraints.

Assisted generation prompt text must bind the contract into the actual image prompt. Do not rely on the YAML contract alone.

For `frc_v2_01_character_identity_reference`, the prompt must include:

```text
Largest title on the page: 人物身份参考图 / CHARACTER IDENTITY REFERENCE
Smaller metadata only: Project: Fog Route Cleaner
Do not make FOG ROUTE CLEANER the largest title.

Asset role: character identity reference, planning board, NOT DIRECT VIDEO INPUT.
Primary job: lock one sanitation worker identity across front, side, back, and 3/4 action views.
Must not do: do not act as a film poster, scene reference, storyboard page, or direct video frame.
Do not redesign the street, ambulance, zombie spacing, shot composition, or story rhythm.
```

For `frc_v2_02_scene_geography_camera_fov_reference`, the prompt must include:

```text
Largest title on the page: 场景空间+镜头视场参考图 / SCENE GEOGRAPHY + CAMERA FOV REFERENCE
Smaller metadata only: Project: Fog Route Cleaner
Do not make FOG ROUTE CLEANER the largest title.

Asset role: scene geography and camera FOV reference, PLANNING ONLY.
Primary job: lock one street route axis, ambulance position, worker/cart path, zombie distance, light direction, S01-S06 camera points, and field-of-view wedges.
Must not do: do not create alternate streets, alternate ambulance positions, new costume designs, cinematic clean frames, or decorative mood panels.
```

For `frc_v2_03_professional_storyboard_motion_map`, the prompt must include:

```text
Largest title on the page: 详细分镜头+镜头运动图 / PROFESSIONAL STORYBOARD + MOTION MAP
Smaller metadata only: Project: Fog Route Cleaner
Do not make FOG ROUTE CLEANER the largest title.

Asset role: professional storyboard and motion map, PLANNING ONLY.
Primary job: show six shot cells with shot ID, timecode, duration, shot image region, detailed frame description, shot size, focal length, camera position, camera movement start/end, subject blocking start/end, foreground/midground/background, lighting cue, sound description, transition, and model risk.
Must not do: do not introduce new character identity, new scene geography, or generic one-line captions.
```

Prompt-only outputs:

- `image_01_character_identity_reference`: one character identity source of truth, visible role label, same worker across views, no scene redesign.
- `image_02_scene_geography_camera_fov_reference`: one street geography source of truth, 360/wide scene strip, top-down route, S01-S06 FOV wedges, path arrows, planning-only label.
- `image_03_professional_storyboard_motion_map`: dedicated storyboard page with full shot-card data for every shot.
- `image_04_clean_frc01_start`: optional after locks, clean cinematic frame, no text, no panels, direct I2V start frame.
- `image_05_clean_frc06_end`: optional after locks, clean cinematic frame, no text, no panels, direct I2V end frame.

## Video Prompt Summaries

### Seedance

Use multi-reference prompt for the full 15-second six-shot sequence.

Reference map:

- `@image frc_ref_01` = worker/equipment identity.
- `@image frc_ref_02` = street geography and camera FOV atlas.
- `@image frc_ref_03` = professional storyboard/motion map, planning-only.
- `@image frc_clean_01` = optional clean start frame after identity/scene lock.
- `@image frc_clean_06` = optional clean end frame after identity/scene lock.

Anti-misread:

Do not show storyboard panels, callouts, arrows, timing text, board borders, or planning labels in final video.

### Kling

Best mode: direct I2V from clean frames.

Use:

- `frc_clean_01_start_frame` for FRC01-FRC03 if testing the route-clearing movement.
- `frc_clean_06_end_frame` for FRC06 ending or start/end-frame route.

Do not use:

- storyboard board as first frame,
- scene geography/camera FOV board as first frame,
- labeled character/equipment board as first frame.

### Runway

Best first test: one single shot, FRC03 lane-clearing push.

Prompt should specify:

- worker pushes disinfectant cart slowly,
- low mist stays near the ground,
- ambulance lights pulse through fog,
- no gore,
- no attack,
- no extra crowd.

### Veo

Use structured prompt:

- subject,
- action,
- scene,
- camera,
- lighting,
- style,
- audio,
- constraints,
- reference map.

Veo prompt must state that the final output is the cinematic scene, not a production board.

## Media Status

Current status: prompt-only.

当前没有生成真实图片或视频。

Blocked:

- `clean_frame_gate` remains pending.
- `media_generation` remains blocked until user authorizes generation or imports external images.
- assisted generation must proceed sequentially; do not batch-generate all assets before character and scene locks.

skill_run_receipt:
  run_id: complete-idea-reference-prompt-plan-2026-05-16
  skill_id: reference-image-planner
  input_artifacts:
    - examples/complete-idea-segmentation-test/03-shot-list.yaml
  output_artifacts:
    - examples/complete-idea-segmentation-test/04-reference-prompt-plan.md
  decisions:
    - "Use V2 hybrid reference strategy: character identity lock, scene geography/camera FOV lock, professional storyboard/motion page, then optional clean direct-I2V frames."
  unresolved_questions:
    - "Real user must approve whether to regenerate sequential V2 references before any video model test."
  qa_gate:
    status: pass
    reasons:
      - "Reference roles, direct-input policy, consistency lock order, professional storyboard page requirements, and model prompt summaries are explicit."
  next_recommended_skill: image-prompt-compiler
