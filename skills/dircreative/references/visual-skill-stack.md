# Visual Skill Stack

Read this reference only when provider choice is ambiguous, the user asks for a
workflow/audit trail, or the host catalog is missing and a read-only refresh is
needed. Obvious work proceeds from the selected Fast, Studio, or Delivery Route
Card without a routing preflight.

## Selection order

1. Lock the requested artifact, medium, stage, model, supplied assets, and real
   side-effect state.
2. Use the current host Skill catalog first. If it is unavailable or refresh was
   explicitly requested, run the read-only discovery tool on an authorized user
   Skill root. Never execute discovered code.
3. Keep at most 12 metadata candidates. Select one `craft_owner`, then only
   non-overlapping collaborators and at most one validator; materialize bodies
   lazily for those seats, not for the whole catalog. DIR, or ADCO only after
   native handoff validation, remains final artifact and state owner.
4. Count candidate metadata and every selected body in the existing mode byte
   budget. The selector returns non-path `body_read_requests` with body hashes,
   but never promotes them to “used”. The primary host independently locates the
   injected Skill, reads its full body, verifies the hash, and applies it before
   appending its own card. Echoing a receipt hash is not adoption. Missing,
   oversized, unread, or unverified bodies remain suggestions.
5. Add an execution adapter only for a real generation, edit, render, publish,
   or external write. Selection never executes it; the existing authorization
   gate remains decisive.

## Mode caps

| Mode | External bodies | Collaborators | Validator | Visible card |
| --- | ---: | ---: | ---: | --- |
| Fast | 1 | 0 | 0–1 | one line |
| Studio | 3 | 0–2 | 0–1 | at most five lines |
| Delivery | 1 | 0 | 0–1 | at most five lines |

The existing 14,000 / 20,000 / 30,000-byte limits always win. When no external
body fits, keep the internal craft reference and use DIRcreative; do not fake an
external invocation. In Fast or Studio, an actually loaded external craft owner
is the single task reference; do not also load the internal craft reference.
Delivery keeps its required evidence reference.

For a verified Delivery execution adapter, the host may materialize exactly one
complete adapter `SKILL.md` in an isolated tool-contract context capped at 24
KiB. The normal Delivery context still stays within 30 KiB; the receipt reports
both contexts and their aggregate bytes. This exception never adds a provider
seat, nested controller, permission, or partial read. Native `imagegen` uses the
host-managed built-in tool when exposed: it asks for no separate API key and
performs no payment action, but subscription, quota, and metered-cost status
remain `UNKNOWN`. Tool availability must never be described as free or entitled.
External or possibly charged adapters such as `fal-ai-media` remain unavailable
without a verified tool and cost boundary.

## Ownership separations

- Structure owns Hook and macro beats; story owns scenes/dialogue; shot
  progression owns cut information; storyboard owns delivery rows; master-shot
  planning owns geography.
- Performance owns observable acting. Model Skills compile an approved acting
  contract and do not perform a second creative pass.
- General VFX owns effect causality; construction owns effect atoms; mechanical
  transformation owns explainable mechanisms and loads; action owns contact
  physics.
- Aesthetic direction owns the visual system; material realism owns physical
  response; visual bible/calibration own pre-generation locks; consistency audit
  owns post-generation drift evidence.
- Asset foundation starts from a minimum visual contract. Character continuity
  owns identity/costume/critical-prop reuse, production design owns world,
  location, vehicle, and prop language, master-shot planning owns geography/FOV,
  and constraint routing assigns each reference one non-conflicting job. Load
  only the answer-changing seats; later consistency audit is a separate stage.
- Asset foundation is a six-pass serial handoff, not one oversized provider
  stack. Use `identity_state → production_design → camera_geography →
  material_response → constraint_assignment → stress_certification`, binding
  each output hash to the next input. `ai-film-asset-stress-test` is the final
  validator and never redesigns or generates the asset.
- A generated storyboard or nine-image narrative sequence without source
  bindings is planning-only. Cross-image resemblance does not prove an identity,
  vehicle, prop, location, or clean direct-input frame.
- For polished cinematic storyboard images or clean narrative input frames,
  `jingzao-image-forge` owns frame-level visual direction and prompt/spec
  compilation through `cinematic_storyboard_frames`. Load its full body in the
  isolated craft context and let it follow its own styleboard, shot-tension, and
  narrative-frame references. Reopen and validate the production handoff, then
  pass only the exact prompt/hash from its manifest to imagegen. DIR owns
  upstream truth and returned state; imagegen remains the separately authorized
  execution adapter. Build the multi-shot overview page deterministically from
  approved frame files and shot-card text rather than asking imagegen to redraw it.
- `convert-script-to-seedance` is a bounded model compiler when selected through
  `script_to_seedance`. Apply the registered `script_to_seedance_v1` contract;
  DIR retains upstream truth and consumes the compiled prompt back into its
  manifest and QA flow.
- For a declared Seedance 2.5 target, keep that same compiler and handoff. Apply
  `mr-li-seedance-25` 1.9.0 first as the authoring-method provider for the
  confirmed visual baseline, authoritative-script fidelity, real performance
  capacity, one binding block per requested scope, voice-reference checks,
  natural-paragraph delivery, and clean-image diagnostics. It does
  not become a controller, state owner, capability source, or execution adapter;
  the exact capability card is still required before model facts or execution.
  If absent, the retained compiler path still works without claiming its method.
- For direct Seedance 2.5 prompt work, `mr-li-seedance-25` is the default craft
  owner. When the task is explicitly emotion/micro-performance led,
  `seedance-25-emotion-prompt` becomes the specialist owner after the mr-li
  method pass. Do not load both for ordinary prompts. Formal compilation runs in
  Studio: the owner uses isolated craft context; use as a compiler collaborator
  uses one 64 KiB isolated method context. A small existing-prompt edit remains
  Fast and does not inflate Fast or silently claim the 1.9.0 method was loaded.
- `ai-film-production-ledger` is an isolated record-only collaborator after
  preflight. It receives only the final generation candidate, preserves
  append-only attempt/event lineage, and cannot become a story owner, director,
  generation adapter, or approval authority.
- Recurring clothed-human asset construction first routes to the canonical
  truth contract in `character-master-sheet.md`. If the active image task has
  multi-view layout, reference, continuity, exact-geography, edit/preserve, or
  observed artifact risk, select the existing `visual_asset_compile` scenario;
  Jingzao owns the visual spec and prompt/reference preflight. A simple low-risk
  image remains eligible for the concise direct path. Do not create another
  router or load every image Skill by default.
- `real_execution` is not a craft shortcut. For still/image-series work it may
  expose `imagegen` only after `asset_execution_gate_v1` passes for the active
  asset. When a prior `visual_asset_compile` selection exists, the packet must
  carry its Skill Stack receipt, provider/ref hashes, validated Jingzao spec,
  compiled prompt manifest, and call-plan status through
  `visual_asset_to_jingzao_v1`; Delivery cannot reset the craft owner to a new
  direct prompt. The caller cannot replace that packet with
  `scenario_id=real_execution` or a generation-authorization boolean.
- Prompt preflight is before generation, output review is after real evidence,
  and iteration doctor prescribes the next bounded retry.
- When explicitly requested or a specific gap warrants it, the optional
  `higgsfield-acting`, `higgsfield-cinedance`, and `lira-image-prompts` references
  can inform performance, timed camera/action writing, and local-edit reasoning
  respectively. Read the available entry's local adaptation rules first. They
  are bounded method references, not additional controllers or replacements for
  Jingzao, the locked acting contract, or the exact-version Seedance compiler.
  Do not import vendor model rankings, fixed word counts, automatic mirroring,
  universal hard-cut/first-frame rules, or pixel-identity guarantees. Keep only
  a demonstrated benefit; absent or unneeded references remain unused.
- Human-language work first builds the operation/profile plan in
  `humanization-workflow.md`. Architecture/venue, discourse and surface findings
  require source-bound quotes, cluster and whitelist verdicts. Long or
  structurally machine-shaped text routes to a findings-only Sepia pass; a
  second call needs accepted IDs plus voice/venue evidence before editing. Its
  document/profile pair and guard are bound, and recreation also needs actual
  source spans in a content-addressed preservation set. `shuorenhua`
  is a conditional contextual Chinese sentence pass; `de-AI-writing` is an
  explicitly selected bounded Chinese fidelity pass; short English work uses
  DIR's bounded path; `humanizer-zh` is findings-only validation. No validator
  repeats the rewrite.
- Sampled voice/venue calibration stays at `waiting_for_host_readback` until the
  host resolves the source references. Humanization evidence is a separately
  accounted Studio context with a 128 KiB ceiling; inline sources over 64 KiB
  fail closed rather than being silently truncated.
- ADCO owns PPT/export/adoption. `codex-ppt` is recommendation-only inside DIR;
  it cannot become an ADCO-worker adapter or introduce nested slide dispatch.

`liu-creative-workflow` and `sophia-research-mode` are explicit overlays only.
Inside DIR, Liu adds preference/packaging and Sophia adds evidence/risk; neither
owns final state. Any Liu instruction to invoke `ai-visual-production-director`
is treated as a capability-map reference. That director is never a nested
controller or provider seat inside DIR.

## Media guards

- Still outputs do not gain event timing, camera travel, editing, or sound.
- Prompt-only outputs are not generated assets.
- A locked performance handoff lets the platform compiler budget and compress;
  it does not reopen performance direction.
- Missing legacy handoffs fall back to a present platform compiler, task-local
  evidence/attempt state, or a currently callable media inspection surface.

## User-visible card

Show it after the artifact. Fast uses one line. Studio may show owner,
collaborator, validator, and explicit optional overlays in no more than five
lines. Say “已用” only after independent full-body read, hash verification, and
actual application. Without that host readback, show `已选` with
`HOST_ADOPTION=UNVERIFIED`; an unloaded candidate is only `建议`. When nothing
adds value, write:

`本次无需额外 Skill，DIRcreative 足够。`
