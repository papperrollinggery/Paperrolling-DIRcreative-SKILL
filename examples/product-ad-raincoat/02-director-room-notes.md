# RainLock Commuter Shell - Director Room Notes

```yaml
artifact:
  artifact_id: rainlock-director-room-v1
  version: 1.0.0
  source_artifact_ids:
    - rainlock-idea-intake-v1
  status: approved
  owner_skill: director-room
  created_at: "2026-05-14"
  locked_by_user: false

roles:
  producer:
    recommendation: "Keep the 15s version to one commute beat and one visible proof moment."
    tradeoff: "A single use case is stronger than showing every feature."
  creative_director:
    recommendation: "Make rain a graphic stress test across glass, fabric, and street reflections."
    tradeoff: "Avoid outdoor-ad cliche; keep city fashion credibility."
  director:
    recommendation: "Follow one commuter from dry lobby threshold into heavy rain, then into a train carriage still composed."
    tradeoff: "Performance should be calm confidence, not heroic posing."
  screenwriter:
    recommendation: "Use title-card copy as product punctuation, not explanation."
    tradeoff: "No dialogue unless a later brand route needs voiceover."
  cinematographer:
    recommendation: "Use macro water-bead inserts and restrained tracking shots with real practical rain."
    tradeoff: "Too much slow motion will feel like a generic fabric demo."
  production_designer:
    recommendation: "Black graphite shell, brushed steel station, amber cafe light, cold rain reflections."
    tradeoff: "Do not let wardrobe disappear into a dark background."
  editor:
    recommendation: "15s cut uses three proof beats: step out, rain beads, arrive dry."
    tradeoff: "The 30s cut can add packability and hood detail."
  sound_designer:
    recommendation: "Rain, subway air, zipper pull, fabric rustle; no music in the proof section."
    tradeoff: "Music can enter only after the product proof lands."
  model_prompt_engineer:
    recommendation: "Create separate product board, use-case storyboard, and material macro board."
    tradeoff: "Do not feed dense boards to single-frame image-to-video models."
  continuity_qa:
    recommendation: "Lock shell color, zipper line, hood shape, water bead scale, and commuter bag position."
    tradeoff: "Product geometry drift damages the claim."

decision:
  direction: "Urban proof film."
  reason: "Advertising success depends on visible product proof, not story complexity."

skill_run_receipt:
  run_id: rainlock-director-room-2026-05-14
  skill_id: director-room
  input_artifacts:
    - examples/product-ad-raincoat/01-idea-intake.md
  output_artifacts:
    - examples/product-ad-raincoat/02-director-room-notes.md
  decisions:
    - "Prioritize visible product proof over narrative twist."
  unresolved_questions:
    - "Legal product claims remain non-final."
  qa_gate:
    status: pass
    reasons:
      - "Required role tradeoffs are present."
  next_recommended_skill: story-development
```
