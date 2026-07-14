# Client Film Hard Gates

Verified: 2026-07-04

Purpose: turn client-facing relationship, anniversary, brand-story, and one-minute proposal failures into blocking DIRcreative gates. This is a production contract, not a style suggestion.

## Core Rule

Client-visible story films must move through these gates in order:

```text
source brief
-> customer-readable story preview
-> timed script and VO budget
-> detailed shot rhythm
-> per-shot asset/reference contract
-> locked-shot prompt plan or prompt-only handoff
-> client-language review
-> structural validation boundary
```

Prompt writing, image generation, video generation, PPT building, and client-visible storyboard pages are blocked until the earlier gates are visible and resolved. A validated structure is not the same thing as a client-sendable deck, strong writing, beautiful visuals, or licensed material.

## Story Gate

The story gate must show a customer-readable story preview before scripts, shots, prompts, or deck pages.

Required output:

- 2 or more real story paragraphs that can be read to the client, not short direction labels.
- The emotional arc, relationship logic, reveal or turn, and ending action in narrative language.
- A `preserved_brief_requirements` list that keeps every source-brief requirement not explicitly removed by the user.
- `omitted_requirements_without_user_removal: []`. Anything omitted without user deletion blocks downstream work.
- Old routes, alternate directions, customer props, and client-provided story bones remain preserved until the user removes them.

Prop ellipsis rule:

- If the brief says something like `telescope, snack basket, tie-dyed cloth...`, the ellipsis means examples, not a closed list.
- Expand the ellipsis into one role identity, prop, action, and shot function per friend/character.
- Do not only copy the first three objects. If the friend count is known, the expansion must cover the friend count.

## Script Gate

A 60-second film must have a duration budget and a VO budget before shot design.

Required output:

- `target_duration_sec: 60` or the explicit duration requested by the user.
- Time budget by story section and edit rhythm.
- VO budget with readable VO text, estimated words, start/end seconds, covered shot IDs, and covered seconds.
- One VO line may cover multiple shots, but the mapping must be copyable and unambiguous.
- Do not write placeholders such as `VO marks this shot segment`, `VO标注本镜头句段`, or internal notes in the VO field.

## Shot Gate

A 60-second film cannot treat 12 customer story sections as the full shot list.

Required output:

- `story_sections_count` for client narrative sections.
- `rhythm_points_count` for the edit rhythm.
- For 60 seconds, at least 30 shot/rhythm points unless the user explicitly accepts a slower format in writing.
- Each shot/rhythm point must include seconds, timecode, shot size, camera position, camera movement, subject action, emotional function, props/characters, asset source, and vertical composition consideration.
- Hero or expression-critical shots need a reference video, reference motion note, or precise movement reference.

The shot card must support a director and editor, not only summarize the story.

## Storyboard Writing Standard

Storyboard page text must read like a director explaining the film:

1. Story first: what changes emotionally or narratively in the shot.
2. Camera language second: shot size, position, movement, blocking, and transition.
3. Material or confirmation point last: source image, missing prop, reference motion, or client confirmation.

Do not reduce a storyboard page to three short bullets, internal production labels, or a production spreadsheet.

## Visual Storyboard Requirement

A PPT storyboard page may use 3-6 images, but it must preserve readability.

Builder requirements:

- Images must not be distorted.
- Use consistent aspect ratios per page; crop rather than stretch.
- Each image region must be large enough to inspect character, prop, action, and composition.
- Captions belong under the image and must carry full story/camera/source meaning, not one-word labels.
- For vertical-first films, reserve a 9:16 crop-safe zone and avoid putting faces, key props, or text near the edge.

## Asset And Reference Gate

Before any new image prompt or generation call, DIRcreative must create a per-shot asset contract.

Each shot declares:

- source decision: live action, UGC, reference video, existing Grok image, existing ChatGPT image, existing ImageGen image, prompt-only, or new image prompt,
- asset owner and file/path/status when known,
- whether browser/local intake is complete,
- whether the asset is for planning, client preview, direct video input, or PPT storyboard illustration,
- usage page or shot ID,
- missing items and blocker status.

If the user says there are existing browser images, downloaded images, Grok images, ChatGPT images, or ImageGen outputs, intake is mandatory before declaring an image missing or regenerating it. Browser/local intake may be manual when tools are unavailable, but the output must state `TOOL_BLOCKED` or the inspected paths.

Reference video and music are part of the same gate:

- Hero, acting, movement, and expression-critical shots need a reference video, reference clip, or explicit motion description.
- Music, video, and existing image sources must keep source, usage, and lock status in the contract so later versions cannot silently drop them.

## Prompt And Generation Gate

Image prompts are downstream of locked shots.

Every new image prompt must bind to:

- locked shot ID,
- character/role identity,
- prop or client object,
- subject action,
- shot size,
- camera angle/position,
- horizontal/vertical composition,
- usage page or downstream shot,
- asset source decision from the per-shot contract.

Do not create generic "clean images" before the story, script, shot, and asset gates are locked. If generation is not available or not authorized, produce `prompt_only` handoff text with the exact shot position and use case.

## Client Language Gate

Customer-visible copy must not expose internal workflow terms.

Forbidden in customer-visible text:

- `prompt`
- `thread`
- `worker`
- `gate`
- `AI`
- `执行过程`
- `内部`
- `素材权限`
- `可授权`
- `需确认`
- `客户稿里标成`

Risk and production limits must be translated into client-readable production boundaries. Internal blockers, tool states, authorization questions, and workflow labels belong in internal checklists or receipts.

## Thread Discipline

If the user asks for multi-threaded DIRcreative work, DIRcreative must use real Codex Thread dispatch, receipt, adoption or rejection, and cleanup evidence.

Do not simulate a director group, worker lane, or review thread inside the current chat and call it a Codex Thread. If real Codex Thread tooling or isolated worktree creation is unavailable for writable worker work, stop and report `TOOL_BLOCKED`.

## Acceptance Boundary

`scripts/validate_project.py`, `dircreative_client_gate_contract`, and any PASS result can only prove structural coverage of the contracted gates.

They do not prove:

- the client can receive the deck,
- the writing is good,
- the visuals are good,
- referenced assets are licensed,
- music/video usage is cleared,
- live user acceptance has happened.

Final delivery still requires professional review, asset/license review, and explicit live user acceptance when the project scope requires them.
