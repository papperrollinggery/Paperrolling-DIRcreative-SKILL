# Model Adapter Notes

Verified: 2026-07-10

Purpose: translate a locked production plan through exact, versioned capability cards. This is research guidance; `docs/film-preproduction/sources/model-sources.yaml` is the machine-readable source of truth.

## Resolution Before Prompting

Resolve all of the following before adapter selection:

```text
capability_card_id
version
status
provider_surface
verified_on / accessed_on
reference_modes
audio_route
duration
edit / extension
rights
failure_modes
```

Reject family aliases, `latest`, stale cards, deprecated defaults, S4-only evidence, and a provider surface that differs from the card.

## Cross-Model Prompt Contract

Every video adapter output contains:

```text
CAPABILITY RECEIPT
exact card, version, status, surface, sources, conflicts

RIGHTS RECEIPT
source assets, likeness/voice/brand/music permissions, provider restrictions

REFERENCE MAP
one reference role per asset; planning-only vs direct input

VIDEO TASK
initial state, trigger, action path, camera start/end target, timing, final state

CONTINUITY LOCKS
identity, product, geography, palette, material, screen direction

DESIRED AUDIO
dialogue, voiceover, music, ambience, sound effects, or silence

GENERATION AUDIO ROUTE
native, native configurable, reference, preserve source, post-production, none

TRANSFORMATION CONTRACT
operation, preserve, change, forbidden change

QA
falsifiable success criteria and one-variable retry route
```

The storyboard/reference board is production guidance by default. A direct first/end-frame slot uses a separate clean frame unless the exact card names another supported role.

## GPT Image 2 — `gpt_image_2_openai_api`

Source scope: OpenAI Image API and Responses API image generation tool.

Verified capabilities:

- text-to-image generation,
- whole-image and masked edits,
- one or more reference images for edits/reference composition,
- conversational multi-turn generation/editing through Responses,
- high-fidelity image-input handling on the named model,
- no transparent background on the documented `gpt-image-2` API surface.

Adapter behavior:

- Use `generate` for a new visual state and `edit` only when an input image exists.
- Name each reference by role.
- For edits, write disjoint `preserve` and `change` sets.
- Do not convert the internal surface-integrity macro into a claimed model requirement.
- Keep downstream audio intent out of the image prompt body.

## Sora 2 / Sora 2 Pro

Cards:

- `sora_2_openai_videos_api`
- `sora_2_pro_openai_videos_api`

Verified surface behavior:

- create synchronized-audio video from text or image input,
- image input is a first-frame anchor,
- reusable character assets are non-human by default and limited by the exact card,
- edit and extension use distinct endpoints,
- extension does not inherit character or image-reference support,
- current guardrails block real people, human faces in input images, copyrighted characters, and copyrighted music on the documented API surface.

Adapter behavior:

- Use a clean first frame for `input_reference`.
- Treat character, first-frame, edit, and extension as separate controls.
- Put dialogue/audio in a dedicated block and keep lines short enough for the selected card duration.
- For edits, change one production variable and preserve everything else explicitly.
- Run the rights gate before suggesting a real-person, character, or music route.

## Seedance 2.0 — `seedance_2_0_official_launch`

Evidence is version-scoped to Seedance 2.0:

Access receipt: `documented_product`; export route: `manual_export`; execution verification: `unverified`. This card is not an API card.

- text, image, video, and audio reference inputs,
- named upper limits for each reference type,
- multi-shot audio-video generation,
- editing and continuation described on the launch surfaces.

Adapter behavior:

- Bind each input (`@image`, `@video`, `@audio`) to one role.
- Mark shooting scripts/storyboards as production guidance and include the anti-misread clause.
- Treat all reference counts and duration claims as 2.0-only; never inherit them into a family alias or a later version.
- Verify the actual UI/API route before promising an edit or continuation run.
- Keep multi-subject, text, and audio-distortion risks visible.

## Seedance 2.5 — `seedance_2_5_official_launch`

The official launch surfaces document a 30-second upper bound, up to 30 image,
10 video, and 10 audio references, native audio-video generation, timestamp
control, editing, and two extensions. These facts never overwrite the retained
2.0 card. Keep export `manual_export` and execution `unverified` until the exact
current product or API surface is read back.

For script conversion, preserve `script_to_seedance_v1`. The reviewed v1.5.0
method snapshot is recorded in `prompt-sources.yaml`; at runtime,
`mr-li-seedance-25` contributes only its selected body bound by actual bytes and
SHA-256. It does not own model facts, state, validation, execution, or approval.

## Kling VIDEO 3.0 — `kling_video_3_0_official_guide`

Verified version-scoped behavior:

Access receipt: `documented_product`; export route: `manual_export`; execution verification: `unverified`. This card is not an API card.

- flexible 3-15 second generation,
- text-to-video, image-to-video, start/end frames,
- single-shot and multi-shot modes,
- element references,
- native audio and element voice binding on the documented product surface.

Adapter behavior:

- Select single-shot vs multi-shot explicitly.
- Bind start/end frames, elements, speaker/voice, and audio independently.
- Keep edit and extension prompt-only until a dedicated current card verifies those routes.
- Use clean first/end frames for literal frame slots; keep a professional storyboard/motion map planning-only.

### Kling legacy — `kling_legacy_i2v_5_10_official_guide`

The 5/10-second rule belongs only to this legacy card. It is never the default for VIDEO 3.0. Select it only when the actual execution surface identifies the legacy image-to-video workflow.

## Runway Generation vs Editing

### Gen-4.5 — `runway_gen_4_5_web`

Verified current generation behavior:

- text-to-video and image-to-video,
- 2-10 second duration on the documented web surface,
- image-to-video prompts focus on motion while text-to-video prompts describe visuals and motion.

Adapter behavior:

- Use this card only for new generation.
- Keep audio in post-production unless another exact current card verifies a native route.
- Do not use a Gen-4.5 generation prompt as an edit prompt.

### Aleph 2.0 Web — `runway_aleph_2_0_web`

Verified current edit behavior:

- in-context video editing,
- one targeted transformation while unrequested background, lighting, and surrounding details are preserved,
- optional motion prompt with keyframe edits.

The Edit Studio guide does not publish a numeric input-duration range. Keep Web duration `unverified`; never copy the API range into this card.

Adapter prompt:

```text
CHANGE
one action verb + exact transformation

PRESERVE
identity, geometry, background, camera, lighting, timing, and audio fields that must stay

FORBIDDEN CHANGE
anything outside the declared target

EXTRA MOTION
only when the edit needs motion absent from source/keyframe
```

### Aleph 2.0 API — `runway_aleph_2_0_api`

The Runway API card uses exact model identifier `aleph2` on `video_to_video`. Its API-only input contract is 2-30 seconds at 30 FPS or lower, with source video plus optional timestamped keyframe images. These limits do not authorize the Edit Studio surface.

### Deprecated Gen-4 Aleph — `runway_gen_4_aleph_api_deprecated`

Runway's current API input manual labels Gen-4 Aleph as Deprecated. Do not conflate this with Aleph 2.0. New API work routes to `runway_aleph_2_0_api`; Web work resolves `runway_aleph_2_0_web` separately.

## Veo 3.1 Stable Vertex Cards

Current stable cards:

- `veo_3_1_generate_001_vertex_api`
- `veo_3_1_fast_generate_001_vertex_api`

Preview aliases are not current defaults. Google release notes map the 3.1 preview names to these stable `*-001` endpoints.

Verified Vertex API behavior:

- the stable model page identifies GA endpoints and their exact reference/duration modes,
- the registered generic Vertex API URL did not expose a locatable exact-card `generateAudio` field during the 2026-07-11 audit,
- the official 2026 product announcement describes native audio across the Veo 3.1 family.

Official-source conflict:

The exact stable model page labels sound generation unsupported for standard and Fast. Because the family announcement conflicts and the generic API page does not prove an exact-card `generateAudio` route, those cards retain `verification_status: ambiguous_official_surface_conflict`, set native audio to unverified, and default to post-production. The exact Lite entry separately marks sound generation supported, so only its endpoint-specific card may retain native audio. Do not generalize between tiers or surfaces.

Adapter behavior:

- Record the stable endpoint and provider surface, not `veo` or a preview alias.
- Set `desired_audio` in creative terms; route stable/fast to post-production and use `generateAudio` only when an exact endpoint card explicitly supports and documents it.
- Keep the official conflict in the receipt.
- Use card-supported first/last/reference modes only; do not substitute a board for a first frame.
- If the live surface contradicts the card, stop generation and fall back to prompt-only or post-production audio.

### Veo 3.1 Lite — `veo_3_1_lite_generate_001_vertex_api`

Lite is a separate preview card. Its current official documentation supports native audio but differs in reference-image support. Never inherit Lite audio/reference behavior into Standard/Fast or vice versa.

## TapNow Canvas — `tapnow_canvas_workflow_2026_07_10`

TapNow is represented as a workflow-only card:

- canvas nodes and edges preserve lineage,
- prompts, reusable assets, boards, and clean frames remain separate nodes,
- each actual generation node must resolve an underlying model capability card,
- the canvas cannot authorize duration, audio, edit, extension, or reference behavior by itself.

## Adapter Selection Rules

| Intent | Required route evidence |
| --- | --- |
| Generate a new image | exact image generation card |
| Edit an existing image | exact image edit mode + preserve/change |
| Generate from first frame | exact first-frame reference mode + clean frame |
| Reuse a character/element | exact character/element mode + rights |
| Generate multi-shot video | exact multi-shot mode and duration |
| Edit existing video | exact current edit card; generation card is insufficient |
| Extend existing video | exact extension card and unsupported-input list |
| Native audio | exact endpoint/surface audio route |
| Post-production audio | desired-audio manifest + post handoff |

## Universal Anti-Misread Clause

```text
The storyboard/reference board is production guidance only.
Use only the declared identity, scene geography, shot order, camera movement, prop, light, or style role.
Do not show or animate the board, panels, layout, labels, tables, arrows, shot-card text, or printed production notes.
```

## Refresh and Failure Policy

- Refresh cards before production use.
- Create a new card for a new model version or provider surface.
- Never mutate a current card into a family alias.
- Preserve deprecation history.
- If sources conflict, record both and fail closed when the exact route cannot be established.
- S4 community/GitHub material may trigger research but never authorize a route.

## Sources — Accessed through 2026-08-29

- OpenAI image generation: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI video generation: https://developers.openai.com/api/docs/guides/video-generation
- OpenAI Sora 2 prompting: https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide
- Seedance 2.0 official launch: https://seed.bytedance.com/en/blog/seedance-2-0-official-launch
- Seedance 2.0 paper: https://arxiv.org/abs/2604.14148
- Seedance 2.5 official launch and model page: https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5 and https://seed.bytedance.com/en/seedance2_5
- Kling VIDEO 3.0 guide: https://app.klingai.com/cn/quickstart/klingai-video-3-model-user-guide
- Kling legacy image-to-video guide: https://kling.ai/quickstart/image-to-video-guide
- Runway Gen-4.5: https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5
- Runway Aleph 2.0: https://help.runwayml.com/hc/en-us/articles/52150503729171-Aleph-2-0-Prompting-Guide
- Runway API Aleph 2.0 changelog/model catalog/inputs: https://docs.dev.runwayml.com/api-details/api_changelog/, https://docs.dev.runwayml.com/guides/models/, https://docs.dev.runwayml.com/assets/inputs/
- Google Vertex AI release notes: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes
- Veo 3.1 stable model page: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-1-generate
- Vertex Veo API reference: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation
- Veo 3.1 family announcement: https://cloud.google.com/blog/products/ai-machine-learning/veo-3-1-lite-and-a-new-veo-upscaling-capability-on-vertex-ai/
