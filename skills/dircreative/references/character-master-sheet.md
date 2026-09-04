# Unified Character Master Sheet

Read this as the single task reference when the user asks to create, repair, or
audit a recurring character/costume asset sheet. It governs the `identity_state`
asset; it does not replace shot design, scene assets, prompt preflight, or media
generation authorization.

When requested independently of a film, use an `asset_only` inventory and the
selected pre-image foundation design stage. No screenplay, timed shots or
already-generated master is required to create the first master. Its identity,
appearance state, purpose and compilation route still bind the image request.

## One identity system, not competing character packs

All character sheets for one state share the same `asset_id`, `state_family`,
`state_id`, `asset_version`, descriptor, body-proportion lock, costume version,
and source-master hash. A derived sheet is another control surface for the same
character, not permission to redesign the face, body, hair, outfit, accessory,
or left/right placement.

Generate the headed master as one coherent image in one model pass from the
locked identity and wardrobe/body sources. Do not build the ordinary character
master by manually pasting a portrait beside separately rendered bodies. The
headless and detail sheets are each single derived generations from the approved
headed master. Deterministic compositing is reserved for verified exact logos,
emblems or text after the garment image exists, not for assembling face and body.

Identity and wardrobe/body may arrive as separate generation inputs. Bind their
paths, hashes, rights and roles as `planning_only` provenance through
`generation_input_reference_ids`; they never become co-active downstream video
references. A headed master accepts either one complete-character generation
input or the pair of identity plus wardrobe/body inputs. A headless-safe sheet
uses the approved headed master as its sole direct generation input.

Select one active master sheet per generation unit. Never submit headed and
headless master sheets together as equal identity references. A conditional
detail sheet may accompany the active master only for a shot where its detail is
actually visible.

## Mode selection

| Mode | Default | Use when | Active sheet |
| --- | --- | --- | --- |
| `headed_master` | yes | ordinary character creation, look development, continuity and most generation work | one headed master sheet |
| `headed_state` | no | a visible wet, damaged, injured, bloodied or wardrobe state must remain a local derivative of the approved base | one headed state sheet plus the supporting approved master hash |
| `headless_safe` | no | the user requests it, a target surface confuses small faces, or inspected outputs show multi-face/face-drift contamination | one headless sheet derived from the headed master |
| conditional detail sheet | only when triggered | asymmetry, signature accessory, logo/emblem/text, complex closure/pocket/hardware/lining/material, or planned macro detail | one detail sheet derived from the headed master |

Do not infer `headless_safe` merely because a character wears clothing. Default
to `headed_master`. Do not keep using headed mode after evidence shows that its
small full-body faces contaminate video; derive the bounded headless sheet and
re-test one variable.

## Headed state derivative

Use `headed_state` when the body remains headed but a visible state changes.
Keep one supporting approved base master and one canonical active state sheet.
The state sheet is a single derived generation whose `derived_from_reference_id`
and `approved_source_master_sha256` bind the exact base bytes. Its direct
generation input is that approved master only; historical identity/wardrobe
generation inputs do not travel into the state report. Preserve the same
portrait/body view coverage, horizontal layout and visual-review gate. A fresh
independent character redesign is not a state derivative.

## Headed master sheet contract

The headed master is one physical image on a neutral plain background with even,
soft lighting and no cinematic grade. Use a wide canvas. The default layout is
one horizontal row, never a 2x2 body grid: the dominant portrait sits at the far
left, followed by front, both side profiles, and back at equal body scale. Keep
front first and back last; either left/right profile order is valid when the
manifest records the physical order accurately. It contains:

1. one dominant, high-resolution three-quarter face close-up, framed from the
   crown to the base of the neck with only minimal shoulder context;
2. full-body front view, headed;
3. full-body left profile, headed;
4. full-body right profile, headed;
5. full-body back view, headed.

Both side profiles are mandatory. One generic side view cannot describe
left/right asymmetry. Keep all four full-body panels at identical scale, ground
line, camera height, relaxed A-pose, anatomy, body proportions, garment hem,
sleeve length, footwear, and lighting. The dominant face close-up owns fine identity;
the full-body panels own build, silhouette, wardrobe construction, side-specific
placement, and hair/body integration.

At the saved-file resolution, the portrait and every full-body subject must each
span at least 75% of the canvas height. Reject a sheet whose views exist but are
too small to inspect. This scale floor is a delivery gate, not an invitation to
upscale a weak board. Use the horizontal strip to preserve source pixels. Move
macro garment construction into the conditional detail sheet instead of
shrinking the master with more panels.

Immediately after saving a headed master, run
`python3 scripts/dircreative_character_master_visual_gate.py --image <png>
--asset-id <id> --asset-truth-sha256 <hash> --mode <headed_master|headed_state|headless_safe>`.
Headed modes must detect
one far-left close-up and exactly four separated full bodies to the right before
any `reviewed/pass` claim or downstream generation. A missing/unavailable probe
fails closed. Headless-safe checks one dominant left portrait, four plausible
full-height body components and zero detected faces in those slots, but remains
`applied_unverified`; only a separate human review signed by an authority in the
host trust registry can unlock it.
It also remains bound to the approved headed source hash. Bind the canonical
sidecar receipt to the plan; do not replace it with a written checklist. This structural measurement still cannot identify
front/left/right/back orientation, identity, garment material or side-specific
details, so the normal manifest-bound visual review remains mandatory.

Add portrait front/left/right close-ups only when planned profile close-ups,
prosthetics, hair asymmetry, or identity stress justify the extra pixels. Do not
mechanically turn every master into an eight-panel board if the main portrait
and four body views already cover the shot plan.

## Headless-safe sheet contract

The headless sheet must be derived from the approved headed master and remain one
physical image. Preserve the same layout, proportions, ground line, clothing,
accessories, footwear, and lighting. It contains:

1. one dominant three-quarter face close-up: the only readable face;
2. headless full-body front;
3. headless full-body left profile;
4. headless full-body right profile;
5. headless full-body back.

Remove the complete head from every full-body panel; do not leave a mannequin
head, tiny alternate face, portrait inset, mirror face, or second identity.
Retain the neck opening and garment construction without inventing a body.
Change only the head region: preserve both natural hands, wrists, fingers,
sleeve lengths and cuff-to-wrist boundaries in every body view. A handless body
or sleeve that swallows the hand fails the headless-safe gate.
Preserve the complete garment neckline: rear collar stand/band, inner back
neckline arc, collar points, facings, shoulder-to-neck seams and their continuous
connection around the absent neck. A scooped cutout, erased rear collar or
floating disconnected lapel fails even when the body is otherwise headless.

## Conditional garment/detail sheet

Create a separate detail sheet only if at least one detail changes continuity or
will be visible in a close shot:

- left/right asymmetry;
- removable or signature accessories;
- logo, emblem, patch, text, print, or placement graphic;
- pockets, closures, zippers, buttons, buckles, straps, cuffs, vents, or hardware;
- lining, interior construction, layered garment order, or unusual seam logic;
- directional material, weave, embroidery, reflective/metallic response, or a
  surface that must survive a macro shot.

The detail sheet is derived from the headed master and covers only named detail
IDs. Include the necessary front/back/left/right crop and enlarged callouts; do
not generate a new full body or another face. Each callout records placement and
what it must not control.

Logo, emblem, and text details require a verified exact graphic source. Do not
ask an image model to invent, redraw, spell, or approximate them. Composite the
approved graphic deterministically after the base garment exists, then bind the
result and exact source hash.

The v3 validator proves that an authorized exact-graphic source is bound to the
named detail. It does not prove that final composite pixels reproduce that source
faithfully. Placement, scale, color and pixel fidelity remain an explicit visual
review of the deterministic output.

## Density and reference balance

The master sheet protects identity, body and outfit in one coordinate system;
the detail sheet protects pixels for small construction features. Do not solve
missing detail by shrinking more panels into the master until faces, side seams,
hardware, or footwear are unreadable.

For the downstream call:

- ordinary shot: active master only;
- detail-visible shot: active master plus the matching detail sheet;
- multi-face failure: headless-safe master instead of headed master;
- state change: a versioned state sheet derived by a local edit from the same
  approved master, never an independent character redesign.

Resolve the target model's current reference limit from its exact capability
card. If references overflow, preserve identity/master first, then the visible
detail sheet, scene, critical prop, and composition according to actual shot
need. Never silently drop or merge roles.

## Prompt template: headed master

```text
Create one professional photorealistic character master sheet based strictly on
the approved identity and wardrobe facts. Neutral mid-gray seamless background,
soft even studio light, neutral expression, no cinematic grade, no text, no
labels, no watermark. One unified sheet: one dominant three-quarter face
close-up framed crown-to-neck at far left; then one horizontal row of four
full-body headed views at identical scale and ground line — Panel 1 front,
Panel 2 left profile, Panel 3 right profile, Panel 4 back. Every portrait and
body spans at least 75% of canvas height.
Left profile means the subject's anatomical left side is visible and the nose
points frame-left; right profile means the anatomical right side is visible and
the nose points frame-right. Panels 2 and 3 are not interchangeable or mirror
substitutes.

This template is a DIR source contract, not the formal image compiler. For a
Studio pre-video asset, route the locked facts through the installed
`jingzao-image-forge` visual spec and its prompt/reference preflight before the
host image adapter is called. Jingzao owns how asymmetric hardware, panel
visibility, references, local edits and material controls are expressed in the
model-facing prompt. A direct DIR prompt is only a rough-planning fallback and
cannot become a reviewed production master.
No 2x2 grid. Same person, exact body
proportions, hair, outfit construction, accessories, footwear and side-specific
placements in every panel. Use the approved pose lock exactly; do not append a
generic relaxed pose that conflicts with it. Accurate anatomy, complete
head-to-toe framing, clear silhouette. Do not add poses, props, costume variants,
carabiners, holsters, pouches, waist tools, dangling equipment or details not
present in the approved asset description.
```

## Prompt template: headless-safe derivative

```text
Using the approved headed master as the sole source of face, body and wardrobe
truth, create one derived headless-safe character sheet. Preserve identical body
proportions, outfit, left/right placements, footwear, scale, ground line and
neutral lighting. One dominant three-quarter face close-up is the only readable face.
It sits at far left, followed by a single horizontal row of four equal-height
full-body views — front, left profile, right profile, back — all fully headless
from the neck opening upward and each at least 75% of canvas height. No 2x2
grid, mannequin head, tiny face, missing hand, sleeve-covered hand, erased rear
collar, missing back neckline, scooped garment hole, disconnected lapel,
alternate portrait, mirror face or redesign. No text, labels or watermark.
```

## Prompt template: conditional detail sheet

```text
Create one garment/detail sheet derived strictly from the approved headed master.
Do not create another person, face or full-body design. Show only these named
details at readable scale: <detail IDs with front/back/left/right/interior
placement>. Preserve exact garment color, material, seam, hardware and placement.
For any logo, emblem or text, leave the deterministic insert region bound to the
provided exact graphic; do not redraw or invent it. Neutral light, no unrelated
objects, no extra details, no watermark.
```

## QA and stress gate

Before promotion, inspect the actual saved files and verify:

- the active master is one physical sheet;
- the required dominant three-quarter face close-up and front/left/right/back body views exist;
- the body views form one horizontal row with front first, both profiles in the
  middle and back last rather than a 2x2 grid;
- the portrait and each body span at least 75% of saved canvas height;
- scale, ground line, body proportions, garment lengths and footwear match;
- left/right details have not swapped or mirrored;
- every conditional detail ID has a readable callout;
- exact graphics come from verified source bytes;
- headless mode contains one readable face total and four fully headless bodies;
- headless mode preserves visible natural hands, wrists and cuff boundaries;
- headless mode preserves the rear collar, inner back neckline and collar-ring continuity;
- headed and headless sheets are not simultaneously active;
- target-light, FOV, group, occlusion/prop, state, handedness and topology tests
  pass with independent evidence before certification.

## Research basis

- HELL GRIND translated workflow: one board composed from a face close-up,
  headless front body and back body; dominant three-quarter face close-up preferred.
- Higgsfield's official AI short-film and character-sheet workflows generate a
  complete sheet directly from an identity reference and use full-body front,
  left profile, right profile and back plus portrait coverage:
  `https://higgsfield.ai/blog/ai-short-film-youtube-guide` and
  `https://higgsfield.ai/blog/ai-vs-vfx`.
- Runway Gen-4 References: neutral expression/even light; use a single clean
  reference when possible and mask an existing competing face to prevent confusion.
  `https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References`
- Scenario Character Model guidance: keep face, body proportions, signature
  clothing/accessories consistent while varying front/profile/three-quarter/back.
  `https://help.scenario.com/articles/4280773511-train-a-consistent-character-model`
- Raspberry Tech Pack: front/back/side are the useful garment views; trims,
  artwork and small construction features require detail callouts.
  `https://www.raspberry.ai/help-docs/user-guide/presentation/tech-pack`

The single horizontal row and 75% height floor are DIRcreative delivery rules,
not claims that those sources publish the same numeric standard. They follow
saved-pixel geometry and the v0.7.0 visual forward test: a 2x2 body grid limits
each body to roughly half-height, while a horizontal turnaround keeps every body
near full height. The threshold is deliberately local, inspectable and covered
by a negative regression case.
