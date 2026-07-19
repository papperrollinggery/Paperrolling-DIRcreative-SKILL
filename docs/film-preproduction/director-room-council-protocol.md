# Director Room Adaptive Perspective Protocol

Verified: 2026-07-19

“Council” is a legacy compatibility label. V2 uses one controlling agent and only
the professional perspectives that can change the work.

## Purpose

Improve complete Studio film-preproduction outputs without placing meeting
ceremony, fixed seats, or manufactured disagreement before the artifact.

## Entry

Read `docs/film-preproduction/director-room-routing.md` and the v2 contracts in
`docs/film-preproduction/schemas/director-role-harness.yaml` and
`docs/film-preproduction/schemas/director-room.yaml`.

Fast never opens Director Room. A complete advertising film, story plus script,
script plus storyboard, or other multi-output Studio request may open it with at
most three perspectives. Delivery uses its own audit route. An orchestrated worker
never starts nested dispatch.

## Dynamic Perspectives

### `narrative_strategy`

Owns copy, story pressure, conflict, structure, dialogue or voiceover, commercial objective, and the effect of revisions on story/script outputs.

### `visual_production`

Owns shot grammar, camera, art direction, blocking, edit rhythm, sound, production clarity, and the effect of revisions on shots and visual systems.

### `model_continuity`

Owns model capability, reference roles, subject/action ownership, identity and
scene continuity, prompt interpretation risk, and downstream model QA.

The ten fixed v1 roles remain a read-only knowledge index. They are not required
passes, user-visible cards, or separate workers.

## Synthesis

Present the recommendation or revised artifact first. Then show no more than three
short judgments that explain a consequential tradeoff or constraint.

If there is no material conflict, record:

```yaml
conflict_status: no_material_conflict
disagreements: []
```

If a material conflict exists, record the competing choices, evidence, production
consequences, recommendation, and decision owner. Do not create conflict merely to
simulate collaboration.

Numbered alternatives are optional. Use them only when the user asks for choices
or an unresolved material conflict truly requires a direction decision. A request
to optimize existing content returns the optimized content directly.

## Execution

- One controlling agent.
- Threads default to zero.
- At most one independent critical pass.
- No nested dispatch.
- No fixed role count.
- No minimum disagreement count.
- No meeting transcript before the artifact.

## Artifact Contract

New artifacts conform to `director-room.yaml` v2 and record mode, route,
`director_room_used`, selected perspectives, recommendation, judgments, conflict
status, optional disagreements/options, open questions, and lock status.

V1 artifacts remain readable and immutable. Migration creates a new v2 artifact;
it never rewrites the source fixture.

## Failure And Retry

| Failure | Smallest correction |
| --- | --- |
| Fast task opened Director Room | Close it and return the bounded result directly. |
| More than three perspectives selected | Keep only perspectives with a decision-changing contribution. |
| Generic judgment | Re-run only that perspective against named evidence. |
| Manufactured disagreement | Replace it with `no_material_conflict`. |
| Options forced without a choice request | Return the recommendation directly. |
| Unsupported model claim | Mark it unverified and route source verification. |

Stop when a change would choose a user-owned incompatible direction, authorize
real generation, or approve client delivery.
