# Detailed Storyboard Coverage

Use for full/detailed preproduction, replacing the general craft reading.
Keep existing shot-card, asset-foundation and model-adapter owners. Infer the
stage from the deliverable; users need not name the sidecar or its craft steps.

## Plan before producing

After story/quality objectives stabilize, expand the existing asset plan into
shots, panels, setups, object states, audio and generation units. Keep stable
IDs, purpose, source, dependencies, scope, risk and acceptance. Planned is not
available. Use the existing attempt ledger; do not create another.

The design ladder is:

`story beat → scene geography → technical shot → action panel → unit reference strategy`

A cut/reverse gets its own shot ID; action phases within a continuous shot share
it but have distinct panel IDs. An overview cannot replace readable phase
coverage. A reviewed annotated reference can supply its bound unit panels.

## Determine the needed panels

Start from audience information, not counts. Declare needed preparation,
contact, change, reaction, outcome, exit or hold. Phases may cross shots;
do not require each phase in each shot. Dialogue needs speaker/listener, gaze
and meaningful interrupted action, not a cut/reaction for every line.

Use more image control for contact, ownership, reveals, direction changes,
multi-person blocking, transformations and pivotal expressions. Simple motion
may use fewer images plus start/path/end and performance notes. Model freedom
allows secondary movement, not invented story, people, objects or outcomes.

Make the narrative drawing and action phase readable first: pose, contact,
object change and camera relation. Short behavior notes and arrows may clarify
a line drawing for human review and, where supported, storyboard or motion
reference. They are guidance, never literal clean frames.
For required motion rehearsal, apply `storyboard-motion-planning.md` and produce
the actual model-generated drawings, colored annotations and legend before
downstream storyboard-reference or color-frame use.
Use `--phase planning` to check their bindings and recorded review; `design`
can pass while those drawings are still pending.

Use `master-shot-camera-planning` for coherent staging and
`professional-storyboard-director` for the board only when available and useful.
Neither authorizes generation or expands scope.

## Sidecar contract

`scripts/dircreative_storyboard_coverage.py` is a read-only supplementary checker
bound to existing shot cards. Its standalone `assets` check retains individual
image requirements. For `annotated_reference` units, use the pre-video gate with
the same coverage and actual `--prompt-ir`; that gate validates the alternative.

### Discover the input once, then author in a batch

When the coverage shape is unfamiliar, first read the checker-owned input
description once:

```bash
python3 scripts/dircreative_storyboard_coverage.py --describe-input
```

It reports the live allowed values and a minimum editable object skeleton from
the same constants used by validation. Use that shape to write the requirements
and panels together; do not turn it into a required lookup before every image
or revision. The command only prints JSON. It does not read a project, create
media, modify a plan, or count planned material as a real image.

`look_direction` records where the viewed subject looks on screen: `left` and
`right` mean screen left/right, `center` means no lateral screen look (for
example, facing camera), and `not_applicable` means gaze direction has no
meaningful application. A conventional eyeline reverse pair needs opposing
`left`/`right` values; a deliberate axis exception still needs
`axis_break_reason` and visual review.

```bash
python3 scripts/dircreative_storyboard_coverage.py validate /path/coverage.json \
  --project-root /path/project --phase design
python3 scripts/dircreative_storyboard_coverage.py validate /path/coverage.json \
  --project-root /path/project --phase assets --legacy-plan /path/project/visual-plan.json
```

The sidecar contains:

- `schema_version: "1.0"`, `project_id`, `frame_rate_fps`, `scope`, optional
  `aspect_ratio`, `shot_cards_file` and its canonical-JSON `shot_cards_sha256`.
- `requirements`: `requirement_id`, `source_anchor`, `kind`, allowed `shot_ids`,
  required `phases`, `risk`, `image_required`. High-risk work requires images.
  Anchors must be checked against the actual script by the author/reviewer;
  the checker cannot discover undeclared story requirements.
- `panels`: `panel_id`, `shot_id`, `requirement_id`, `phase`, absolute
  `at_seconds`, `state`, `camera_setup`, `view_subject`, `gaze_target`, `axis_id`,
  `axis_side`, `look_direction`, and `image` with `planned` or `available` status.
  Available images carry project-relative `path` and byte `sha256`.
- Optional `eyeline_pairs`: `panel_a`, `panel_b`, optional `axis_break_reason`.
  Conventional reverse pairs use distinct setups/shots, reciprocal gaze targets,
  opposite screen looks and the same side of the declared axis. A deliberate
  exception needs a creative reason and visual review, not a metadata shortcut.
- Motion drawings use separate `planning_image` and `motion_annotations` fields
  on the same panels. `motion_planning` binds boards and review; see the motion
  planning card. They never become production `image`; supported annotated units
  validate them separately through the pre-video gate.

`design` verifies declared phases, source binding, shot coverage, panel order and
declared eyeline relationships. `assets` also requires actual per-shot image
coverage and all additional required phase images. PNGs must be contained,
decodable, aspect-correct when specified and hash-matched. One unchanged image
cannot prove different states in the same shot. A planned image stays missing.
An individual-frame unit needs its actual representative images. These may
derive from accepted panels with recorded lineage. An annotated unit instead
needs its complete current board, reviewed panels and supported IR attachment.

Both sidecar and visual plan must bind the same cards, project and scope;
`--legacy-plan` checks this without granting `visual_assets_complete`.
The pre-video gate consumes `--storyboard-coverage`, plus current `--prompt-ir`
for annotated units. Inspect rendered actions, camera and gaze; a checker cannot
detect omitted story requirements or judge visual success. Record AI review as
AI, never human approval. Preserve all unresolved adoption errors.

## Panel dispatch and return

Use the existing `storyboard_frame_to_jingzao_v1` handoff when cinematic frame
compilation adds value. DIR supplies truth/intent, Jingzao compiles, imagegen
executes with authorization; do not duplicate those owners.

Bind each frame's `panel_context` to a frozen design sidecar: file/hash, panel
ID, phase, time and state. Set `frame_id=panel_id`; retain real `shot_id`.
For individual frames, dispatch same-shot panels in separate packets. Annotated
boards use the unit's styleboard handoff. Return images to their IDs in a new revision;
never overwrite the design receipt or fabricate extra shots.

## Bounded revisions

Show **shot/panel ID → change → protected facts → affected items → status**
with a thumbnail/file. Ordinary-language feedback needs no separate browser.
Reuse authorization. Use existing owners, not every specialist on every shot.
Return defects to the earliest responsible stage: unclear story, geography,
contact, image or model unit. Preserve successful assets; use the dependency
ledger to mark affected descendants stale. Dialogue changes can affect timing
and audio; local material fixes need not rebuild the film. Recompare the same
criterion and continuity neighbors. New source hashes need new bound revisions.

## Seedance 2.5 and 2.0

Keep one authoritative film and adapt the production grouping, not the story.
Use the current exact capability card for each version. A connected 2.5 dramatic
unit may contain several shots; 2.0 may split that unit at a natural event or
dialogue boundary. Keep actual beginning/end states and sound continuity.

Use the least ambiguous set of available identity, geography, state, composition,
motion or audio references. Reference limits are ceilings, not quotas. A panel
is not automatically a literal first frame; dense boards must never enter clean
frame slots. An explicitly supported storyboard reference needs an explicit role
and authorization. Planned audio/video is not an active reference.

Write action timing, body/prop response, gaze and exact dialogue separately;
name what may change and what stays fixed. Use native multi-shot/audio, extension
or local edit capabilities when they help the scene, verifying the actual product
surface before execution. Do not disable these abilities by a universal
one-short-clip-per-panel rule. This stage stops before video generation when
that is the user's boundary.
