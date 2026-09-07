# Image execution

Use for initial motion drawings or exact compiled image calls. Replace the shared
Delivery guide at this image step; reuse its authorization and completion limits.
The existing asset execution gate still applies.

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

## Transfer compiled data to the image tool

After the current execution packet passes, read the saved compiler result as
data; do not copy, shorten or retype its prompt. A board's compiled JSON is one
object; a production manifest stores each frame at `frames[].compiled`. Select
the intended frame in memory. Run Jingzao's `reference_delivery.py` on that same
spec for the current tool, inspect the actual references, and retain its result.
Use its resolved local paths. Conversation references require fresh window
confirmation immediately before submission.

For the current Codex tool, this host-side example reads a single compiled leaf
and that spec's latest reference delivery, then submits the exact string:

```javascript
// @exec: {"yield_time_ms": 120000}
const reads = await Promise.all([
  tools.exec_command({cmd: "cat '/absolute/project/compiled.json'", max_output_tokens: 14000}),
  tools.exec_command({cmd: "cat '/absolute/project/reference-delivery.json'", max_output_tokens: 4000})
]);
if (reads.some(r => r.exit_code !== 0)) throw new Error("compiled inputs unreadable");
const c = JSON.parse(reads[0].output), p = JSON.parse(reads[1].output).imagegen_call_plan;
const ids = c.attachments.filter(a => a.must_attach).map(a => a.input_id);
if (!['ready', 'approved'].includes(c.prompt_review.status) || p.status !== 'ready' ||
    JSON.stringify(ids) !== JSON.stringify(p.required_input_ids) ||
    !['none', 'referenced_image_paths', 'num_last_images_to_include'].includes(p.mechanism))
  throw new Error("current prompt/reference plan is not ready");
const args = {prompt: c.prompt, ...(p.mechanism === 'none' ? {} : {[p.mechanism]: p.argument})};
generatedImage(await tools.image_gen__imagegen(args));
```

Replace paths with the actual current artifacts. Truncated JSON fails parsing;
load it safely instead of supplying a summary. The tool accepts these prompt
and reference arguments, not Jingzao's whole `parameters` object. This transfer
does not grant authorization or visual approval; record the actual call/result.
