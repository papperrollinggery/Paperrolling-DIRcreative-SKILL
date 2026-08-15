# Generation and Delivery

Use this card only when the user is about to generate, hand off a formal asset, or
make work client-visible. Keep the creative result visible while adding the
minimum evidence the action requires.

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
  optional non-redundant look board, per-shot storyboard frames, director
  storyboard pages, then clean generation-unit inputs;
- `sequence`: require the same coverage for the selected sequence only and name
  the excluded shots/scenes;
- `representative_sample`: generate only the explicitly bounded test assets and
  label the result `sample_visual_assets_complete`, never whole-film complete.

Bind every generated image to the current delivery profile. A TVC test uses a
landscape broadcast profile and its safe-area/packshot constraints; a 9:16
social image set is a channel variant and cannot validate TVC readiness. Exact
master, loudness, legal-line, and caption requirements come from the named
broadcaster/client delivery specification; do not invent a universal target.

For whole-film scope, each recurring character, hero product/critical prop,
distinct scene, approved shot, director-storyboard cell, and generation unit
must map to at least one required asset. Every approved shot needs an individual
`storyboard_frame`; the `professional_storyboard_motion_map` must cover every
shot exactly once. In visual asset plan v2, split a generation unit at every
scene-anchor change. Let the selected model strategy require zero, one, or
multiple clean first/key/end inputs within an explicit minimum/maximum range;
do not force every model into a one-frame rule. Planning boards remain separate
from clean direct inputs.

An explicit “generate now” instruction can satisfy generation authorization. A
planning request, ambiguous “prepare,” or missing rights cannot. If blocked, ask
one question that names the exact missing authorization or input.

Once authorized:

- Call an available compatible media tool now. A prompt, plan, preview, or
  “ready” state is not a generated result. If no compatible tool is available,
  return `TOOL_BLOCKED` or a clearly labeled external handoff.
- For a new image sequence without locked identity, generate the identity reference first.
  Select the first required identity asset from the matrix, lock or reject it,
  then continue one dependency layer and one shot at a time while inheriting
  character, product, prop, scene, and look truth. Inspect the saved file, not
  only the chat preview, and retry one failed variable at a time.
- In an explicitly delegated test or smoke evaluation, choose the smallest
  representative assets and approve, reject, or retry them yourself. Continue
  without asking for test-only confirmation; test evidence is never client or
  production approval.
- Only for a formal release or global-install forward test, keep the execution
  evidence separate from visual judgment: bind the exact candidate, invocation,
  prompt, ordered references, tool observation, and outputs to a bounded prefix
  of the host's raw event log. The invocation must be an exact sealed user request,
  not a receipt-only string. Then give a different task a sealed request containing
  only raw references, outputs, and rubric; bind one actual image-view event per
  output plus the review claim. Label this evidence `unsigned_host_trace` and label
  visual conclusions as reviewer judgment. Do not add this receipt work to normal
  creative generation.

`visual_assets_complete` is allowed only when every required matrix row has a
fully decodable canonical PNG inside the evidence root; scene, style, per-shot
storyboard, and clean video-input frames match the delivery-profile aspect; its
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

Check the actual deliverable, not the whole archive:

- correct artifact, version, format, openability, and intended audience;
- approved facts/claims, names, copy, required scenes, and supplied exclusions;
- source/usage rights for visible image, video, music, voice, likeness, brand, and
  character material;
- continuity, legibility, crop/safe zones, and absence of internal workflow text;
- limitations expressed in client-readable production language.

Hash or version real inputs and outputs only when identity matters to the handoff.
Do not create hashes, receipts, records, or state files for hypothetical work.

## Scoped validation

The current artifact and its direct dependencies determine its result. Historical
assets, unrelated FinalDelivery folders, old control-plane records, and other
project debt may be listed as a separate project-level warning, but they cannot
turn an independent scoped pass into a failure. Never upgrade a scoped pass into
a claim that the whole project is send-ready.

Lead with the generated media, saved path and scoped QA status; otherwise lead
with the delivery decision or one blocker. Put compact evidence after it.
