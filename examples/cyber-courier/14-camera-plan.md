# Cyber Courier Camera Plan

```yaml
artifact_id: cyber-courier-camera-plan-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-shot-list-v1
  - cyber-courier-script-breakdown-v1
status: approved
owner_skill: shot-design
created_at: 2026-05-14
locked_by_user: false
```

## Camera Strategy

The sequence uses a simple threshold-to-depth camera grammar:

```text
static wide threshold
-> slow tracking commitment
-> static macro reveal
-> close reaction push-in
-> locked-off final activation
```

This keeps the 15-second test readable and gives each shot one visual job.

## Lens Progression

| Shot | Lens | Reason |
| --- | --- | --- |
| SH01 | 24mm | Establish alley geography and forbidden threshold. |
| SH02 | 35mm | Follow the courier without losing environment. |
| SH03 | 90mm macro | Make the package seal readable and tactile. |
| SH04 | 50mm | Read micro-expression without flattening the face. |
| SH05 | 35mm | Reconnect courier, door, and puddle reflection in one space. |

## Camera Movement Rules

- SH01 locked-off: geography first.
- SH02 slow tracking: commitment into the alley.
- SH03 static macro: object information must be clear.
- SH04 subtle dolly in: psychological pressure.
- SH05 locked-off: the world activates around the still courier.

Avoid handheld shake in MVP. It would add urgency but reduce continuity reliability for model tests.

## Axis And Screen Direction

```yaml
primary_axis: "alley entrance to destination door"
camera_side: "street-left side of the alley axis"
screen_direction:
  SH01: "courier faces from left foreground into center/background"
  SH02: "courier moves away from camera into depth"
  SH03: "object insert preserves bag orientation from SH02"
  SH04: "eyeline moves from package to far door"
  SH05: "courier faces door; camera confirms path depth"
axis_breaks_allowed: false
```

## Lighting And Exposure

```yaml
base: "blue-black rainy night"
key_motivations:
  - red sign on left
  - cold cyan blue sign deeper in alley
  - red package scanner pulse after SH03
  - intercom panel glow in SH05
exposure_priority:
  - courier red jacket silhouette
  - wet pavement reflections
  - package scanner seal
  - final door/intercom panel
```

## Model Reliability Notes

- For Seedance, the camera plan should be expressed as a chronological shot flow.
- For Kling, split each shot into subject movement, background movement, and camera movement.
- For Runway, keep each image-to-video run simple and motion-focused.
- For Veo, the camera plan can be included in structured cinematic language with audio kept separate.

## Hand-Off To Blocking

Camera and blocking must preserve:

- entrance-to-door geography,
- courier movement into depth,
- package glow beginning only in SH03,
- courier stopping before door,
- door activation without opening.
