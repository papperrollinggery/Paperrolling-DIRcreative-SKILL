# Image execution

Use for initial motion drawings or exact compiled image calls. Replace the shared
Delivery guide at this image step; reuse its authorization and completion limits.
The existing asset execution gate still applies. Prepare each call's current
arguments and register its actual saved output. Produce the independent batch
before one consolidated review; do not turn every saved image into an approval
stop. Use `execution.mode: batch_then_review` for this workflow (the legacy
`serial_review_gated` value remains readable). Calls sharing a plan still register
against its current revision; batch review does not require concurrent writes.
Only a defect affecting the next real input interrupts production. These helpers
do not intercept arbitrary raw host-tool calls or grant visual approval.

## New foundation assets

First derive the current inventory/plan and complete the selected initial design
pass. Recurring human identities each need their own character-master contract;
“related assets” does not mean one shared portrait or a pair of single views.
Keep single-portrait/poster work on its bounded image path.

Before the first call, resolve the visual design from the supplied references:
silhouette, materials, color ownership and the details needed by planned shots.
A reference reconstruction should preserve the reference's successful visual
solution; do not append unrelated costume or camera defaults. Keep a requested
five-view master complete. Remove duplicated instructions, not requested views,
design detail or quality. When a spatial/side-specific relation remains ambiguous,
use the existing constraint-input stage to provide a scoped layout reference;
do not keep appending corrective words or editing degraded pixels. Do not add a new user approval when the
brief and authorization are sufficient.

Prepare the original Jingzao spec with the current role **before** validating
and compiling it:

```text
python3 scripts/dircreative_visual_asset_jingzao_handoff.py prepare-role-spec --project-root PROJECT --visual-plan PLAN --asset-id C01 --spec source-spec.json --output role-spec.json
```

Use the returned spec for the installed Jingzao validator, compiler and reference
delivery. This inserts the canonical character/product/prop/scene/style contract
into actual compiler inputs while preserving the chosen medium, mode and ratio.
Reconcile other spec fields with that contract before generation. Check actual
source panel order, anatomical versus image left/right, numbered views, poses,
reference responsibilities and overlapping preserve/change instructions. The
compiler checks known clauses and exact conflicts, not visual semantics; a
`ready` receipt does not prove those judgments. Narrative
frames and temporary motion drawings keep their own existing compilation contracts.
A generic `ready` compile lacking the current role requirements cannot pass the
formal handoff. Do not patch its final prompt or invent a passed asset image.

For a reviewed failed foundation candidate, keep its current asset and use
`prepare-candidate-repair --project-root PROJECT --visual-plan PLAN
--expected-plan-sha256 HASH --asset-id C01 --spec SOURCE_SPEC --changes CHANGES
--output-spec REPAIR_SPEC --output-binding REPAIR_BINDING`. `CHANGES` is a JSON
array of `{ "check_id": "frontal_portrait", "instruction": "<observed correction>" }`
targeting failed observations. The preparer builds a compact delta spec and
removes create-time staging, subject poses, lighting and style instructions;
only the source, bound changes and custom preservation facts enter the repair.
use Jingzao's `source_matched` surface policy when existing texture is sound.
Compile the returned edit spec with the installed provider. Put its returned
`reference_asset` in the asset request and identical `candidate_repair` bindings
in the new handoff and packet. This candidate is the sole `base_edit_source`,
not an approved parent or a self-dependency. The current headed master keeps its
mode and truth; crop/pose repair does not become a headless or state derivative.

Keep the best-quality base, not automatically the latest output. After one
failed repair, do not recursively edit its result. Use the reviewed same-truth
best base via `--base-plan BASE_PLAN --expected-base-plan-sha256 BASE_HASH`, or
make a fresh candidate from corrected design/references. When returning to a
base, account for its known defects as well as the current candidate's defects.
Do not keep retrying while other requested work is missing: defer the bounded
defect and continue independent work, then address it in the batch review.

The native call here exposes text and attached images, not an explicit mask or
pixel-lock parameter. `Only change...`, coordinates and `protected` are requests,
not guarantees. Do not advertise unchanged pixels. If exact preservation is
needed, choose a supported regional-edit/compositing workflow, preserve the
original outside the changed area, and verify the actual result; do not invent
unsupported arguments. Do not improve a model's detector score by moving limbs,
stripping clothing detail or restyling a design the user already accepted.

## Existing foundation images

For supplied character, product, prop, scene or style PNGs that serve the current
asset role, declare `existing_sources` in the inventory:

```json
{"existing_sources":[{"asset_id":"scene-L01","relative_path":"references/L01.png","sha256":"<actual PNG hash>"}]}
```

Derive the plan with the existing `--inventory --output` command. It binds the
source and sets `action: reuse`; it does not claim a new generation, visual QA
or user acceptance. Use `--plan PLAN --stamp-evidence --asset-id ID` (repeat IDs)
to record only currently available files while future frames stay planned.
Technical stamping does not change lifecycle status or approve the image.
Record any later candidate/review state from the actual evidence; never use a
lock label to skip review. A reuse target is read back, not sent to imagegen.
An image that only guides a new design remains a reference, not that design's
completed canonical asset.

## Initial motion drawings

Use the current coverage design as the drawing target, including when the final
unit uses individual color frames. Resolve its fields without changing that
strategy or inventing completed parents:

```text
python3 scripts/dircreative_storyboard_coverage.py resolve-planning-target coverage.json --project-root PROJECT --visual-plan visual-plan.json --scope-asset director-storyboard-page-01 --panel-ids P01 P02
```

Freeze the input coverage revision; write generated-image bindings to a new
coverage revision so the submitted source remains replayable.
The scope asset is an existing source anchor. The returned temporary `asset`,
`dependencies` and `motion_planning` are derived from the current plan/cards/
coverage; do not add the temporary target to `visual_plan.assets`. Copy its
ID/role/truth into the existing execution packet and active JZ handoff. Preserve
`motion_planning` identically in both. In the JZ input request use the returned
purpose and `asset_foundation_pass: null`; the bound coverage supplies this
initial design evidence. Compile preparation can precede image authorization.

At actual execution, use `stage_contract.stage_id: motion_board` with this
package's motion-planning reference/hash. Bind the exact compiled prompt and
ordered real references through the existing JZ handoff. Keep dependencies in
their true planned states. Supply the original request, project/task identity
and `available_tools` from the actual host catalog to `select --stage
asset_execution`; for the currently available native tool that list includes
`image_gen.imagegen`. A missing declaration is not proof a host tool is absent.

Write generated drawings only to coverage's `planning_image` and bound board
records, then inspect them. This does not complete a formal page/frame or approve
parents. Formal individual frames still need their production handoff; supported
annotated-reference adoption still needs complete coverage, actual review,
appearance dependencies and the current Prompt IR/entrance checks.

## Lay out corrected native panels

When individual model-drawn panels are correct, retain them. The existing
assembler can place their complete annotated PNGs on one white page:

```text
python3 scripts/dircreative_storyboard_page_assembler.py --coverage coverage.json --panel-ids P01 P02 --columns 2 --layout-only --cell-size 512x460 --output board.png --receipt board-layout.json
```

Choose cell dimensions for the actual sources and readable notes. This mode
centers each image, preserving aspect and orientation, with downscaling only;
it does not draw people, arrows, captions or a legend. Originals remain intact.
For a legend already drawn on a selected panel's verified source sheet, use
`--legend-crop` with a JSON file containing
`{"panel_id":"P01","source":"source_sheet","rect":[left,top,right,bottom]}`. Inspect
the original and choose the actual legend rectangle; no inferred or new text.

The receipt binds the original files, their extraction evidence, placed
rectangles, recipe and output. Coverage re-renders that recipe to check the
pixels. Record the resulting board with
`acquisition: assembled_model_panels`; report it as document layout of native
model images, never as one new image-model generation. Inspect the assembled
page and bind a fresh motion review after placement. Provenance proves where
pixels came from, not whether an action or annotation is correct.

For supported annotated-reference delivery, set that inventory unit's
`storyboard_acquisition: assembled_model_panels` alongside
`storyboard_strategy: annotated_reference`, then derive its canonical plan.
Its board uses `action: assemble`; bind the actual layout output and receipt.
Do not send that assembly target to imagegen. Complete unit coverage, appearance
references, actual page review and exact Prompt IR image binding still apply.
The default native-board path and other units retain their own requirements.

## Selected image evidence

- Every direct image-tool candidate reaching `selected` binds a validated
  coverage panel/requirement hash in `execution_risk_binding`. Verified `low` or
  `medium` keeps the lightweight path; verified `high` additionally requires
  `execution_input_manifest`: exact prompt hash, ordered
  attachments, and structured scene/support revision bound to the handoff truth
  artifact/hash. The ledger reopens the validated packet and requires the actual
  prompt text/hash and normalized ordered inputs to equal its target frame entry.
  A production (`fixture_only:false`) packet also requires the explicit trusted
  `--handoff-provider-root`; the ledger forwards it into nested handoff
  validation rather than downgrading the packet to fixture mode.
  Required support binds unique subject and anchor inputs.
  Missing/false upstream risk, scene
  input, or ready parent blocks selection. Selection also needs a signed
  semantic truth review bound to output/truth hashes: scene pass, visible
  support, no forbidden background/ground contamination, and current parent
  states. A generic `accept` is insufficient. Legacy low-risk candidates remain
  compatible after their risk source is hash-bound; they need no scene/support
  manifest, spatial layout, or semantic truth review.

## Transfer current validated arguments and register the output

Freeze the current packet and use Jingzao's `reference_delivery.py` for that same
spec/tool. Inspect the actual local references. `--prepare-call` revalidates the
packet, source plan, compiler replay and ordered local attachments; it returns
one `imagegen_arguments` object. Pass it unchanged in the same host call. Current
canonical assets use local files; unresolved conversation references must first
follow their existing provenance/materialization path.
For a prepared same-asset repair, add `--retry-failed-asset` to `--prepare-call`.

This Codex example uses actual paths returned by the selected stage. `destination`
is a new candidate path within the plan's evidence root, and `nextPlan` is a new
revision beside `currentPlan`. Preserve the original generated file.

```javascript
// @exec: {"yield_time_ms": 120000}
const gate = "/absolute/current-package/scripts/dircreative_asset_execution_gate.py";
const project = "/absolute/project", task = "current-task-id";
const packet = project + "/packet.json", refs = project + "/reference-delivery.json";
const nextPlan = project + "/visual-plan-02.json";
const destination = project + "/candidates/C01-v01.png";
const quote = s => "'" + String(s).replaceAll("'", "'\\''") + "'";
const run = argv => tools.exec_command({cmd: argv.map(quote).join(" "), max_output_tokens: 16000});
const prepared = await run(["python3", gate, packet, "--project-root", project,
  "--prepare-call", "--reference-delivery", refs, "--execution-task-id", task]);
if (prepared.exit_code !== 0) throw new Error(prepared.output);
const call = JSON.parse(prepared.output);
if (call.preflight_status !== "ready" || !call.imagegen_arguments) throw new Error("asset call blocked");
const repairArgs = [];
if (call.candidate_repair) {
  const binding = project + "/C01-repair-call-binding.json"; // New path for this attempt.
  const saved = await run(["python3", "-c",
    "from pathlib import Path\nimport sys\nwith Path(sys.argv[1]).open('x') as f: f.write(sys.argv[2])",
    binding, JSON.stringify(call.candidate_repair)]);
  if (saved.exit_code !== 0) throw new Error(saved.output);
  repairArgs.push("--candidate-repair-binding", binding);
}
const result = await tools.image_gen__imagegen(call.imagegen_arguments);
generatedImage(result);
const match = String(result.output_hint || "").match(/\bas (\/[^\n]+\.png) by default\./);
if (!match) throw new Error("No exact saved PNG in the actual tool result; resolve before continuing");
const copy = await run(["python3", "-c",
  "from pathlib import Path\nimport shutil,sys\nsrc,dst=map(Path,sys.argv[1:])\ndst.parent.mkdir(parents=True,exist_ok=True)\nwith src.open('rb') as a, dst.open('xb') as b: shutil.copyfileobj(a,b)",
  match[1], destination]);
if (copy.exit_code !== 0) throw new Error(copy.output);
const recorded = await run(["python3", gate, "--project-root", project, "--record-output",
  "--plan", call.visual_plan_path, "--asset-id", call.asset_id, "--image", destination,
  "--expected-plan-sha256", call.visual_plan_sha256,
  "--execution-task-id", task, "--output", nextPlan, ...repairArgs]);
if (recorded.exit_code !== 0) throw new Error(recorded.output);
text(recorded.output);
```

The output-hint pattern is the currently observed native response, not a promise
of a stable path API. A missing/changed result or failed registration stops that
output's registration and dependent uses; do not guess the newest file or report
success. Resolve it without losing the real result, and continue unrelated work
whose inputs and current plan are valid.
Registration rechecks the exact prepared plan hash. If source truth changes while
generation runs, keep the real output but do not attach it to the changed truth;
review the change and reprepare the affected work.
The returned PNG dimensions describe saved pixels, not native detail gain.

## Review the completed batch before dependent use or final delivery

`--record-output` returns a blank `self_check_template` and records the real image
as `generated_candidate`, even when the picture is poor. Open that exact saved
PNG. Fill the returned observations from what is actually visible; do not prefill
`pass` from the prompt, existence, a preview thumbnail or a structural result.
Characters explicitly check the frontal portrait, front, left, right, back,
identity/scale and wardrobe side details. Other roles check their actual geometry,
state, camera/contact, source facts and intended medium. Compare repaired images
with both their source and the best earlier version: the requested fix must not
hide new identity, material or detail deterioration. A common `pass` sentence
copied over every observation is not a visual inspection.
Use the character visual probe at the character batch/dependency review, not as
a prerequisite to generate an unrelated asset. Its measurement cannot decide
style quality; inspect apparent false positives before prescribing any repair.

Save the completed template as an executor self-check manifest, then:

```text
python3 scripts/dircreative_asset_execution_gate.py --project-root PROJECT --check-output --plan visual-plan-02.json --asset-id C01 --self-check-manifest C01-self-check.json --output visual-plan-03.json
```

Use the returned plan revision for the next packet and carry it in the existing
project state. Old plan snapshots remain history, never a shortcut around a
pending/failed current candidate. Replacing that candidate requires its current
observations; unrelated pending candidates do not block the call. Actual parent
dependencies retain their readback and review requirements. A reviewed `retry`
may be repaired with `--retry-failed-asset` for that same asset. Changing task ID
does not erase failures or authorize unreviewed source use.

Self-check observations are explicit executor statements, not authenticated
proof that a host displayed the image. A successful self-check does not set
`visual_qa_approved`, independent QA, user adoption, or delivery completion.
Those retain their existing manifest/trust/readback checks. Temporary motion
images remain registered in coverage, as above, and receive their existing actual
picture review before their dependent use. Image failure affects the image state; it does
not rewind an already delivered prompt or occupy a new narrative unit ID.
