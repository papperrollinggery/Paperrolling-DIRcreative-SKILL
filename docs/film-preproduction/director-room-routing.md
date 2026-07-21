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

## Execution Budget

- one controlling agent;
- zero Threads by default;
- at most three perspectives;
- at most one independent critical pass;
- no nested dispatch;
- no user-visible role cards.

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
