# Generation and Delivery

Use for an already-designed active asset or client delivery. If a film still
needs story/shots, stay in Studio and apply `shot-development.md` first;
authorization does not replace craft or its pre-call packet.

Default to native files, inline previews, copyable text and a short index.
Reuse ledger data. A website, dashboard, workbench or local server requires an
actual requested web deliverable; routine browsing does not. Keep necessary
spatial/camera interaction in its existing focused viewer.

## Real generation

Before execution, resolve only the facts that can change safety or success:

- the exact provider surface and model/version from current official evidence;
- runtime tool availability and whether the current instruction authorizes use;
- each direct input's role, source, rights/consent, and provider restrictions;
- subject/product/character identity locks, preserve/change boundaries, output
  format, duration/aspect ratio, and falsifiable success criteria;
- desired audio versus native, reference, preserved, or postproduction route.

Resolve scope before the first media call:

- `whole_film`: load or derive the visual asset matrix and generate its required
  assets in dependency order: identity/product/prop locks, scene anchors,
  needed look evidence, the selected storyboard strategy, and required clean inputs;
- `sequence`: require the same coverage for the selected sequence only and name
  the excluded shots/scenes;
- `representative_sample`: generate only the explicitly bounded test assets and
  label the result `sample_visual_assets_complete`, never whole-film complete.

Bind images to their delivery profile; a TVC uses a landscape broadcast profile.
A 9:16 social variant does not validate TVC readiness. Use the client's master, safe-area, packshot, loudness and
caption requirements; do not invent a universal broadcast specification.

Cover every recurring identity, critical prop, scene, shot, required phase and
generation unit. The usual strategy uses individual `storyboard_frame` images
and a deterministic overview. A unit explicitly using `annotated_reference`
can instead use a reviewed native board or verified native-panel layout, with exact coverage and
a supported conditional `storyboard_motion` Prompt IR attachment. Verify its
actual bytes and upload mapping; it is never a literal clean frame. Other units
retain their own requirements. Split units at scene-anchor changes and preserve
their declared zero/one/multiple clean-input ranges.

An explicit “generate now” instruction can satisfy generation authorization. A
planning request, ambiguous “prepare,” or missing rights cannot. If blocked, ask
one question that names the exact missing authorization or input.

An adopted spatial arrangement can supply a current layout/staging reference
only after it is written to the existing scene/shot source and its affected
exports are refreshed. Viewing, switching cameras, or trying positions in a
discussion surface is presentation-only. “Adopt and generate a reference” uses
the same `generation_authorization` scope; a still-valid authorization for that
asset scope already satisfies it and must not be requested again.

Once authorized:

- First validate the canonical visual-plan JSON; CSV/Markdown never replaces it.
  Every image call needs a saved exact packet accepted by
  `dircreative_asset_execution_gate.py --execution-task-id <host task id>`.
  Standalone images use `asset_only` scope and `still` delivery: null time/rate
  fields, empty timelines, and no whole-film completion claim.
- Call an available compatible media tool now after the role-specific asset
  execution gate passes. A prompt, plan, preview, or
  “ready” state is not a generated result. If no compatible tool is available,
  return `TOOL_BLOCKED` or a clearly labeled external handoff.
- For a new sequence, establish required identity evidence before dependent
  frames; rough action planning need not await finished portraits. Continue by
  dependency layer, reusing current character/prop/scene/look truth. Inspect
  saved files and repair actual failed variables; independent ready assets may
  be generated together within the authorized scope.
- Dependency unlock needs the full visual manifest plus either host-registry
  signature or a separate Codex task's sealed request, image view and host claim;
  reviewer labels and self-hashes are insufficient.
- A headed character master needs the `character-master-sheet.md` Vision sidecar;
  prose review alone cannot unlock another asset.
- In an explicitly delegated test or smoke evaluation, choose the smallest
  representative assets and approve, reject, or retry them yourself. Continue
  without asking for test-only confirmation; test evidence is never client or
  production approval.
- Formal release/global-install forward tests additionally bind the exact request,
  prompt, references and outputs to a bounded host-log prefix, then use a separate
  image-view task. `unsigned_host_trace` is execution evidence, never visual approval.

For image execution, use `image-execution.md` for the current planning target and
exact compiled-data transfer. Retain the known authorization and completion
boundaries when replacing this shared guide.

## Completion evidence

`visual_assets_complete` is allowed only when every required matrix row has a
fully decodable canonical PNG inside the evidence root; scene, style, individual
storyboard and clean video-input frames match the delivery-profile aspect;
annotated reference canvases retain their reviewed drawing/annotation layout; its
file hash, normalized pixel hash, perceptual fingerprint, normalization profile,
and technical receipt match; and a separate role-specific visual-review manifest covers the exact
asset, truth and pixels. The plan validator never creates that manifest.
`reviewer_type`, reviewer IDs, task IDs, manifest hashes, and rehashed receipts inside
the plan remain untrusted payload claims; none can grant whole-film completion. The
standalone validator keeps `visual_assets_complete` fail-closed until the primary host
binds the review to a separate trusted adoption/readback context that the plan author
cannot mint; the current standalone CLI intentionally has no override for this gate.
Without that host evidence, report the visual plan and review as complete
at their bounded layers, but keep whole-film visual completion unverified.
JPEG/WebP may remain source or preview assets, but normalize them to canonical
PNG before they can become completion evidence.
`user_locked` and `reused_locked` remain workflow states and cannot bypass visual
review. Duplicate pixels are rejected unless explicitly inherited by a
`derive`/`reuse` asset. The inventory and approved shot-card hash, continuous
frame-aligned timecodes, complete per-shot creative truth, asset purpose/truth
hashes, scene and shot coverage, director-page dependencies, and model-specific
input ranges must remain exact. Technical stamping alone, prompt-ready,
previewed, or sample-only assets are not completion.
This visual contract has no `accepted` state: a final video/audio master,
loudness, subtitles, legal/rights checks, client approval, and broadcaster QC
belong to the delivery acceptance contract.

## Client-visible delivery

Deliver preparation materials as browsable files with an index. Create a ZIP only
when requested; software release/install archives follow their existing protocol.

Check the actual deliverable, not the whole archive:

- correct artifact, version, format, openability, and intended audience;
- approved facts/claims, names, copy, required scenes, and supplied exclusions;
- source/usage rights for visible image, video, music, voice, likeness, brand, and
  character material;
- continuity, legibility, crop/safe zones, and absence of internal workflow text;
- limitations expressed in client-readable production language.

Hash or version real inputs and outputs only when identity matters to the handoff.
Do not create hashes, receipts, records, or state files for hypothetical work.

For current spatial controls, read `spatial-discussion.md` and use its
`prepare-layout` path before the existing provider validation/compile.

## Scoped validation

The current artifact and its direct dependencies determine its result. Historical
assets, unrelated FinalDelivery folders, old control-plane records, and other
project debt may be listed as a separate project-level warning, but they cannot
turn an independent scoped pass into a failure. Never upgrade a scoped pass into
a claim that the whole project is send-ready.

Lead with the generated media, saved path and scoped QA status; otherwise lead
with the delivery decision or one blocker. Put compact evidence after it.
