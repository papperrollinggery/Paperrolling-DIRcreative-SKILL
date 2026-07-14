# Idea Intake

artifact:
  artifact_id: zombie-cleaner-idea-intake-v1
  version: 1.0.0
  status: approved
  owner_skill: idea-intake

## Raw Idea

Use the public success of `Zombie Scavenger` as a benchmark, then create an original AI short about a wasteland sanitation worker who has one night to clean a zombie-contaminated district before sunrise.

## Structured Brief

```yaml
project:
  title: "Wasteland Sanitation Route"
  channel: "ai_short_film"
  target_duration_sec: 180
  aspect_ratio: "16:9"
  audience: "global genre short viewers who like dark comedy, zombie action, and stylish AI films"
  tone:
    - black comedy
    - atom-punk
    - grimy but playful
    - cinematic action
  references:
    - "Zombie Scavenger public benchmark traits only"
    - "wasteland road film"
    - "municipal worker visual irony"
  constraints:
    - "do not copy the referenced short"
    - "prompt_only mode"
    - "no generated media in fixture"
    - "3 minute longform test"
```

## Intake Decision

Proceed as an original longform fixture.

Primary test question:

Can DIRcreative turn a public AI short reference into a professional, original 180s prompt package without copying the source?

## skill_run_receipt

```yaml
skill_run_receipt:
  run_id: zombie-cleaner-idea-intake-2026-05-16
  skill_id: idea-intake
  input_artifacts:
    - examples/zombie-cleaner-test/00-source-study.md
  output_artifacts:
    - examples/zombie-cleaner-test/01-idea-intake.md
  decisions:
    - "Use the public short as a benchmark reference, not as source story."
  unresolved_questions: []
  qa_gate:
    status: pass
    reasons:
      - "Brief has channel, duration, audience, tone, constraints, and originality boundary."
  next_recommended_skill: director-room
```
