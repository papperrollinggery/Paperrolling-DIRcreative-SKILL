# Storyboard Frame to Jingzao Handoff

Use `storyboard_frame_to_jingzao_v1` when DIRcreative has locked story, technical
shots, state continuity, and canonical assets, but the deliverable needs polished
cinematic storyboard images or clean video-input frames. This is a real provider
handoff to `jingzao-image-forge`, not a copy of its craft rules into DIRcreative.
Persist and validate the chain with
`docs/film-preproduction/schemas/storyboard-frame-to-jingzao.schema.json` and
`python3 scripts/dircreative_storyboard_frame_handoff.py validate <receipt>`.
Legacy fixtures without `panel_context` need no external roots; panel fixtures
need `--artifact-root` to resolve their design. A generated production
packet must also pass `--artifact-root <project-output-root> --provider-root
<jingzao-skill-root> --host-event-log <absolute Codex host JSONL>` so the
validator can resolve every file, recompute every hash, and match each image to
a completed host generation event. The log must resolve beneath the current
host's `~/.codex/sessions` tree and outside the writable artifact root; an
arbitrary producer-written JSONL is not accepted as host evidence.
For production packets the resolved provider root must be disjoint from the
artifact root and exactly match an installed `jingzao-image-forge` directory in
`~/.codex/skills`, `~/.agents/skills`, or `~/.skillshub`. Symlink overlap and
unregistered provider copies fail closed; ordinary CLI callers cannot extend
the trusted catalog.

## Ownership and execution

- DIRcreative owns story purpose, canonical shots/timecodes, continuity states,
  asset truth, approval state, and the returned image manifest.
- `jingzao-image-forge` owns frame-level visual direction, reference-role
  compilation, shot tension, cinematic framing, and the image-generation spec.
- The host loads Jingzao in its isolated craft context and follows Jingzao's own
  conditional references, including styleboard, shot-tension, and narrative-frame
  guidance. The isolated 128 KiB budget covers the full provider body plus the
  task-relevant reference pack; referenced bytes must be accounted before use.
  DIR does not paraphrase those bodies or claim they were used without a
  verified full-body read.
- The selector receipt must include bounded `reference_read_requests` for every
  required Jingzao reference with provider-relative path, SHA-256, byte count,
  and isolated context scope. Selecting the body alone is not adoption.
- Jingzao prepares specifications and prompts. A callable image tool such as
  imagegen performs generation only after the normal DIR Delivery authorization.
- Generated frames return to DIRcreative for cross-shot consistency, continuity,
  model-input policy, user lock, and status. Neither Jingzao nor imagegen grants
  `visual_assets_complete`, client approval, or delivery.
- A multi-shot professional storyboard/motion page is assembled after the
  individual frame reviews with `scripts/dircreative_storyboard_page_assembler.py`.
  It is a planning overview PNG with its own receipt and visual review, never a
  second imagegen interpretation or a direct video-model input.

## Required input packet

Every requested frame must bind:

```text
frame_id / canonical shot_id / time range / generation_unit_id
shot function and narrative purpose
visible event and relationship change
viewer task and viewer position
dominant read and secondary read
one frozen action phase
action vector and counterforce
foreground / midground / background jobs
attention entry / interruption / landing / exit
camera height / distance / pitch / yaw / roll / state
focal-length feel, projection, and protected edge behavior
crop pressure, occlusion, parallax, and movement room
exaggeration budget and one protected realism/spatial anchor
one quiet or stable region
canonical identity/state assets and reference sovereignty
camera_action or composition references with must_not_control
locked medium, aspect, palette, material, light, and target surface
```

For detailed action-panel work, add the optional frame `panel_context`:
`coverage_file`, its byte `coverage_sha256`, `panel_id`, `phase`, `at_seconds`,
and `state`. Bind an immutable design sidecar; `frame_id` equals `panel_id`,
while `shot_id` stays the real technical shot. Dispatch multiple panels of one
shot as separate packets: the existing one-frame-per-shot packet rule remains.
The validator checks the source design and exact panel state, not merely a
matching display name. Returned prompts/images retain that same frame ID.
This optional binding does not promote planning panels to clean model inputs
or change legacy visual-completion and host-evidence requirements.

## Scene/support truth gate

High-risk panels require `truth_contract` binding scene/attachments, support,
parents, and constraints. Identity/prop/style references cannot own background,
ground, geography, or support. A bound spatial `layout` may own geometry and
support, but must disclaim identity, material, texture, and final style. Prompt
rows bind ordered inputs plus exact `reference_authority`; exactly one scene role
must match `scene_asset_id`. Before execution, a detached trusted reviewer signs
the exact prompt/authority/truth/coverage hashes and a no-conflict verdict;
missing, failed, or drifted review blocks. Observed runs use the sealed request.
Pixel review remains separate.

If the installed Jingzao provides a production-manifest compiler, inspect its
actual contract before using it. Map DIR `panel_id` to provider frame `id` and
retain canonical `shot_id`; pass one complete image specification per frame.
Keep coverage metadata out of model-facing prose. Consume each returned frame
envelope through the existing spec/prompt/evidence chain, not a prose slice of
a combined board. Provider coverage checks do not replace DIR's story-derived
requirements: a provider's valid video-only row cannot waive a DIR-required
contact/state image. An unavailable compiler falls back to individual validated
Jingzao specs; never execute another task's unreleased worktree as the default.

A missing asset may block identity correctness; it must not cause the camera to
fall back to a centered asset showcase. Conversely, a strong composition
reference cannot overwrite identity, vehicle topology, prop state, geography,
or damage progression.

## Reference roles

Assign each actual reference one primary role: identity, wardrobe, vehicle,
scene, prop, camera_action, layout, style, palette, or clean-frame state. Record
secondary roles explicitly and keep a `must_not_control` list.

- Canonical assets own identity, topology, material, and declared state; they do
  not own camera or composition unless assigned `camera_action`.
- A prior narrative frame may own viewer position, action phase, crop, or
  attention flow as `camera_action`; it remains candidate evidence and cannot
  silently regain identity or topology authority.
- Human planning boards stay outside generation inputs. Model-layout references
  may control position/direction only and must not leak diagram styling.
- If a camera/composition reference repeatedly contaminates canonical truth,
  remove or replace that reference and preserve the frame card instead of
  weakening the canonical asset.
- Resolve the actual provider reference limit before execution. Overflow uses
  declared sovereignty or an already validated combined identity/state asset;
  no reference is silently dropped.

## Two independent gates

### Asset-truth gate

Check identity, wardrobe, vehicle/prop topology, scene geography, state
progression, material, light ownership, rights, and direct-input eligibility.

### Director-frame gate

Check that the output is a narrative frame rather than an asset presentation:

- one causally informative frozen moment;
- motivated viewer position and camera placement;
- dominant read at thumbnail size;
- action vector plus visible resistance or consequence;
- distinct foreground/midground/background functions;
- intentional occlusion, parallax, crop pressure, and offscreen space;
- focal length, distance, height, roll, and projection serving the same beat;
- declared exaggeration with a protected anchor;
- one quiet region so tension remains readable;
- no centered full-asset overview unless the shot function explicitly needs it.

Passing asset truth never auto-passes director-frame quality. A `clean_frame`
means text-free, border-free, role-safe, and technically usable; it does not mean
neutral, centered, flat, or catalog-like.

## Sequence diversity gate

Across a storyboard sequence, compare adjacent and non-adjacent frames. Flag
unmotivated repetition of viewer position, subject/frame ratio, shot size,
camera height, attention path, horizon, visual center, and depth pattern. Each
cut should change information, relationship, action phase, scale, or viewer
position. Canonical asset consistency must survive those changes.

Do not impose a mechanical quota of wide/medium/close shots. Preserve a repeated
grammar only when it creates a deliberate pattern or match cut.

## Output packet

Return to DIRcreative:

- the consumed DIR input `spec_id` and SHA-256;
- one validated Jingzao visual specification and compiled prompt per frame;
- a Jingzao output `spec_id` and SHA-256 plus the prompt/call-plan hashes;
- ordered reference call plan with roles, sovereignty, and ignored layers;
- prompt review plus asset-truth and director-frame QA targets;
- generation strategy: sheet_direct, independent_frames, or hybrid;
- actual image receipts when generation was separately authorized;
- failures and one-variable retry class without silently changing upstream truth.

The later Delivery/imagegen receipt must echo the exact Jingzao output spec ID
and SHA-256 it consumed. A matching body hash or prompt text alone does not prove
that the compiled frame contract reached generation.

For non-fixture production, bind the DIR input spec, Jingzao output spec,
compiled prompt manifest, execution receipt, and generated image by safe
root-relative path plus actual SHA-256. This compile-only handoff never grants
`generated: true`; the field remains `false`. When local host evidence is found,
record only `status: observed_unverified`, an exact `frame_outputs` manifest
covering every `frame_id`, and one distinct execution receipt and decodable PNG
per frame. Each receipt
must identify `image_gen.imagegen`, the completed host call, consumed spec,
frame-specific compiled prompt hash, output path, and result hash. The prompt
manifest must contain a `frame_prompts` entry for every frame and may not reuse
one prompt hash as proof for unrelated frames. The bound host-log prefix is
read with no symlink following; its session ID, prefix hash, completed call ID,
prompt digest, and returned PNG bytes must match. A log stored inside the
artifact root is rejected because the producer cannot also manufacture its own
proof. Even a match under `~/.codex/sessions` remains an observation, not an
independent trust root: only the separate candidate-bound media-forward/C2PA
gate may certify real generation. Provider `SKILL.md` and every requested `references/...` file are re-read
under the supplied provider root; traversal, symlink escape, missing files,
byte-count drift, and hash drift fail closed.

If the isolated Jingzao context or actual image tool is unavailable, return the
handoff packet and `prompt_only`; do not substitute a lower-quality generic frame
while claiming Jingzao was used.

## Conditional frame dynamics

Apply dynamics fields by shot class. Static product, identity, interview,
dialogue, observation, or intentionally calm frames may set action/counterforce,
crop pressure, parallax, or exaggeration to `not_applicable` only with a concrete
reason. Do not invent motion or resistance to fill the contract. Viewer task and
position, dominant read, depth organization, and camera motivation remain
required for narrative frames.
