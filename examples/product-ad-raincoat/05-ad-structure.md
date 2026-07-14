# RainLock Commuter Shell - 15s / 30s Ad Structure

## 15s Vertical Social

| Time | Beat | Visual | Audio | Copy |
| --- | --- | --- | --- | --- |
| 0-2s | Hook | Lobby doors open to hard rain; commuter steps out without hesitation. | Rain hits glass, city air. | |
| 2-6s | Proof | Macro beads roll off graphite shell; zipper seam stays clean. | Rain on fabric, soft zipper touch. | "Arrive dry." |
| 6-11s | Use | Tracking shot through crosswalk, bag tucked under shell line. | Footsteps, traffic wash. | |
| 11-15s | Payoff | Train platform: shirt collar dry, commuter composed. | Rain falls behind doors. | "RainLock Commuter Shell" |

## 30s Product Film

| Time | Beat | Visual | Audio | Copy |
| --- | --- | --- | --- | --- |
| 0-4s | City pressure | Phone weather alert, lobby rain wall, commuter zips shell. | Phone buzz, zipper. | |
| 4-10s | Hood fit | Hood adjusts cleanly without hiding face. | Fabric rustle, rain. | "Built for the weather between meetings." |
| 10-16s | Water proof | Macro water beads, shoulder seam, sleeve cuff, bag cover. | Rain detail close. | |
| 16-23s | Mobility | Crosswalk track, turnstile step, stair descent. | Subway air, steps. | |
| 23-30s | Dry arrival | Train platform; commuter lowers hood, collar and shirt dry. | Rain fades behind closing doors. | "Arrive dry." |

```yaml
artifact:
  artifact_id: rainlock-ad-structure-v1
  version: 1.0.0
  source_artifact_ids:
    - rainlock-selected-concept-v1
  status: approved
  owner_skill: script-treatment
  created_at: "2026-05-14"
  locked_by_user: false

audio_policy:
  image_prompts: "No music notation inside image prompts; image boards may include sound labels only as production annotations."
  video_prompts: "Use rain, zipper, fabric rustle, city air, and train ambience as optional audio section. No dialogue."
  post_production: "Music optional after product proof; keep proof section led by diegetic sound."

skill_run_receipt:
  run_id: rainlock-ad-structure-2026-05-14
  skill_id: script-treatment
  input_artifacts:
    - examples/product-ad-raincoat/04-selected-concept.md
  output_artifacts:
    - examples/product-ad-raincoat/05-ad-structure.md
  decisions:
    - "Use 15s as performance proof and 30s as product-feature extension."
  unresolved_questions:
    - "Final copy requires product claim verification."
  qa_gate:
    status: pass
    reasons:
      - "Both durations define hook, proof, payoff, audio, and copy."
  next_recommended_skill: shot-design
```
