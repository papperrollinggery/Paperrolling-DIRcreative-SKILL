# RainLock Commuter Shell - Selected Concept

```yaml
artifact:
  artifact_id: rainlock-selected-concept-v1
  version: 1.0.0
  source_artifact_ids:
    - rainlock-concept-options-v1
  status: approved
  owner_skill: story-development
  created_at: "2026-05-14"
  locked_by_user: false

selected_concept:
  title: "The City Arrives Dry"
  logline: "A commuter steps into heavy city rain and arrives at the train platform dry, composed, and ready for the day."
  promise: "Weather protection that still looks right in the city."
  emotional_turn: "The storm changes from disruption into proof."
  visual_hook: "Rain beads streak across the shell while the commuter keeps the same calm pace."
  channel_strategy:
    15s: "Immediate hook, product proof, dry arrival."
    30s: "Adds hood fit, sleeve seal, packable detail, and brand memory line."
  copy_direction:
    primary_line: "Arrive dry."
    support_line: "Built for the weather between meetings."
  legal_note: "Replace claims with verified product specifications before external release."

skill_run_receipt:
  run_id: rainlock-selected-concept-2026-05-14
  skill_id: story-development
  input_artifacts:
    - examples/product-ad-raincoat/03-concept-options.md
  output_artifacts:
    - examples/product-ad-raincoat/04-selected-concept.md
  decisions:
    - "Use visible proof and restrained copy instead of feature enumeration."
  unresolved_questions:
    - "Verified waterproof rating."
  qa_gate:
    status: pass
    reasons:
      - "Concept includes proof, emotional turn, channel split, and visual hook."
  next_recommended_skill: script-treatment
```
