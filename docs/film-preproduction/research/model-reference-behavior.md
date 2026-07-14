# Model Reference Behavior

Verified: 2026-07-10

Purpose: plan image, video, audio, character, element, board, and clean-frame references through exact capability-card modes.

## Core Rule

Reference assets are control inputs, not mood decoration.

Every reference declares:

- one primary production job,
- source and rights evidence,
- exact capability card/version/provider surface,
- `planning_only` or one supported direct reference mode,
- what must be preserved,
- what the model must not copy or animate,
- failure and retry route.

## Reference Binding Shape

```yaml
reference_binding:
  ref_id: ""
  asset_role: ""
  rights_gate_status: "verified | conditional | unverified | blocked"
  capability_card_id: ""
  version: ""
  provider_surface: ""
  reference_mode: "planning_only | first_frame | last_frame | asset_reference | style_reference | character_reference | element_reference | motion_reference | audio_reference"
  upload_slot: ""
  preserve: []
  do_not_copy_or_animate: []
  direct_input_allowed: false
  risk_note: ""
```

Family names never satisfy `capability_card_id`.

## Stable Reference Classes

### Planning boards

Includes master boards, identity boards, scene/FOV atlases, professional storyboard/motion maps, lighting/material boards, floor plans, and shot strips.

Default: `planning_only`.

Conditional direct use requires an exact card mode, an anti-misread clause, readable panels, rights, and accepted interpretation risk.

### Clean first / key / end frames

A clean first frame contains one cinematic state and no production UI. It may fill a first/start/end/keyframe slot only when the card supports that mode.

### Asset/style/element/character references

These roles are not interchangeable:

- `asset_reference`: subject, product, prop, or scene identity,
- `style_reference`: palette, light, or texture only,
- `element_reference`: provider-defined reusable element,
- `character_reference`: provider-defined reusable subject,
- `motion_reference`: timing, movement, or camera path,
- `audio_reference`: rhythm, voice, music, ambience, or sound behavior.

Use only the exact mode named by the card. A reusable character or element still needs rights and provider-specific restrictions.

## Current Card Routing Snapshot

The machine-readable facts are in `model-sources.yaml`; this table is a routing summary.

| Card | Reference behavior | Important separation |
| --- | --- | --- |
| `gpt_image_2_openai_api` | one or more image references for edit/composition; multi-turn editing | image edit is not video first-frame binding |
| `sora_2_openai_videos_api` / Pro | image is first frame; reusable non-human character route | character, first-frame, edit, and extension constraints differ |
| `seedance_2_0_official_launch` | named image/video/audio/storyboard references | all counts and modes are Seedance 2.0-only |
| `kling_video_3_0_official_guide` | start/end frames plus elements and multi-shot roles | 3.0 must not inherit legacy 5/10 rules |
| `kling_legacy_i2v_5_10_official_guide` | legacy first-image motion workflow | legacy only; never default Kling |
| `runway_gen_4_5_web` | text/image generation | generation is separate from Aleph edit |
| `runway_aleph_2_0_web` | Edit Studio source video plus keyframe/edit prompt | numeric duration is unverified on this Web surface |
| `runway_aleph_2_0_api` | `aleph2` on API `video_to_video` | 2-30 second input range is API-only |
| `runway_gen_4_aleph_api_deprecated` | historical edit route | deprecated; do not use for new work |
| `veo_3_1_generate_001_vertex_api` / Fast | stable Vertex first/last/asset routes | bind the stable endpoint and preserve audio-source conflict |
| `veo_3_1_lite_generate_001_vertex_api` | Lite-specific routes | preview; reference support differs from Standard/Fast |
| `tapnow_canvas_workflow_2026_07_10` | graph and lineage only | underlying generation model must resolve separately |

## Seedance Reference Planning

For Seedance 2.0, bind every `@image`, `@video`, and `@audio` role explicitly. A storyboard may guide shot order, camera, and visual copy only with an inline anti-misread clause. The published reference upper limits are locked to the 2.0 card and cannot be reused for another version.

If results drift, remove competing roles before adding prose.

## Kling Reference Planning

For Kling VIDEO 3.0, select single-shot or multi-shot, then bind clean start/end frames and element roles independently. Audio/voice bindings remain distinct from visual elements.

The legacy Kling image-to-video card uses its own duration/profile and motion-first prompt formula. Do not mix it into the VIDEO 3.0 receipt.

## Runway Reference Planning

For Gen-4.5 image-to-video, the clean input image defines visual state and the prompt focuses on motion. For Aleph 2.0, the source video/keyframe defines the edit context; `preserve` and `change` must be disjoint. Resolve `runway_aleph_2_0_web` and `runway_aleph_2_0_api` separately; only the API card authorizes the `aleph2` 2-30 second input range.

Runway Gen-4 Aleph is Deprecated in the current API input manual. Keep that deprecated card separate from current Aleph 2.0.

## Veo Reference Planning

Use stable `veo-3.1-generate-001` or `veo-3.1-fast-generate-001` cards, not preview aliases. Bind first frame, last frame, and asset references only according to the exact stable card.

The exact stable and Fast pages currently mark sound generation unsupported, while a family announcement claims native audio and the registered generic API URL does not expose a locatable exact-card `generateAudio` binding. Preserve that conflict, default those two exact cards to post-production audio, and do not infer audio behavior from another Veo tier. The Lite endpoint may retain sound only because its exact page explicitly marks sound generation supported.

## TapNow-Style Canvas Flow

TapNow remains a workflow card:

- represent prompts and assets as inspectable nodes,
- keep original structured intent when a prompt optimizer runs,
- keep planning boards and clean frames as different nodes,
- block arbitrary graph edges that bypass story, rights, reference, or QA gates,
- resolve every generation node to an underlying current capability card.

## Storyboard vs Clean Frame

Professional storyboard/motion map:

- planning truth,
- role title is the dominant page title,
- contains shot image, timecode, duration, focal length, camera movement, blocking, sound, transition, and model risk,
- direct input policy defaults to `planning_only`.

Clean first frame:

- one shot state,
- no visible text, labels, arrows, panels, tables, maps, or borders,
- explicit shot and reference-mode binding,
- rights verified,
- may be direct input only after capability and clean-frame gates pass.

## Compression Policy

Good compression:

- one primary job per asset,
- large readable visual evidence,
- explicit direct input policy,
- one role per binding,
- source/right provenance retained.

Bad compression:

- tiny faces or unreadable labels,
- one board solving identity, scene, style, motion, copy, and product proof,
- conflicting subject identities,
- a board passed as a literal clean frame,
- multiple provider modes collapsed into one generic `reference` label.

## Anti-Misread Clause

```text
This board is production guidance only.
Use only the declared identity, product, scene geography, shot order, camera path, light, or style role.
Do not show, animate, copy, or recreate labels, arrows, panel borders, floor-plan marks, tables, shot-card text, or board layout.
```

## Rights and Preserve/Change

- Direct references require verified source rights.
- Likeness, voice, brand/character, and music permissions are separate fields.
- A generated reference does not erase rights obligations from its inputs.
- Editing requires non-overlapping `preserve` and `change` sets.
- A blocked or unverified reference may remain planning-only, never generation-ready.

## QA Gate

Reference export fails when:

- exact card/version/surface is missing,
- a deprecated, legacy, preview, workflow-only, or S4-only card is used without the correct gate,
- reference mode does not exist on the selected card,
- a storyboard/motion map is bound as a literal first frame,
- a clean first frame contains board graphics,
- source rights are unverified,
- preserve/change overlap,
- a model-family rule overrides endpoint evidence,
- official source conflicts are hidden,
- audio reference or native audio is assumed from another card.

## Sources — Accessed 2026-07-10

- Machine-readable registry: `docs/film-preproduction/sources/model-sources.yaml`
- OpenAI image/video guides: https://developers.openai.com/api/docs/guides/image-generation and https://developers.openai.com/api/docs/guides/video-generation
- Seedance 2.0: https://seed.bytedance.com/en/blog/seedance-2-0-official-launch
- Kling VIDEO 3.0: https://app.klingai.com/cn/quickstart/klingai-video-3-model-user-guide
- Runway Gen-4.5 / Aleph 2.0 / API inputs: https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5, https://help.runwayml.com/hc/en-us/articles/52150503729171-Aleph-2-0-Prompting-Guide, https://docs.dev.runwayml.com/assets/inputs/
- Google Vertex stable Veo and API sources: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-1-generate, https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation, https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes
