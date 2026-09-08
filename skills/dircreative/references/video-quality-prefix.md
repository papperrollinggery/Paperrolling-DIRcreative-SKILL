# Video quality prefix

Use `build_video_quality_prefix(payload, unit=None)` only for a video prompt
submission. Put its twelve ordered lines once before a whole-film submission or
once before each independently submitted generation unit: Style,
Cinematography, Lighting, Color, Camera, Skin, Acting, Physics, Composition,
Continuity, Technical, Audio. Do not add it to a static character sheet, image
reference board, or a shot body repeatedly.

The formatter reads existing PromptIR look, camera, composition, locks and
audio fields. An optional caller-owned `video_quality` mapping can explicitly
override a line without becoming a required PromptIR schema field. Structured
scene lighting and atmosphere take priority: a night-fire scene does not acquire
a sky/window source, and `intensity: none` does not acquire haze. An explicit
animation or CG style wins over the photoreal cinema baseline.

For `native` and `reference_audio` routes, the Audio line carries the authored
dialogue, ambience, music and SFX. For `postproduction`, `none` and `unresolved`
routes it only carries the post-production audio boundary; it must not claim
that authored dialogue or music is generated natively. `exact_text` omits the
default no-subtitles direction.

Use `wrap_video_prompt(payload, prompt, unit=None)` when attaching the prefix.
It removes only old top-level `Continuity:` and `Look:` sections because their
facts now live in the prefix; Timeline-internal Camera, Audio and Look change
sentences remain intact.

“8K”, “IMAX”, “24 fps” and “180-degree shutter” are requested visual/motion
intent in prompt text. They do not assert a provider API setting, execution
receipt, or verified output resolution. The prefix contains only model-facing
creative direction; keep routing, model parameters, QA and management records
outside it.
