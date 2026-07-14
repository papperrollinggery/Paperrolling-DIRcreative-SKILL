# Longform Decomposition Policy

Verified: 2026-07-10

Purpose: turn a full film into edit-ready generation units whose length and capabilities come from exact model cards, not a static universal limit.

## Principle

Longform AI video is not one opaque generation.

```text
full story duration
-> full sequence plan
-> global visual/audio/rights locks
-> exact capability-card resolution
-> card-specific generation units
-> sequence reference packs
-> clean frames or other supported references
-> generation/edit/extension prompts
-> edit assembly plan
```

A model limit is a generation-unit ceiling, not the default story duration.

## Duration Classification

Classify every duration statement before scripting:

- `story_duration`: total audience-facing film duration.
- `generation_unit_limit`: maximum or accepted unit length for one exact capability card.
- `ambiguous_duration`: ask one clarification question; a dry-run fixture may record a simulated choice.

Do not compress a multi-minute story into one 15s script because a provider example or legacy model card mentions 15 seconds.

Compatibility language such as `5-15s sequence units` or `5-15s generation units` describes older mixed-model fixtures only. It is not a universal limit and must never override the resolved card.

## Capability-Resolved Generation Unit

```yaml
generation_unit:
  sequence_id: ""
  unit_id: ""
  target_sec: 0
  story_duration_sec: 0
  capability_card_id: ""
  model_version: ""
  provider_surface: ""
  duration_rule_source: "duration"
  allowed_values_sec: []
  allowed_range_sec: []
  reference_mode: ""
  desired_audio: {}
  generation_audio_route: ""
  operation: "generate | edit | extend"
  rights_gate_status: ""
```

Rules:

- Validate every unit against the exact card's `duration` field.
- Do not compute a cross-provider universal minimum/maximum.
- If several cards are exported, keep separate unit recipes when their duration or reference modes differ.
- A legacy or deprecated duration profile applies only when that exact card is explicitly selected and allowed.
- Editing and extension use their own card fields; they do not inherit create-video duration automatically.
- When the card is stale, ambiguous, or unsupported, produce a prompt-only provisional unit and mark the duration unresolved.

## Unit Size Choice

Within the card's allowed duration, prefer shorter units when:

- dialogue timing is fragile,
- identity or product consistency drifts,
- a product proof must be exact,
- camera choreography is complex,
- reference roles compete,
- rights differ between segments,
- the model fails a longer timing test.

Prefer a longer supported unit when:

- one dramatic function spans the unit,
- the card explicitly supports the requested multi-shot behavior,
- references, audio, and motion are not overloaded,
- the edit does not require an exact cut earlier,
- the user accepts additional model interpretation.

## Longform Modes

```yaml
longform_generation_mode: "hybrid | stepwise | batch | single_sequence"
```

### Hybrid

Default for longform work:

```text
plan all sequences
-> lock global identity, scene family, palette, audio intent, and rights
-> resolve card-specific unit recipes
-> approve one sequence reference pack at a time
-> export prompts and QA
```

### Stepwise

Lock and execute one sequence at a time after global continuity anchors exist. Use for uncertain direction, expensive generation, or high identity/product risk.

### Batch

Export all provisional packs together only when the accepted continuity and regeneration risk is explicit:

```yaml
batch_skip_per_sequence_gate: true
accepted_risk:
  - higher_continuity_drift
  - higher_regeneration_cost
  - lower_user_control
```

### Single Sequence

Use only when the full story genuinely fits one card-valid unit. Do not infer this from a provider maximum.

## User Gates

| Gate | Decision |
| --- | --- |
| `sequence_plan_gate` | Approve total story duration, sequence count, and dramatic function |
| `global_visual_lock_gate` | Approve reusable identity, product, scene, style, and lens anchors |
| `rights_gate` | Verify rights for every global and sequence input |
| `model_strategy_selection` | Approve exact card/version/surface and preview/legacy risk |
| `sequence_reference_pack_gate` | Approve the sequence's model-safe reference pack |
| `clean_frame_gate` | Approve direct clean frames when the selected card mode requires them |
| `video_prompt_gate` | Approve model-specific prompt and audio route |
| `edit_assembly_gate` | Approve clip order, transitions, audio spine, and retry priorities |

## Reference Levels

```text
global references:
  character, product, wardrobe, location family, palette, lens grammar, desired audio, rights basis

sequence references:
  scene plate, lighting state, action state, camera grammar, supported start/end/reference assets

shot references:
  clean direct frame, prop detail, special action, insert, macro, or model-specific reference
```

The normal planning unit is a sequence pack. Use one direct input per shot only when the selected card, shot risk, or QA result requires it.

## Desired Audio and Generation Route

Every sequence carries both:

```yaml
audio_plan:
  desired_audio: {}
  generation_audio_route: "native | native_configurable | reference_audio | preserve_source | postproduction | none | unresolved"
  capability_card_id: ""
  handoff_to_next_sequence: ""
```

An audio-capable family name is insufficient. The exact card and provider surface must authorize the route. Post-production audio remains valid when the visual generation card does not create audio.

## Edit and Extension Units

An edit/extension plan must include:

```yaml
transformation_contract:
  operation: "edit | extend"
  source_clip_id: ""
  preserve: []
  change: []
  forbidden_change: []
  overlap_check: "pass | fail"
```

Extensions also state how the original and added segments meet at picture, motion, and audio boundaries. Unsupported references cannot silently carry into an extension.

## Edit Assembly

Every sequence plan includes:

- sequence and unit order,
- target and actual duration,
- exact capability card per unit,
- intended first and last visible state,
- edit transition into the next unit,
- desired audio and actual generation route,
- audio handoff,
- continuity anchors,
- rights basis,
- retry priority,
- preserve/change contract for edits.

DIRcreative need not render the final edit, but the editor must be able to assemble clips without guessing.

## QA Gate

A longform plan is not ready unless:

- total story duration is distinct from every generation-unit limit,
- every unit is valid for its exact current capability card,
- preview/legacy/deprecated status is handled explicitly,
- sequence functions are distinct,
- global anchors and rights are reused consistently,
- references match each card's budget and modes,
- storyboard boards and clean frames remain separate,
- `desired_audio` and `generation_audio_route` are both present,
- preserve/change sets are disjoint for edits/extensions,
- user gates match the selected longform mode,
- downstream prompts know whether assets are prompt-only, generated, locked, or imported.
