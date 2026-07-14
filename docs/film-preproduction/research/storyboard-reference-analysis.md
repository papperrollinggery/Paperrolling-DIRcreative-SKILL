# Storyboard Reference Analysis

Verified: 2026-05-14

Purpose: define what a high-density storyboard/reference image pack should contain before prompts are generated.

## Target Reference Type

The target is not a 3x3 storyboard grid.

The target is a production board or reference bible sheet that combines:

- character identity and wardrobe,
- prop/product assets,
- environment and blocking,
- shot sequence,
- camera and lens notes,
- lighting/style notes,
- audio planning notes.

For complex projects, the correct output is a reference pack, not one overloaded image.

## Good Board Structure

### Single-page production board

Use when the sequence is short and simple.

Recommended layout:

```text
top bar: project title, duration, shot count, aspect ratio, palette, model target
section 1: character + prop reference
section 2: environment + blocking map
section 3: storyboard / shot strip
section 4: lighting / mood / audio / style notes
```

### Multi-image reference pack

Use when any of these are true:

- more than one important character,
- complex environment geography,
- product or prop continuity matters,
- more than 5-6 shots,
- video model needs clean reference images,
- single board would make panels too small.

Default pack:

```yaml
reference_pack:
  character_board:
    role: identity, wardrobe, expression, pose
  environment_blocking_board:
    role: location, camera path, subject path, spatial relation
  prop_product_board:
    role: object shape, material, detail, interaction
  director_storyboard_board:
    role: shot order, framing, camera movement, timing
  lighting_style_board:
    role: palette, lens texture, mood, post look
```

## Required Board Fields

| Field | Purpose | Minimum requirement |
| --- | --- | --- |
| Project header | Quickly identify sequence | title, duration, shot count, aspect ratio |
| Color palette | Lock style continuity | 4-6 swatches with labels |
| Character reference | Lock identity | front, side, back or 3/4, face close-up, key expression |
| Costume/material | Lock outfit | labeled fabric/material details |
| Prop reference | Lock important object | front, side/angle, macro, hand interaction |
| Environment hero | Lock location feel | one clear large frame |
| Blocking map | Lock geography | top-down map, subject path, camera positions |
| Shot strip | Lock sequence | shot ID, timecode, frame, action, camera |
| Lens/camera notes | Lock execution | shot size, focal length or lens type, camera motion |
| Audio plan | Lock sound policy | dialogue/VO/SFX/music/silence notes |
| Style notes | Lock visual mood | lighting, lens, texture, grading |

## Layout Rules

- Shot frames must be large enough for the video model to read the visual relationship.
- Tables must be readable by humans, but the video adapter must not rely on model OCR.
- Large decorative empty space is failure.
- Tiny panels that hide body/action are failure.
- Every section must have a role.
- Use short labels; do not write paragraphs inside the image.
- If text must be read, specify exact text and readable typography.

## Prompt Rules For Image Generation

Include these instructions in storyboard/reference board prompts:

```text
Create a clean high-density film production reference board.
Every panel must serve production information.
No decorative filler, no generic mood collage, no fake text.
All labels must be readable, short, and aligned.
Shot frames must be large enough to show action and blocking.
Use a professional white production-board layout with clear black section headers.
```

For video-model-safe boards:

```text
This board is meant as a planning reference for downstream video generation.
Keep each reference image/frame clear and large enough to be understood without relying on tiny text.
```

## Video Adapter Warning

Never pass a production board to a video model without this instruction:

```text
Use the storyboard/reference board only as production guidance.
Do not show or animate the board, panels, text labels, arrows, grids, or layout.
Generate the cinematic scene described by the shot list.
```

## Failure Taxonomy

| Failure | Cause | Fix |
| --- | --- | --- |
| Board animated as board | Adapter failed to block layout interpretation | Add anti-misread clause; use clean first-frame images instead |
| Character drift | Character reference too small or inconsistent | Split character board; add face/wardrobe locks |
| Space confusion | No blocking map | Add environment board with top-down path |
| Prop changes shape | Prop board missing macro and interaction views | Add prop/product board |
| Text unreadable | Too many labels or small type | Reduce text; move detail to manifest |
| Shot overload | Too many actions in one shot | Split shot or simplify action |
| Looks professional but unusable | Pretty layout with weak production data | Enforce field checklist |

## Sources

- StudioBinder shot list guide: https://www.studiobinder.com/blog/shot-list-template-free-download/
- StudioBinder storyboard camera movement: https://www.studiobinder.com/blog/storyboard-camera-movement/
- Google Veo prompt guide: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide
- Runway image-to-video prompting guide: https://academy.runwayml.com/guides/prompting-guide
