# Video distillation: design and acceptance

Status: local source candidate, not a published or installed release.

## Problem and ownership

DIR can plan shots, assets, sound and model prompts, and its Skill Stack already
declares `film_study`. It lacked a reference-media route and an evidence-bound
report connecting external video analysis to craft transfer and source learning.
The extension adds a Studio route, one conditional craft reference, a local
bridge and isolated tests. It does not duplicate the external downloader,
Workbench, `film-breakdown-distiller`, shot schema or generation adapters.

The bridge records media identity and imported candidate intervals/frames;
Codex performs interpretation. Workbench's review-copy dimensions, synthetic
scene grouping, default sound tags and machine confidence are not source truth.
Raw ASR is also not verified dialogue. Unknowns are expected, not errors to fill.

When external credentials are unavailable, an explicitly requested host-model
substitution reads the analyzer's actual system prompt, per-frame schema and
aggregation code. The host inspects each frame, emits the exact neutral payload,
and calls only the analyzer's pure payload validator. A companion dataset names
the real executor and input digests; it is not written as an OpenAI/MiniMax
provider receipt and cannot satisfy the analyzer's human-review gate. Whole-film
craft interpretation is a separate authored layer. This avoids pretending that
a deterministic summary is a full visual-model analysis.

## Design function

The central output is a causal review, not a genre description:

`reference effect → original need → actual gap → targeted change → reinspection`

The twelve-axis transfer table is authoring guidance, not twelve automatically
generated or machine-certified production artifacts. Existing production owners
create the requested output, which the controller must inspect.

Every proposed improvement must explain why it serves the viewer and where it
can be inspected. Before/after artifact references accompany actual iteration
claims. Structural validity, complete fields and passing tests cannot establish
creative parity. Mechanisms remain candidates until an original-transfer trial
has independent evidence; no auto-promotion in the local helper.

## Sequence and exit criteria

1. Inspect the source: verified media, explicit coverage, reviewed examples,
   source/inference separation and research sufficient for the decision.
2. Complete the method report and compare existing DIR owners. Missing modules,
   integration gaps and untested behavior must not be confused.
3. Implement only authorized source changes in a branch. Verify routing,
   unchanged external gates, evidence tamper rejection and context budget.
4. Independently review design/function and accept only locally reproduced
   improvements. Record disagreements and remaining limits.
5. Only then run an authorized original film through existing preproduction:
   script, sound, shots, actual assets, generation-unit plan and ledger.
6. Compare the actual outputs with the same effect criteria. Iterate the weakest
   necessary link. Explicitly defer temporal/video-only claims until footage.

Side effects remain distinct: source edit, image generation, video generation,
installed-skill replacement, client delivery and release. Analysis does not
authorize the rest. Runtime self-learning proposes changes; authorized source
maintenance is a separate invocation. No hidden scheduler or global rewrite.

## Evidence from the initial local trial

The six-minute public reference produced 149 Workbench candidate intervals.
Visual triplets revealed intervals crossing actual cuts; a separate lower
scene-threshold pass produced 193 candidate boundaries. Neither count is ground
truth. Raw ASR repeated the final question with reversed/beyond-duration timing.
These findings justify importing evidence conservatively and retaining unknowns.

Independent code review found a study-route early return before delivery gates
and mutable media metadata accepted as fact. Regression tests must protect
side-effect precedence and recomputed media properties, not merely happy paths.

## Later interface PRD (not an implementation requirement)

The user should not reopen an awkward browser page for every adjustment. The
existing Visual Workspace project documents a native stdio MCP App, selectable
images, notes, task-context insertion, revision conflicts and negotiated
inline/fullscreen/PiP. These are a stronger reuse candidate than a separate
web application. This is repository-documentation evidence, not fresh host
acceptance. A specifically named “ChatGPT Vision” implementation was not yet
identified; do not claim parity or invent its API.

Research target: selected shot → image/source comparison → editable line or
change note → dependency impact → user-readable proposal → controller adoption.
Keep one source of truth. Panel edits must bind project/version/shot IDs; only
accepted changes update production records. Show stale downstream items and
preserve unaffected assets. File presence or localStorage is not host adoption.

Acceptance for a future implementation: reopen the same project without duplicate
approval, select a frame and carry its exact identity into the current task,
review a dialogue change and affected duration, avoid cross-project stale writes,
and verify actual host close/reopen/resize behavior. Fallback: images and concise
numbered change requests in the existing conversation. No panel code is added
by this video-distillation change.

## Research sources (read 2026-09-01)

- [Frame.io: animation editing](https://blog.frame.io/2019/07/15/animation-editing/):
  practitioner account of radio-play and animatic stages; applicable to early
  timing decisions, not proof of any particular AI creator's process.
- [ASC: Star Wars Rebels](https://theasc.com/article/star-wars-rebels-animated-allies/):
  lighting concepts derived from boards; supports separating look continuity
  from scene-specific lighting decisions.
- [Runway: Gen-4 prompting](https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide):
  incremental motion controls and visible action; model-specific guidance, not
  a universal limit or a guarantee of output quality.
- [ComfyUI: Wan2.2](https://docs.comfy.org/tutorials/video/wan/wan2_2): official
  first/last-frame route; illustrates a possible state-control strategy, not
  evidence of which model made the reference film.

## Validation

Run route self-test, context-budget audit and
`python3 -m unittest discover -s tests -p test_video_distill.py -v`.
Media tests use temporary synthetic inputs and require ffmpeg/ffprobe. The
production study stays outside the source package. Full project validation and
independent review complement these checks; no tests certify artistic parity.
