# Cyber Courier Audio Policy

```yaml
artifact_id: cyber-courier-audio-policy-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-script-v1
  - cyber-courier-script-breakdown-v1
  - audio-design-notes
status: approved
owner_skill: script-breakdown
created_at: 2026-05-14
locked_by_user: false
```

## Policy Summary

```yaml
dialogue: none
voiceover: none
music: none_for_mvp
ambience: planned
sfx: planned
generation_audio: model_dependent
post_production_audio: recommended_default
image_prompt_audio: labels_only_if_needed
```

The story must remain readable as a silent visual sequence. Audio strengthens the mood but must not carry missing story information.

## Image Prompt Audio Rules

Image prompts do not generate sound.

Allowed later in storyboard/reference boards:

```text
small Audio Plan label: rain ambience, neon buzz, scanner beep, no dialogue, no music
```

Rules:

- Treat audio labels as production notes only.
- Do not expect video models to infer sound from image labels.
- Do not put music mood into character, prop, or environment board prompts unless the board is specifically an audio/storyboard planning artifact.

## Video Prompt Audio Rules

For models or workflows with audio support, write audio in a separate section:

```text
Audio: steady rain ambience, distant city hum, subtle neon electrical buzz, soft scanner beep when the package seal pulses, faint relay click when the intercom activates, no dialogue, no voiceover, no music.
```

For visual-only generation, write:

```text
Audio: silent visual-only clip, no dialogue, no voiceover, no music, no sound effects.
```

Never bury audio inside general style words.

## Post-Production Audio Plan

Recommended default for MVP:

```yaml
generation_mode: post_production
ambience:
  - steady rain on pavement
  - distant traffic hum behind alley entrance
  - faint electrical buzz from neon signs
sfx:
  - wet footsteps during courier approach
  - soft fabric/strap tension as bag is gripped
  - scanner beep or pulse during package reveal
  - relay click when intercom activates
music: none
dialogue: none
voiceover: none
silence_strategy: keep the final beat sparse so door activation feels ominous
```

## Timing Notes

| Time | Sound Intent | Story Function |
| --- | --- | --- |
| 0-3s | Rain, distant traffic, low neon buzz | Public street vs forbidden alley threshold |
| 3-6s | Wet footsteps and bag strap movement | Courier commits to entry |
| 6-8s | Soft scanner beep or electronic pulse | Package becomes active |
| 8-12s | Rain remains, city hum falls back | Courier registers danger |
| 12-15s | Intercom relay click, sparse rain | Destination wakes |

## What To Avoid

- No spoken exposition.
- No synthetic voice explaining the package.
- No loud action trailer hit.
- No music swell that makes the clip feel like a trailer.
- No overlapping dialogue, music, and SFX in a 15-second MVP.

## Phase D Hand-Off

Shot design must include audio fields per shot, even if the field says `none`.

The later video model adapter must choose one of two modes per model:

```yaml
audio_mode:
  visual_only: "silent generation, post-production audio planned"
  generated_audio: "explicit audio section in model prompt if model/workflow supports it"
```
