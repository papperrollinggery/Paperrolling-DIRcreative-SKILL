# Video prompt structure and direction

Use while authoring or repairing video prompts, after selecting the existing
scenario and requested unit. This is the shared writing method, not another
router, approval gate or required form. Keep a successful supplied prompt's
structure unless the request or an evidenced conflict calls for changing it.
The source study is `docs/film-preproduction/research/prompt-structure-20260909.md`.

## Structure follows the scene

A useful prompt gives the generator a specific scene to realize: what the viewer
must notice, what exists, what changes, how it is seen/heard, and what carries
forward. Author this causal sequence before filling technical fields. Internal
IR is more detailed than the copyable text; completeness does not require every
IR field to become a heading or every shot to repeat the world description.

For a simple image-to-video beat, a paragraph naming the subject's change,
camera response and ending condition may suffice. For a multi-shot sequence,
use a compact common context followed by ordered local events:

1. **Intent and medium:** duration/aspect when supplied, dramatic or visual
   purpose, and the chosen live-action, animation, graphic or mixed treatment.
2. **Reference roles and stable facts:** only actual inputs, their jobs, recurring
   identity/geometry, and the scene relations needed to understand the action.
3. **Visible sequence:** each event starts from the current state, changes it,
   and leaves a consequence or motion for the next event. Put its camera,
   environmental response, expression and sound beside the event they serve.
4. **Shared look, sound and continuity:** establish once what really spans the
   unit; write local changes at their moment. Relevant shared look may precede
   the sequence when visual treatment is the main brief.
5. **Targeted constraints:** only unresolved misreadings that matter to this
   scene and are supported by the selected model's prompting surface.

These are content responsibilities, not five mandatory headings or a fixed
ordering. A character PV can foreground graphic language, a dialogue scene its
spoken exchange, and kinetic typography its exact text. Explicit user formats,
including a twelve-part quality block, remain valid; never populate them with
unrequested skin, haze, camera hardware, pause, frame-rate or resolution defaults.
Do not prepend model/provider/account/QA instructions to creative prose.

## Lock identity; describe changing state

Separate three kinds of information when resolving references and source truth:

- **Stable design:** face, age, body silhouette/proportions, costume construction,
  prop dimensions and connections, named architectural landmarks, world rules.
- **Incoming state:** where each entity is, facing/holding what, current contact,
  velocity, damage/wetness, emotional relation and local lighting situation.
- **Permitted evolution:** movement, grip exchange, cloth deformation, tears,
  opening/closing, reflections, light exposure, expression and damage caused by
  this sequence. Once a change happens, carry it forward until another event
  changes it; continuity does not mean restoring the pristine opening state.

Resolve contradictory facts in authoring, not by adding “except everything in
the shots” after an immutable lock. A prop may rotate while its topology stays
fixed; a coat's cut stays fixed while its hem gets wet. If an authoritative
source fixes both incompatible outcomes, surface that specific conflict and
continue only work/units independent of it. Keep the affected unit unresolved,
not submission-ready, until its authoritative state is resolved or the unit is
split without changing the source facts. Do not silently override a source lock.

Assign each reference only its actual role. Identity/style/location/motion
references are not automatically literal first frames. An actual first frame
constrains the opening pose, framing and support; an end frame guides final
arrival, not an early jump or a requirement to return to the opening. A planning
board supplies only its supported role and must not appear as panels or labels.
Do not invent attachments for placeholder tags in a copied example.

Inspect pixels as well as role labels. A photoreal identity reference, a grayscale
action board and a clean scene frame can give incompatible appearance or state
cues even when all three carry correct names. Assign one visual authority per
property; planning annotations are not that authority. When a supported motion
board is deliberately attached, use the existing direct-input gate: professional
storyboard/motion boards start `planning_only`; the actual manifest policy and
the selected exact capability card must both allow that particular reference
role, including any existing promotion/review requirement. General support for
image or motion input and a role sentence alone are insufficient. Limit the
permitted board's job and inspect the result for copied
arrows, panels, grade and pose holds. If leakage occurs, return to the approved
clean sources and change that input strategy; repeating “no arrows” is not an
input repair. Keep supported identity masters and explicit storyboard-reference
routes available; one failed annotated board does not invalidate either class.

An upload screenshot proves the visible order, not suitability or actual model
use. If renumbering changes the set of attachments, recheck the changed files'
roles, appearance and temporal state before treating the list as ready. Preserve
the observed numbering while distinguishing a proposed corrected upload plan.
Each unit gets only the references needed for it. An earlier pristine scene or
later climax frame must not silently reset a persistent effect, object ownership
or damage state. A role sentence cannot guarantee a model ignores conflicting
pixels; resolve the conflicting input when text alone has failed.

Use stable names or positional identifiers when multiple entities act. A single
unambiguous subject may use natural pronouns. Keep each action and voice owned.
When distilling a human reference, retain visible body-form evidence (shoulders,
torso/waist/hips, limb proportions, volume, pose/perspective and clothing fit);
mark unseen details unknown and do not invent measurements. Carry only the
adopted visible body facts into the prompt; the body form is not a mandatory
model-facing questionnaire. Nonhuman/product/graphic work has no skin default.

## Space, environment and appearance

Describe the few spatial relations that constrain the scene: support plane,
travel route, obstacle, destination, distance/scale, entrances or landmarks.
World positions and screen positions differ. A reverse angle or camera roll
changes the view, not the room. If the horizon inverts, give a persistent
landmark, target or trajectory to restore orientation. Do not enforce a fixed
screen-left assignment through a deliberately changing viewpoint.

Separate the persistent world from its local effects. Rain may already be
falling; a footstep displaces a local puddle; the splash trails the foot and
settles into ripples. Use the material actually present, rather than adding
stone explosions to cloth, open water or a floorless void. If a scene needs a
supporting floor, establish it before the impact. Broken structures, displaced
objects and drifting debris remain in the next view when still in its field.

The environment can also be the protagonist: light moving through an empty
station, wind lifting a curtain, a flood reaching a threshold. No human or
destructive climax is required. Still air, a flat black plane or a locked-off
view are valid choices when they serve the brief.

Translate important style anchors into visible decisions: line/shape language,
dimensionality, cadence, palette, edge treatment, surface response and selective
optical effects. Preserve requested named references as useful anchors, but do
not let a style label substitute for these choices. Separate light sources from
grade: a fixed window stays in the world while its incidence on a moving face
changes. A metal highlight, transparent edge or painted skin responds according
to the chosen medium and viewing distance. Do not force photoreal texture onto
hand-drawn work or cinematic haze/shallow focus onto exact flat graphics.

## Events have causes and available time

Use the sequence `current relation → trigger → owned action/path → contact or
miss → consequence → next available state` as an internal reasoning aid. Render
it naturally, e.g. “As the door rebounds, she catches its edge with her left
hand and slips through; the latch strikes the frame behind her.” Do not print a
seven-field form for every small motion.

One dominant event is an intelligible causal unit, not a limit of one verb or
one attack per shot. A connected dodge/counter/recovery can share a shot; several
unrelated stunts cannot become coherent just because they share a timestamp.
Keep setup/acceleration/contact/follow-through where they are needed to explain
the result. They need not each consume a separate pause: a prior recovery can
load the next move. Preserve the intended intensity and decisive contact.

Keep the other participant alive in the exchange. State what they want, attempt
and are prevented from doing; explain the temporary constraint that makes a
counter or handoff possible. Do not park a free arm or leave an opponent's punch
extended for several seconds just so the next instruction can happen. A precise
contact is a short state with consequences, not a demonstration pose to hold
until every body part has been described. Show the critical relation at a useful
scale without returning to an earlier handoff pose at the next cut.

Distinguish subject speed, camera speed, edit frequency and playback speed.
Rapid cuts or a fast camera do not by themselves make a body move fast; a heavy
object does not require the entire scene to play in slow motion. Convey speed
with purposeful travel, closing distance, support changes, brief acceleration,
background parallax and selective directional blur. Preserve readable ownership
and the decisive contact instead of covering every error with shake or a flash.

Time effects are authored choices. For a requested slow-motion accent, name the
event where it starts, what continues moving and where real-time motion resumes.
Do not add a slow accent at every impact or ban all slow motion/holds. A quiet
conversation, monumental lift or final graphic read may intentionally be slow.
A fast sequence may start already in motion and end during an unfinished attack;
do not spend its first/last several seconds on automatic establishing/hero poses.

Budget serial prerequisites rather than count verbs, shots or effects. Releasing
an embedded blade, repositioning hands and lifting it take ordered time; hair,
cloth, breath and debris may respond concurrently. If the requested sequence is
overfull, first remove repetition and move secondary responses into the same
event; then use a motivated cut/ellipsis or propose generation-unit boundaries.
Do not silently delete decisive actions, shorten the requested film, or invent
longer model capacity. Timecodes communicate intent, not guaranteed frame-level
control. Preserve exact requested timing in the plan and verify it on output.

For stylized physics, establish the exception and keep its consequences coherent:
which force permits a wall run or air turn, where it applies and what continues
after it. Anime displacement, smears, impact color and graphic holds are options
within that treatment, not requirements for all scenes. A genuinely unwieldy
weapon cannot also reverse instantly without a new force or a readable redirect.

## Camera, performance, transitions and sound share events

Choose framing by what must be read now: relationship/path, face/listening,
contact/hand ownership, material change or graphic layout. A main camera movement
may have ordered phases tied to events. For a single take, keep a continuous
camera path and focus handoffs; do not hide independent cuts under “one take”.
For a montage, name the outgoing movement/shape/sound and the incoming relation.
POV belongs to a specific observer or object; a camera watching a character from
outside is not simultaneously that character's literal eyesight. Lens numbers
express framing intent when useful, not verified physical metadata.

Write performance as a response to a person, discovery or obstacle. Bind a change
of expression/voice to the trigger, let the listener react, and preserve exact
source dialogue and speaker identity. Avoid mechanically cycling through a list
of smiles, blinks, breaths and moist eyes. Blocking and framing should let the
audience see a change in the relationship, not just decorate an emotion label.

Bridge cuts with a reason: carry a swing through its arc, reveal the target of a
look, follow a falling object, or carry a sound ahead of its source. The outgoing
state can remain in motion. At unit boundaries preserve the authored handoff;
within a unit, damage, light and emotional progression do not reset at each cut.

Attach event sounds to their source and perspective: preparation/footfall,
acceleration/cloth, contact, then material decay/reverberation. Music tempo is
distinct from visual event density; not every cut requires a drum hit. Specify
exact speech and meaningful silence only when authored. Native/reference audio
follows the selected capability; post-production cues stay in the sound handoff.

## Use the relevant scene grammar

| Scene | Main organizing question | Preserve deliberately |
| --- | --- | --- |
| Physical action/chase | What threat changes the route or initiative? | Support, distance, attack/reply, momentum and consequence |
| Character PV/weapon display | Which gesture reveals this character? | Body silhouette, expression, prop handling, graphic rhythm; no invented enemy |
| Dialogue/quiet performance | What does this line or discovery change between people? | Exact words, listener, eyeline, emotional/physical distance |
| Product/material | Which physical change proves the feature? | Geometry, contact, particles/liquid/reflection, readable end state |
| Environment/reveal | What changes the audience's understanding of the place? | World geography, scale, weather/light source and reveal order |
| Kinetic typography | When is each exact word readable, and what motion changes it? | Glyph integrity, flat/3D choice, palette, layout, rhythmic read windows |

For exact typography, partial glyphs can be transitional states if requested,
but each required word needs a complete readable state. A “white point” or
unrelated shape is not automatically permitted by a text-only whitelist. Keep
strict spelling/timing deliverable requirements separate from a generator's
verified capability; use the established finishing route when deterministic
text placement is required. Do not claim prompt wording guarantees exact glyphs.

## Review the scene, not the template

Read the exported full prompt and each independent unit, not only the IR. Check
source fidelity and conflicting locks; actual input roles; space/support and
environment evolution; causal action/performance with plausible time; camera
and transitions; selected medium/material; exact text/voice and sound routing.
Do not score success by headings, adjectives, shot count or word count.

If a rendered clip fails, record the visible failure and its time: slow playback,
long anticipation, missing contact, wrong owner, spatial reset, style/identity
drift, glyph change or audio mismatch. Compare with the actually submitted
prompt and settings. Preserve the best source, change the smallest responsible
layer, and inspect non-target deterioration. Text inspection suggests causes;
same-input controlled generations and video review are needed to establish
effectiveness. Never turn one sample, a community claim or compiler tests into a
universal model rule or a claim of proven video quality.
