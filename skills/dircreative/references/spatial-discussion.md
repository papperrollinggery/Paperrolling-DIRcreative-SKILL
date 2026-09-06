# Spatial discussion and reference production

Use for scene geography, blocking, eyelines, reverse shots and movement. Keep the
current requested scope: viewing a layout does not start a whole-film pipeline;
a full preproduction request continues through its authorized deliverables.

## Run the existing route

The existing natural-language route returns `spatial_discussion` under
`film_development`. Read the current host Visualize contract and the normative
`docs/film-preproduction/chat-inline-visualization-interface.md`. Build the scene
from current scene/shot facts and sources. For a design from zero, use labeled
design assumptions; for an existing environment image, inspect it and distinguish
observed geometry from inferred/offscreen areas before planning cameras.

Use the existing scene artifact as owner. For an overhead-only discussion, keep
positions, orientation if needed, room anchors and paths; cameras, human heights
and an explicit relationship axis are optional. Add camera/projection detail
only when a real space risk needs it: multi-person blocking, reverse, eyeline,
handoff, path or occlusion. A readable narrative storyboard and action phase
remain primary; an overhead diagram is not required for every shot.
The helper consumes one JSON snapshot
with `scene_id`, `revision`, `coordinate_system: normalized_xy_design`, room
features, entity IDs/asset IDs/positions/facing/gaze/support, optional paths and
transfers, a relationship axis, and cameras carrying canonical `shot_id` values.
Use unique `order` values on every path/transfer when movements and handoffs
interleave. Each `path-N` or `transfer-N` view replays events up to that point;
`final` includes all. Legacy records without order retain transfers-then-paths
behavior. Mark solid furniture `blocks_movement: true`; paths may stow a held
prop through `stow_prop_ids`. A held prop follows its owner and stops appearing
when stowed. Recheck shot prose and audio after revising geometry or prop state;
new hashes alone do not repair old screen directions or sounds of removed props.
`examples/spatial-dialogue/scene.json` is a small **designed test scene**, not a
required template or an identity-asset pack. Coordinates and FOV are design
intent. Add detail only when needed; complex contact or perspective can require
pose/animatic/white-model references and visual inspection.

A constructible scene needs `scene_id`, advancing `revision`, `description`,
`coordinate_system: normalized_xy_design`, `room.features`, `entities`, and
`paths`/`transfers` arrays (which may be empty); cameras are optional for an
overhead-only discussion. A moving character's path has `entity_id`, ordered
2D `points` beginning at that character's position at its event turn, a readable
`trigger`, and unique `order`. A transfer has `prop_id`, `from_holder`,
`to_holder`, a 3D contact `position`, `trigger`, `to_hand`, and unique `order`;
the prop's initial `holder` must match the first transfer's `from_holder`.
Event order is shared across paths and transfers, so a person who must clear a
doorway moves before another arrives. Use `crossing_reason` on a camera only
for an intentional axis crossing and state the narrative reason. See
`examples/spatial-dialogue/three-person-handoff.json` for a runnable handoff
and clearance example.

```text
python3 scripts/dircreative_spatial_scene.py view --scene <active-project/scene.json> --project-root <active-project> --output <absolute-task-owned/blocking-camera.html>
```

The helper validates the scene, then uses the existing visualization schema and
renderer. Include the result through the current host's response-content
contract in this reply. It is incomplete to deliver only the path or an offline
preview. If no host display is available, give the helper's complete readable
fallback. Do not fabricate a mount receipt or wait indefinitely for readback.

The initial view is presentation-only. Camera and action-phase selection affects
both diagrams, never the adopted scene. The controller receives a user's adoption
from chat or the host follow-up mechanism and uses the existing writeback checks.
A same-scope authorization remains effective after adopting the layout; avoid
asking for it again. A user merely viewing a scene has not requested generation.

## Derive usable controls

After adoption, export the relevant current camera and visible state:

```text
python3 scripts/dircreative_spatial_scene.py export --scene <active-project/scene.json> --project-root <active-project> --shot <canonical-shot-id> --phase initial --output-dir <active-project/references>
```

SVG/PNG and a binding JSON come from the same geometry as the discussion view.
The PNG uses sparse colored outlines, no labels or UI. Pillow is required only
for PNG export; missing Pillow does not block discussion/SVG or other work.
The sidecar binds source bytes, revision, shot, phase, image bytes, color-to-entity
roles and continuity. These are actual deterministic control references, not
model-generated cinematic frames or evidence of media quality.
Because a static layout export contains no motion pixels, it is staging only.
It cannot be called or bound as motion reference because the discussion view
showed a path; use a phase sequence, motion control or supported storyboard
reference when movement must be consumed.

`validate_export` re-reads the current scene and files. A changed scene makes the
old export fail as stale even if its PNG still exists. For a local path change,
`revise_path` returns a new revision changing only that entity's path. The
helper retains its event order, final facing and stow settings; when that actor
has multiple paths, select the current source's `path-N` via `path_id` rather
than replacing all its moves. Recheck later dependent start points after a
selected endpoint changes. The
controller writes the adopted revision, marks affected downstream work stale,
and regenerates its controls and prompt bindings. Preserve other identities and
fixed geometry. Do not mirror a reverse shot or move people to fake its screen
projection.

## Consume, then deliver

Pass the export JSON as a hash-bound `spatial_source` to existing Jingzao and
video-prompt consumers. `attach_spatial_layout` in
`scripts/dircreative_visual_asset_jingzao_handoff.py` appends the actual PNG to a
Jingzao spec with `role: layout`, `source_kind: local_path` and `must_attach: true`.
It preserves the craft spec and binds the color responsibilities. Read and use
the installed provider's actual compiler; matching a Skill name/hash is not use.
The storyboard handoff checks the same current source, layout image and role.

Use the existing Prompt IR and compiler for the target video model. Resolve each
actual upload in explicit order, retain each primary job and match the binding
text to that order. A layout has `layout_reference` role, never `clean_first_frame`
or `clean_end_frame`; an I2V entry without a separate control slot needs a real
clean frame first. Unknown or unverified entry capabilities remain unresolved.
Identity/scene/prop assets still own appearance and environment truth. A layout
cannot substitute for them or silently grant whole-film visual completion.

Deliver current controls, any requested real assets/frames, actual upload order,
entry settings and the complete copyable prompt in the visible reply. Check
missing references, source revisions, dialogue, action capacity and neighboring
states internally. State concrete missing assets and affected units when the
requested full package is incomplete; do not call a compile-only example ready
for video submission.

## 空间布局派生输入

空间讨论导出的 PNG 只能作为当前站位、姿态、尺度、遮挡与机位侧的参考，不能接管人物身份、道具身份、材质或最终风格。先从当前场景导出，再派生新的 Jingzao spec 与可插入 `reference_assets` 的记录；这一步不回写 foundation 或 sealed handoff：

```sh
python3 scripts/dircreative_spatial_scene.py export --project-root ROOT --scene ROOT/spatial/scene.json --output-dir ROOT/spatial/exports --shot S01 --phase initial
python3 scripts/dircreative_visual_asset_jingzao_handoff.py prepare-layout --project-root ROOT --spec ROOT/visual-spec.json --export ROOT/spatial/exports/SCENE-S01-initial-REVISION.json --output-spec ROOT/prepared/layout-visual-spec.json --output-reference ROOT/prepared/layout-reference.json
```

把 `layout-reference.json` 原样加入 handoff input spec 的 `reference_assets`，以 `layout-visual-spec.json` 更新其 `output_spec.visual_generation_spec` binding。随后使用 handoff 已绑定的真实 Jingzao provider 重跑 validate/compile，并用新的 receipt、compiled manifest 和 prompt hash 更新 handoff；这仍只是编译和附件准备，不代表媒体已生成或验收。
