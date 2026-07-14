# Cyber Courier Image Layout Spec

```yaml
artifact_id: cyber-courier-image-layout-spec-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-visual-bible-v1
  - cyber-courier-reference-pack-plan-v1
  - image-prompt-style-system
status: approved
owner_skill: visual-bible
created_at: 2026-05-14
locked_by_user: false
```

## Layout Policy

All reference images must use the project-wide art direction policy:

```text
Do not use a generic layout.
Do not use evenly distributed grids unless a technical sub-section requires it.
Do not make the layout symmetrical only for symmetry.
Composition must feel art-directed, intentional, and slightly asymmetric.
Every section must feel carefully placed, not automatically generated.
```

Technical grids are allowed only inside specific sub-sections:

- turnaround views,
- expression studies,
- shot strip,
- top-down blocking map.

The overall board must still have hierarchy.

## Canvas Rules

```yaml
default_aspect_ratio: "16:9"
minimum_readability:
  large_hero_panel: "at least 35% of board area"
  secondary_panel: "large enough to see body/action/material"
  text_label: "short, readable, exact words"
  map_markers: "large enough to distinguish path and camera position"
forbidden:
  - "tiny thumbnail contact sheet"
  - "decorative empty margins"
  - "unlabeled mood collage"
  - "fake text"
  - "overcrowded equal grid"
```

## Per-Image Layout

### image_01 Character Board

Hierarchy:

```text
large hero full-body pose
-> three support views
-> two face/expression studies
-> material callouts near jacket and bag
```

Readability:

- Full body must show red jacket, black pants, black bag.
- Face close-ups must be large enough to compare identity.
- Material labels must not cover the character.

### image_02 Environment Blocking Board

Hierarchy:

```text
large alley hero view
-> top-down blocking map
-> destination door detail
-> sign anchors and camera markers
```

Readability:

- The blocking map must clearly show entrance, path, red sign, blue sign, and door.
- Camera positions SH01-SH05 must be readable by humans.
- Video adapter must not rely on OCR; the manifest will restate these mappings.

### image_03 Prop Board

Hierarchy:

```text
large bag + package hero view
-> package off/on state strip
-> hand interaction detail
-> material and reflection details
```

Readability:

- Package shape must remain compact.
- Scanner pulse must be visible but not explosive.
- Bag material and wet surface must read naturally.

### image_04 Director Storyboard Board

Hierarchy:

```text
large SH01/SH05 geography anchors
-> ordered SH01-SH05 shot strip
-> duration/lens/camera notes
-> small audio plan box
```

Readability:

- Shot panels must be large enough to see action and blocking.
- Labels must use exact short text.
- Include a visible planning note: `REFERENCE BOARD ONLY`.

Risk:

- This board is most likely to be misread by video models.
- Phase G video prompts must explicitly say not to show or animate the board, panels, labels, arrows, grids, or layout.

### image_05 Lighting Style Board

Hierarchy:

```text
large mood frame
-> palette swatches
-> lighting source samples
-> material texture samples
-> surface integrity guard note
```

Readability:

- Swatches must be labeled.
- Rain texture must not become noisy.
- Include a small note: `NO FISH-SCALE TEXTURE`.

## Text Label Rules

- Use exact quoted text in Phase F prompts.
- Keep labels short.
- Avoid paragraphs inside images.
- Important production meaning must also live in manifest fields, not only image text.

## Surface Integrity Rules

Use `surface_integrity_guard` in Phase F for all five images:

```yaml
required:
  - clean natural materials
  - smooth and coherent surface texture
  - main subject remains clear
  - background depth layers remain distinct
  - complete object geometry
avoid:
  - fish-scale texture
  - excessive sharpening
  - color speckles
  - random noise
  - cracks
  - collapsed surfaces
  - distorted geometry
  - broken material continuity
```

## Phase F Hand-Off

The image prompt compiler must produce:

- one manifest mapping image IDs to downstream reference roles,
- one JSON-first style config per image,
- selected pattern IDs from `prompt-pattern-registry.json`,
- exact label text,
- targeted avoid list,
- anti-generic layout policy,
- surface integrity guard.

No real image generation is allowed in Phase F.
