# RainLock Commuter Shell - Concept Options

```yaml
artifact:
  artifact_id: rainlock-concept-options-v1
  version: 1.0.0
  source_artifact_ids:
    - rainlock-director-room-v1
  status: approved
  owner_skill: director-room
  created_at: "2026-05-14"
  locked_by_user: false

concept_options:
  - concept_id: option_a
    title: "The City Arrives Dry"
    channel_fit: "15s social and 30s product film"
    hook: "The commuter steps from a dry lobby into heavy rain without changing rhythm."
    product_proof: "Water beads and rolls off fabric while the inside collar and shirt remain dry."
    risk: "Needs clean macro reference to avoid fake water texture."
  - concept_id: option_b
    title: "Rain Commute Split Screen"
    channel_fit: "performance comparison ad"
    hook: "Two commuters enter the same storm; one arrives soaked, RainLock arrives composed."
    product_proof: "Contrast makes benefit obvious."
    risk: "Comparison can feel negative or generic."
  - concept_id: option_c
    title: "Pack, Zip, Weather"
    channel_fit: "e-commerce and product page video"
    hook: "The shell unfolds from a small pouch moments before the storm hits."
    product_proof: "Packability, zipper detail, hood fit, and water beading."
    risk: "Too feature-led for a brand film."

selected_option: option_a

skill_run_receipt:
  run_id: rainlock-concept-options-2026-05-14
  skill_id: director-room
  input_artifacts:
    - examples/product-ad-raincoat/02-director-room-notes.md
  output_artifacts:
    - examples/product-ad-raincoat/03-concept-options.md
  decisions:
    - "Select option_a for emotional simplicity and clear visual product proof."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "Each option includes channel fit, hook, proof, and risk."
  next_recommended_skill: story-development
```
