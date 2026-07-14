# Isolated User Simulation Protocol

Verified: 2026-05-18

Purpose: test whether DIRcreative feels usable to a normal user without leaking test criteria into the creative run.

## Isolation Rule

An isolated simulation has three separated roles:

| Role | Sees | Must Not See | Output |
| --- | --- | --- | --- |
| `simulated_user` | only the project situation and prior chat turns | scoring checklist, expected answer, internal docs | natural user requests, questions, satisfaction feedback |
| `dircreative` | only simulated user messages | reviewer rubric, future user feedback, repair plan | normal chat-first DIRcreative response |
| `independent_reviewer` | full transcript after the dialogue ends | none | root cause, repair need, and evidence |

The simulated user can be confused, impatient, satisfied, or dissatisfied. It must not tell DIRcreative how to pass the test.

## Required Scenario Set

Each isolated simulation pack must include:

- `rough_idea`: one vague creative idea.
- `complete_idea`: a user with a mostly complete premise who needs segmentation, not broad brainstorming.
- `longform_request`: a story longer than one model generation unit.
- `image_request`: a user asking to see images before the gates are ready.
- `midstream_change`: a user changing a core premise after downstream planning has begun.

## Pass Boundary

The simulation is useful only if it records:

- what the user said,
- how DIRcreative responded,
- whether the simulated user was satisfied,
- the dissatisfaction reason when present,
- the reviewer root cause,
- whether the Skill needs repair.

## Non-Acceptance Rule

Isolated simulation is not live acceptance.

It must keep:

```yaml
run_type: isolated_simulation_fixture
real_user_co_creation_verified: false
live_user_acceptance_receipt_written: false
real_media_generated: false
```

It must not create `.dircreative/runs/live-user-acceptance.yaml`.

## Midstream Change Rule

When a user changes a core premise, protagonist, product, channel, duration, tone, reference lock, or safety boundary after downstream planning has started, DIRcreative must:

1. name the changed upstream decision,
2. mark affected downstream artifacts as stale in chat,
3. stop before prompt or media generation,
4. ask one revision-scope question,
5. preserve unchanged locked decisions when possible.

If this is not visible in chat, the independent reviewer must mark `repair_required: true`.

## Validation

Run:

```bash
python3 scripts/dircreative_isolated_user_sim.py
```

This script validates the fixture and prints a human-readable report. It does not generate images or videos.
