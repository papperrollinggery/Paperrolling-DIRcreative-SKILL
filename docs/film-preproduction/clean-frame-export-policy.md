# Clean Frame Export Policy

Verified: 2026-07-10

Purpose: keep planning boards and direct video inputs separate while allowing exact capability cards to decide which reference modes exist.

## Core Rule

Reference boards are planning/continuity artifacts. Clean frames are single-state cinematic assets.

No workflow may call a dense board a first frame, last frame, keyframe, or direct image-to-video input merely because the board contains a useful panel.

## Required Separation

Planning boards may contain:

- role titles,
- labels and callouts,
- shot-card text,
- maps and FOV wedges,
- arrows and subject paths,
- timecodes,
- panel borders,
- material notes,
- style swatches.

Clean frames contain only the cinematic scene:

- one shot state,
- no title or visible production text,
- no label, arrow, table, or border,
- no storyboard strip or floor plan,
- no swatch or watermark-like note,
- no alternate angle inset.

## Capability-Resolved Strategy

Choose a strategy only after resolving the exact model version and provider surface:

| Strategy | Use when | Required evidence |
| --- | --- | --- |
| `all_reference_sequence` | the card supports the declared board/asset reference modes | exact card fields, rights, bindings, anti-misread clauses |
| `hybrid` | boards guide continuity and selected clean frames provide literal anchors | planning-only board edges plus clean-frame direct edges |
| `per_shot_i2v` | the card uses first/start/end/key frames per generated shot | one clean frame prompt or file for every required direct slot |
| `text_to_video` | the card supports text generation and direct images are intentionally omitted | accepted consistency risk and source-lock wording |
| `minimal_test` | one small proof is enough | exact test goal, one or two assets, no claim of full pack readiness |

Do not select a strategy from a family name. Bind it to `capability_card_id`, `version`, `provider_surface`, and `reference_modes`.

## Dynamic Clean-Frame Selection

The number of clean frames comes from the selected strategy and shot risk, not a fixed rule.

Select a clean frame when it controls:

- opening geography or identity,
- a product/prop interaction,
- a transformation or state change,
- a precise end state,
- a high-risk gesture or composition,
- a direct input slot required by the selected card.

Omit clean frames only when the chosen text/all-reference route supports that decision. Record the accepted drift risk.

## Clean Frame Prompt Contract

Every clean-frame prompt records:

```yaml
clean_frame_contract:
  asset_id: ""
  shot_id: ""
  frame_role: "clean_first_frame | clean_key_frame | clean_end_frame"
  exact_visual_state: ""
  shot_size: ""
  camera_angle: ""
  lens: ""
  composition: ""
  lighting: ""
  continuity_locks: []
  rights_gate_status: ""
  direct_model_input:
    capability_card_id: ""
    provider_surface: ""
    reference_mode: ""
    allowed: false
  forbidden_visible_elements:
    - title
    - label
    - arrow
    - panel_border
    - storyboard_strip
    - floor_plan
```

The prompt itself must state `Clean frame contract:`, `no visible title`, and `Direct video input policy: allowed` only when the exact card resolution allows that slot.

## Storyboard Export Contract

A professional storyboard/motion map remains a separate asset with a dominant role title and full shot-card information. Its direct input policy defaults to `planning_only`.

If an exact card conditionally accepts a storyboard reference:

- bind the board to a supported reference mode, never a first-frame slot,
- state what the model may read,
- include the anti-misread clause inline,
- preserve a separate clean frame for any literal first/end-frame slot,
- record accepted interpretation risk.

## Readiness Rule

Prompt export may exist in `prompt_only`. Direct generation is blocked until:

- the exact capability card is current and resolved,
- the required clean frame exists as `external_imported`, `generated_candidate`, or `user_locked` according to the mode,
- self-QA and rights pass,
- any required user lock is recorded,
- the motion prompt does not contradict the clean frame,
- the direct binding names the same shot and reference mode.

## Failure Conditions

Reject the workflow when:

- a board is bound as a literal clean frame,
- a clean frame contains planning graphics or text,
- a prompt says to crop/export a hidden clean frame from a board,
- a capability family alias is used instead of an exact card,
- a required direct input is only planned but claimed as existing,
- rights are unverified,
- the motion/action contradicts the visible start state,
- every project is forced into the same number of clean frames,
- a text/all-reference route omits clean frames without recording accepted risk.
