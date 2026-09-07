# Storyboard Frame to Jingzao Handoff

Use `storyboard_frame_to_jingzao_v1` for cinematic storyboard or clean input frames
from locked story, shots, state and assets. Jingzao owns frame compilation.
Persist and validate with
`docs/film-preproduction/schemas/storyboard-frame-to-jingzao.schema.json` and
`python3 scripts/dircreative_storyboard_frame_handoff.py validate <receipt>`.
Panel fixtures need `--artifact-root` to resolve their design; legacy fixtures
without panels do not. Production validation also needs `--provider-root` at
an installed `jingzao-image-forge` under `~/.codex/skills`, `~/.agents/skills`,
or `~/.skillshub`, disjoint from the artifact root, and `--host-event-log` at
an absolute Codex JSONL under `~/.codex/sessions`, outside producer-writable
artifacts. Unregistered copies, overlapping roots and producer-written host
logs fail closed. CLI callers cannot extend the trusted catalog.

## Ownership and execution

- DIRcreative owns story purpose, canonical shots/timecodes, continuity states,
  asset truth, approval state, and the returned image manifest.
- `jingzao-image-forge` owns frame-level visual direction, reference-role
  compilation, shot tension, cinematic framing, and the image-generation spec.
- The host reads/applies Jingzao's full body and conditional references in the
  existing isolated 128 KiB craft budget; account for their bytes before use.
  DIR cannot paraphrase the bodies and claim a verified provider read.
- The selector receipt must include bounded `reference_read_requests` for every
  required Jingzao reference with provider-relative path, SHA-256, byte count,
  and isolated context scope. Selecting the body alone is not adoption.
- Jingzao prepares specifications and prompts. A callable image tool such as
  imagegen performs generation only after the normal DIR Delivery authorization.
- Generated frames return to DIRcreative for cross-shot consistency, continuity,
  model-input policy, user lock, and status. Neither Jingzao nor imagegen grants
  `visual_assets_complete`, client approval, or delivery.
- The assembler's `--plan` mode makes a final frame overview after individual
  reviews. Needed early black-and-white action rehearsal uses its separate
  `--coverage` mode; apply `storyboard-motion-planning.md` before the color batch.
  Neither page is a direct clean video input.

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

Give each reference one primary role, explicit secondary roles and a
`must_not_control` list: identity, wardrobe, vehicle, scene, prop, camera_action,
layout, style, palette or clean-frame state.

- Canonical assets own identity, topology, material, and declared state; they do
  not own camera or composition unless assigned `camera_action`.
- Prior frames may guide viewer position, phase, crop or attention as
  `camera_action`, never silently regain identity or topology authority.
- Human planning boards stay outside generation inputs. Model-layout references
  may control position/direction only and must not leak diagram styling.
- A deterministic spatial export enters as `layout` only when its PNG is the
  actual attachment and `spatial_source` still resolves to the export whose
  current scene-source and PNG hashes match. Its color-binding sentence names
  positions, poses, occlusion, and camera side; it cannot control identity,
  material, texture, or final art style. Bind its explicit continuous upload
  order to the corresponding user-visible image slot; its position among valid
  references follows that mapping rather than a fixed last-image rule.
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

Test the actual output against the required input packet above: the frozen event,
viewer position, camera motivation, readable action/resistance, depth roles and
all declared optical/dynamic choices must serve that beat. Check dominant read at
thumbnail size and retain a quiet region. A centered full-asset overview requires
an explicit shot purpose. For narrative specs enable both `direction.deliverable`
and `cinematic.profile` as `narrative_film_frame`; generic compilation is not this
gate. Compare all compiled fields with the current source state before generation.

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

Production binds input/output specs, prompt manifest, execution receipts and
PNGs by safe root-relative path and SHA-256. Keep `generated: false`; host matches
are only `status: observed_unverified`. `frame_outputs` covers every frame with
a distinct execution receipt and decodable PNG. Each receipt identifies
`image_gen.imagegen`, completed call, consumed spec, exact prompt, output and
result hashes. `frame_prompts` covers every frame without unrelated prompt
reuse. When the provider requires nonblocking length/reference review, retain
its complete approved `prompt_review` in that frame entry for exact replay.
This cannot approve story/physics or override a provider hard block.

Read the bound host-log prefix without symlink following; match session/prefix,
completed call, prompt digest and returned PNG bytes. Producer-owned logs are
invalid. Only the separate candidate-bound media-forward/C2PA gate can certify
real generation. Re-read provider `SKILL.md` and requested references, rejecting
missing files, traversal, symlink escape and byte/hash drift.

Missing Jingzao context or image tool: return the packet as `prompt_only`,
without claiming a generic replacement used Jingzao.

## Conditional frame dynamics

Calm frames may mark dynamics `not_applicable` with a concrete reason, without
inventing motion or resistance. Narrative frames still require viewer task and
position, dominant read, depth organization and camera motivation.
