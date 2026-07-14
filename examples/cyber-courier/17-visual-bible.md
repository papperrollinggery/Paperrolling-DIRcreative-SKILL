# Cyber Courier Visual Bible

```yaml
artifact_id: cyber-courier-visual-bible-v1
version: 1.0.0
source_artifact_ids:
  - cyber-courier-shot-list-v1
  - cyber-courier-asset-requirements-v1
  - cyber-courier-shot-qa-v1
status: approved
owner_skill: visual-bible
created_at: 2026-05-14
locked_by_user: false
```

## Style Statement

Grounded cyber-noir suspense in a wet service alley: one red courier shape moving through blue-black rain, with a small red package pulse awakening a hidden mechanical address system.

The visual style should feel cinematic and production-designed, not generic cyberpunk decoration. Every light source, prop, sign, and panel must support geography, tension, or continuity.

## Palette

```yaml
primary:
  red_courier_jacket: "#C6212B"
  blue_black_rain: "#07111A"
  wet_asphalt: "#141A1F"
accent:
  scanner_red: "#FF2A2A"
  cyan_signage: "#3BC7FF"
  intercom_white: "#D8F2FF"
rules:
  - red belongs to courier, package scanner, and left-side sign family
  - cyan belongs to background sign and cold alley depth
  - warm practical light is minimal
  - do not introduce green, purple, or gold as dominant colors
```

## Character Lock

```yaml
character_id: courier_01
role: protagonist
identity_anchor: red waterproof jacket, black delivery bag, restrained fear
age_range: young adult
body_language:
  - shoulders slightly forward from rain and pressure
  - controlled steps
  - bag kept close to ribs
  - stillness after scanner pulse
expressions:
  - tired focus
  - threshold hesitation
  - controlled resolve
  - restrained dread
forbidden_changes:
  - no helmeted faceless biker look
  - no heavy armor
  - no exaggerated panic
  - no weapon
  - no second character double
```

Wardrobe:

- red waterproof courier jacket with visible rain beading and practical seams,
- black utility pants,
- black waterproof boots,
- optional small courier ID patch,
- no large brand logo.

Material rules:

- jacket reads as wet nylon shell,
- bag reads as wet black coated fabric,
- face and hair/hood edge interact softly with rain and neon,
- no plastic toy finish,
- no scale-like texture artifacts.

## Location Lock

```yaml
location_id: alley_01
role: single controllable environment
geography:
  entrance: public street edge behind courier
  axis: straight narrow path from entrance to destination door
  left_anchor: red sign near entrance
  depth_anchor: blue 24-hour sign deeper/right
  endpoint: sealed metal service door with intercom
weather: heavy rain
surface: wet reflective pavement
set_dressing:
  - exposed pipes
  - closed service panels
  - steam or vent haze
  - narrow walls
forbidden_changes:
  - no crowd
  - no open storefront
  - no wide city plaza
  - no door opening before final cut
```

## Prop Lock

```yaml
bag_01:
  role: carried concealment prop
  shape: compact black courier bag
  material: wet nylon or coated fabric
  state: closed or half-open for insert only

package_01:
  role: story trigger and hidden key
  shape: compact sealed matte-black hard parcel
  material: matte rigid surface, not glossy plastic
  state_off: dark and hidden inside bag
  state_on: thin red scanner pulse

terminal_01:
  role: optional address confirmation
  shape: small handheld device
  state: brief screen check only
```

## Lighting Rules

- Red sign motivates red reflections near entrance.
- Cyan-blue sign motivates cold depth and rim light.
- Scanner glow appears only after SH03.
- Intercom light appears only in SH05.
- Rain reflections should connect light sources to ground plane.
- Avoid unmotivated glowing UI clutter.

## Lens And Texture Rules

```yaml
lens_texture: grounded cinematic realism, restrained shallow depth of field
rain_texture: visible but not noisy
surface_integrity:
  avoid:
    - fish-scale texture
    - excessive sharpening
    - color speckles
    - cracked or collapsed surfaces
    - broken material continuity
```

## Continuity Rules

- Same courier face and body proportions across all references.
- Same jacket, bag, package, and alley geometry across every board.
- Package glow starts only after courier enters alley.
- Door panel activates but does not open.
- No recipient appears.
- No extra action beyond the five approved shot actions.

## Reference Pack Decision

Use a multi-image reference pack, not one overloaded board.

Reason:

- character identity, environment geography, prop state, shot sequence, and lighting style each need readable space,
- downstream video models need clean references rather than tiny panels,
- the prop state change and alley blocking are both continuity-critical.

Approved reference pack:

```text
image_01_character_board
image_02_environment_blocking_board
image_03_prop_board
image_04_director_storyboard_board
image_05_lighting_style_board
```

## Visual Bible Gate

```yaml
visual_bible_gate: pass
phase_f_can_proceed: true
missing_assets: []
drift_risks:
  - courier face drift if character board lacks close-up studies
  - alley geography drift if blocking map is too small
  - package shape drift if prop board lacks interaction view
  - board misread risk if video adapter omits anti-misread clause
```
