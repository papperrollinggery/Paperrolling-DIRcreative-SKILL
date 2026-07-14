# Channel Playbooks

Verified: 2026-05-14

Purpose: force the agent system to adapt structure, pacing, visual language, sound, and deliverables to the target channel.

## Channel Decision Matrix

| Channel | Primary success metric | Structure bias | Visual bias | Sound bias |
| --- | --- | --- | --- | --- |
| Film short | Emotional or thematic completion | Setup -> escalation -> turn -> resolution | Cinematic blocking, motivated camera, coherent geography | Dialogue/ambience/score must support story |
| Commercial / product film | Recall, persuasion, product clarity | Hook -> problem/desire -> product proof -> memory beat/CTA | Product hero, use case, packshot, controlled lighting | VO/BGM/SFX often critical |
| Short drama | Retention and episode continuation | Hook -> conflict -> escalation -> reversal -> cliffhanger | Vertical close-ups, readable emotion, fast scene economy | Dialogue and reaction timing dominate |
| Short video / social | Stop-scroll, replay, share, conversion | First 1-3s hook -> value/action -> payoff/CTA | Platform-native framing, captions, face/object clarity | Sound hook, captions, VO, music trend |
| MV / concept film | Mood, rhythm, motif, identity | Music sections -> visual progression -> emotional peak | Motif repetition, color progression, rhythmic cuts | Music first; visuals follow audio structure |

## Film Short

### Required questions

- What is the protagonist trying to do?
- What changes emotionally by the end?
- What is the central image or visual motif?
- Is the ending resolved, ambiguous, or cliffhanger?
- Is dialogue necessary, or can performance and blocking carry it?

### Recommended output structure

```text
logline
theme statement
character want/need
3-5 beat outline
treatment
shot list
visual bible
sound plan
```

### Prompt requirements

- Include location geography before close emotional shots.
- Use motivated camera movement tied to character psychology.
- Keep one main action per shot.
- Use ambience and silence intentionally.

### Common failures

- Looks like a trailer but has no story.
- Too many style words, no blocking.
- Beautiful frames but no emotional turn.
- Shot list lacks continuity between directions and eyelines.

## Commercial / Product Film

### Required questions

- What is being sold or remembered?
- What problem, desire, or status does the product answer?
- Is the product a hero object, background brand, or narrative trigger?
- What is the required CTA?
- What duration: 6s, 15s, 30s, 60s?

### Recommended output structure

```text
creative brief
audience insight
single-minded proposition
hook
proof/demo beat
product hero shot
packshot
CTA
cutdown plan
```

### Prompt requirements

- Product shape, logo area, material, and handling must be locked in reference images.
- Product shot must have dedicated macro or hero frame.
- Use packshot or final memory beat if applicable.
- Keep claims out unless user provides validated copy.

### Common failures

- Product is visually inconsistent between shots.
- The story hides the product.
- CTA is missing.
- Prompt over-focuses mood and under-specifies product use.

## Short Drama

### Required questions

- What is the opening hook?
- What conflict appears in the first few seconds?
- What is the reversal?
- What question forces the next episode?
- Is the format vertical?

### Recommended output structure

```text
episode premise
opening hook
conflict ladder
reversal
cliffhanger
vertical shot plan
dialogue/reaction plan
```

### Prompt requirements

- Favor faces, reactions, and readable emotional states.
- Keep locations simple and reusable.
- Use close-ups and medium close-ups.
- Track eyeline and screen direction tightly.

### Common failures

- Too cinematic and too slow for short drama.
- Wide shots waste vertical frame.
- Conflict is explained instead of shown.
- Cliffhanger is weak or missing.

## Short Video / Social

### Required questions

- Why would someone stop scrolling?
- What is the first visible action or object?
- Is the content sound-on or sound-off first?
- Does it need captions or text overlays?
- What is the replay or share trigger?

### Recommended output structure

```text
hook variants
beat-by-beat script
caption plan
visual action plan
sound hook
CTA or interaction prompt
```

### Prompt requirements

- First shot must be readable without context.
- Use strong subject motion or reveal.
- Text overlays should be separately planned, not left to video model text rendering.
- Generate a silent/caption-safe variant if platform behavior demands it.

### Common failures

- Slow opening.
- Weak first frame.
- Captions omitted.
- Music assumed but not specified.

## MV / Concept Film

### Required questions

- What is the music structure?
- What visual motif repeats?
- What changes between verse, chorus, bridge, or drop?
- Is performance, narrative, or abstract imagery dominant?
- Should camera movement follow rhythm or contrast it?

### Recommended output structure

```text
music map
motif list
color progression
performance/narrative/abstract ratio
beat-synced storyboard
lighting progression
```

### Prompt requirements

- Audio is the structural spine.
- Visual references must lock motifs and palette.
- Shot timing should align with music sections.
- If video model cannot reliably generate audio, keep audio plan for post-production.

### Common failures

- Treats MV like a normal story scene.
- Visuals do not follow musical rhythm.
- Motif changes randomly.
- Sound strategy is absent.

## Default Channel Inference

When user provides only one sentence:

1. If it has product/brand/offer, infer commercial.
2. If it has episode conflict, status reversal, revenge, romance, or cliffhanger, infer short drama.
3. If it has platform-native behavior, challenge, tutorial, or social hook, infer short video.
4. If it references a song, rhythm, performer, or mood montage, infer MV.
5. Otherwise infer film short or cinematic test.

The system must present the inferred channel and ask for confirmation only when the channel changes the deliverable substantially.

## Sources

- TikTok creative best practices: https://ads.us.tiktok.com/help/article/creative-best-practices
- StudioBinder shot list guide: https://www.studiobinder.com/blog/shot-list-template-free-download/
- Runway Academy prompting guide: https://academy.runwayml.com/guides/prompting-guide
