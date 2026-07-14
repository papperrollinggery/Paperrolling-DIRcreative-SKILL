# Idea Intake

artifact:
  artifact_id: noodle-idea-intake-v1
  version: 1.0.0
  status: approved
  owner_skill: idea-intake

## Raw User Idea

Make a 15-second vertical ad for a self-heating noodle cup. It should feel warm, cinematic, and useful for late-night workers, not like a loud snack commercial.

## Intake Result

Project title: Midnight Broth Cup

Deliverable: 15-second vertical product ad.

Core audience: late-night office workers, students, editors, and drivers who need a fast warm meal without a kitchen.

Primary promise: hot broth in a quiet moment, ready when the night is still moving.

Constraints:

- prompt-only test, no real images or videos generated,
- one product, one main user, one location family,
- no claims about nutrition, health, or safety beyond warmth and convenience,
- final outputs must be usable by image and video generation tools later.

skill_run_receipt:
  run_id: noodle-idea-intake-2026-05-16
  skill_id: idea-intake
  input_artifacts: []
  output_artifacts:
    - examples/live-user-sim-noodle/01-idea-intake.md
  decisions:
    - "Use a compact product ad because it exercises concept, visual direction, reference, image prompt, and video prompt gates quickly."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "The idea is scoped to one 15-second generation unit."
  next_recommended_skill: director-room
