# Story Package

artifact:
  artifact_id: noodle-story-package-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-selected-concept-v1
  status: approved
  owner_skill: script-treatment

## Beat Sheet

1. Hook: cold office glow, tired worker, untouched cup.
2. Activation: red seal tab opens, heat indicator glows.
3. Transformation: steam rolls through the blue monitor light.
4. Human proof: first sip, shoulders drop, focus returns.
5. Product lock: cup hero with end copy.

## Production Rules

- one worker,
- one desk,
- one cup,
- no visible fake app UI,
- no medical or energy claims,
- steam must feel natural and edible,
- noodle texture must stay clean, not over-sharpened.

## Audio Policy

Image prompts should not include music. Video prompts can include diegetic sound notes. Music is optional in post only.

skill_run_receipt:
  run_id: noodle-story-package-2026-05-16
  skill_id: script-treatment
  input_artifacts:
    - examples/live-user-sim-noodle/04-selected-concept.md
  output_artifacts:
    - examples/live-user-sim-noodle/05-story-package.md
  decisions:
    - "Use five beats to match a five-shot 15-second structure."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "Story package separates visual, product, and audio constraints."
  next_recommended_skill: script-treatment
