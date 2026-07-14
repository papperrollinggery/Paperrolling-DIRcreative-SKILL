# Cyber Courier Asset Requirements

```yaml
artifact_id: cyber-courier-asset-requirements-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-script-v1
  - cyber-courier-script-breakdown-v1
status: approved
owner_skill: script-breakdown
created_at: 2026-05-14
locked_by_user: false
```

## Required Assets

### Character

```yaml
character_id: courier_01
asset_role: protagonist identity lock
must_define:
  - face identity
  - body proportions
  - red waterproof courier jacket
  - black utility pants
  - black delivery bag handling
  - restrained fear performance range
used_by_later_phases:
  - visual bible
  - character design board
  - shot list continuity
  - video reference map
```

Quality bar:

- Readable silhouette in rain.
- Red jacket remains the identity anchor.
- Expression range supports tired focus, hesitation, and restrained dread.

### Location

```yaml
location_id: alley_01
asset_role: environment and blocking lock
must_define:
  - alley entrance
  - path into depth
  - red sign on left
  - blue 24-hour sign deeper in frame
  - wet reflective pavement
  - pipes and service panels
  - sealed metal destination door
  - intercom panel
used_by_later_phases:
  - environment blocking board
  - camera plan
  - shot list
  - video reference map
```

Quality bar:

- Geography must stay coherent across shots.
- Final door must be visible as the destination before activation.
- Signs should support composition; they must not become fake narrative text.

### Props

```yaml
prop_id: bag_01
asset_role: carry object and concealment
must_define:
  - black wet nylon material
  - strap
  - size against courier body
  - opening angle for reveal

prop_id: package_01
asset_role: story trigger
must_define:
  - compact matte-black sealed object
  - red scanner seal
  - glow state off/on
  - reflection behavior on wet ground

prop_id: terminal_01
asset_role: optional address confirmation
must_define:
  - small wet black handheld terminal
  - minimal screen glow
```

Quality bar:

- Package cannot visually drift into a large suitcase, weapon, or food-delivery box.
- Scanner glow must be subtle and mechanical.
- The terminal is optional and should not distract from the package.

### Wardrobe And Material

```yaml
wardrobe:
  red_waterproof_jacket:
    material: rain-wet nylon shell
    function: identity color anchor
  black_utility_pants:
    material: dark work fabric
    function: practical courier silhouette
  black_work_boots:
    material: waterproof leather or rubberized work boot
    function: grounded movement through puddles
```

Quality bar:

- Rain interaction must be visible.
- No plastic toy look.
- Fabric seams, folds, and wet highlights should be consistent.

### VFX / Practical Light

```yaml
vfx:
  scanner_glow:
    color: red
    source: package seal
    timing: object reveal onward
  intercom_activation:
    color: cold white or red-white
    source: door panel
    timing: final beat
```

Quality bar:

- Glow sources must have plausible reflections.
- Effects must not overpower the courier or alley.
- The alley activates mechanically, not organically.

## Assets Not Needed In MVP

- Visible recipient.
- Second courier or future self.
- Vehicles.
- Weapons.
- Crowd extras.
- Logo or brand identity.
- Complex holographic UI.

## Phase D Hand-Off

The shot design phase should treat these as fixed story assets:

- `courier_01`
- `alley_01`
- `bag_01`
- `package_01`
- `scanner_glow_01`
- `intercom_activation_01`

Shot design may decide exact framing and timing, but should not add new major assets unless required for continuity.
