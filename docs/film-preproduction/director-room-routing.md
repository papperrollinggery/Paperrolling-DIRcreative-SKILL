# Director-Room Automatic Routing

This contract decides whether DIRcreative opens the director room before it asks the user for a creative choice. It prevents a non-trivial advertising-film or film-preproduction request from falling into a single generic reply, while keeping simple language work fast.

The executable source of role contracts and behavior cases is `docs/film-preproduction/schemas/director-role-harness.yaml`. The one canonical typed council result contract is `docs/film-preproduction/schemas/director-room.yaml`. Run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_director_harness_audit.py` after changing either contract.

## Routing Decision

Use this order for every standalone chat request after resolving the outer execution context:

1. Apply the absolute typed lightweight exception for explicit non-creation language. A request that says not to create and only to explain stays lightweight even when it names scripts or storyboards.
2. Evaluate the overall multi-artifact intent before bounded or generic lightweight words. If a request asks for an advertising film, promotional film, brand video, short-form video, shoot, or shot plan plus at least two output groups such as concept direction, script, storyboard, shot plan, production plan, title, or copy, it enters the director room. An incidental `标题`, `一句`, `title`, `tagline`, course, review, or distribution subject cannot swallow the larger production job.
3. Only then apply the remaining bounded typed lightweight exceptions for commentary/影评, courses, distribution, explanation-only work, and line edits, followed by generic lightweight signals. A genuinely title-only, one-line, rewrite, translation, proofreading, or single factual request remains lightweight.
4. For remaining requests, check for both a film-preproduction domain and an artifact-creation intent. When both are present, schedule `阶段: 导演组会议` automatically as the next substantive creative stage. Do not ask the user to name Producer, Director, or any other seat first.
5. When either signal is absent, use the lightweight path. A lightweight answer can clarify the request, but it must not manufacture a council, claim council work occurred, or lock a creative direction.

This is semantic routing, not word matching alone. `广告片通常多长？` is a single question and stays lightweight. Film review, film-course, distribution, existing-shot explanation, and `不要创作……只解释……` requests stay lightweight. `请对这支广告片的专业分镜进行评审` is a professional preproduction review and enters the director room. `做一支品牌宣传片，包含创意方向、完整脚本、分镜和拍摄镜头，最后顺带给一个标题和一句文案` is a complex multi-artifact intent and must open the director room.

Automatic routing never skips an earlier unresolved brief gate. When the initial request lacks a confirmed project brief, show the required idea-intake gate first; once that gate is resolved, director room is the mandatory next substantive creative stage.

## What Automatic Entry Does

Automatic entry creates a `director_room` stage gate with `status: needs_user` until the user chooses a direction. The controller reads the role harness, assigns the default bounded lanes, and gathers role judgments before showing options:

- `creative_story_lane`: creative director, director, screenwriter.
- `production_image_lane`: producer, cinematographer, production designer, editor, sound designer.
- `model_continuity_lane`: model prompt engineer, continuity QA.

For substantive standalone work, use the thread policy in `thread-orchestration-protocol.md`: every true Codex Thread lane requires a `lane_id`, real thread id/class, dispatch record, worker receipt, adoption decision, and cleanup status, and each role card links to its lane thread. If the user explicitly requires true Codex Threads and that tool is unavailable, return `TOOL_BLOCKED`; do not substitute simulated role passes. Simulated role passes are limited to a non-explicit `standalone_chat` small gate with no durable artifact work and a recorded fallback reason. In `orchestrated_worker`, do not dispatch nested lanes: execute only the handoff-selected sub-skill and return `open_questions` to ADCO.

## Role Harness Contract

Every activated seat must use its complete entry in `director-role-harness.yaml`, then emit the canonical typed role-card shape in `director-room.yaml`. Each result card declares:

- bounded `inputs`;
- sourced `evidence`;
- one craft `judgment`;
- a typed `quality` result;
- the downstream `handoff`;
- the smallest `retry` and stop condition;
- its lane/mode `execution` provenance.

The controller can group seats into professional lanes, but grouping never erases an individual seat's judgment, evidence boundary, or failure ownership. A role name, empty mapping, or untyped summary is not a contribution.

## Council Output Contract

The user must be able to see that the director room happened. Before the recommendation, the frontstage output includes:

1. `阶段: 导演组会议` and distinct role cards with craft judgments.
2. A discussion round that makes the relevant production pressure visible.
3. At least two useful disagreements, not manufactured agreement.
4. A clear arbitration/ruling plus resolution notes that turn each useful conflict into a downstream production rule.
5. Two or three user-visible directions, each with why it works, its tradeoff, and its reference-pack implication.
6. One recommendation and exactly one user decision question.

The council may recommend, but it cannot lock final direction before a real user choice. A fixture may simulate a choice only when marked `simulated_fixture`.

## Failure And Retry

| Failure | Smallest corrective action | Stop condition |
| --- | --- | --- |
| A role card is missing its professional judgment or evidence | Re-run only the missing seat card against the same locks | The missing input is a user-owned decision. |
| The room contains no useful disagreement | Run the narrowest pressure test on channel, story, production, or model risk | There is no factual basis to choose between the positions. |
| The recommendation has no ruling or downstream rule | Arbitrate the one unresolved conflict and write its production rule | The ruling would lock a user-owned creative direction. |
| A simple rewrite or factual question was escalated | Return to the lightweight path and do not claim director-room work | The user expands the request into a multi-artifact creative task. |
| A model or platform claim is unsupported | Mark it unverified and remove it from the recommendation | Source verification or account authorization is required. |

Do not retry by rewriting the whole creative package. Preserve accepted brief locks, change one smallest artifact, record the reason, and return to the earliest owning gate when the failure crosses roles.
