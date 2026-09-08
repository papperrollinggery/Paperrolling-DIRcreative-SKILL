# Source-derived video quality direction

`build_video_quality_prefix(payload, unit=None)` forwards the authored PromptIR
look, composition, continuity and relevant audio facts once per video submission.
Empty or irrelevant categories are omitted. It supplies no default skin, acting
pause, physics style, palette ratio, composition formula, haze, camera equipment,
resolution or frame rate. The author resolves these choices for the actual scene
with `prompt-structure.md` before compilation.

The optional caller-owned `video_quality` mapping preserves explicit overrides.
If the user supplies all twelve fields, they retain this order: Style,
Cinematography, Lighting, Color, Camera, Skin, Acting, Physics, Composition,
Continuity, Technical, Audio. Fewer fields do not trigger boilerplate filling.
Unique medium, material, body-proportion and scene facts must survive adaptation;
shorter output by itself is not a quality result.

`wrap_video_prompt(payload, prompt, unit=None)` attaches that direction once.
It moves only old top-level Continuity and Look sections into the shared block;
Timeline-internal camera, audio, look changes and state transitions remain.
Do not use the video wrapper on still character sheets or image references.

Native/reference audio carries the authored sound. Postproduction/none/unresolved
routes keep finishing cues outside the model prompt and do not claim generated
speech or music. Exact-text work retains its text policy. Capability cards and
execution receipts remain the authority for real model settings; an authored
technical phrase is creative intent, not proof of output metadata.

Legacy `audio_plan` strings are shared directions, not a typed per-unit event
map. The compiler preserves them rather than guessing which speech can be
deleted. For a split film, author each unit's actual dialogue/event cues and
resolve any whole-film speech repeated in the shared plan before submission.
Locally rebased shot cues do not establish the scope of arbitrary global prose.

Shot `transition_in/out` and continuity locks travel with their shot. A
transition-plan boundary matching existing `<from_shot_id>_to_<to_shot_id>` can
be scoped to an independent unit. An opaque legacy label remains in the full
plan; it is not guessed onto an individual cut or made an error solely for its
spelling. Put a required unit-local bridge in its shot transition or explicit
boundary before export. Internal identifiers are crosswalked to readable timing;
unknown IDs, local paths and hashes are not laundered into approved references.
