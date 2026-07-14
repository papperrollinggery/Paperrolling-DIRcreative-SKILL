# Cyber Courier Concept Options

## Option A: The Alley Accepts The Package

Logline:

> A rain-soaked courier delivers a sealed package to a forbidden alley and realizes the address is alive enough to recognize it.

Best for:

- 15s cinematic test,
- Seedance multi-reference continuity,
- storyboard/reference board workflow.

Strengths:

- One protagonist, one prop, one location.
- Strong visual progression.
- Clear suspense without dialogue.
- Easy to test camera, lighting, prop, and scene continuity.

Risks:

- Needs precise environment blocking so the alley does not change between shots.
- Final reveal must be simple.

## Option B: The Courier Is Being Watched

Logline:

> A courier crosses a neon alley while hidden observers track the package from every reflection around him.

Best for:

- noir surveillance mood,
- more camera experimentation,
- possible multi-screen / reflection motifs.

Strengths:

- Strong visual style.
- Natural use of security camera POV and reflections.
- Good fit for thriller tone.

Risks:

- Too many implied observers may exceed 15s.
- Model may invent extra characters.
- Requires tighter QA for reflections and eyelines.

## Option C: The Package Changes Hands

Logline:

> A courier reaches the alley endpoint, but the person who takes the package is the same courier from the future.

Best for:

- sci-fi twist,
- short drama hook,
- social platform cliffhanger.

Strengths:

- Strong ending.
- Good for episodic expansion.
- Creates a memorable story question.

Risks:

- Requires second character/identity control.
- Time paradox adds complexity.
- Harder for first reference-pack MVP.

## Recommendation

Choose Option A for the first full workflow.

Reason:

- It is the cleanest test of the system's intended chain.
- It forces the workflow to handle character, prop, scene, blocking, shot design, audio policy, and model adapters.
- It avoids extra story complexity before the production grammar is stable.

Selected direction:

```yaml
selected_concept: "The Alley Accepts The Package"
target_duration: "15s"
shot_count: 5
audio_policy: "visual-first, rain ambience and scanner beep as optional video/audio adapter notes"
reference_pack:
  - character_board
  - environment_blocking_board
  - prop_board
  - director_storyboard_board
```
