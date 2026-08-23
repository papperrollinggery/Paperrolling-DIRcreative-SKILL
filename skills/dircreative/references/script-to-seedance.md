# Script-to-Seedance Handoff

Read this contract only when the selected Skill Stack scenario is
`script_to_seedance`. It lets `convert-script-to-seedance` compile locked
DIRcreative work without becoming a second story, shot, asset, or state owner.
Persist and validate the machine packet with
`docs/film-preproduction/schemas/script-to-seedance-handoff.schema.json` and
`python3 scripts/dircreative_script_to_seedance_handoff.py validate <packet>`.

## Ownership

- DIRcreative owns the approved story, authoritative script, canonical shot IDs
  and timecodes, generation units, entity ownership, visual and continuity
  locks, asset roles, audio policy, and current artifact state.
- `convert-script-to-seedance` owns only the bounded conversion of those inputs
  into Seedance-ready unit prompts, continuity snapshots, and stable asset/audio
  slot ledgers.
- The converter may budget performance, split an overloaded unit at a natural
  boundary, and make the smallest executable wording change. It must not invent
  or re-author dialogue, actions, props, wardrobe, geography, identities,
  claims, or downstream approval.
- DIRcreative consumes the converted prompts back into the video prompt
  manifest and remains responsible for Prompt IR validation, exact capability
  card resolution, direct-input policy, rights, QA, retry, and status.

## Required input packet

Pass only current, approved material:

1. authoritative script scope and immutable dialogue lines, each with a stable
   `dialogue_line_id` plus owning shot IDs;
2. canonical `S01`-style shot IDs with continuous start/end timecodes;
3. explicit narrative-node to shot to generation-unit mappings;
4. generation-unit IDs, target duration, incoming/outgoing handoff keys, and
   visible incoming/outgoing states;
5. entity ownership for every person, vehicle, product, prop, action, dialogue,
   and event sound;
6. continuity locks for identity, wardrobe, props, scene geography, axis,
   screen direction, light, damage/state progression, and audio;
7. asset ledger entries with source status, rights, production role,
   direct-input policy, user lock, and required shot/unit bindings;
8. audio policy, provider reference-slot limit, and the selected exact model
   card and provider surface.
9. the complete `asset_foundation_pass_v1` file and bound
   `ai_film_asset_stress_test_v1` report, including real file hashes and scoped
   compile permission.

If the source consists only of a nine-grid or another generated image sequence,
first classify it as `planning_only`, recover narrative beats, and derive the
technical shot, asset-foundation, and generation-unit truth. Cross-frame visual
similarity is not identity, vehicle, prop, scene, or clean-frame evidence.

## Asset foundation before direct inputs

Use the smallest sufficient asset plan, in this dependency order:

1. recurring character, costume-state, vehicle/product, critical-prop, and
   irreversible damage/open/closed state-family identity references;
2. distinct scene geography and camera-FOV references;
3. a professional storyboard/motion map for human planning when needed;
4. only the clean first/key/end frames required by the selected generation
   route.

Separate `human_planning_board` from `model_layout_reference`. Boards with
labels, arrows, grids, panels, floor plans, or timing notes stay human-only.
Narrative frames stay human planning evidence unless an explicit promotion
receipt and independent QA authorize a narrower model-reference role. Neither
class becomes a literal first frame. A clean frame is a separate text-free,
border-free, QA-passed asset.

## Deterministic slot crosswalk

Do not renumber or compress existing slots. Every attached reference must have
one row containing:

```text
source_asset_id: <DIR asset id>
asset_version: <immutable version>
relative_path: <project-relative canonical file>
sha256: <actual canonical bytes>
converter_slot: 【图片N】 | 【音频N】
platform_slot: @Image N | @Audio N
global_number: N
local_order_by_gu: {GUxx: N}
role: <identity / scene_fov / clean_frame / audio reference>
shot_ids: [Sxx]
unit_ids: [Uxx]
direct_input_policy: allowed | conditional | forbidden | planning_only
attached_to_run: true | false
status: available | planned | optional | post_dub | rejected | planning_only
primary_owner: <one Skill or controller>
assist: [<optional helpers>]
validator: <optional validator>
preserve: [...]
anti_misread: [...]
must_not_control: [...]
literal_frame_boolean: true | false
```

`【图片N】` and `【音频N】` are converter-ledger notation. The final Seedance
terminal surface uses only the exact current platform notation selected by the
DIRcreative adapter, such as `@Image N`, `@Video N`, and `@Audio N`. Internal
asset IDs, paths, hashes, QA fields, missing slots, and planning-only assets stay
out of the pasted prompt.

Only `status: available` plus `attached_to_run: true` may enter a terminal
prompt. Every such image binding must byte-match the same version/path/hash in
the canonical foundation provenance and stress-tested asset record. Planned or optional audio remains in the ledger and is never compiled
as an existing `@Audio` slot. Before export, reject duplicate/mismatched global
numbers, missing or duplicate per-unit local order, and any unit whose attached
references exceed the verified provider limit. Resolve overflow by explicit
reference sovereignty, not silent deletion: identity/state > vehicle/product >
scene > model-layout > composition.

## Unit compilation

- Compile one locally rebased generation unit at a time.
- Preserve shot IDs and time ranges outside or alongside the prompt so the edit
  assembly remains traceable.
- Each unit has one recoverable initial visible state, pressure/trigger, action
  path, camera start/end target, timing beat, final visible state, and sound or
  silence policy.
- Adjacent units must agree on entity positions, held props, wardrobe, damage,
  light, screen direction, emotional state, and audio handoff.
- Validate every within-unit state change against a declared predecessor and
  require exact outgoing-to-incoming state equality between adjacent units.
- When the requested performance exceeds the selected route, return a split
  recommendation tied to a natural shot/unit boundary; never squeeze the whole
  assembly into one executable prompt.
- User-supplied dialogue remains exact. Proposed optional empty shots or
  connective beats must be visibly optional and cannot silently change the
  authoritative script.
- Before compiling any unit, run the handoff validator with
  `--asset-foundation-pass`, `--asset-stress-report`, `--asset-artifact-root`,
  `--asset-review-receipt`, and `--asset-review-signature`. The review authority
  must already be configured in the host-owned trust registry; CLI input cannot
  add it. Missing project/asset bindings, host-pinned signatures, stages,
  unresolved gaps, incomplete
  stress matrices, unverified verdicts, or requested shots outside the allowed
  scope fail closed.
- Each `prompt_unit` carries the actual non-empty terminal `prompt_text`, a
  unique `artifact_id`, the exact packet status, and a SHA-256 over the UTF-8
  prompt bytes. A list of binding IDs without the compiled prompt is not a
  completed handoff.
- The platform slots visible in each prompt must equal that unit's locally
  rebased attached bindings. Missing, extra, stale, or wrong-media slots fail
  validation. Dialogue is validated by stable line identity and owning shot/unit
  scope; if two distinct lines use the same text, the prompt must contain two
  occurrences in that unit rather than collapsing them into one.

## Output packet

Return:

- one hash-bound Seedance prompt payload per generation unit;
- the complete image/audio slot crosswalk and upload order;
- the validated machine handoff packet with node/shot/unit coverage, provider
  limits, and binding availability;
- incoming/outgoing continuity snapshots per unit;
- any split or missing-asset blocker tied to exact shot/unit IDs;
- prompt-only or instructions-only status unless a separate authorized
  execution has a verified external receipt.

Run `ai-video-prompt-preflight` after conversion when validation is requested.
Generated video review and edit assembly remain later stages; the converter
must not claim that prompt export produced a video.
