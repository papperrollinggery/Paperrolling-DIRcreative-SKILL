# Cyber Courier Beat Sheet

```yaml
artifact_id: cyber-courier-beat-sheet-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-story-logline-v1
  - cyber-courier-selected-concept
status: approved
owner_skill: story-development
created_at: 2026-05-14
locked_by_user: false
```

## Format

```yaml
channel: cinematic_short_test
duration: 15s
aspect_ratio: 16:9
beat_count: 5
dialogue: none
voiceover: none
audio_policy: visual-first; optional ambience and scanner cue handled later
```

## Beat Structure

| Beat | Time | Story Function | Visible Action | Emotional Shift | Production Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | 0-3s | Establish the forbidden threshold | The courier stands at the mouth of a narrow alley in heavy rain, red jacket isolated against blue-black street light. | Controlled urgency becomes hesitation. | Must show alley depth, red sign left, blue `24小时` sign deeper in frame. |
| 2 | 3-6s | Commit to the delivery | He steps into the alley, one hand tightening around a black delivery bag as rain hits the hood and shoulders. | Hesitation becomes professional resolve. | Keep one main movement: forward entry. Avoid extra pedestrians or attackers. |
| 3 | 6-8s | Reveal the object as active | Close detail: inside the bag, a sealed package or scanner tag starts to emit a red pulse. | Routine delivery becomes wrong. | The red glow should match the alley signage, implying a system connection. |
| 4 | 8-12s | Register danger | The courier looks up from the package toward something off-screen; his jaw tightens, breath visible in the cold rain. | Resolve becomes dread, but he does not run. | Performance must be micro-expression, not broad panic. |
| 5 | 12-15s | Deliver the suspense hook | A metal service door at the end of the alley lights up; the intercom wakes, and the courier stops just short of it. | Dread becomes irreversible activation. | End before showing who or what receives the package. |

## Causality

```text
Courier approaches forbidden alley
-> courier commits to delivery
-> package reacts before delivery is complete
-> courier understands the alley is responding
-> destination activates
```

## Beat QA

- The story has a beginning: courier at threshold.
- The story has escalation: package reacts.
- The story has a turn: destination is a responsive system, not a normal address.
- The story has an ending: door activation.
- The ending is unresolved but not empty; it opens the larger world.

## Constraints For Next Phase

- Do not add a second character yet.
- Do not explain the package with dialogue.
- Do not reveal the whole hidden network.
- Keep the final reveal simple enough for a 15-second video model test.
