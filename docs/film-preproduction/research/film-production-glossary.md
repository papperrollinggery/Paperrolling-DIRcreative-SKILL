# Film Production Glossary

Verified: 2026-05-14

Purpose: provide the minimum professional vocabulary the agent system must use before it writes scripts, shot lists, storyboard prompts, or video model prompts.

## Development Documents

| Term | Definition | Used by | Prompt implication |
| --- | --- | --- | --- |
| Logline | One-sentence summary of protagonist, goal, obstacle, and hook. | Creative Director, Screenwriter | Must be resolved before outline or shot list. |
| Premise | The central story situation or dramatic question. | Creative Director | Defines what the audience expects to see tested. |
| Beat Sheet | Ordered story beats showing major changes in action, emotion, or information. | Screenwriter, Editor | Drives timing and cut structure. |
| Outline | Scene-level or sequence-level story structure without full prose detail. | Screenwriter | Should not contain final shot language yet. |
| Treatment | Prose description of the intended film experience, including story, tone, and visual feel. | Director, Screenwriter | Good input for director notes and visual bible. |
| Script | Scene/action/dialogue document. | Screenwriter | Must separate action, dialogue, voiceover, and sound. |
| Shooting Script | Script version with production-facing scene and shot considerations. | Director, Producer | Can feed script breakdown and shot list. |
| Script Breakdown | Extraction of production needs from the script: cast, locations, props, wardrobe, effects, sound, vehicles, animals, extras, etc. | Producer, AD, Production Designer | Must happen before reference image prompt planning. |
| Visual Bible | Unified visual specification for characters, locations, props, color, lighting, lenses, and texture. | Director, DP, Production Designer | Locks continuity before image prompts. |
| Shot List | Table of all planned shots with ID, duration, shot size, angle, lens, camera motion, action, sound, and purpose. | Director, DP, Editor | Primary input to storyboard prompt compiler and video adapter. |
| Storyboard | Sequential visual plan of shots, often with shot numbers, motion arrows, action notes, dialogue, and sound notes. | Director, DP, Editor | Should show camera and blocking, not just pretty frames. |
| Previsualization / Previs | Early visual simulation of shots or sequence rhythm before final production. | Director, VFX, Editor | AI video tests can serve as rough previs, not final footage. |

## Shot Size

| Term | Meaning | Use | Risk if misused |
| --- | --- | --- | --- |
| Extreme Wide Shot / EWS | Subject is tiny or absent; environment dominates. | Establish scale, isolation, geography. | Weak for emotion or product detail. |
| Wide Shot / WS | Subject visible in environment. | Establish location and blocking. | Too many wide shots reduce emotional clarity in short formats. |
| Full Shot / FS | Full body visible. | Show costume, posture, movement. | Can lose face detail in vertical short video. |
| Medium Long Shot / MLS | Knees or thighs up. | Body action with some emotion. | Ambiguous if prompt lacks blocking. |
| Medium Shot / MS | Waist up. | Dialogue, reaction, object handling. | Good default for short drama. |
| Medium Close-Up / MCU | Chest or shoulders up. | Emotion and dialogue while retaining context. | Can hide important prop action. |
| Close-Up / CU | Face or object fills frame. | Emotion, product detail, reveal. | Overuse loses spatial context. |
| Extreme Close-Up / ECU | Very small detail: eye, finger, logo, drop of rain. | Suspense, tactile detail, product macro. | Needs clear subject; video models may invent context. |
| Insert Shot | Close shot of an object or action detail. | Prop state, phone screen, lock, package seal. | Must define object continuity. |
| Establishing Shot | Location-setting shot, often wide. | Opens sequence, explains geography. | Should be brief in 15s work. |

## Camera Angle

| Term | Meaning | Use | Prompt pattern |
| --- | --- | --- | --- |
| Eye-Level | Neutral human-height viewpoint. | Realism, dialogue, observation. | `eye-level medium shot` |
| Low Angle | Camera below subject looking up. | Power, threat, heroism. | `low-angle shot looking up at the courier` |
| High Angle | Camera above looking down. | Vulnerability, surveillance, geography. | `high-angle shot from security camera position` |
| Top-Down / Bird's-Eye | Direct overhead. | Map-like spatial relation, blocking. | `top-down view showing subject path and camera path` |
| Dutch Angle / Canted | Tilted horizon. | Unease, chaos. | Use sparingly; can look accidental. |
| Over-the-Shoulder / OTS | From behind one subject toward another/object. | Confrontation, information reveal. | `over-the-shoulder shot toward the alley entrance` |
| Point of View / POV | What a character sees. | Immersion, subjective fear. | `POV shot from courier looking at the flickering sign` |

## Camera Motion

| Term | Meaning | Use | Model prompt caution |
| --- | --- | --- | --- |
| Static / Locked-Off | Camera does not move. | Tension, tableau, clarity. | For Runway use positive wording: `locked-off camera remains still`. |
| Pan | Camera rotates left/right from fixed position. | Reveal, follow lateral action. | Avoid combining with dolly unless needed. |
| Tilt | Camera rotates up/down. | Reveal height, shift attention. | Keep one subject target. |
| Dolly In / Out | Camera physically moves toward/away. | Emotional push, reveal, isolation. | Stronger than zoom for cinematic prompts. |
| Truck / Track | Camera moves sideways, often parallel. | Follow subject movement. | Good for walking/running shots. |
| Pedestal | Camera moves vertically. | Reveal scale. | Less commonly understood; include simple description. |
| Handheld | Imperfect human camera movement. | Urgency, realism, chaos. | Too much can create jitter. |
| Crane / Jib | Camera moves vertically or in arc. | Dramatic reveal. | Usually better for large scenes. |
| Drone / Aerial | High moving aerial view. | Location scale. | Often overkill for short close action. |
| Arc Shot | Camera moves around subject. | Hero reveal, emotional wrap. | Good for product/character reveal. |
| Whip Pan | Very fast pan blur. | Transition, shock. | Risky for generation; use with simple scenes. |
| Rack Focus | Focus shifts between depth planes. | Reveal information. | Needs foreground and background subject. |
| Dolly Zoom / Vertigo | Dolly and zoom in opposite directions. | Disorientation. | Advanced; reliability varies by model. |

## Lens And Optical Terms

| Term | Meaning | Use | Prompt implication |
| --- | --- | --- | --- |
| Wide-Angle Lens | Broad field of view; exaggerated perspective. | Environment, kinetic movement. | Good for narrow alley and near-camera movement. |
| Normal Lens | Natural perspective, often around 35-50mm equivalent. | Dialogue, balanced realism. | Good default for story clarity. |
| Telephoto Lens | Narrow field, compressed space. | Isolation, surveillance, beauty. | Good for noir observation shots. |
| Macro Lens | Very close detail. | Product, texture, fingertips, raindrops. | Use for prop board and insert shots. |
| Shallow Depth of Field | Background/foreground blur. | Focus attention, cinematic portrait. | Helps isolate character or product. |
| Deep Focus | Most planes stay sharp. | Blocking, geography, ensemble scenes. | Useful for environment board. |
| Anamorphic | Wide cinematic optical look, flares, oval bokeh. | Premium film feel. | Use only when visual style supports it. |

## Blocking And Continuity

| Term | Definition | Required fields |
| --- | --- | --- |
| Blocking | Actor and object movement through space. | start position, end position, path, eyeline, prop handoff |
| Screen Direction | Apparent movement direction on screen. | left-to-right, right-to-left, toward camera, away from camera |
| Eyeline | Direction subject looks. | target object/person, emotional intent |
| 180-Degree Rule / Axis | Maintains consistent left-right spatial relation across cuts. | axis line, camera side, exception reason |
| Foreground / Midground / Background | Depth layers in frame. | layer content and movement |
| Continuity | Consistency of character, costume, prop state, light, geography, and sound. | continuity locks and exception notes |

## Sound Terms

| Term | Definition | Prompt implication |
| --- | --- | --- |
| Dialogue | Spoken words by on-screen or implied characters. | Must specify speaker, language, tone, exact line if model generates audio. |
| Voiceover / VO | Narration not necessarily tied to visible mouth movement. | Safer than lip-synced dialogue for many video models. |
| SFX | Designed sound effect such as alarm, door buzz, package beep. | Add only in video/audio prompt, not pure image prompt. |
| Foley | Performed sound matched to actions, such as footsteps or cloth rustle. | Useful as post-production cue. |
| Ambience | Environmental bed: rain, traffic, ventilation hum. | Good for mood and realism. |
| Score | Composed music background. | Usually non-diegetic. |
| Music Cue | Specific point where music starts/stops/changes. | Needed for ads, MV, and emotional transitions. |
| Diegetic Sound | Sound from inside the story world, heard by characters. | Example: neon sign buzz, alley loudspeaker. |
| Non-Diegetic Sound | Sound outside the story world, heard by audience only. | Example: score, narrator, trailer hit. |
| Silence | Intentional absence or near-absence of sound. | Must be explicit if target model supports audio. |

## Image And Video Prompt Translation Rules

- Image prompts describe visual reference assets only.
- Storyboard images may include audio labels, but those labels are production metadata.
- Video prompts must restate sound decisions explicitly; do not rely on the model reading tiny board text.
- A shot list is not a video prompt. The adapter must rewrite it for each model.
- Professional terms must be paired with plain physical action when reliability matters.

## Sources

- StudioBinder shot list guide: https://www.studiobinder.com/blog/shot-list-template-free-download/
- StudioBinder storyboard camera movement: https://www.studiobinder.com/blog/storyboard-camera-movement/
- Google Veo prompt guide: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide
- Runway Gen-4 video prompting guide: https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide
