# Complete Idea Intake

artifact:
  artifact_id: complete-idea-segmentation-intake-v1
  version: 1.0.0
  status: approved
  owner_skill: idea-intake

## User Input

I already have the full idea. I do not need brainstorming.

Make a 15-second vertical AI short film called **Fog Route Cleaner**.

A municipal sanitation worker moves through a foggy zombie-contaminated street at dawn. He is not a superhero. He calmly clears one narrow lane with a humming disinfectant cart so an ambulance can pass. The tone should be grounded, professional, tense, and humane. No gore, no comedy, no heroic posing. I need you to split it into the right number of shots, describe each shot professionally, then prepare reference image and video model prompts.

## Locked Inputs

- Title: Fog Route Cleaner
- Duration: 15 seconds
- Format: vertical 9:16
- Channel: AI short film / proof-of-concept cinematic scene
- Tone: grounded municipal realism, tense but humane
- Must avoid: gore, comedy, superhero posing, chaotic zombie action
- User goal: professional segmentation, shot design, reference plan, prompt-only export

## Intake Decision

The user supplied a complete concept. DIRcreative should not force broad concept brainstorming.

It should still validate story logic, timing, shot count, visual locks, reference strategy, and model prompt strategy in chat.

skill_run_receipt:
  run_id: complete-idea-intake-2026-05-16
  skill_id: idea-intake
  input_artifacts: []
  output_artifacts:
    - examples/complete-idea-segmentation-test/01-complete-idea.md
  decisions:
    - "Treat this as a complete-idea segmentation scenario, not an open brainstorm."
  unresolved_questions:
    - "Real user must still approve shot structure and reference pack before media generation."
  qa_gate:
    status: pass
    reasons:
      - "User intent, locks, and boundaries are explicit."
  next_recommended_skill: story-development
