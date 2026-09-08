# Director Room Adaptive Routing

Verified: 2026-07-19

This document owns v2 perspective selection. The repository router first chooses
Fast, Studio, or Delivery; Director Room never overrides that mode.

## Decision Order

1. Repository maintenance is outside Skill runtime.
2. A bounded revision stays Fast.
3. A valid complete multi-output film request enters Studio.
4. Generation authorization and client delivery stay Delivery.
5. A valid ADCO handoff executes only its selected provider scope and never opens
   a nested Director Room.

## Perspective Map

| Task evidence | Selected perspectives | Director Room |
| --- | --- | --- |
| One sentence, paragraph, or bounded copy change | `narrative_strategy` | no |
| Existing script local revision | `narrative_strategy`; add `visual_production` only if screen execution changes | no |
| One shot optimization | `visual_production`; add `model_continuity` when generation or identity can drift | no |
| Small storyboard review | `visual_production`, `model_continuity` | no |
| Prompt compilation | `visual_production`, `model_continuity` | no |
| Complete advertising film, broadcast TVC, or multi-output Studio development | `narrative_strategy`, `visual_production`, `model_continuity` | yes |

Do not route by a broad word such as “script” or “storyboard” alone. Scope,
requested outputs, existing artifacts, and whether the user asks for revision or
full development determine the result.

## Photography during conception

Within `visual_production`, involve photography while story beats and blocking
are still being designed. Jingzao can contribute its current cinematic-shot and
shot-tension methods through the existing Studio collaborator selection; it
does not require finished assets or a locked shot table to advise. Read and
apply the selected provider before claiming its participation. If unavailable,
make the local photography judgment explicitly without inventing a provider run.

Give the photographer the intended viewer experience, current causal beat,
supplied facts, actual reference roles and known geography. Distinguish hard
story/identity/custody/topology constraints from proposed focal lengths, crops,
camera heights and screen layouts. Tentative choices remain redesignable;
user-approved choices stay authoritative. Return a usable proposed view and
its effect on acting, movement, reveal and the neighboring cut. DIR integrates
that advice into the story and canonical shots before downstream compilation.
An unresolved visual idea can change staging or a beat in the same creative
pass; do not wait until the script is final to discover the scene cannot work.

Design variety as information progression. A wide view may establish a route,
barrier, scale or hidden observer; a medium view carries body/hand interaction;
a close view reveals a clue, decision or reaction. Choose only useful views for
the scene, allowing sustained takes and deliberate repeated setups. Lens labels
alone do not create variety: vary viewer position, subject/environment ratio,
depth and what is revealed or withheld. Do not make every view wide, frontal,
equally sharp, spectacular or tightly cropped.

When references matter, inspect their images and name the mechanisms worth
carrying: for example a dark aperture around a distant lit court, asymmetric
negative space, overlapping planes or material/value separation. Identify how
each adopted mechanism participates in an actual story shot; an attractive
location asset alone does not carry it into the film. Preserve world geometry
while allowing the new camera projection. With no reference, design those
relationships from the brief and world rules; missing images do not justify a
generic close-up or a mandatory reference hunt.

Keep the result in the current treatment/shot cards, not a new mandatory form.
Carry adopted photographic choices into the existing Jingzao frame handoff.
At compilation, a real conflict returns to its source decision; do not silently
flatten a working composition to satisfy a generic readability default. A
detail that cannot be read in the wide can receive a motivated insert.
Set readability at that shot's scale: an establishing view can prove an exchange
through posture and object silhouette; its insert proves fingertip separation.
Do not copy close-up demands for facial or finger detail into every wide-frame
field. Check the actual image's crop, depth and action phase; a focal-length
label or requested subject percentage is not evidence that the view was made.

## Execution Budget

- one controlling agent;
- zero Threads by default;
- at most three perspectives;
- at most one independent critical pass;
- no nested dispatch;
- no user-visible role cards.

## Explicit Collaboration

The budget above is the default, not a ban on an explicit collaboration request.
The existing `dircreative_route.py` result owns `collaboration`; perspective
selection consumes the routed task and must not classify its mode again.

| User request | Execution intent |
| --- | --- |
| Invoke the creative group or director group | Main-thread professional perspectives; no worker claim |
| Ask those groups to work jointly/in parallel, or explicitly request subagents | Actual host subagents, at most two independent assignments |
| Explicitly create new tasks or request real Threads | Host task/thread capability, only for the requested scope |
| Quoted example, negated invocation, historical report, explanation, or conditional suggestion | No new dispatch permission |

The creative group contributes strategy, story, character motivation and writing;
the director group contributes performance, shots, space, edit and sound. These
are responsibility areas, not fixed seat counts. Keep bounded edits Fast even
when a group is named. One main controller integrates the artifact. Choose only
independently useful assignments; when a request only names perspectives, work
locally. Do not substitute user-visible tasks for subagents.

Before an actual dispatch, inspect the tools and supported parameters exposed by
the current host. Use its subagent capability for `host_subagents`; use its task
capability only for `host_threads` when the user explicitly requested a new task
or Thread. Give each worker a bounded output, source facts, write scope, acceptance
criteria and return format. Keep scopes disjoint and preserve the user's current
model/settings; neither group names nor this plan prove a runtime model choice.
Source maintenance and ADCO workers never dispatch through this runtime.

The route returns `execution_status: not_dispatched` and `dispatch_receipts: []`.
It does not invoke tools. After a real call, retain only the host-returned agent
or task identifier, requested scope, actual completion/status evidence and the
returned artifact; the controller reviews the artifact before adoption. A planned
role, invented identifier or textual roleplay cannot populate that evidence.
If the capability is unavailable, report `TOOL_BLOCKED` for the requested
delegation and continue independent local work without claiming real teamwork.
Existing external gates remain effective; collaboration cannot authorize media,
external delivery or nested dispatch.

Ten v1 roles remain detailed knowledge in
`docs/film-preproduction/schemas/director-role-harness.yaml#legacy_v1_role_contracts`.
They are not activation seats. New results use the three v2 perspective IDs.

## Output Order

1. requested artifact or recommendation;
2. selected professional judgments;
3. material conflict only when one exists;
4. options only when the user requested a choice or a conflict requires one;
5. one open question only when blocked.

Aligned judgments record `no_material_conflict`. There is no minimum disagreement count. A direct optimization request receives the optimized result, not a meeting record.

## Compatibility

`director_room` schema v1 is accepted read-only. Do not add fields to or rewrite
an existing v1 fixture. A migrated result is a new v2 artifact with explicit
source provenance. New runs default to v2.
