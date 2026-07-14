# Noodle Ad QA And Retry Plan

artifact:
  artifact_id: noodle-qa-retry-plan-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-image-prompt-manifest-v1
    - noodle-video-prompt-manifest-v1
    - noodle-co-creation-run-v1
  status: approved
  owner_skill: generation-qa

## Purpose

Make the one-sentence idea path show the same prevention and retry logic as the complete-idea path. The user should see how DIRcreative prevents bad generated assets before any image or video call.

## Current Media State

- visual_output_mode: `prompt_only`
- 当前没有生成真实图片或视频
- product board, office board, lighting/material/style board, and storyboard board are prompt-ready only
- clean frames are deferred
- direct I2V remains blocked until clean frames are generated or imported and self-QA passes

## Pre-Generation Contract

Before assisted image generation, every image asset must have a visible `pre_generation_contract`.

Example contract for `noodle_image_01`:

```yaml
pre_generation_contract:
  status: pass
  asset_id: noodle_image_01
  asset_role: product_identity_board
  dominant_title: "产品身份参考图 / PRODUCT IDENTITY REFERENCE"
  secondary_project_metadata: "Project: Midnight Broth Cup"
  title_hierarchy:
    role_label_largest: true
    project_title_secondary: true
    forbidden_largest_text:
      - "MIDNIGHT BROTH CUP"
      - "film title"
      - "product ad title"
  role_purity:
    primary_job: "lock cup identity, red seal, lid edge, broth, noodles, steam, and hand scale"
    must_not_do:
      - "act as final video frame"
      - "act as office environment reference"
      - "act as storyboard page"
      - "act as text-heavy brand poster"
  inheritance:
    product_identity_source: self
    environment_source: none
  direct_video_input_policy:
    allowed: false
    reason: "product board contains labels and multiple support panels"
  prompt_lint:
    exact_role_label_present: true
    title_hierarchy_instruction_present: true
    forbidden_poster_hierarchy_present: true
    no_unowned_scene_or_character_redesign: true
  image_generation_allowed: true
```

Prompt text must include:

- Largest title on the page: `产品身份参考图 / PRODUCT IDENTITY REFERENCE`
- Smaller metadata only: `Project: Midnight Broth Cup`
- Do not make `MIDNIGHT BROTH CUP` or product/ad title the largest text.
- Use concise, failure-specific material or geometry constraints. The fixed surface-integrity macro stays off unless an observed failure ID or internal A/B test activates it.

## Pre-Generation QA

Before generation, verify:

1. `pre_generation_contract.status: pass`.
2. Contract `asset_id` matches the image being generated.
3. Dominant title is the asset role, not the project/product title.
4. One asset has one primary job.
5. Planning boards are marked `NOT DIRECT VIDEO INPUT` or `PLANNING ONLY`.
6. Clean frames are text-free, panel-free, arrow-free, and direct-I2V eligible only after user approval.
7. Surface integrity guard is present for broth, noodles, steam, paper cup, and lighting.

If any item fails, do not call image generation.

## Post-Generation Self-QA

After any generated image candidate, run self-QA before user review:

- product label drift
- cup shape, red seal, copper lid, broth, noodle, or steam inconsistency
- character/hand deformation at cup contact
- office scene geography drift
- reference asset role conflict
- reference role label hierarchy wrong
- unreadable reference text
- fish_scale_material_artifact
- storyboard_board_misread_by_video_model
- board_used_as_direct_i2v_input_when_forbidden
- missing_audio_policy
- copied_video_prompt_across_models

If self-QA fails, do not ask the user to lock the image. Record `self_qa.status: fail`, failure IDs, and the next retry action.

## Retry Routing

Retry only the smallest artifact that fixes the failure:

- Product identity drift: retry `noodle_image_01` only, with stronger cup, red seal, broth, noodle, and steam locks.
- Office geography drift: retry `noodle_image_02` only, inheriting product identity from the locked product board.
- Lighting/material style drift: retry `noodle_image_03` only, preserving locked product and office design.
- Storyboard information too thin: return to `shot-design`, then regenerate `noodle_image_04` as planning-only.
- Clean-frame missing or contaminated by text/panels: generate or crop a clean N01/N05 frame from the approved environment source.
- Board used as direct I2V input: replace it with clean frame input for Kling/Runway.
- Model-specific motion failure: retry the failing model only, simplifying motion and preserving the input frame.

## User-Facing QA Message

```text
阶段: QA 与重试规则
智能体创作内容:
- 这里仍是 prompt-only，没有生成真实图片或视频。
- 如果你授权 assisted_generation，我会先写并检查 pre_generation_contract，再调用生图。
- 每张图生成后先过 self-QA，不把失败图直接交给你锁定。
- 失败只重试最小环节: 产品板、办公室板、灯光材质板、分镜板、clean frame、或某个视频模型提示词。

用户确认点:
是否同意进入顺序生成: 1 产品身份板 -> 2 办公室/clean-frame 来源 -> 3 灯光材质板 -> 4 分镜运动板 -> 5 clean N01/N05 -> 6 单模型视频测试？
```

skill_run_receipt:
  run_id: noodle-qa-retry-plan-2026-05-17
  skill_id: generation-qa
  input_artifacts:
    - examples/live-user-sim-noodle/10-image-prompt-manifest.yaml
    - examples/live-user-sim-noodle/11-video-prompt-manifest.yaml
    - examples/live-user-sim-noodle/15-co-creation-run.yaml
  output_artifacts:
    - examples/live-user-sim-noodle/12-qa-retry-plan.md
  decisions:
    - "Expose pre-generation contract and QA/retry rules in the one-sentence idea path."
    - "Keep media blocked in prompt-only mode."
    - "Require self-QA before user lock."
  unresolved_questions:
    - "Live user must authorize whether to start assisted_generation."
  qa_gate:
    status: pass
    reasons:
      - "Plan names contract requirements, self-QA, failure IDs, media blockers, and smallest-artifact retry routes."
  next_recommended_skill: chat-facilitator
