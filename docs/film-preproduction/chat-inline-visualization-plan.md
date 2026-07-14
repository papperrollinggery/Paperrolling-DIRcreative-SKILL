# DIRcreative Chat Inline Visualization Integration Plan

Status: superseded for UX implementation by `chat-inline-visualization-v2-ux-plan.md`; retained as V1 architecture baseline

Date: 2026-07-14

## Goal

Turn DIRcreative's existing chat-first, artifact-backed workflow into a visual decision experience inside supported ChatGPT/Codex desktop conversations without replacing stage gates, source truth, locks, receipts, or ADCO ownership.

The user should understand four things at a glance:

1. where the project is now,
2. what creative work is being shown,
3. what decision is required,
4. what that decision will unlock or invalidate.

The memorable product behavior is: **one visible production decision at a time, explained visually, with its downstream effect made explicit before anything is written.**

## Verified Starting Point

- The repository and installed DIRcreative root `SKILL.md` have the same SHA-256.
- DIRcreative already requires a chat-first loop: stage, preview, one question, user answer, artifact write, receipt, next stage.
- `co-creation-run.yaml` already records gate status, options, selection, rationale, downstream artifacts, and blocks.
- The planned Workbench already defines a workflow rail, artifact canvas, comparison pane, QA drawer, and timeline.
- The current visual dogfood is static standalone HTML containing transcript text. It verifies visible terms and browser cleanliness, but it is not an interactive in-conversation decision surface.
- The installed ChatGPT desktop app includes the Visualize plugin and supports thread-scoped inline HTML fragments in supported conversations.
- OpenAI's current Visualizations documentation says rendering is available only on supported ChatGPT web/desktop/mobile surfaces, not Codex CLI or the IDE extension.

## Research Findings

### OpenAI conversation UI

- [Visualizations](https://learn.chatgpt.com/docs/visualizations) recommends the smallest visual format that materially improves understanding and treats a visualization as a snapshot, not a live synchronized dashboard.
- [Apps SDK inline-card guidance](https://developers.openai.com/apps-sdk/concepts/ui-guidelines#inline-card) limits an inline card to one action or decision, at most two primary actions, no deep navigation, and no nested scrolling.
- [Apps SDK fullscreen guidance](https://developers.openai.com/apps-sdk/concepts/ui-guidelines#fullscreen) reserves fullscreen for rich canvases, maps, diagrams, or multi-step exploration while keeping the native composer available.
- [Apps SDK state guidance](https://developers.openai.com/apps-sdk/plan/components#define-the-state-contract) separates component state, authoritative server state, and transcript messages.
- [Apps SDK rendering guidance](https://developers.openai.com/apps-sdk/build/chatgpt-ui#decoupled-pattern) separates data/decision processing from UI rendering.

### Creative production products

- [Boords storyboard views](https://boords.com/docs/storyboard-views) separates global scan, grid, shot list, individual frame editing, animatic, and client review instead of forcing all tasks into one view.
- [Frame.io Comparison Viewer](https://help.frame.io/en/articles/9952618-comparison-viewer) uses focused side-by-side comparison with linked viewing controls and comments.
- [Runway Workflows](https://help.runwayml.com/hc/en-us/articles/45769159004691-Building-your-first-Workflows) makes inputs, outputs, node history, selection, and restoration visible.
- [Milanote comments](https://help.milanote.com/en/articles/10684379-comments) binds discussion to a specific visual object rather than separating feedback from the work.
- [Adaptive Cards](https://adaptivecards.io/explorer/Action.Submit.html) keeps staged input local until an explicit submit action and validates associated inputs before submission.

## Product Decision

Do not build one embedded Workbench with tabs inside every reply.

Build a sequence of small, stage-specific decision surfaces:

```text
conversation context
-> compact stage rail
-> one current decision visualization
-> user selects, mixes, requests revision, or expands
-> component sends a human-readable follow-up message
-> DIRcreative validates the decision against the active gate
-> authoritative artifact/lock/receipt write
-> next stage produces a new visualization
```

Use fullscreen only for information that cannot remain legible in one inline card:

- 30+ shot or rhythm-point timelines,
- reference asset relationship graphs,
- detailed visual-bible continuity matrices,
- generated candidate comparison with inspection detail.

## Surface Architecture

### 1. Stage Context Strip

Purpose: answer “where am I?” without becoming navigation.

Show only:

- completed and locked stages,
- the current stage,
- the next blocked or available stage,
- one active blocker when present.

Do not make the entire workflow clickable in the first release. Clicking old stages would introduce hidden revision semantics and conflict with current-first state governance.

### 2. Decision Canvas

Purpose: answer “what am I deciding?”

Every inline decision card contains:

- a customer-readable stage label,
- the decision in one sentence,
- the smallest useful visual preview,
- two or three options when comparison is required,
- DIRcreative's recommendation and production reason,
- the downstream effect of the selected option,
- one primary action and at most one secondary action.

Primary action examples:

- `采用这个方向`
- `确认这个脚本`
- `锁定这套参考图方案`
- `重试最小失败项`

Secondary action examples:

- `混合或修改`
- `展开查看`
- `暂停在 prompt-only`

### 3. Inspection View

Purpose: let the user inspect enough detail to judge without dumping raw YAML.

Use inline expansion for a few additional rows. Request fullscreen for large timelines, graphs, image comparisons, or dense shot details.

The inspection view is read-only in the first release. A requested change becomes a follow-up chat message and re-enters the typed stage gate.

### 4. Confirmation Echo

Purpose: prevent ambiguous clicks from silently becoming project truth.

After the user acts, the component sends a plain-language message containing:

- selected option or requested mix,
- affected stage gate ID,
- requested action,
- known downstream effect.

DIRcreative then checks current state and replies with:

- what was recorded,
- artifact/lock status,
- which downstream artifacts became stale or remained preserved,
- the next visible output.

The component does not directly claim approval, lock, readiness, acceptance, or completion.

## Stage-to-Visualization Map

| Stage | Inline visualization | Fullscreen when needed | Primary decision |
| --- | --- | --- | --- |
| Idea intake | Brief map with channel, duration, audience, product, boundary, and missing facts | Never in MVP | Confirm or correct the brief |
| Director room | Two or three concept territories with hook, emotional engine, visual signature, production risk, and recommendation | Rich concept board only when real media exists | Select or mix a direction |
| Story approval | Beat ribbon or emotional curve with beginning, turn, proof, and ending | Longform sequence map | Approve story logic |
| Script approval | Timed script bands with VO/dialogue/audio budget and overrun warning | Full script plus timing inspector | Approve or revise script |
| Shot list | Compact shot-density timeline with duration, shot size, movement, action, audio, and risk | 30+ point timeline and shot inspector | Approve shot structure |
| Visual direction | Two or three direction boards with palette, light, material, optics, avoid list, and optional images | Image-rich moodboard | Select visual direction |
| Visual bible | Lock matrix for identity, environment, props, wardrobe, light, material, and drift risks | Continuity graph | Approve visual locks |
| Reference pack | Asset-role graph showing planning-only, reference-only, and direct-video-input edges | Full asset graph and per-shot binding | Lock, compress, or split the pack |
| Image prompt handoff | Prompt intent summary, inherited references, generation boundary, and QA target | Prompt inspector only on request | Prompt-only or authorized generation |
| Video model choice | Exact capability-card comparison with route, duration, reference, audio, and unresolved evidence | Detailed model evidence table | Choose first test route |
| Generation QA | Candidate comparison with pass/fail overlays, locked-fact deltas, blocker, and smallest retry | Linked A/B inspection | Retry, switch route, or stop |
| Checkpoint | Current-first stage rail, locks, stale artifacts, unresolved decision, and next action | Never | Resume or keep paused |

## Visual Language

### Aesthetic

Use a restrained production-desk aesthetic:

- neutral host surfaces,
- one semantic accent for the current/selected state,
- typography and spacing as the main hierarchy,
- thin timelines, connectors, and annotations,
- no decorative gradients, cinematic chrome, or fake editing-software panels.

The visual language should feel like a director's review desk, not an AI dashboard.

### Information hierarchy

1. Current decision.
2. Visual evidence needed to decide.
3. Recommendation and tradeoff.
4. Downstream effect.
5. Action.

Internal IDs, hashes, capability evidence, and receipt paths remain backstage unless the user asks to inspect them.

### Responsive and accessible behavior

- Design for 736 px and reflow to 320 px.
- Native buttons, radio controls, selects, and text inputs only.
- Never rely on color alone; pair color with text, shape, or line style.
- Preserve keyboard order and visible focus.
- Provide an accessible summary for every SVG, chart, graph, timeline, or image comparison.
- Honor reduced motion and avoid looping animation.
- Avoid internal scrolling and fixed viewport heights.

## Interaction Contract

### Component-local interactions

These do not change project truth:

- select an option for preview,
- hover or focus for detail,
- expand or collapse a small detail,
- compare two candidates,
- adjust presentation-only filters,
- stage a mix or revision note.

### Conversation-turn interactions

These send a human-readable follow-up message to DIRcreative:

- confirm the staged option,
- request a mix,
- request revision,
- request fullscreen inspection,
- choose prompt-only versus an authorized next step,
- choose the smallest QA retry.

### Authoritative writes

Only DIRcreative or ADCO, after validating the current gate and scope, may write:

- selected option,
- artifact revision,
- user lock,
- stale downstream status,
- generation authorization,
- QA verdict,
- acceptance state,
- receipt.

## State Contract

Introduce a versioned `dircreative.chat-visualization` specification.

Minimum fields:

```yaml
spec_version: "1.0"
view_id: ""
execution_context: "standalone_chat | orchestrated_worker"
stage_gate:
  id: ""
  type: ""
  status: "pending | needs_user | blocked | simulated"
view:
  intent: "confirm | compare | inspect | timeline | graph | qa"
  display_mode: "inline | fullscreen | fallback"
  title: ""
  decision_prompt: ""
source_truth:
  artifacts:
    - artifact_id: ""
      version: ""
      sha256: ""
presentation:
  options: []
  recommendation: ""
  annotations: []
  downstream_effects: []
interactions:
  allowed: []
  primary_action: ""
  secondary_action: ""
write_boundary:
  preview_only: true
  confirmation_required: true
  write_owner: "dircreative | ad-creative-orchestrator"
  possible_write_targets: []
fallback:
  format: "markdown | table | mermaid"
  required_visible_fields: []
```

The spec is generated from current artifacts and stage state. It is not itself an approval receipt.

### Three state layers

| State | Examples | Authority |
| --- | --- | --- |
| Component state | selected card, expanded detail, staged mix text | presentation only |
| Conversation state | submitted user intent and DIRcreative response | visible decision evidence |
| Artifact state | selected option, lock, stale markers, receipt | authoritative source truth |

Never infer artifact state from component state alone.

## Surface and Fallback Matrix

| Environment | Preferred rendering | Behavior |
| --- | --- | --- |
| Supported ChatGPT web/desktop/mobile with Visualize | Inline visualization; optional fullscreen | Full interaction contract |
| Supported Apps SDK plugin surface | MCP UI component backed by structured tools | Durable component state and tool actions |
| Codex CLI or IDE extension | Markdown table, compact Mermaid, and one plain-language question | Same gate semantics, no visual dependency |
| Unsupported or failed visualization | Normal DIRcreative chat template | No blocked workflow and no lost decision fields |

Visualize availability is a progressive enhancement, not a prerequisite for using DIRcreative.

## Standalone and ADCO Ownership

### `standalone_chat`

DIRcreative may prepare the visualization spec, render the view when the surface supports it, receive the follow-up selection, validate the gate, write its artifact/receipt, and continue.

### `orchestrated_worker`

DIRcreative must not surface or persist a client decision directly. It returns:

- customer-readable preview data,
- recommended visualization intent,
- options and tradeoffs,
- the decision prompt,
- visualization spec as a scoped output artifact when authorized.

ADCO remains the user-facing controller, renders or converts the view, receives the decision, owns adoption, and writes host current truth.

Do not add a DIR-only rendering requirement to the ADCO exchange protocol. Negotiate visualization support as an optional capability so older ADCO versions can use the text fallback.

## Repository Changes Required

### Root Skill

Modify `skills/dircreative/SKILL.md` to:

- read the new visualization interface contract when the surface supports Visualize or when the user requests a visual decision view,
- choose the smallest visualization that materially improves the current gate,
- prohibit monolithic tabbed dashboards in inline cards,
- preserve the existing one-question rule,
- require fallback output on unsupported surfaces,
- state that visualization state cannot become source truth.

Do not expand the root Skill with HTML/CSS implementation details. Keep those in the visualization contract and reusable templates.

### Sub-skills

Update only sub-skills with material visual decision surfaces:

- `chat-facilitator`
- `co-creation-gate-runtime`
- `director-room`
- `story-development`
- `script-treatment`
- `shot-design`
- `visual-bible`
- `reference-image-planner`
- `image-prompt-compiler`
- `video-model-adapter`
- `generation-qa`
- `checkpoint`

Each sub-skill should declare:

- visualization intent,
- minimum visible fields,
- allowed interactions,
- action-to-gate mapping,
- fallback format,
- source artifacts and write owner.

### Docs and schemas

Add:

- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/schemas/chat-visualization-spec.schema.json`
- `docs/film-preproduction/schemas/chat-visualization-spec.template.yaml`

Update:

- `chat-co-creation-interface.md`
- `chat-stage-gate-integrity.md`
- `live-chat-start-protocol.md`
- `workbench-product-spec.md`
- `workbench-data-flow.md`
- `phase-contracts.yaml`
- `co-creation-run.yaml`
- `adco-integration-contract.md` only for optional capability negotiation and ownership, without changing required v1 behavior.

### Scripts and reusable assets

Add deterministic helpers:

- `scripts/dircreative_visualization_spec.py`: build and validate visualization specs from fixture artifacts.
- `scripts/dircreative_visualization_audit.py`: validate state separation, required fields, supported modes, fallbacks, action limits, and source bindings.
- `skills/dircreative/assets/visualizations/`: small reusable fragments or data templates for stage rail, decision comparison, timeline, relationship graph, and QA comparison.

Do not copy OpenAI's proprietary Visualize plugin code or assets. DIRcreative owns only its domain spec, templates, and validation.

Replace the static transcript-dump dogfood with interactive fixture views while preserving standalone render output for browser testing.

## Development Plan

### Phase 0: Contract freeze

Deliver:

- visualization spec schema,
- interface contract,
- surface fallback matrix,
- ADCO ownership note,
- five representative positive fixtures and negative fixtures.

Exit criteria:

- every interaction maps to an existing typed gate,
- every field maps to a current artifact or is explicitly presentation-only,
- no UI action can directly claim lock, readiness, acceptance, or completion.

### Phase 1: MVP decision surfaces

Implement:

1. idea-intake brief map,
2. director-room concept comparison,
3. story beat ribbon,
4. script timing bands,
5. compact shot timeline,
6. visual-direction comparison,
7. Markdown/Mermaid fallback for each.

Exit criteria:

- rough-idea and complete-idea fixtures can complete every required gate with one visual decision per turn,
- no regression in the text-only chat path,
- keyboard and 320/736 px rendering pass.

### Phase 2: Visual continuity and references

Implement:

- visual-bible lock matrix,
- reference asset-role graph,
- per-shot source binding view,
- fullscreen shot and asset inspectors,
- stale downstream impact preview.

Exit criteria:

- every displayed asset resolves to ID, version, hash, role, and status,
- planning-only and direct-input assets cannot be confused,
- changed upstream selections preview downstream staleness before write.

### Phase 3: Prompt, model, and QA views

Implement:

- model capability-card comparison,
- prompt inheritance summary,
- candidate A/B comparison,
- QA delta overlay,
- smallest-artifact retry action.

Exit criteria:

- exact model cards and evidence conflicts remain visible,
- failed QA cannot expose a lock action,
- retry changes one variable and preserves accepted locks.

### Phase 4: ADCO and packaging

Implement:

- optional visualization capability negotiation,
- neutral provider visualization spec output,
- ADCO controller rendering/fallback path,
- package inclusion and installed parity checks.

Exit criteria:

- old ADCO/text-only consumers remain compatible,
- orchestrated DIR workers cannot directly surface client decisions or write host truth,
- release and installed package contain identical contracts and assets.

### Phase 5: Future Apps SDK productization

Consider only after the Skill-based MVP proves repeated value.

Build a dedicated MCP Apps SDK component when DIRcreative needs persistent component state, reusable shared installation, authenticated project data, or tool-backed writes across ChatGPT clients.

This is not required for the first release.

## Validation Plan

### Schema and semantic tests

- valid spec for every supported view intent,
- reject unknown stage gate or action,
- reject more than two primary actions,
- reject missing fallback,
- reject source artifact without version/hash,
- reject component state presented as artifact truth,
- reject write owner mismatch,
- reject ADCO worker direct-client action,
- reject lock/accept/complete actions without current gate confirmation.

### Visual tests

- render at 320, 736, and 1024 px,
- light and dark theme,
- keyboard-only path,
- visible focus,
- no clipped labels or nested scrolling,
- reduced-motion path,
- accessible summary for SVG/chart/graph,
- no console errors,
- primary interaction visibly updates the view.

### Conversation tests

- rough idea,
- complete idea,
- midstream premise change,
- longform 60s shot plan,
- missing asset intake,
- prompt-only handoff,
- generation authorization boundary,
- QA failure and one-variable retry,
- Goal-mode simulation,
- ADCO orchestrated worker,
- unsupported visualization fallback.

### Release gates

Extend:

- `scripts/validate_project.py`
- `scripts/dircreative_chat_surface_audit.py`
- `scripts/dircreative_visual_dogfood.py`
- `scripts/dircreative_readiness_audit.py`
- `scripts/dircreative_objective_audit.py`
- `scripts/dircreative_release_gate.py`
- installed parity and package verification.

The release gate must verify both the interactive path and the text fallback path.

## Acceptance Criteria

The integration is accepted only when:

1. A new user can identify current stage, presented work, required decision, and downstream effect without reading a file.
2. Every required gate has exactly one primary decision surface.
3. Inline cards have no deep navigation, no nested scroll, and no more than two actions.
4. Large shot/reference/QA views open in fullscreen or degrade to a legible fallback.
5. A click alone never becomes a lock, acceptance, completion, or generation authorization.
6. Submitted selections appear as human-readable conversation turns before authoritative write.
7. Artifact IDs, versions, hashes, locks, stale state, and receipts remain canonical.
8. Unsupported surfaces complete the same workflow using Markdown/Mermaid.
9. `standalone_chat` and `orchestrated_worker` preserve their current ownership boundaries.
10. Repo, release artifact, and installed Skill pass parity and validation.

## Risks and Controls

| Risk | Control |
| --- | --- |
| Visualize preview availability differs by account or surface | Mandatory text/Markdown/Mermaid fallback |
| Generated HTML changes style or behavior between runs | Versioned domain spec plus small reusable templates and deterministic audits |
| One card becomes a miniature application | One-decision rule, two-action limit, fullscreen for rich tasks |
| Component state drifts from artifact state | Three-state contract and confirmation echo |
| User mistakes review surface for final truth | Persistent `preview_only` boundary and authoritative write owner |
| ADCO and DIR both try to control the user | Optional capability negotiation and ADCO-only client ownership in worker mode |
| Dense film data becomes unreadable on mobile | Stage-specific summaries, progressive inspection, responsive visual tests |
| New UI bypasses current safety gates | Every action must map to an existing typed stage gate and negative fixture |

## Recommended First Implementation Slice

Start with six surfaces that prove the architecture without touching media generation:

1. stage context strip,
2. idea brief map,
3. director-room concept comparison,
4. story beat ribbon,
5. script timing bands,
6. compact shot timeline.

This slice covers the complete early conversation, exercises select/mix/revise/confirm, and remains fully testable with existing fixtures. Reference graphs, model cards, and QA comparisons should follow only after the state and fallback contracts pass.
