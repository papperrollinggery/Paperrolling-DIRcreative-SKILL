---
name: dircreative-image-prompt-compiler
description: Compile JSON-first reference image prompts from visual bible, reference pack, and prompt pattern registry.
---

# Image Prompt Compiler

## Required Knowledge

- `docs/film-preproduction/schemas/prompt-ir.schema.json`
- `docs/film-preproduction/schemas/prompt-ir.yaml`
- `docs/film-preproduction/prompt-authoring-standard-v1.md`
- `docs/film-preproduction/asset-intake-and-state-standard-v1.md`
- `docs/film-preproduction/prompt-qa-and-incident-runbook-v1.md`
- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/ad-reference-pack-generation-gate.md`
- `docs/film-preproduction/schemas/image-prompt-manifest.yaml`
- `docs/film-preproduction/schemas/image-prompt-style-config.schema.json`
- `docs/film-preproduction/templates/image-prompt-style-config.template.json`
- `docs/film-preproduction/prompt-pattern-registry.json`
- `docs/film-preproduction/research/image-prompt-style-system.md`
- `docs/film-preproduction/co-creation-gate-policy.md`
- `docs/film-preproduction/capability-aware-generation-policy.md`
- `docs/film-preproduction/longform-decomposition-policy.md`
- `docs/film-preproduction/clean-frame-export-policy.md`
- `docs/film-preproduction/reference-consistency-gate.md`
- `docs/film-preproduction/customer-visible-production-gates.md`
- `docs/film-preproduction/client-film-hard-gates.md`
- `docs/film-preproduction/film-commercial-quality-standard.md`
- `docs/film-preproduction/creative-production-integration.md`
- `docs/film-preproduction/production-demo-retrospective.md`
- `docs/film-preproduction/council-adversarial-review.md`
- `docs/film-preproduction/production-prompt-discipline.md`
- `docs/film-preproduction/research/ai-video-prompt-community-lessons.md`
- `docs/film-preproduction/sources/model-sources.yaml`
- `docs/film-preproduction/sources/prompt-sources.yaml`
- `skills/dircreative/references/storyboard-frame-to-jingzao.md` only when the
  selected Skill Stack scenario is `cinematic_storyboard_frames`

## Inputs

- visual bible
- reference pack plan
- image layout spec

## Outputs

- image prompt manifest
- image prompt files
- visible pre-generation contract inside every exported image prompt
- machine-readable pre-generation contract for every assisted-generation image
- external generation instructions when `visual_output_mode` is `prompt_only` or `external_generation`
- exact capability-card, rights, and preserve/change receipts

## Chat Surface

Show image execution recommendations before prompt internals:

- `阶段: 出图执行建议`
- `客户可见预览`: the few images recommended, what each image is for, and what the user will see.
- `智能体创作内容`: recommended image count, first test image, consistency rationale, and execution risk.
- `先试哪张`: one safest first image and why it protects consistency.
- `不能直接喂视频模型`: planning-only boards, identity sheets, prompt/reference boards.
- `可以直接喂视频模型`: only clean, text-free, QA-passed clean frames.
- `当前媒体状态`: prompt-only, generated candidate, imported, or user locked.
- `用户确认点`: ask which material to make next before any prompt compilation or generation: character identity reference, scene geography/FOV reference, professional storyboard + motion map, selected clean frame, style/material board, first test image, full recommended pack, prompt-only export, or stop.

Do not dump raw JSON prompt bodies in chat unless the user explicitly asks to copy the prompt. Keep JSON prompts and `pre_generation_contract` as backstage artifacts.

Do not call any image generation tool unless the user explicitly authorizes it.

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#image-prompt-handoff-summary`. Show prompt intent, inherited references, selected model, generation boundary, and QA target without exposing raw prompt bodies; prompt-only and generation requests remain separate conversation intents with a Markdown fallback.

## Rules

- Author prompts as JSON-first configs.
- For cinematic storyboard or clean narrative frames, DIR may hand frame-level
  craft ownership to `jingzao-image-forge` through
  `storyboard_frame_to_jingzao_v1`. Pass the complete shot-tension contract and
  ordered canonical references; consume the compiled spec/prompt back into the
  DIR manifest. Do not paraphrase Jingzao's craft rules, claim it was used
  without an isolated full-body read, or let asset identity sheets choose a
  neutral catalog composition.
- Resolve the exact image capability card, version, status, provider surface, source tier, and accessed date before naming generation/edit/reference/output behavior. Reject family aliases, `latest`, stale cards, S4-only evidence, workflow-only cards, and deprecated defaults.
- Select `operation: generate | edit | retry`. `edit` requires a real input image plus non-overlapping `preserve` and `change` sets; `retry` changes one production variable and records the observed failure.
- Run the rights gate for every input/reference image, likeness, brand, character, logo, and exact text asset. Unverified/blocked rights force prompt-only and block external upload as well as assisted generation.
- Before delivering any image prompt, generation recommendation, or retry instruction, run the production prompt discipline pre-delivery harness: active routing, required knowledge, lock order, user gate state, visual output mode, execution capability, prompt contract, reference bindings, model constraints, targeted avoid constraints, prompt-window hygiene, and falsifiable success criteria.
- For client-facing films, every new image prompt must come from a locked shot and the per-shot asset/reference contract. It must bind locked shot ID, character or role identity, prop, action, shot size, camera angle or position, vertical/horizontal composition, and usage page.
- Do not write a generic "clean image" prompt before story, script, shot, and asset/reference gates pass. Missing images may be handled as `prompt_only`, but the handoff must clearly label the exact shot position and use case.
- For complex image assets, include `evidence_policy`, `visual_decomposition`, `prompt_layers`, `type_treatment`, and `style_tags` in the style config.
- `visual_decomposition` must cover subject, action/pose or blocking, details/appearance, environment/background, lighting/atmosphere, composition/framing, style/camera, colors/palette, materials/texture, proportion/scale, and generation intent.
- Map decomposition fields into director language: blocking, foreground/midground/background, readable zone, shot size, angle, lens feel, camera support, movement, focus, palette, material behavior, continuity locks, and downstream video-model use.
- `prompt_layers.director_recreation_prompt` is the full production prompt for the exact asset. `prompt_layers.prompt_core` is the reusable lock. `prompt_layers.negative_prompt` is a targeted avoid-list for drift and artifacts.
- Do not use standalone filler quality words such as `high detail`, `masterpiece`, `best quality`, `cinematic`, `beautiful`, or `premium`. Replace them with concrete surface, lens, lighting, composition, readability, and continuity constraints.
- Image prompt model constraints must be explicit when relevant: aspect ratio, output mode, direct-input policy, text policy, reference role, and whether generated files are expected to exist.
- Keep `desired_audio` as downstream metadata only and `generation_audio_route: not_applicable` in an image manifest. Never ask an image model to generate dialogue, voiceover, music, ambience, or sound effects.
- Do not write plausible platform or model facts as verified facts. Aspect ratios, output controls, direct-input policy, and current tool availability must come from local policy, source docs, or tool schema evidence.
- Use only locked upstream facts and visible generated/imported evidence. If a detail is uncertain, write a broader production-safe description instead of inventing brands, logos, exact text, locations, camera bodies, lens models, hidden objects, or offscreen props.
- Default to the project working language plus exact displayed labels. Add multilingual prompt fields only when the client handoff, UI, or external generation target requires them.
- Add 3-5 short style tags only as routing and QA metadata; do not treat tags as a substitute for the visual decomposition.
- Apply type treatment before writing the final prompt: portrait, product, poster/ad, UI, illustration, 3D, and photography each require different visible facts and failure checks.
- For brand/product films where product identity is not locked, the first assisted-generation image must be a clean single-product `PRODUCT IDENTITY REFERENCE`.
- Before product identity generation, freeze product silhouette, scale, material, diffusion/opening method, logo/text policy, desk/car use readability, and forbidden style drift.
- The first product identity image must not include the protagonist, full ad scene, storyboard panels, labels, captions, detail insets, product-sheet collage panels, strong category-rewriting background props, large slogan text, ancient/fantasy symbols, or luxury perfume ad cliches unless explicitly requested.
- Material macro views, vent details, packaging, and usage-context views must be separate later assets, not insets inside the first product identity candidate.
- Product identity QA must check for video-model misread risks: speaker, power bank, air purifier, car control knob, perfume bottle, incense burner, and ancient ornament.
- For abstract pebble, pod, stone, or capsule products, also check mouse, soap, jewelry box, stone decor, charging case, and generic electronic accessory risks.
- Do not mark an abstract product identity as locked from a beauty shot alone. Compile follow-up `FUNCTION DETAIL REFERENCE` and, for multi-mode products, `USAGE POSITION REFERENCE` prompts before final identity lock.
- If a base, coaster, tray, dock, magnet, stand, or holder appears, write whether it is product hardware or environment/support hardware in the pre-generation contract.
- Every exported image prompt, including `prompt_only` and `external_generation`, must begin with a visible prompt contract. Do not rely on chat, YAML, or hidden state to carry the image role, title hierarchy, inheritance, or direct video input policy.
- Before any assisted image generation, compile and pass a `pre_generation_contract` for the exact asset. Do not call image generation from a prompt that has not passed this contract.
- The pre-generation contract must define asset id, role, dominant title, secondary project metadata, title hierarchy, role purity, inheritance sources, direct video input policy, and prompt lint.
- The actual prompt text must contain the exact `pre_generation_contract.dominant_title`, the smaller `secondary_project_metadata`, and the instruction `Do not make <project title> the largest title`; a passing YAML contract without these prompt words is invalid.
- Prompt-only handoff text must still include `Pre-generation contract:`, `Largest title on the page:`, `Smaller metadata only:`, `Do not make <project title> the largest title`, and `Direct video input policy:` for boards. Clean frames must instead include `Clean frame contract:`, `no visible title`, and `Direct video input policy: allowed`.
- For character identity references, the prompt must explicitly say the largest title is `人物身份参考图 / CHARACTER IDENTITY REFERENCE`, and `Project: <title>` is smaller metadata. It must explicitly forbid making the film title the largest text.
- For scene/FOV references, the prompt must explicitly say the largest title is `场景空间+镜头视场参考图 / SCENE GEOGRAPHY + CAMERA FOV REFERENCE`, and the project title is smaller metadata.
- For professional storyboard/motion pages, the prompt must explicitly say the largest title is `详细分镜头+镜头运动图 / PROFESSIONAL STORYBOARD + MOTION MAP`, and the project title is smaller metadata.
- Prompts must preserve the lock order: character identity first, scene geography/camera FOV second, professional storyboard/motion page third, clean frames last.
- Do not infer the material type from a vague image request. If the user asks for a "director storyboard image" or "the image", first offer material choices unless the current chat already explicitly selected one.
- If the active intent is only visual exploration, label outputs as draft exploration and do not lock story, character, scene, or acceptance artifacts. If the active intent is formal lockable material, require approved story/script/shot gates first.
- Later prompts must inherit locked character and scene anchors instead of redesigning them.
- Do not repeat the same character or scene across multiple boards unless the prompt explicitly says which locked source is being reused and what new job the image performs.
- Every board prompt must include a clear role label: `CHARACTER IDENTITY REFERENCE`, `SCENE GEOGRAPHY + CAMERA FOV REFERENCE`, `PROFESSIONAL STORYBOARD + MOTION MAP`, or the matching Chinese label.
- The role label must be the dominant page title. The project or film title must be smaller metadata, never the largest header.
- Product identity boards may include clear packaging text; do not apply `no readable text` to identity boards that need brand or product recognition.
- Clean frames must be no-text, no-label, no-arrow, no-panel direct I2V frames.
- Professional storyboard/motion maps default to planning-only; a clean frame is a separate prompt/asset and must never be an implied crop from a board.
- Clean frame prompts must be individual image prompts, not only a note saying to crop/export from a board.
- If a reference pack includes a clean frame set, compile one prompt per required clean frame and mark each as `text_policy: no_text`.
- Storyboard/motion board prompts must include shot duration, camera movement, subject movement, and transition logic.
- Professional storyboard/motion page prompts must include one shot cell per approved shot with timecode, duration, shot image region, detailed frame description, character design locks, scene layout locks, prop continuity, shot size, focal length, camera position, camera movement, subject movement path, subject blocking, emotional beat, sound, transition, and model risk.
- Professional storyboard/motion page prompts must require compact professional shot-card text inside each cell. The text may be short, but it must name narrative purpose, lens/support/movement, subject blocking/path, continuity lock, sound or edit cue, and model risk. Reject thin labels such as only `wide`, `close-up`, `slow push`, `conversation`, or `emotional ending`.
- The visible text inside each storyboard cell must follow this structure: `S03 00:18-00:24 | Narrative purpose: ... | Lens/support/movement: ... | Blocking/path: ... | Continuity: ... | Sound/edit: ... | Model risk: ...`.
- When adapting external/community prompt examples, keep only the reusable structure. Do not copy a Reddit, X, or prompt-library recipe into an image prompt unless it has been converted into DIRcreative source truth, material role, prompt contract, targeted negative constraints, and falsifiable success criteria.
- Record `visual_output_mode`, `execution_capabilities`, and `asset_output` for every image.
- Use `scripts/dircreative_prompt_compiler.py` as the executable compiler; the
  media gate only revalidates its content-addressed output and never rewrites it.
- For `storyboard_frame` and clean-frame roles, the accepted prompt is the exact
  prompt read back from a production `storyboard_frame_to_jingzao_v1` manifest,
  bound to the installed Jingzao Skill and the active shot truth. A locally
  reconstructed DIR helper prompt is invalid. Assemble the professional
  storyboard/motion page deterministically from approved individual frames and
  shot-card text with `scripts/dircreative_storyboard_page_assembler.py`; never
  ask imagegen to redraw that overview page. Write the PNG and assembly receipt
  into the project, then bind and visually review them through the normal plan.
- Include selected pattern IDs, exact labels, art-directed layout policy, material truth, consistency locks, and surface integrity guard.
- Treat `surface_integrity_guard_v1` fixed wording as an optional internal QA macro, never a required Image2/GPT Image suffix. Default it off; activate it only for an observed matching failure or recorded A/B eval, preserve the control prompt, and never use its word `transparent` as evidence of alpha-background support.
- Retry prompts must change one variable at a time: subject/product identity, primary action, camera/framing, look/material/light, reference binding, or output control. Record the failure ID and smallest upstream artifact being corrected.
- In `prompt_only`, produce complete prompts and import instructions without generated files.
- In `external_generation`, name the target tool, upload role, and reference binding expected downstream.
- In `assisted_generation`, require explicit user authorization before calling any image tool.
- Creative Production may be used only as a deep generation and review adapter after upstream DIRcreative gates and `pre_generation_contract.status: pass`; use Mood boards, Scenes, Offers, Ads, Shots, or Generative Polish only through the mapping in `creative-production-integration.md`.
- When Creative Production is used, `render_moodboard_board_widget` is the review surface and is not the source of truth. Write the candidate, QA status, and user lock state back into `.dircreative/runs/` or the relevant manifest.
- A Creative Production candidate starts as `generated_candidate`; do not mark it `user_locked` until self-QA passes and the real user locks it.
- Do not compile locked image generation tasks from `simulated_fixture` decisions in a live run.
- In `prompt_only` and `external_generation`, do not call image tools. In an
  authorized `assisted_generation` handoff, return the validated prompt and
  packet to the Delivery executor; this compiler still does not perform the
  media call itself.
- Validate Prompt IR v1.1 before compiling DIR-owned prompts. Treat `prompt-ir.yaml` as an authoring template, not as the executable schema; Jingzao-owned frame prompts use their validated production handoff and prompt manifest instead.
- Keep source locators, hashes, entity IDs, capability evidence, QA, retry, and post-production metadata inside Prompt IR/manifests. The image model receives only attached reference roles, observable visual instructions, preserve/change boundaries, and targeted current constraints.

## Prompt IR and look closure

Before compiling any image prompt, run asset intake against the supplied files or conversation media. Record source kind, locator, hash, role, authorization, inherits_from, preserve, may_change, do_not_copy_or_animate, reuse_action, lock state, and downstream use. If an existing image already resolves identity, material, scene, or composition, use direct_reference, edit, or derive; do not recreate it from prose.

Every complex image prompt must include a composition card with visual center, hierarchy, foreground/midground/background, negative space, movement room, leading lines or occlusion, perspective depth, crop safety, and narrative purpose. Do not default to rule of thirds, center framing, symmetry, or cinematic as a substitute for a reason.

Every complex image prompt must include a four-layer render look card:

~~~text
lighting -> optics -> atmosphere -> grade
condition -> effect -> intensity -> preserve -> exit/continuity
~~~

Separate physical lens/filter behavior from post effects. Write none by design when a layer is not needed. Image prompts never generate audio; audio intent remains downstream metadata.

After an image is generated or imported, perform self-QA before asking for lock. Return the artifact, current status, pass/fail findings, and next_action. A generated_candidate is not user_locked, and prompt_only is not generated.

## skill_run_receipt

Record selected patterns, exact capability card/version/surface and source evidence, source conflicts, rights status, operation, preserve/change contract, optional QA macro activation, visual output mode, execution capability, asset output statuses, storyboard/clean-frame separation, manifest QA, prompt files, and `next_recommended_skill: video-model-adapter`.
