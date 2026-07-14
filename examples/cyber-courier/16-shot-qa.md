# Cyber Courier Shot QA

```yaml
artifact_id: cyber-courier-shot-qa-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-shot-list-v1
  - cyber-courier-camera-plan-v1
  - cyber-courier-blocking-plan-v1
status: approved
owner_skill: shot-design
created_at: 2026-05-14
locked_by_user: false
```

## Shot Gate

```yaml
shot_gate: pass
phase_e_can_proceed: true
shot_count: 5
total_duration: 15s
overloaded_shots: []
missing_required_fields: []
```

## Required Field Audit

| Field | Status |
| --- | --- |
| duration | present on all shots |
| narrative purpose | present on all shots |
| shot size | present on all shots |
| camera angle | present on all shots |
| lens | present on all shots |
| camera motion | present on all shots |
| subject action | present on all shots |
| blocking | present on all shots |
| location layers | present on all shots |
| continuity locks | present on all shots |
| audio fields | present on all shots |
| model notes | present on all shots |

## Overload Check

Each shot has one primary action:

- SH01: threshold hesitation.
- SH02: forward entry.
- SH03: package scanner pulse.
- SH04: courier reaction.
- SH05: intercom activation.

No shot requires a chase, fight, second character, door opening, complex UI, or exposition.

## Continuity Check

Pass:

- Courier identity and red jacket stay fixed.
- Black delivery bag stays with courier.
- Package glow begins only in SH03.
- Alley axis remains entrance to door.
- Red sign and blue sign positions remain stable.
- Door activates only in final shot.
- No recipient appears.

## Model Risk Review

### Seedance

Risk: multi-shot flow may over-interpret the storyboard as a literal board later.

Mitigation: later video adapter must include reference map and anti-misread clause.

### Kling

Risk: if action prompts are too broad, model may add running, attackers, or door opening.

Mitigation: use subject movement, background movement, and camera movement per shot; keep actions minimal.

### Runway

Risk: long multi-shot prompt would be unreliable.

Mitigation: treat shots as separate image-to-video or short motion runs.

### Veo

Risk: audio can become overproduced if music is not explicitly excluded.

Mitigation: separate audio section; no dialogue, no voiceover, no music for MVP.

## Phase E Requirements

Visual bible and reference pack must lock:

- courier identity and wardrobe,
- alley geography,
- black bag and sealed package,
- scanner glow state,
- metal door/intercom,
- color and rain material behavior,
- board roles for character, environment, prop, storyboard, and style.

## Phase E Readiness

```yaml
next_phase: phase_e_visual_bible_reference_pack
required_outputs:
  - examples/cyber-courier/17-visual-bible.md
  - examples/cyber-courier/18-reference-pack-plan.yaml
  - examples/cyber-courier/19-image-layout-spec.md
phase_e_permission: proceed
```
