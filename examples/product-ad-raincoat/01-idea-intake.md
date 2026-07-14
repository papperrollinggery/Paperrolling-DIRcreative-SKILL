# RainLock Commuter Shell - Idea Intake

```yaml
artifact:
  artifact_id: rainlock-idea-intake-v1
  version: 1.0.0
  source_artifact_ids: []
  status: approved
  owner_skill: idea-intake
  created_at: "2026-05-14"
  locked_by_user: false

project:
  title: "RainLock Commuter Shell"
  raw_user_idea: "A raincoat ad where rain becomes proof, not a problem."
  channel: "product_ad"
  deliverables:
    - "15s vertical social ad"
    - "30s horizontal product film"
  audience: "urban commuters who want technical protection without outdoor-performance styling"
  product_role: "lightweight waterproof commuter shell"
  desired_response: "The viewer trusts the coat because the film proves dryness, mobility, and city polish."
  constraints:
    - "No lab demo language."
    - "No fantasy storm spectacle."
    - "Product benefit must be visible in motion."
    - "Works without dialogue."
  open_questions:
    - "Final brand name can be replaced later."
    - "Exact product specs must be verified before legal copy."

skill_run_receipt:
  run_id: rainlock-idea-intake-2026-05-14
  skill_id: idea-intake
  input_artifacts:
    - raw_user_idea
  output_artifacts:
    - examples/product-ad-raincoat/01-idea-intake.md
  decisions:
    - "Treat as product advertising, not narrative short."
  unresolved_questions:
    - "Exact waterproof rating."
  qa_gate:
    status: pass
    reasons:
      - "Channel, audience, deliverables, product role, and constraints are explicit."
  next_recommended_skill: director-room
```
