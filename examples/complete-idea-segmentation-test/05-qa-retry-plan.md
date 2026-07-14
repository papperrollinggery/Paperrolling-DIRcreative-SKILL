# Complete Idea QA And Retry Plan

artifact:
  artifact_id: complete-idea-qa-retry-plan-v1
  version: 1.0.0
  source_artifact_ids:
    - complete-idea-director-room-v1
    - complete-idea-shot-list-v1
    - complete-idea-reference-prompt-plan-v1
  status: approved
  owner_skill: generation-qa

## Purpose

Make QA and retry behavior visible before any image or video generation. The user should know what will be checked, what blocks progress, and which smallest artifact is retried when a failure happens.

## Current Media State

- visual_output_mode: `prompt_only`
- 当前没有生成真实图片或视频
- `clean_frame_gate` remains pending
- `media_generation` remains blocked
- No user lock may be requested until self-QA passes

## Pre-Generation QA

Before any assisted image generation, the assistant must verify:

1. `pre_generation_contract` exists for the target asset.
2. `dominant_title` is the asset role, not the film title.
3. `FOG ROUTE CLEANER` appears only as smaller project metadata.
4. `role_purity.primary_job` names one job only.
5. `direct_video_input_policy.allowed` matches the asset role.
6. Downstream assets inherit from locked sources instead of redesigning identity or scene.
7. `surface_integrity_guard` includes the anti fish-scale texture suffix.

If any item fails, do not call image generation.

## Post-Generation Self-QA

After any generated image candidate, run self-QA before asking the user to approve or lock it.

Required checks:

- `character_identity_reference_drift`
- `scene_geography_reference_drift`
- `reference_asset_duplicate_conflict`
- `reference_asset_role_label_missing`
- `reference_role_label_hierarchy_wrong`
- `image_generation_called_without_pre_generation_contract`
- `storyboard_information_density_too_low`
- `fish_scale_material_artifact`
- `clean_first_frame_missing`
- `board_used_as_direct_i2v_input_when_forbidden`
- `storyboard_board_misread_by_video_model`
- `copied_video_prompt_across_models`
- `missing_audio_policy`

If self-QA fails, record `self_qa.status: fail`, failure IDs, and corrected next action. Do not ask the user to lock a failed candidate.

## Retry Routing

Retry only the smallest artifact that can remove the failure.

- Character identity fails: retry `frc_v2_01_character_identity_reference` only. Do not generate scene, storyboard, clean frames, or video prompts from the failed identity.
- Scene geography or camera FOV fails: retry `frc_v2_02_scene_geography_camera_fov_reference` only, using the locked identity.
- Storyboard density fails: return to `shot-design` and rebuild `frc_v2_03_professional_storyboard_motion_map` with timecode, duration, shot image region, frame description, shot size, focal length, camera position, movement, subject blocking, sound, transition, and model risk.
- Title hierarchy fails: return to `image-prompt-compiler`; make the asset role the largest page title and move `Fog Route Cleaner` to smaller metadata.
- Dense board used as I2V input: switch to clean first/end frames. Keep the board as planning-only.
- Fish-scale material artifact appears: strengthen `surface_integrity_guard`, reduce sharpening language, and regenerate only the failing image.
- Model motion failure: retry the failing video model only. Simplify movement and keep input image physically compatible.
- Missing audio policy: return to `video-model-adapter` and add visual-only silence, generated ambience, dialogue, voiceover, music, and effects boundaries.

## User-Facing QA Message

```text
阶段: QA 与重试规则
智能体创作内容:
- 我不会把生成图直接交给你判断。每张图先过 self-QA。
- 失败会定位到最小环节: 人物、场景/FOV、分镜运动页、clean frame、或某个视频模型提示词。
- 人物没锁就不生成场景；场景没锁就不生成分镜页；分镜页不合格就不生成 clean frames；clean frames 没锁就不进视频。
- 旧的失败类型会直接拦截: 人物漂移、场景漂移、标题层级错误、参考图职责混乱、分镜信息密度不足、鱼鳞材质、把规划板当视频首帧、模型提示词混写。

用户确认点:
如果开始 assisted_generation，是否同意按顺序生成并逐步 QA: 1 人物身份参考图 -> 2 场景/FOV 图 -> 3 专业分镜运动页 -> 4 clean start/end frames -> 5 单模型视频测试？
```

skill_run_receipt:
  run_id: complete-idea-qa-retry-plan-2026-05-17
  skill_id: generation-qa
  input_artifacts:
    - examples/complete-idea-segmentation-test/02-director-room-notes.md
    - examples/complete-idea-segmentation-test/03-shot-list.yaml
    - examples/complete-idea-segmentation-test/04-reference-prompt-plan.md
  output_artifacts:
    - examples/complete-idea-segmentation-test/05-qa-retry-plan.md
  decisions:
    - "Expose QA and retry rules before any assisted image or video generation."
    - "Require self-QA before user lock."
    - "Retry the smallest failed artifact instead of regenerating the whole workflow."
  unresolved_questions:
    - "Real user must authorize whether to begin sequential assisted generation."
  qa_gate:
    status: pass
    reasons:
      - "QA plan names pre-generation checks, post-generation self-QA checks, retry routing, media blockers, and the next user decision."
  next_recommended_skill: chat-facilitator
