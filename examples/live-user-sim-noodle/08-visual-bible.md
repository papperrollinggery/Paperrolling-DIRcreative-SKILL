# Visual Bible

artifact:
  artifact_id: noodle-visual-bible-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-shot-list-v1
  status: approved
  owner_skill: visual-bible

## Identity Locks

Product: ivory self-heating noodle cup, red seal band, copper foil lid edge, black vertical label reading MIDNIGHT BROTH.

Main user: late-night office worker, dark overshirt, tired but composed, no exaggerated acting.

Environment: quiet office desk near a rainy city window, blue monitor light, warm desk lamp, scattered but tidy work tools.

Palette: monitor blue, desk-lamp amber, ivory cup, red seal band, copper foil highlight, black label.

Camera grammar: restrained product realism, macro proof inserts, slow practical camera movement.

Material rules:

- paper cup must look matte and tactile,
- broth must look clear and hot,
- noodles must look natural, not crunchy or over-sharpened,
- steam must be soft and layered,
- hands must remain anatomically plausible.

Avoid:

- loud snack commercial energy,
- explosive steam,
- fantasy glow,
- messy food texture,
- unreadable fake label text,
- generic symmetrical reference boards.

skill_run_receipt:
  run_id: noodle-visual-bible-2026-05-16
  skill_id: visual-bible
  input_artifacts:
    - examples/live-user-sim-noodle/07-shot-list.yaml
  output_artifacts:
    - examples/live-user-sim-noodle/08-visual-bible.md
  decisions:
    - "Use warm practical food realism with slight neo-noir office contrast."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "Visual bible includes product, user, environment, palette, camera, material, and avoid rules."
  next_recommended_skill: reference-image-planner
