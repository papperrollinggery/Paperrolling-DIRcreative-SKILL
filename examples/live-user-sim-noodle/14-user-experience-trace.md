# User Experience Trace

artifact:
  artifact_id: noodle-user-experience-trace-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-video-prompt-manifest-v1
  status: approved
  owner_skill: co-creation-gate-runtime

## Purpose

This fixture simulates what a real user would experience when DIRcreative runs from one rough idea to generation-ready prompt artifacts.

No real image or video generation was run.

The primary user experience should happen in chat. `16-chat-interface-demo.md` shows the intended conversational surface.

## Simulated Interaction

1. User gives one rough idea: "15s vertical ad for a self-heating noodle cup, warm and cinematic."
2. Director room returns three concept directions.
3. User selects `Last Light At The Desk`.
4. DIRcreative previews story beats and asks for story approval.
5. User approves the story direction.
6. DIRcreative previews the 15-second script and asks for script approval.
7. User approves the script.
8. DIRcreative previews the five-shot structure and asks for shot-list approval.
9. User approves the shot structure.
10. DIRcreative offers three visual directions.
11. User selects `warm practical food realism with slight neo-noir office contrast`.
12. DIRcreative previews visual bible locks and asks for visual-bible approval.
13. User approves the visual bible locks.
14. DIRcreative proposes a compact reference pack.
15. User selects `product board + office board + lighting/material/style board + storyboard board + clean frames deferred`.
16. DIRcreative writes JSON-first image prompts.
17. User chooses `prompt-only export` instead of generating images.
18. DIRcreative writes model-specific video prompts for Seedance, Kling, Runway, and Veo.

## What This Proves

- The user is asked at concept, story, script, shot-list, style, visual-bible, sequence, reference, clean-frame, and video-prompt decision points.
- Simulated choices are labeled as `simulated_fixture`, not real user approval.
- Prompt-only mode can complete a generation-ready planning package without image generation capability.
- Dense boards and clean I2V frames are separated.
- Model-specific video prompts do not share one universal prompt.

## What This Does Not Prove

- Real images were not generated.
- Real clips were not generated.
- Live user co-creation is not verified by this fixture.
- Visual fidelity cannot be judged until generated assets exist.

## Commands

```text
python3 scripts/dircreative_run.py status --example examples/live-user-sim-noodle
python3 scripts/validate_project.py
```

skill_run_receipt:
  run_id: noodle-user-experience-trace-2026-05-16
  skill_id: co-creation-gate-runtime
  input_artifacts:
    - examples/live-user-sim-noodle/11-video-prompt-manifest.yaml
  output_artifacts:
    - examples/live-user-sim-noodle/14-user-experience-trace.md
  decisions:
    - "Treat this as a UX simulation, not a live user-verified run."
  unresolved_questions:
    - "A real run should ask the actual user before image generation."
  qa_gate:
    status: pass
    reasons:
      - "The trace exposes decision points and boundaries."
  next_recommended_skill: generation-qa
