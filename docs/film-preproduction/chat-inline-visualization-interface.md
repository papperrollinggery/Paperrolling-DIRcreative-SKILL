# Chat Inline Visualization Interface

Status: normative v1.1. Read legacy `dircreative.chat-visualization@1.0` and
`dircreative.chat-visualization-writeback@1.0` records without creating their
old stage gates in new discussions.

## When and how to show

Use a view when it helps the current creative task: spatial relationships,
blocking, reverse shots, movement, coverage or a meaningful comparison. A user
need not name a plugin. A bounded wording edit needs no visual surface.

Discover the current host catalog and read its **current Visualize Skill** before
preparing response content. Follow that host's actual fragment and response
reference contract. Do not require a composer mention, pin a cache version,
guess a private protocol, or assume an HTML file is visible. If the host permits
an inline content reference, include that reference in the same reply; a file
path or a renderer PASS alone does not finish the display step.

`dircreative_visualization_render.py render-html --host-contract <current-SKILL.md>`
can prepare the response reference from the supplied host contract. It does not
send a response or certify a mount. Its output remains `USER_VISIBLE=UNVERIFIED`
and `NATIVE_VISUALIZATION=NOT_INVOKED` until there is independent host evidence.

Record the actual evidence level: offline rendering, content emitted in this
reply, host-confirmed mount, or user-confirmed visibility. An unavailable mount
readback does not block delivering valid response content or the rest of the
task. If display is unavailable, deliver the complete Markdown/table/Mermaid
fallback and continue independent work. Do not ask the user to change clients.

## Presentation and adoption

Use the smallest view that serves the current purpose. Static labeled
relationships can use Mermaid; interactive spatial or temporal comparisons can
use inline views. Use wider presentation only as permitted by the host.

| Intent | Spec behavior | Controller behavior |
| --- | --- | --- |
| View, switch camera, preview a path | `interaction_mode: presentation_only`; no `stage_gate`, no actions, no write targets, no decision question | No adoption or media authorization |
| Adopt the chosen layout | `interaction_mode: adopt`; explicit user-readable follow-up | Re-read current scene/shot revision and apply the user's decision within scope; no synonymous second approval |
| Adopt and make references | `interaction_mode: adopt_and_generate`; explicit generation request | Reuse applicable `generation_authorization`; proceed when that scope is already authorized |
| Historical decision view | v1.0 or v1.1 `decision` with existing gate | Preserve its source/ownership checks, without reintroducing a stage-by-stage wizard |

Optional decision controls use one primary action and at most one secondary
action. Ordinary viewing needs neither. The view is `preview_only` and
`writes_authoritative_state: false`; only the existing controller owns writes.
Camera/phase switching changes local presentation state only.

When the current host exposes `window.openai.sendFollowUpMessage`, adoption
buttons send readable intent with scene revision, selected shot/camera and phase.
The host may ask the user to confirm sending that message; it is not a new DIR
creative gate. Without the follow-up API, show the exact message to enter in
chat. Never let HTML call a model, mutate files, or invent a generation receipt.

## One scene, several outputs

`stage-surface-registry.json#spatial-blocking-camera` selects `blocking_camera`.
Read `skills/dircreative/references/spatial-discussion.md` for the executable
scene-to-view-to-export path. The optional `presentation.spatial_scene` is a
source-bound projection of the existing scene artifact, not another database.

A scene snapshot with entities/cameras must match the physical source JSON
exactly after removing its presentation binding fields. Its revision/hash and
`source_refs` bind to `source_truth.artifacts[].evidence_path`. Missing files,
changed hashes or edited snapshot positions fail validation. Source JSON must
remain within the active project root. Designed, observed, inferred and unseen
geometry retain their distinct evidence labels.

Discussion views can contain labels and controls. Human storyboard pages may
contain arrows. A model layout is separately exported from the same current
camera/state as a text-free image with one layout role. It is not a literal
first/last frame. Actual cinematic frames still need the real identity/scene
assets, a supported execution path and visual review.

## Source and media contracts

Every spec retains controller ownership, a source-bound presentation and a
complete readable fallback. Use `artifact_id#/path` references. `source_bound`
fields require a valid reference; `presentation_only` fields use null.
Recommendations and options bind to the same source revision when present.
Pure explanatory views do not need synthetic options, locks, decision fields or
project-file matrices.

For image previews, the renderer checks physical files and SHA-256 before data
URI embedding. PNG, JPEG, WebP and passive SVG are supported; active/external SVG,
path escapes and mismatches fail. A `real_candidate` also needs the existing
confirmed source, authorization and channel-fit evidence. Illustrative media
must remain visibly identified and cannot claim acceptance. Keep fragments
under the current host limit (1 MB for the supported contract); bound thumbnails
instead of embedding oversized originals.

Local paths, hashes, internal IDs and validation records remain in the source
spec, not visible prose. Name the actual creative subject and effect in labels
and follow-ups. The view cannot grant lock, readiness, acceptance, completion or
generation authorization.

## Ownership and writeback

In standalone chat, DIRcreative owns surface and artifact adoption. In an ADCO
worker, keep `controller.user_facing: false` and
`write_boundary.write_owner: ad-creative-orchestrator`; DIR returns a neutral
spec/fallback to the caller. This is an optional presentation capability, so a
text-only negotiated handoff remains valid.

After actual adoption, use the existing v1.1 writeback validator. Bind the
source-spec path/hash and selected action, real user intent, source revision,
artifact before/after hashes and exact write evidence. `adopt_and_generate`
additionally references an inherited, applicable authorization; it cannot create
one from browsing. Ordinary adoption never implies media authorization. Report
only real writes; fixture receipts cannot prove user adoption or generation.

Show a concise read-only confirmation after writing. It introduces no second
question. Mark affected exports and downstream prompts stale on a source change;
preserve unrelated identity, environment and successful media. Historical
v1.0 gate receipts remain readable for migration and audit.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_spec.py validate <spec.json> --project-root <active-project>
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_render.py render-html <spec.json> --project-root <active-project> --output <absolute-task-owned-fragment.html> --host-contract <current-Visualize-SKILL.md>
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_writeback.py validate <receipt.json> --project-root <active-project>
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_visualization_audit.py
```

Use actual browser interaction to verify synchronized camera/phase views,
readability at 736/360 px in light/dark, no world-position mutation, and no
follow-up from presentation-only input. Test stale-source rejection separately.
Browser previews and fixture follow-up stubs are not native mount evidence.
