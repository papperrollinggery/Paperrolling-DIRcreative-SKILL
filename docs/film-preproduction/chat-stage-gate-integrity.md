# Chat Stage Gate Integrity

Verified: 2026-07-19

Status: v2 integrity guide with legacy v1 read compatibility. The canonical gate
set is owned by `skills/dircreative/runtime/routing-policy.yaml`.

## Active External Gates

New runs may block for exactly these gates:

| Gate | Due only when | Unlocks |
| --- | --- | --- |
| `concept_lock` | two or more incompatible creative directions would materially change the output | the selected concept direction |
| `generation_authorization` | real image or video generation is ready and lacks scoped authorization | the exact authorized generation scope |
| `client_delivery_approval` | an external client-visible handoff is ready and lacks scoped approval | the exact approved delivery |

No other stage is a default external user gate.

## Internal State Integrity

`story_state`, `script_state`, `shot_state`, `visual_state`, `reference_state`,
`prompt_state`, and `qa_state` are reversible. They may be draft, current, stale,
or revised. A transition between them does not require a visible
`用户确认点` unless it reaches one of the three external gates.

When a premise changes, name the affected outputs and mark only those outputs
stale. A bounded line, shot, or prompt edit must not reset unrelated internal
state.

## Stop Algorithm

1. If no real blocker exists, continue and return useful work.
2. If incompatible directions require a human preference, show the work and stop
   at `concept_lock`.
3. If real generation lacks scoped authorization, show the exact input/output
   scope and stop at `generation_authorization`; otherwise execute it.
4. If an external client-visible handoff lacks scoped approval, show the
   deliverables and stop at `client_delivery_approval`; otherwise perform it.
5. Unknown facts may trigger one blocking question only when proceeding would be
   misleading or unsafe; that question does not create a new named gate.

“继续” continues internal work and actions with still-valid scoped permission.
It cannot manufacture permission for a new side effect. `system_default` cannot
manufacture a user approval.

## Gate Surface

An actual gate shows:

1. the artifact or delivery preview;
2. the professional reason the decision matters;
3. the exact gate id;
4. one decision question;
5. what the answer authorizes.

A visual click cannot directly claim a lock, authorization, delivery approval,
readiness, or completion. The controller must echo a human-readable decision and
bind it to current inputs.

## Failure Cases

Fail v2 interaction integrity when:

- a new run requires any legacy gate;
- “继续” stops without a real blocker;
- a local revision returns to idea intake or full story approval;
- a complete brief is asked again instead of reused;
- a direct artifact request receives only process narration;
- real generation proceeds without `generation_authorization`;
- client delivery proceeds without `client_delivery_approval`;
- a stale or simulated choice is presented as current human approval.

## Legacy V1 Fixture Reader

The old co-creation schema is frozen at v1 and read-only. Its eleven gate types
are `concept_options_gate`, `story_approval_gate`, `script_approval_gate`,
`shot_list_approval_gate`, `visual_direction_gate`,
`visual_bible_approval_gate`, `sequence_plan_gate`,
`global_reference_pack_gate`, `sequence_reference_pack_gate`,
`clean_frame_gate`, and `video_prompt_gate`.

Existing dry-run fixtures may still use `simulated_fixture`,
`simulated_choices_allowed: true`, and `real_user_co_creation_verified: false`.
Existing live fixtures may use `real_user`. The validator reads these records to
preserve compatibility; it must never use their required-gate list as the
template for a new v2 run.
