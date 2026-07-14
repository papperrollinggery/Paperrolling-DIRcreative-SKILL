# Selected Concept

artifact:
  artifact_id: noodle-selected-concept-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-concept-options-v1
  status: approved
  owner_skill: story-development

Title: Midnight Broth Cup

Logline: In a quiet late-night office, a self-heating noodle cup turns screen fatigue into a warm, focused pause.

Format: 15-second vertical product ad.

Tone: cinematic, restrained, warm, practical.

Selected visual direction: warm practical food realism with slight neo-noir office contrast.

Core story:

1. Cold screen light and an unfinished timeline.
2. A hand pulls the red seal tab on the cup.
3. Steam rises and warms the frame.
4. The worker takes one quiet sip.
5. Product end frame: cup, steam, city window, short line.

End copy: Warmth, ready at midnight.

skill_run_receipt:
  run_id: noodle-selected-concept-2026-05-16
  skill_id: story-development
  input_artifacts:
    - examples/live-user-sim-noodle/03-concept-options.md
  output_artifacts:
    - examples/live-user-sim-noodle/04-selected-concept.md
  decisions:
    - "Lock concept for the simulation as if the user chose Option A."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "Concept has product, user, setting, emotional turn, and end copy."
  next_recommended_skill: script-treatment
