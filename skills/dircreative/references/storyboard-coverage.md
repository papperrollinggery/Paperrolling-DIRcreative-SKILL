# Detailed Storyboard Coverage

Use at the explicitly requested full/detailed preproduction stage, replacing the
general craft reading for that stage rather than stacking a new controller.
Preserve the existing shot-card, asset-foundation and model-adapter owners.

## Plan before producing

After story/quality objectives stabilize, expand the existing asset plan into
shots, panels, setups, object states, audio and generation units. Keep stable
IDs, purpose, source, dependencies, scope, risk and acceptance. Planned is not
available. Use the existing attempt ledger; do not create another.

The design ladder is:

`story beat → scene geography → technical shot → action panel → clean input → generation unit`

A cut/reverse gets its own shot ID; action phases within a continuous shot share
it but have distinct panel IDs. A scene hero or director-board page cannot
replace complete, readable individual action images.

## Determine the needed panels

Start from audience information, not counts. Declare needed preparation,
contact, change, reaction, outcome, exit or hold. Phases may cross shots;
do not require each phase in each shot. Dialogue needs speaker/listener, gaze
and meaningful interrupted action, not a cut/reaction for every line.

Use more image control for contact, ownership, reveals, direction changes,
multi-person blocking, transformations and pivotal expressions. Simple motion
may use fewer images plus start/path/end and performance notes. Model freedom
allows secondary movement, not invented story, people, objects or outcomes.

Use `master-shot-camera-planning` for coherent staging and
`professional-storyboard-director` for the board only when available and useful.
Neither authorizes generation or expands scope.

## Sidecar contract

`scripts/dircreative_storyboard_coverage.py` is a read-only supplementary checker.
It binds an existing JSON shot-card file; it does not replace or silently relax
the legacy one-representative-frame-per-shot visual plan.

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

`design` verifies declared phases, source binding, shot coverage, panel order and
declared eyeline relationships. `assets` also requires actual per-shot image
coverage and all additional required phase images. PNGs must be contained,
decodable, aspect-correct when specified and hash-matched. One unchanged image
cannot prove different states in the same shot. A planned image stays missing.

For detailed/full preproduction, require both this sidecar and the legacy visual
asset plan against the same shot-card identity before reporting combined visual
coverage. The legacy `visual_assets_complete` alone covers representatives, not
all action panels. Neither checker proves artistic quality or actual pixel gaze:
inspect the images and run the reference-effect comparison loop.

`--legacy-plan` checks both validators and the exact shared shot-card path/hash,
project and scope. It preserves the legacy completion claim and every adoption
error. A valid `plan_complete` plus panel assets is still not a trusted
`visual_assets_complete` claim. Review the requirement list against the actual
script for omitted actions; record AI review as AI, never human approval.

## Panel dispatch and return

Use the existing `storyboard_frame_to_jingzao_v1` handoff when cinematic frame
compilation adds value. DIR supplies truth/intent, Jingzao compiles, imagegen
executes with authorization; do not duplicate those owners.

Bind each frame's `panel_context` to a frozen design sidecar: file/hash, panel
ID, phase, time and state. Set `frame_id=panel_id`; retain real `shot_id`.
Dispatch panels sharing a shot in separate packets to preserve the legacy
one-frame-per-shot rule. Return images to the same IDs in a new assets revision;
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
