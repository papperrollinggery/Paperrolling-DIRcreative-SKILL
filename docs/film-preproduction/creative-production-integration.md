# Creative Production Integration

Verified: 2026-06-15

Purpose: define how DIRcreative may use the Creative Production plugin as a deep generation and review path while keeping DIRcreative artifacts as the source of truth.

## Core Rule

Creative Production is an execution and review adapter, not the DIRcreative truth source.

DIRcreative owns:

- story, script, shot, visual bible, and reference pack gates,
- `pre_generation_contract`,
- image and video prompt manifests,
- generated/imported asset status,
- self-QA, user lock, retry routing, and live acceptance.

Creative Production may provide:

- image-led exploration,
- generated candidates,
- inline mood-board review surface,
- remix or variant review,
- final asset polish after a locked direction.

## Stage Mapping

Use this mapping only after DIRcreative's upstream gate is visible and resolved:

| DIRcreative stage | Creative Production path | Allowed use |
| --- | --- | --- |
| visual direction | Mood boards or Scenes | visual territories, audience feel, context exploration |
| brand/product reference planning | Offers or Ads | offer routes, product proof, campaign image directions |
| shot variants after approved shot list | Shots | alternate angles, crops, macro details, selected view options |
| final approved asset | Generative Polish | publish-safe finish while preserving copy, logo, size, and safe zones |

Do not use Creative Production for story invention, script approval, shot approval, or live acceptance.

## Adapter Receipt

Every Creative Production run registered by DIRcreative must write a receipt under `.dircreative/runs/` with:

```yaml
creative_production_adapter:
  visual_output_mode: assisted_generation
  user_authorization:
    explicit: true
    prompt_or_statement: ""
  dircreative_gate_state:
    story_locked: true
    script_locked: true
    shot_list_locked: true
    reference_pack_locked: true
    pre_generation_contract_status: pass
  creative_production_path: Mood boards | Scenes | Offers | Ads | Shots | Generative Polish
  review_surface:
    primary: render_moodboard_board_widget
    runDirectory: ""
    streamPath: ""
    widget_is_truth_source: false
  generated_candidates:
    - asset_id: ""
      asset_output_status: generated_candidate
      qa_status: pass | fail | pending
      user_lock_status: pending | locked | rejected
  truth_source:
    source_of_truth: dircreative_artifacts
    writeback_required: true
```

Allowed candidate states are:

- `prompt_ready`
- `generated_candidate`
- `user_locked`
- `rejected`
- `external_pending`
- `external_imported`

## Hard Blocks

Block Creative Production when any of these are true:

- story, script, shot, or reference gate is missing outside a Goal dry-run,
- `pre_generation_contract.status` is not `pass`,
- user authorization is absent for `assisted_generation`,
- generated candidate self-QA is missing,
- a widget, HTML page, temporary screenshot, or local URL is being treated as final truth,
- a `simulated_fixture` decision is being promoted into live acceptance.

## User-Facing Rule

When Creative Production is used, the chat should lead with what the user can review:

```text
阶段: 出图执行建议
客户可见预览:
- 我会用 Creative Production 做 <path>，但只作为候选图评审。
- 生成候选不会自动锁定为角色、产品、场景或验收真相。
- 自检通过后，我会让你选择 lock / reject / retry。

用户确认点:
是否授权生成这个已过合同的候选图组？
```

Do not ask the user to approve widget internals. Ask what production action to take.

## Acceptance Boundary

Creative Production evidence may support live acceptance, but it cannot close the goal.

The goal still closes only when `.dircreative/runs/live-user-acceptance.yaml` exists, contains a real user acceptance statement, and `scripts/dircreative_goal_audit.py --require-installed` reports `GOAL_COMPLETE: YES`.
