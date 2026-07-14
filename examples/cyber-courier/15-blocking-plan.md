# Cyber Courier Blocking Plan

```yaml
artifact_id: cyber-courier-blocking-plan-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-shot-list-v1
  - cyber-courier-camera-plan-v1
status: approved
owner_skill: shot-design
created_at: 2026-05-14
locked_by_user: false
```

## Spatial Map

```text
PUBLIC STREET / ALLEY ENTRANCE
  |
  |  red sign on left wall
  |
  |  wet alley corridor, pipes, service panels
  |
  |  blue "24小时" sign deeper/right
  |
  |  sealed metal door + intercom panel
DESTINATION
```

## Actor Path

```yaml
start: "alley mouth, left foreground"
path: "moves forward into the alley along the entrance-to-door axis"
stop_1: "mid-alley after package scanner pulse"
stop_2: "short of metal door after intercom activation"
end: "facing door, bag still in hand"
```

## Shot Blocking

### SH01

Courier stands at the threshold. His body is angled into the alley, but his hesitation keeps him from entering. Bag is held close to torso. He looks into the alley depth, then down or toward terminal if used.

Purpose: make the threshold readable.

### SH02

Courier crosses the threshold and moves away from camera. His walk is controlled, not a run. One hand tightens on bag strap as the red sign reflection passes across wet ground.

Purpose: make commitment readable.

### SH03

Bag opens enough to reveal the sealed package. Hands and bag edge can move slightly from walking momentum. Scanner glow begins here.

Purpose: make object state change readable.

### SH04

Courier stops. Head angle changes from package to far door. Jaw tightens. Body remains still. He does not step backward.

Purpose: make recognition and dread readable.

### SH05

Courier stands short of the destination door. The intercom panel activates. He remains still, holding the bag. Door does not open.

Purpose: make irreversible activation readable.

## Continuity Locks

- Red sign stays on the entrance-left side.
- Blue `24小时` sign stays deeper in the alley.
- Destination door stays at the far end.
- Package glow starts only in SH03.
- Courier does not run.
- No extra character enters.
- Door does not open.

## Shot Design Risks

| Risk | Prevention |
| --- | --- |
| Model adds attackers or a chase | Keep all shot actions single-subject and controlled. |
| Alley geography changes | Reference environment board must lock entrance, signs, path, and door. |
| Package changes shape | Prop board must define compact matte-black sealed object. |
| Courier emotion becomes exaggerated | Use restrained dread, micro-expression, stillness. |
| Final reveal becomes too large | Use intercom light activation only, no door opening. |
