# Director Room Notes

artifact:
  artifact_id: zombie-cleaner-director-room-v1
  version: 1.0.0
  status: approved
  owner_skill: director-room

## Roles

producer: Keep the test scoped to a 180s prompt-only fixture. Do not generate media.

creative_director: The hook is civic bureaucracy inside an apocalypse. The worker treats zombie cleanup like a boring night shift.

director: Make the action readable. Use a strong vehicle silhouette, one hero worker, one glowing barrel, and a small zombie crowd.

screenwriter: The story needs one job, one route, one mistake, one payoff.

cinematographer: Atom-punk sodium vapor, sickly green waste glow, 35mm road shots, 85mm gross-comedy inserts.

production_designer: Municipal decals, rusted street sweeper, rubber gloves, hazard forms, faded quarantine signs.

editor: Twelve 15s units. Each unit needs a clean comic or suspense beat.

sound_designer: Engine rattle, broom bristles, wet zombie footsteps, Geiger clicks, no dialogue by default.

model_prompt_engineer: Use global identity/vehicle boards and sequence clean frames. Keep dense boards away from direct Kling/Runway first frames.

continuity_qa: Lock hero face, orange sanitation suit, vehicle decals, barrel glow, and sunrise deadline.

## Recommendation

Choose a black-comedy action route:

```text
municipal worker
-> zombie quarantine street
-> glowing barrel pickup
-> street sweeper malfunction
-> zombie crowd accidentally herded into recycling compactor
-> dawn cleanup report stamp
```

## skill_run_receipt

```yaml
skill_run_receipt:
  run_id: zombie-cleaner-director-room-2026-05-16
  skill_id: director-room
  input_artifacts:
    - examples/zombie-cleaner-test/01-idea-intake.md
  output_artifacts:
    - examples/zombie-cleaner-test/02-director-room-notes.md
  decisions:
    - "Use municipal black comedy as the original angle."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "All core production roles contributed distinct constraints."
  next_recommended_skill: story-development
```
