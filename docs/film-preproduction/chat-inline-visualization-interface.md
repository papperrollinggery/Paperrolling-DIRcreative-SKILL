# Chat Inline Visualization Interface

Status: normative v1

Schema: `schemas/chat-visualization-spec.schema.json`

Author template: `schemas/chat-visualization-spec.template.yaml`

## Purpose

Use a visualization only when it makes the current creative decision easier to understand than concise chat text. The visualization is a review surface, not source truth, a live dashboard, an approval receipt, or an authorization mechanism.

The user must be able to see, in this order:

1. current stage,
2. current creative work,
3. required decision,
4. production recommendation and tradeoff when useful,
5. downstream effect,
6. one primary action and at most one secondary action.

Preserve the existing chat loop:

```text
stage -> customer-visible preview -> production judgment -> one decision
-> human-readable conversation intent -> gate validation
-> artifact/lock/receipt write -> next stage
```

## Surface Selection

Choose the smallest surface that materially improves the decision.

| Condition | Surface | Requirement |
| --- | --- | --- |
| Labeled nodes and edges fully explain a static relationship | Mermaid | Keep the existing one-question chat gate |
| One compact comparison, timeline, staged choice, or QA decision | Inline | One decision, no deep navigation, at most two actions |
| 30+ shots, dense continuity matrix, reference graph, or linked A/B inspection | Fullscreen | Keep the native conversation as the control plane |
| Visual surface unavailable, unsupported, or failed | Markdown/table/Mermaid fallback | Preserve the same visible fields and decision question |

Do not place a tabbed Workbench, multi-stage editor, file browser, or persistent project dashboard inside an inline view.

## State And Authority

Keep three state layers separate.

| Layer | Examples | Authority |
| --- | --- | --- |
| Component | selected option, expanded detail, staged revision note | presentation only |
| Conversation | submitted user intent and controller response | visible decision evidence |
| Artifact | gate decision, revision, lock, stale marker, authorization, QA verdict, receipt | authoritative source truth |

A component selection or click cannot directly:

- lock an artifact,
- claim readiness,
- record acceptance,
- claim completion,
- authorize media generation.

An action sends a human-readable conversation intent containing the selected value, target gate, requested action, and known downstream effect. DIRcreative or ADCO then re-reads current state, validates the gate, writes within its authority, and emits a confirmation echo.

## Required Spec Contract

Every visual decision view must validate against `dircreative.chat-visualization@1.0` and contain:

- execution context and controller ownership,
- typed current gate and decision owner,
- view intent and display mode,
- hash-bound source artifacts,
- typed image previews when media is available, including a safe project-relative path, MIME type, review classification, source/authorization/channel-fit status, alt text, caption, and bounded annotations,
- source-bound or explicitly presentation-only fields,
- no more than three comparison options,
- local interactions separated from conversation actions,
- one or two actions mapped to the current gate,
- an explicit preview-only write boundary,
- a complete text fallback.

### Source bindings

Use `artifact_id#/path` references. The artifact prefix must match an item in `source_truth.artifacts`.

- `source_bound` fields require a non-null source reference.
- `presentation_only` fields require `source_ref: null`.
- Every option requires at least one source reference.
- The recommendation must reference an option present in the same view.
- Evidence used to classify a preview as a real candidate must be an independent project-relative JSON record with `lifecycle_status: current` and a matching SHA-256. Its JSON Pointer must exist, and source, authorization, and channel-fit evidence must resolve to content whose `status` is `confirmed`.

Do not expose local paths, raw hashes, internal capability evidence, or backstage YAML in the user-facing view. They remain in the spec and receipt for inspection and audit.

For image previews, the renderer verifies the physical file and SHA-256 before embedding it as a data URI. Supported formats are PNG, JPEG, WebP, and passive SVG. Active or externally linked SVG is rejected. A `real_candidate` requires confirmed source, authorization, and channel fit; an `illustrative_placeholder` is visibly labeled and cannot offer `submit_selection`.

### Customer conversation language

Design every visible label, value, action, status line, and follow-up prompt for the person making the creative decision. Use phrases such as `你的选择`, `专业判断`, `会继续沿用`, `需要重新确认`, and `接下来`. Do not surface implementation vocabulary such as `artifact`, `gate`, `receipt`, `sha256`, `source truth`, `writeback`, `prompt-only`, `项目写回`, `新建锁`, or `保留锁`. Translate them to the actual creative meaning. The validator and browser audit fail on these backstage terms.

### Actions

Allowed action kinds are:

- `submit_selection`
- `request_revision`
- `request_mix`
- `request_fullscreen`
- `retry_smallest`
- `stop`
- `pause_prompt_only`

Every action must target `stage_gate.id`. An action records conversation intent only; no action writes project truth.

### Forbidden claims

Every spec must explicitly forbid all of:

- `lock`
- `readiness`
- `acceptance`
- `completion`
- `generation_authorization`

These labels describe authoritative claims that remain outside component authority.

## Stage Mapping

| Gate type | Preferred intent | Minimum visible evidence | Primary action family |
| --- | --- | --- | --- |
| `idea_intake_gate` | confirm | brief, known facts, inferred risks, missing fact | submit or revise |
| `concept_options_gate` | compare | hook, emotional engine, visual signature, tradeoff, recommendation | select or mix |
| `story_approval_gate` | timeline | beginning, turn, proof, ending, tension | approve or revise |
| `script_approval_gate` | timeline | time bands, VO/dialogue/audio budget, overrun | approve or revise |
| `shot_list_approval_gate` | timeline | timecode, shot size, action, movement, audio, risk | approve or inspect |
| `visual_direction_gate` | compare | palette, light, material, optics, avoid list | select or mix |
| `visual_bible_approval_gate` | graph | locked identity, environment, props, wardrobe, drift risk | approve or inspect |
| reference-pack gates | graph | asset id, role, status, shot binding, planning/direct-input distinction | lock request or revise |
| `video_prompt_gate` | confirm | prompt intent, inherited references, selected route, generation boundary | prompt-only or next authorized step |
| `generation_qa_gate` | qa | candidate deltas, locked facts, blocker, smallest retry | retry, stop, or switch route |
| `checkpoint_gate` | inspect | current stage, locks, stale artifacts, unresolved decision | resume or stay paused |

## Standalone Chat

In `standalone_chat`:

- `controller.surface_owner` is `dircreative`;
- `controller.user_facing` is `true`;
- `write_boundary.write_owner` is `dircreative`;
- DIRcreative may render the view, receive the conversation intent, validate the gate, write the artifact/receipt, and show the confirmation echo.

If the visual surface is unavailable, use `fallback` without asking the user to change clients.

## ADCO Worker

In `orchestrated_worker`:

- `controller.surface_owner` is `ad-creative-orchestrator`;
- `controller.user_facing` is `false` for the provider-produced spec;
- `write_boundary.write_owner` is `ad-creative-orchestrator`;
- DIRcreative returns a neutral, hash-bound visualization spec or fallback payload to ADCO;
- ADCO decides whether and how to surface it, receives the user decision, owns adoption, and writes host current truth.

Visualization is an optional negotiated capability. Its absence must not invalidate an otherwise compatible v1 text-only handoff. A DIR worker must not call a client-facing follow-up action directly.

## Confirmation Echo

After the controller validates and records a submitted intent, write and validate a `dircreative.chat-visualization-writeback@1.0` receipt. The receipt must bind the originating visualization spec by path, hash, view id, gate id, action id, and selected option. It must also hash every artifact it claims was created, updated, or preserved.

Only after `scripts/dircreative_visualization_writeback.py validate` passes, show a read-only confirmation echo containing:

- what the user chose or revised,
- whether that choice is now confirmed,
- one short production judgment,
- what will continue unchanged when relevant,
- what needs another look when relevant,
- what the user will see next.

Do not show `artifact`, `gate`, hashes, receipt ids, write targets, source bindings, lock ids, stale markers, controller names, or protocol status codes in the customer-facing echo. Keep that evidence in the writeback receipt. Translate a real production constraint into customer language such as `暂时不能开始生成素材`.

If validation fails, keep the current artifact unchanged and explain the one blocking conflict in customer language.

The confirmation echo is not another decision gate. It contains no action button, never calls `sendFollowUpMessage`, and cannot grant generation authorization or live acceptance. The next stage is presented by the normal chat controller after the echo.

For `standalone_chat`, DIRcreative owns the writeback receipt and may show the echo. For `orchestrated_worker`, DIRcreative returns provider output only; ADCO owns host adoption, host artifact hashes, the host writeback receipt, and any client-facing echo.

## Validation

Validate one spec:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_spec.py validate \
  <spec.json-or-yaml> --project-root <active-project-root>
```

Render a standalone-chat fragment into the current thread visualization directory:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_render.py render-html \
  <spec.json-or-yaml> \
  --project-root <active-project-root> \
  --output ~/.codex/visualizations/<date>/<thread-id>/<lowercase-title>.html
```

The renderer fails closed for `orchestrated_worker` specs. ADCO must consume those specs through its negotiated controller path. Image paths are project-relative and must stay inside `--project-root`; the renderer rejects missing files, path escapes, hash mismatches, active/external SVG, and fragments above 2 MB. Create bounded review thumbnails rather than embedding full-resolution originals.

Run the positive and negative fixture gate:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_audit.py
```

Generate the representative dogfood pages and run the browser audit when Chrome and Playwright are available. The audit covers 736/320 px light, 736/320 px dark, 320 px forced text spacing, and 736 px large text. It also checks all dynamic options, selected-state projection, action payloads, target size, clipping, curve-label overlap, and minimum secondary text size:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_dogfood.py
node scripts/dircreative_visualization_browser_audit.cjs
```

The audit must reject action overflow, direct authoritative writes, incomplete fallback, unbound source fields, and ADCO controller/ownership violations.

Validate a controller writeback receipt and render its read-only confirmation echo:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_writeback.py validate \
  <writeback-receipt.json> --project-root <project-root>
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_writeback.py seal \
  <writeback-draft.json> --project-root <project-root> \
  --output .dircreative/runs/<writeback-receipt.json>
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_writeback.py render-confirmation \
  <writeback-receipt.json> --project-root <project-root> --output <confirmation-echo-fragment.html>
```

The validator fails closed on a stale source-spec hash, unknown action or option, controller mismatch, missing or changed written artifact, contradictory lock/downstream classification, or an unresolved gate that claims the next stage is ready.
