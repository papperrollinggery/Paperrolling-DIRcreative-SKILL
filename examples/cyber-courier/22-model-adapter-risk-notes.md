# Cyber Courier Model Adapter Risk Notes

```yaml
artifact_id: cyber-courier-model-adapter-risk-notes-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-video-prompt-manifest-v1
  - cyber-courier-image-prompt-manifest-v1
  - model-adapter-notes
status: approved
owner_skill: video-model-adapter
created_at: 2026-05-14
locked_by_user: false
```

## Adapter Decision

Use four materially different prompt strategies:

| Model | Strategy | Reason |
| --- | --- | --- |
| Seedance | Multi-reference 15s sequence | Best fit for complete reference pack and shot flow. |
| Kling | Per-shot subject/background/camera motion | Best fit for image-to-video motion control. |
| Runway | Per-shot motion-only prompts | Best fit for short single-scene motion from strong stills. |
| Veo | Structured cinematic prompt | Best fit for full component prompt and optional audio. |

## Universal Risk

Storyboard/reference boards can be misread as the thing to animate.

Required clause:

```text
Use storyboard/reference boards only as production guidance.
Do not show or animate the board, panels, text labels, arrows, grids, tables, or layout.
Generate the cinematic scene described by the shot list.
```

## Seedance Risks

- Multi-shot sequence may dilute character continuity.
- Dense storyboard board may appear in output.
- Audio support depends on selected product/API route.

Retry:

- Reduce to three shots if continuity fails.
- Remove storyboard board and keep text shot flow if board appears.
- Prioritize character and environment references before style board.

## Kling Risks

- If the still image does not match the requested movement, Kling may reinterpret the scene.
- Broad danger language can introduce attackers or running.
- Dense board inputs are weaker than clean shot stills.

Retry:

- Use one clean first-frame still per shot.
- Rewrite prompt as subject movement, background movement, camera movement.
- Remove extra mood language.

## Runway Risks

- Multi-shot prompts may overload the run.
- Negative wording can behave unpredictably.
- Over-description can reduce motion clarity.

Retry:

- Split every shot into its own run.
- Use one dominant movement per prompt.
- Keep positive motion language and let the input image define style.

## Veo Risks

- Structured prompts can still conflict if too many actions are compressed.
- Audio behavior depends on selected Veo workflow.
- Advanced lens terms may vary.

Retry:

- Generate 5-8 second segments if the 15-second sequence collapses.
- Keep audio as post-production if generated audio is wrong.
- Pair each camera term with a plain-language description.

## QA Result

```yaml
video_prompt_gate: pass
reference_map_present: true
audio_policy_present: true
anti_misread_clause_present: true
model_prompts_differ_materially: true
no_video_generated: true
phase_h_can_proceed: true
```
