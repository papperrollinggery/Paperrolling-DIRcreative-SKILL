# Shot Development and Craft Handoffs

Use at technical shot development. Keep bounded
edits on `shot-storyboard.md`. Select only the stages the actual script needs.

## Activate craft as the film develops

Infer the required stages from the requested result and the developed script.
“Make the short and real images; I will generate the video” means full
preproduction without naming each craft stage. It defers the video call.
The router's `craft_stages` describes pending work, not provider execution.
Reassess concrete gaps after writing the script.

| Active stage / condition | Existing craft to apply | Usable result before continuing |
| --- | --- | --- |
| Technical shot design | This shot contract; select `shot_information` or `technical_storyboard` for a demonstrated gap | Motivated cuts, viewer positions, action phases and camera decisions |
| Combat, pursuit or physical interaction drives a sequence | `action_choreography`; `vfx_design` only when designed effects need construction | Force/contact/reaction chain and environment consequences at the intended intensity |
| Blocking, travel, reverse coverage, handoff or occlusion changes the view | `master_camera` and the relevant `spatial-discussion.md` method | Constructible geography, actor paths and distinct shot/phase camera setups |
| Full image preparation | `storyboard-coverage.md`; needed `motion_board` rehearsal; supported annotated references or required cinematic frames | Reviewed panel design, actual motion drawings when needed, then the selected Jingzao prompt handoff |

Follow dependency order within existing budgets. When selection returns
`before_image_submission`, complete that existing stage before resuming;
do not skip required motion planning or bypass a blocked handoff with a raw
image prompt. Replace references by stage and retain current shot/scene decisions.

Select one current stage, read its task output and provider, produce/review its
artifact, then select the next. The task view shows prior work first; use JSON
for a complete machine receipt. Reading a future stage does not complete it.

```text
python3 scripts/dircreative_skill_stack.py select --stage action --format task --request '<original request>'
```

Use `shot_design`, `action`, `camera_geography`, `environment_effects`, or
`panel_coverage`, `motion_board`, or `frame_compile` only when applicable. After story development, add
`--craft-source <current shot-cards.json> --execution-project-root <project>`
so selection considers the actual action and space, not only brief keywords.
Omit `--root` in ordinary use, including when running a candidate DIR package:
its package path chooses the controller version, not the provider search scope.
The CLI finds the configured Codex Skill directory. Change `--root` or `--catalog`
only for an explicitly scoped provider catalog; those overrides are authoritative.
Source text cannot authorize media or expand scope. `--intent` may supply the
existing stage's asset/spec inputs, but cannot replace its scenario or grant a
side effect. For narrative frames consume the actual Jingzao compiler output;
a selector receipt alone does not mean its method was applied.
For an authorized image call, `--stage asset_execution --intent <active inputs>`
derives the Delivery context from the same original request. Supply the existing
exact asset packet and `available_tools` from the actual host catalog; its gates apply. This transition
does not authorize video, replace the prompt, or request permission again.
Pass saved compiled JSON as data using the short example in `image-execution.md`.

For complex contact or changing geography, apply `storyboard-motion-planning.md`:
generate the action drawings, semantic-color arrows, notes and legend together;
inspect actual pictures before downstream use. Bind the same coverage IDs to
supported storyboard references or required color frames. Other scenes can use
simpler planning. Keep chosen first frames distinct
from the strongest storyboard phase; preparation cannot prove contact/aftermath.

Review what each cut reveals before extending the image batch. Repeated setups
need a story reason, not different lens labels. A literal first frame may precede
contact; retain the decisive contact/consequence when it matters. One main action
is a coherent event with force, response and changed state, not timid motion.
Preserve calm beats. Fix a systemic camera/reference error before its descendants.

## The shot contract

Keep canonical shot ID and timecode, narrative purpose, observable start/action/end,
blocking path and eyeline, motivated camera position/height/direction and lens,
foreground/midground/background jobs, sound/edit bridge and continuity state.
For cinematic frames, preserve viewer task and position, dominant/secondary read,
frozen phase, action vector/counterforce, crop pressure, parallax/occlusion,
exaggeration with a protected anchor and a quiet region. Calm frames use concrete
not-applicable reasons for dynamic fields. The existing Jingzao handoff owns the
structured frame contract and compilation; do not recreate that compiler here.

Separate world-space anchors and light sources from each camera's screen
projection. Build unseen reverse space as a design assumption, then use the
current actor/prop state for the target shot. Scene appearance references must
not freeze every later camera, screen side or damage state. Carry force-driven
deformation, fracture, spray and aftermath into the spec; clean inputs remove
overlays and accidental artifacts while retaining those motivated events.

## Carry craft into generation

Before the first narrative-frame call in full preproduction, apply the current
shot-design and storyboard-coverage stage. Carry the selected
`cinematic_storyboard_frames` craft through the actual Jingzao spec/compile
handoff. A missing review/capability blocks its dependent claim/action. Continue
independent design, provider reading and compilation; report the blocked step.

Set both `direction.deliverable` and `cinematic.profile` to
`narrative_film_frame`. Use `dircreative_narrative_spec_preflight.py` before
consuming the compiled prompt: pass `--project-root <project>` and the relative
spec path. It enables Jingzao's existing narrative checks.
A generic template's successful compilation is insufficient. Its length/reference
`approved` status does not review story, physics or cinematography.

Resolve the current frame from the canonical source before filling its spec:
each visible actor gets that actor's action; trace critical prop custody and
light/damage state across adjacent shots; derive foreground/background and light
direction from this camera. Keep offscreen cast out of `subjects`. Reconcile all
template fields with the resolved state, including `setting`, `lighting.key`,
practicals, tone locks, depth roles and reference descriptions. Do not append
generic continuity reminders to pass length checks or leave alternatives such as
“as the shot requires.” Defaults such as restrained dynamics or clean-reset
rendering need a shot reason and cannot erase the chosen action intensity.

For coupled contact, handoffs or reverse coverage, obtain a bounded independent
read of the current source cards and actual compiled prompts before the image
batch when delegation is available. Fix source contradictions first, then
recompile affected specs. Use this semantic review to catch mismatched actors,
unexplained custody changes and stale camera/light fields; schema PASS cannot.
If independent review is unavailable, disclose that limit and still perform the
comparison; never invent a review receipt.

- For storyboard/clean-frame candidates, compare the actual view with the shot's
  camera and phase, then inspect neighboring frames as a sequence. Record
  concrete visible evidence in the existing review notes for viewpoint/depth,
  contact and counterforce when relevant, environment response and persistent
  state. Generic face/hand/texture checks cannot certify action cinematography.
  Treat clean inputs as free of overlays and accidental artifacts; preserve
  intended motion cues, material damage, spray and physically sourced particles.
  Repair a repeated background/composition error upstream before further frames.
