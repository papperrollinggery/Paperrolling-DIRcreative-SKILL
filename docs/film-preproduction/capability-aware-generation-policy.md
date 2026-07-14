# Capability-Aware Generation Policy

Verified: 2026-07-10

Purpose: keep volatile platform facts in versioned capability cards while the DIRcreative core consumes stable behavior contracts.

## Principle

DIRcreative is a production workflow, not a model-family alias.

The durable chain is:

```text
approved source artifacts
-> exact capability-card resolution
-> rights gate
-> prompt manifest
-> reference pack manifest
-> execution or external handoff
-> QA receipt
```

Platform facts live in `docs/film-preproduction/sources/model-sources.yaml`. Core policy must not hard-code a provider's current duration, reference count, native-audio claim, edit route, or extension route.

## Source-Tier Contract

Capability evidence is ranked and scoped:

| Tier | Source | Authority |
| --- | --- | --- |
| `S1` | official API reference or manual | Authorizes only the named endpoint, version, and provider surface |
| `S2` | original research paper | Supports only the named research version and evaluated behavior |
| `S3` | version-scoped official guide | Authorizes only the named product/version/mode |
| `S4` | community or GitHub | Clue only; cannot make a route generation-ready |

When sources conflict, preserve the conflict in the receipt, prefer the most endpoint-specific current S1 evidence for that surface, and fail closed when the execution route remains ambiguous.

An authoritative `S1`, `S2`, or `S3` claim is valid only when its tier, allowed source type, exact HTTPS URL, registered claim scope, exact version, and provider surface match one source entry on the resolved capability card. An allowed official domain by itself is not authority; unregistered paths and self-declared tiers fail closed.

## Capability-Card Resolution

Before any image prompt, video prompt, edit prompt, generation recommendation, or retry, resolve:

```yaml
capability_resolution:
  registry_version: ""
  capability_card_id: ""
  model_key: ""
  version: ""
  status: "current | preview | legacy | deprecated | workflow_only"
  provider_surface: ""
  verified_on: ""
  accessed_on: ""
  evidence_level: "S1 | S2 | S3 | S4"
  source_urls: []
  source_conflicts: []
  resolution_status: "resolved | stale | ambiguous | unsupported"
```

Rules:

- A family name such as Seedance, Kling, Runway, Veo, Sora, or GPT Image is not a resolution.
- `latest`, `current model`, or a provider alias is not a version.
- `deprecated`, stale, ambiguous, S4-only, or workflow-only cards cannot authorize new media generation.
- A canvas/workflow card may route assets, but every generation node still needs a model capability card.
- If the selected provider surface differs from the card, resolve another card or stay `prompt_only`.

Every card must contain `version`, `status`, `verified_on`, `accessed_on`, `source`, `evidence_level`, `reference_modes`, `audio_route`, `duration`, `edit`, `extension`, `rights`, and `failure_modes`.

## Visual Output Modes

```yaml
visual_output_mode: "prompt_only | assisted_generation | external_generation"
default: "prompt_only"
```

### `prompt_only`

Produce complete prompts, capability receipt, rights status, reference bindings, upload instructions, and QA criteria. Do not claim media exists.

### `assisted_generation`

Use only when the current runtime exposes the exact tool, the user authorizes generation, the capability card resolves, and the rights gate passes.

Do not silently switch from `prompt_only` to `assisted_generation`.

### `external_generation`

Produce an exact provider surface, model/version card ID, upload order, reference roles, desired audio, generation audio route, duration controls, and external verification checklist.

`external_generation` is an instructions-capable mode, not proof that an external upload or run happened. It may enter an actual external upload/execution state only when all of these are true:

- `external_upload_authorized: true`,
- the rights gate is `verified` or `conditional`,
- `generation_allowed: true`,
- provider restrictions and every applicable authorization are resolved,
- a named external provider surface and execution state are recorded.

Without that authorization, the handoff must stay `external_execution_state: instructions_only`, carry upload instructions, and keep `external_execution_evidence: []`. It must not claim `external_upload_ready`, `externally_executed`, generated media, or an external import.

## Execution Capability Receipt

```yaml
execution_capabilities:
  image_generation:
    available: false
    provider: "none | openai_imagegen | external | unknown"
    allowed_by_user: false
    external_upload_authorized: false
    external_execution_state: "instructions_only | external_upload_ready | externally_executed"
    external_execution_evidence: []
  video_generation:
    available: false
    provider: "none | sora | seedance | kling | runway | veo | external | unknown"
    allowed_by_user: false
    external_upload_authorized: false
    external_execution_state: "instructions_only | external_upload_ready | externally_executed"
    external_execution_evidence: []
  file_write:
    available: true
  browser_review:
    available: false
```

Runtime availability does not prove model capability, and a capability card does not prove runtime availability. Both receipts are required.

## Rights Gate

Rights are a blocking production input, not a warning after generation.

```yaml
rights_gate:
  status: "verified | conditional | unverified | blocked"
  conditions: []
  source_asset_rights: ""
  likeness_authorization: "not_applicable | verified | unverified | blocked"
  voice_authorization: "not_applicable | verified | unverified | blocked"
  brand_or_character_authorization: "not_applicable | verified | unverified | blocked"
  music_or_audio_rights: "not_applicable | verified | unverified | blocked"
  provider_restrictions_checked: false
  evidence_refs: []
  generation_allowed: false
```

Rules:

- `unverified` and `blocked` always force `generation_allowed: false`.
- `conditional` may authorize an external upload only when its conditions and decision owner are recorded, all applicable authorizations are resolved, and `generation_allowed: true`; local assisted execution still requires `verified`.
- `generation_allowed: true` requires a typed `source_asset_rights` value such as `client_owned` or `user_licensed`, plus a durable license, authorization, consent, ownership, release, rights, or contract reference. Free-text claims and self-asserted notes cannot authorize assisted or external generation.
- Prompt-only work may retain free-text or unverified rights notes only while `generation_allowed: false` and no upload or generation execution is authorized.
- Longform `direct_input_policy` is computed from the exact capability card, asset role, and that card's `reference_modes`. An `allowed`, `conditional`, `element_only`, or `reference_only` declaration cannot override an unsupported or absent exact-card reference mode; `planning_only` and `forbidden` remain non-execution modes.
- Every direct image, video, audio, likeness, voice, brand, character, or music input needs rights evidence.
- Provider-specific restrictions come from the selected card; do not invent a universal rights list.

## Desired Audio vs Generation Audio Route

Creative intent and model execution are separate fields:

```yaml
audio_plan:
  desired_audio:
    dialogue: ""
    voiceover: ""
    music: ""
    ambience: ""
    sound_effects: []
    silence: false
  generation_audio_route: "native | native_configurable | reference_audio | preserve_source | postproduction | none | unresolved"
  capability_card_id: ""
  route_evidence: []
  postproduction_handoff: ""
```

Rules:

- `desired_audio` says what the film needs.
- `generation_audio_route` says where that audio will actually be made or preserved.
- Native audio is allowed only when the exact card and provider surface support it.
- If the route is `postproduction`, the visual generation may proceed only when the post-production handoff is explicit.
- Image prompts may carry downstream `desired_audio` metadata but must not ask the image model to generate sound.

## Preserve / Change Contract

Every image edit, video edit, extension, or targeted retry must declare:

```yaml
transformation_contract:
  operation: "generate | edit | extend | retry"
  preserve: []
  change: []
  allow_incidental_change: []
  forbidden_change: []
  overlap_check: "pass | fail"
```

`preserve` and `change` must not overlap. For `edit`, both lists must be non-empty; image edit also requires at least one concrete `source_references` entry. If an item must change only partly, name the invariant and mutable subfield separately. One pass should change one production variable when fidelity matters.

## Storyboard and Clean-Frame Separation

A professional storyboard/motion map is planning truth. A clean frame is direct visual input.

Default routing:

```text
professional_storyboard_motion_map -> planning_only
clean_first_frame / clean_end_frame -> direct input only when the card supports that reference mode
```

Dense boards may become a direct reference only when the selected card explicitly supports that role and the manifest carries an anti-misread clause. A board is never silently cropped or treated as a clean frame.

## Asset Output Status

Every planned or generated asset uses `asset_output.status`:

```text
prompt_ready
generated_candidate
user_locked
external_pending
external_imported
rejected
```

`generated_candidate` is not visual truth. `user_locked` requires self-QA, rights verification, and a real user lock.

## Canvas Graph Receipt

```yaml
canvas_graph_receipt:
  nodes:
    - node_id: ""
      node_type: "idea | story | shot_list | reference_board | clean_frame | image_prompt | video_prompt | edit_prompt | qa"
      capability_card_id: ""
      rights_gate_status: ""
      asset_output_status: ""
  edges:
    - from: ""
      to: ""
      relationship: "derives_from | references | planning_only | direct_video_input | qa_checks"
      allowed_for_direct_input: false
      risk_note: ""
```

The graph is provenance, not permission to skip co-creation, rights, or model-resolution gates.

## E0-E6 Behavioral Eval Contract

| Eval | Must reject | Positive control |
| --- | --- | --- |
| `E0` | family alias, `latest`, or missing exact card/version/surface | exact current card resolution |
| `E1` | forged S1, S4-only, or unscoped evidence used as authoritative | registered S1-S3 claim with matching scope |
| `E2` | native audio route unsupported by the resolved card/surface | desired audio routed to supported native/reference/post path |
| `E3` | empty/overlapping edit contract or missing image source/reference | non-empty disjoint edit contract plus concrete source/reference |
| `E4` | rights status conflicts with provider review or likeness/voice/brand/audio authorization | verified rights gate with evidence and no authorization conflict |
| `E5` | storyboard/motion board bound as literal first frame | planning-only board plus separate clean frame |
| `E6` | fixed Image2 suffix forced into every prompt | optional internal QA macro activated by a recorded failure |

The executable audit is `python3 scripts/dircreative_model_capability_audit.py`.

## QA Gate

A run is not ready unless:

- the exact capability card resolves and is current for the provider surface,
- source URLs and `accessed_on: 2026-07-10` or a newer verified date are recorded,
- `visual_output_mode` and execution capabilities agree,
- the rights gate permits the proposed action,
- every asset has `asset_output.status`,
- `desired_audio` and `generation_audio_route` are distinct and compatible,
- edits/extensions have disjoint preserve/change sets,
- storyboard and clean-frame roles are not collapsed,
- missing or unlocked files block direct generation,
- E0-E6 positive controls pass and negative fixtures fail for the expected reason.
