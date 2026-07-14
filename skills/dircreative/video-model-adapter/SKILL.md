---
name: dircreative-video-model-adapter
description: Convert shot list and reference pack into exact-card Sora, Seedance, Kling, Runway, and Veo video or edit prompts.
---

# Video Model Adapter

## Required Knowledge

- `docs/film-preproduction/schemas/prompt-ir.schema.json`
- `docs/film-preproduction/schemas/prompt-ir.yaml`
- `docs/film-preproduction/prompt-authoring-standard-v1.md`
- `docs/film-preproduction/asset-intake-and-state-standard-v1.md`
- `docs/film-preproduction/prompt-qa-and-incident-runbook-v1.md`
- `scripts/dircreative_prompt_compiler.py`
- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/schemas/video-prompt-manifest.yaml`
- `docs/film-preproduction/schemas/reference-pack-manifest.yaml`
- `docs/film-preproduction/research/model-adapter-notes.md`
- `docs/film-preproduction/research/model-reference-behavior.md`
- `docs/film-preproduction/research/tapnow-agentic-canvas-lessons.md`
- `docs/film-preproduction/research/audio-design-notes.md`
- `docs/film-preproduction/research/storyboard-reference-analysis.md`
- `docs/film-preproduction/reference-locking-policy.md`
- `docs/film-preproduction/reference-consistency-gate.md`
- `docs/film-preproduction/co-creation-gate-policy.md`
- `docs/film-preproduction/longform-decomposition-policy.md`
- `docs/film-preproduction/capability-aware-generation-policy.md`
- `docs/film-preproduction/creative-production-integration.md`
- `docs/film-preproduction/clean-frame-export-policy.md`
- `docs/film-preproduction/production-prompt-discipline.md`
- `docs/film-preproduction/research/ai-video-prompt-community-lessons.md`
- `docs/film-preproduction/schemas/sequence-plan.yaml`
- `docs/film-preproduction/schemas/longform-reference-pack.yaml`
- `docs/film-preproduction/sources/model-sources.yaml`

## Inputs

- shot list
- reference pack plan
- reference pack manifest
- image prompt manifest
- audio policy

## Outputs

- video prompt manifest
- model-specific prompt files
- adapter risk notes
- external generation upload map when assets are not generated locally
- exact capability-card, rights, audio-route, and preserve/change receipts

## Chat Surface

Show video prompt summaries by model:

- `阶段: 视频生成建议`
- `智能体创作内容`: model-specific motion strategy, reference binding, audio policy, and risk notes.
- `客户可见预览`: which sequence or shot group to test first, which model is recommended first, and why.
- `prompt-only产物`: state that exact-card Sora, Seedance, Kling, Runway, and Veo prompt bodies are available backstage or on request.
- `参考绑定`: show which image/board/clean frame maps to each model prompt and upload slot.
- `不能直接喂给视频模型`: reference input warnings for each model.
- `未生成真实图片/视频`: state current media status.
- `用户确认点`: ask which model or generation mode should be tested first, or whether to stay prompt-only.

Do not dump raw model prompt bodies in chat unless the user explicitly asks to copy prompts. The chat decision is model/sequence/action selection, not approval of internal prompt text.

Do not export a generation-ready run that pretends missing clean frames exist.

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#video-route-capability-comparison`. Compare exact model, duration, reference slots, audio, evidence status, and route risk from current capability cards; model choice remains a conversation intent with a table fallback.

## Rules

- Use different prompt strategies per model.
- Resolve `capability_card_id + version + provider_surface` before naming reference modes, duration, native audio, edit, extension, or upload slots. Reject family aliases, `latest`, stale cards, S4-only evidence, workflow-only cards, deprecated defaults, and preview aliases when a stable endpoint is current.
- Preserve `verified_on`, `accessed_on`, source tier/URLs, status/deprecation, and official-source conflicts in the manifest. If the live execution surface differs from the card or a conflict remains material, stay prompt-only.
- Run the rights gate before binding image, video, audio, character, element, likeness, voice, brand/character, or music inputs. Unverified/blocked rights prevent generation and external upload.
- Before delivering any video prompt, model test recommendation, external generation handoff, or retry instruction, run the production prompt discipline pre-delivery harness: active routing, required knowledge, lock order, user gate state, visual output mode, execution capability, prompt contract, reference bindings, model constraints, targeted avoid constraints, prompt-window hygiene, and falsifiable success criteria.
- Every generated/reference image must either map to a video prompt role or be explicitly marked human-planning-only.
- If image prompts are exported, also export the corresponding video prompt reference binding: model, shot_id, upload slot, direct/secondary/planning role, and risk note.
- Read `visual_output_mode` before referencing images.
- In `prompt_only`, bind expected reference slots and write external generation instructions instead of pretending files exist.
- In `assisted_generation`, use only generated assets that are user locked or explicitly approved as candidates.
- Do not use generated assets rejected for character drift, scene drift, duplicated visual contradictions, missing role labels, or low storyboard density.
- Model prompts must bind to the locked character identity source and locked scene geography/camera FOV source; do not allow each prompt to reinterpret them.
- The professional storyboard/motion page is planning-only. Use it to translate timing, lens, camera movement, blocking, sound, transition, and model risk, not as a literal video frame.
- In `external_generation`, export tool-specific upload order, start/end frame rules, and reference roles.
- For TapNow-style canvas workflows, export a model input graph showing prompt nodes, image nodes, clean-frame nodes, and video nodes.
- Include reference map and anti-misread clause.
- Include audio policy as a separate section.
- Separate `desired_audio` from `generation_audio_route`. Native audio is valid only when the exact card/surface supports it; otherwise use reference/preserve/post-production/none and write the handoff. Image prompt metadata never proves an audio route.
- For edit, extension, and retry operations, declare non-overlapping `preserve` and `change` sets plus forbidden changes. Keep one-variable retry behavior.
- Respect each asset's `direct_input_policy`.
- Verify model constraints before naming aspect ratios, durations, media roles, audio behavior, clean-frame requirements, or upload slots. If current schema evidence is unavailable, mark the prompt as prompt-only or external-generation with a risk note.
- Every video prompt must satisfy the five-layer check: model, camera, subject, look, and action.
- Every scene prompt must satisfy the six-slot check: camera, subject, action, setting, style, and lighting.
- Every video prompt must pass the micro-scene beat-sheet check before export: initial visible state, trigger or pressure, subject action path, camera start target, camera end target, timing beat or pause, final visible state, and sound or silence policy where relevant.
- Do not overfit to public Reddit, X, or prompt-library recipes. Use them only as structure after verifying model facts and binding the prompt to DIRcreative source truth, material role, reference map, and falsifiable QA.
- Do not use `master_reference_board`, `storyboard_motion_board`, `professional_storyboard_motion_map`, or `environment_camera_board` as a literal first-frame input. They default to planning-only; bind a separate clean frame to an exact supported first/end-frame mode.
- If an asset came from Creative Production, confirm the adapter receipt says `render_moodboard_board_widget` is not the source of truth and that the asset was written back as `generated_candidate`, `user_locked`, `rejected`, or `external_imported`.
- Do not use a Creative Production `generated_candidate` as video truth until generation QA passes and the user lock is recorded in DIRcreative artifacts.
- For any exact first/end-frame workflow, keep direct generation blocked unless the selected clean frames are generated or imported, self-QA/rights pass, and the required user lock is recorded.
- If the selected mode is all-reference or text-to-video, explain why clean frames are not required and record the accepted risk.
- In `prompt_only`, list required image prompt files and the upload slot each one will occupy.
- For `sora_2_openai_videos_api` or Pro, use image input only as a clean first-frame anchor, keep non-human character assets separate, enforce current rights restrictions, and route create/edit/extension separately.
- For `seedance_2_0_official_launch`, bind `@image`, `@video`, and `@audio` roles explicitly; keep every published limit scoped to version 2.0 and mark access `documented_product`, export `manual_export`, execution `unverified`.
- For `kling_video_3_0_official_guide`, use the current 3-15-second card and bind single/multi-shot, start/end frames, elements, and audio distinctly. Mark access `documented_product`, export `manual_export`, execution `unverified`; use the 5/10-second rule only when `kling_legacy_i2v_5_10_official_guide` is explicitly selected.
- For Runway, use `runway_gen_4_5_web` only for new generation. Resolve edits by surface: `runway_aleph_2_0_web` keeps numeric duration unverified for Edit Studio, while `runway_aleph_2_0_api` authorizes model `aleph2` and 2-30 second API inputs. Reject `runway_gen_4_aleph_api_deprecated` for new work and preserve its deprecation in the receipt.
- For Veo on Vertex, select the exact endpoint card. The stable `veo_3_1_generate_001_vertex_api` and `veo_3_1_fast_generate_001_vertex_api` cards default to post-production audio because their exact page says sound generation is unsupported and the registered generic API URL does not bind `generateAudio` to either card. Keep the source conflict visible. Only an exact endpoint card such as Lite may retain native audio when its own page explicitly supports sound; never generalize that fact across Veo tiers.
- Mark model prompts blocked if required clean first frames or locked references are missing.
- Keep video prompt export blocked while `clean_frame_gate` or `video_prompt_gate` is pending.
- For longform work, export prompts per sequence pack and preserve sequence IDs for edit assembly.
- Retry prompts must change one variable at a time: subject/product identity, primary action, camera/shot size, look/material/light, reference binding, or output controls. Record the failure ID and the smallest upstream artifact being corrected.
- Do not let a graph edge connect a dense board directly to a literal I2V node unless the asset role and model policy allow it.
- Do not generate videos.
- Run the executable Prompt IR schema and semantic validator before adaptation. Compile only references marked `attached_to_run: true`; planning-only assets, missing slots, internal IDs, paths, hashes, QA/retry fields, and post-production-only audio are forbidden on the terminal prompt surface.
- Every person/product/prop action and every dialogue or event sound must resolve to a valid entity owner. Targets longer than one generation unit require contiguous units with exact adjacent handoff keys/states and audio handoff. Compile and deliver one locally rebased unit prompt at a time; never present a 30-second assembly plan as one model-executable prompt.

## Prompt IR, composition, and conditional Look closure

Before model adaptation, consume the model-neutral Prompt IR and its intake record. Prefer user/client/project-supplied locked assets over unlocked candidates or model imagination. Verify every source path/hash/role/inheritance before compiling slots. Use one selected model adapter per run; do not emit parallel model prompts unless the user explicitly selects them.

The adapter must preserve these fields in the exported prompt:

- composition: visual center, hierarchy, foreground/midground/background, negative space, movement room, leading lines/occlusion/parallax, screen direction, and purpose;
- subject action, object action, and environment action as initial state, trigger, path, physical consequence, and final state;
- camera shot size, angle/height/axis, lens reason, support, start target, path, end target, speed/easing, focus, and motivation;
- time-coded emotional or attention beats, audio cues, transition bridges, and continuity locks;
- render look layers lighting, optics, atmosphere, and grade, each with condition, effect, intensity, preserve, and exit/continuity.

For Seedance 2.0, compile internal assets to platform roles such as @Image 1, @Video 1, and @Audio 1. Never expose R-number labels, internal asset ids, local paths, or manifest instructions in the final pasted prompt. Planning boards remain planning_only; clean frames are the direct visual anchors.

After prompt compilation, return prompt_only or instructions_only unless there is a verified external generation receipt. The receipt must include self-QA, current status, next_action, user lock state, and explicit unverified external work. Do not stop silently after writing the prompt.

## skill_run_receipt

Record model adapters, exact capability cards/version/status/provider surfaces, source tiers/dates/deprecations/conflicts, rights status, desired audio and generation audio route, preserve/change contracts, visual output mode, reference asset bindings, storyboard/clean-frame separation, optional model input graph, missing/generated/external asset status, forbidden direct inputs avoided, E0-E6 status, risk notes, QA status, and `next_recommended_skill: generation-qa`.
