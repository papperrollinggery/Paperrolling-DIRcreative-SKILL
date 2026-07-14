# Script

artifact:
  artifact_id: noodle-script-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-story-package-v1
  status: approved
  owner_skill: script-treatment

## 15s Script

00:00-00:03
Cold monitor light washes over a late-night desk. A worker rubs one eye. The ivory noodle cup sits unopened beside the keyboard.

00:03-00:06
Close on the hand pulling a red seal tab. A small heat indicator warms from dull red to amber.

00:06-00:09
Steam lifts from the cup, crossing the monitor glow. Noodles and broth look clean, hot, and natural.

00:09-00:12
The worker takes one sip. Shoulders relax. The room feels quieter.

00:12-00:15
Hero product frame on the desk, steam rising against the city window. Copy: Warmth, ready at midnight.

Dialogue: none.

Audio: office hum, tab peel, soft heat click, steam, spoon touch, distant elevator bell.

skill_run_receipt:
  run_id: noodle-script-2026-05-16
  skill_id: script-treatment
  input_artifacts:
    - examples/live-user-sim-noodle/05-story-package.md
  output_artifacts:
    - examples/live-user-sim-noodle/06-script.md
  decisions:
    - "Keep the ad dialogue-free so visual prompt quality carries the test."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "Script maps cleanly into five shots."
  next_recommended_skill: shot-design
