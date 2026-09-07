# Annotated motion storyboards

Use inside the existing panel-coverage stage when the developed story needs
contact, pursuit, changing geography, handoffs or other difficult physical
relationships, or the user requests annotated sketches. Infer this need from
the actual scene. The user does not have to request each step. Simple static
work can proceed without an action board.

Work from current shot/phase and camera plan → generate the annotated drawing
board → inspect and correct it → bind it to the supported downstream use.
Resolve hand/prop/state conflicts and source-correct force/support first. Give
each panel one visual job; use a same-phase detail when a wide view cannot prove
contact. A frame catalog cannot replace rehearsal. Make color frames only when
the selected delivery/input needs them.

## Draw and inspect

When the user supplies a tutorial or board prompt, inspect its actual prompt
and example frames. Carry forward its drawing/annotation grammar and downstream
reference use; unreadable source text stays uncertain. Compare adaptations on
the same events and references when needed, not by prompt length or resemblance
alone. Keep the more effective controls; do not transfer fixed panel counts,
sample characters, platform versions or claimed retry rates.

Select `--stage motion_board` with the original request and current shot cards.
When coverage exists, supply `--craft-coverage coverage.json` alongside
`--craft-source shot-cards.json --execution-project-root PROJECT`; declared
planning needs can activate this stage even without matching action keywords.
This uses the existing `cinematic_storyboard_frames` scenario with
`downstream_use: rough_planning`, without demanding finished identity/material
assets before a sketch can exist. Read the returned Jingzao provider and its
`references/styleboard-mode.md`; use its real validator/compiler and reference
delivery. Set `mode: styleboard`, `styleboard.presentation: line_art`; use
`sheet_direct` for an integrated board, or `hybrid` to repair failed cells.
Use `image-execution.md` for the planning target, execution packet and exact
compiled-data transfer. Selection or compilation alone does not generate a board.

For an annotated story/action board, the image model generates bodies, weight,
supports, contact, local hand/foot/head motion, arrows, short notes and legend
together. Draw people and scenery in sparse black/gray on white; annotation
colors carry meaning. In the chosen reference convention: red = subject/action
motion, blue = camera motion, green = composition/environment notes, orange = light direction,
purple = sound/emotion, black = panel IDs and shot captions. This is a declared
board convention, not a universal industry standard. Use only needed categories,
keep their meanings stable, and show one concise legend. Fixed cameras need no
invented movement. Arrow direction and endpoints must explain a visible subject
in this camera's image coordinates; world north is not always page-up. Sound
notes cannot stand in for unpictured action, nor labels for a missing grip.

The user's annotated-board choice overrides provider defaults that put all
production text outside generation or allow only one semantic accent. Encode
the actual labels, colors and roles in the existing spec; remove contradictory
"no text/arrows/color" clauses before compilation. Do not change the provider.
Identity/wardrobe/scene references retain their roles, never the reference camera.
Do not substitute grayscale photographs or program-drawn arrows for this method.

Preserve the original generated board. Inspect each actual cell against the
source before mapping IDs; do not infer grid position from shot numbers. Use
the existing assembler's `--extract-sheet SHEET --cell-map MAP --output-dir DIR
--receipt RECEIPT` when cells are needed. MAP contains `sheet_sha256` and ordered
`cells:[{panel_id,rect:[left,top,right,bottom]}]`, using source-pixel top-left
coordinates and half-open rectangles. Check gutters; never flip or stretch.
Cell count follows the story/layout. Preserve annotated reference canvases,
including notes; their aspect need not match video output. Check any explicitly
requested drawing format. Optional `frame_rect` names an actual drawn region,
never an invented rectangle to pass a ratio check.

## Same coverage, separate image duties

Keep production `panels[].image` unchanged. Add `planning_image` with `status`,
`presentation: line_art|hand_drawn`, project-relative PNG `path` and byte `sha256`.
For model-drawn notes, set `planning_image.annotation_source: model_generated`.
Record observed `motion_annotations` with `kind`, `subject`, `label`; coordinates
are not required. Kinds include `actor_path`, `action`, `camera`, `environment`,
`lighting`, `sound`, `emotion`. Bind their color meanings in
`motion_planning.legend` as `{kind:{color,label}}`. These declarations describe what was inspected; they
do not prove the pixels match. Preserve notes in cell crops; do not overlay again.

Declare `motion_planning.panel_ids` and its `reason`. Medium/high-risk action
requirements already imply drawing needs; other difficult requirements can set
`planning_required: true`. Planning never satisfies `panels.image`; an
`annotated_reference` unit validates its board in the supported reference role.

Bind the original board and extraction receipt in `motion_planning.boards` as
`{annotation_source:model_generated,panel_ids,image:{path,sha256},receipt:{path,sha256}}`.
Use `image-execution.md` for `--layout-only` placement of corrected native
panels and its provenance binding.
An explicit overlay request may instead use the existing `--coverage --panel-ids
--columns --output --receipt` assembly mode with normalized annotation points.
That optional operation must be reported as post-annotation. The existing
`--plan/--asset-id` color overview remains a separate late delivery.

Inspect the full board and magnified cells: picture/ID/phase correspondence,
local motion, contact/support, arrow target/direction, legend colors, readable
notes, light and sound intent, and neighboring geography. A label cannot rescue
a missing action. Use a bounded independent visual read for coupled/high-risk
action when delegation is available; repair the failed cells before advancing.
Record concrete observations. `motion_planning.review` carries `status: reviewed`,
`kind: ai|human`, its `path/sha256`, and `inputs_sha256` from
`motion_review_sha256(coverage)` (sources plus actual rendered pages); never label
AI observation as human acceptance. Replacing a page invalidates its old review.

Before downstream use, run coverage validation with `--phase planning`.
Missing drawings, boards or bound review keep that phase incomplete. Design
validation can pass before drawings exist, so this creates no circular startup
dependency. Structural validity still requires actual visual judgment.

## Bind the intended downstream use

For an entrance that supports storyboard/R2V, reuse `storyboard_motion`: bind the
actual annotated board, its reading order, relevant panel IDs and color legend
to the complete segment prompt. Explain that panels become successive full-frame
shots; notes/arrows guide motion and never appear as screen graphics. Character,
scene and style assets control final appearance. Verify the current entrance;
do not put a board in a literal first/last-frame slot.

Select this from the actual task/model strategy, without requiring the user to
name internal fields. Set that inventory unit's `storyboard_strategy` to
`annotated_reference`; its reviewed board replaces redundant individual-frame
and overview assets for that unit. Supply each actual unit Prompt IR to the
pre-video gate with `--prompt-ir`. It checks current board coverage/review,
supported conditional attachment and exact bytes. Other units and declared
clean-input minimums retain their requirements.

When a color narrative frame is required, the selected sketch is `camera_action`
or layout authority for view, pose and contact only. Exclude annotation colors,
text, sketch medium and identity from that authority. Inspect the actual result
against the board before extending the batch. A contact frame may depict a
middle event; it is not automatically a literal video first frame.
