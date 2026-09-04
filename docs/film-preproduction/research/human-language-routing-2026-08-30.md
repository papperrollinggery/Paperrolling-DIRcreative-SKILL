# Human-language routing research

Status: local workflow evidence, not a corpus to copy.

## Observed usage

### Shanhaijing second iteration

The Studio task began with DIRcreative and image generation, then loaded
`de-AI-writing` only after the user explicitly said the script, PPT, README and
reports must “说人话”. This exposed a routing gap: the repository already had
de-AI and humanizer rules, but an ordinary whole-film route did not reliably
apply them to all audience-facing text.

The project also shows why plain-language cleanup cannot be universal. Its
novel/screenplay voice uses mythic register, coined terms, poetic compression
and character-specific diction. Flattening those features into casual modern
Chinese would remove authored value rather than AI residue.

### RTBC V10 storyboard descriptions

The RTBC task loaded `humanizer-zh` after the user rejected mechanical,
template-like picture descriptions. The useful behavior was not a copied phrase
list. The task changed the target role to “what a director or storyboard artist
would write”: short, concrete, tied to visible action, and free of repeated
“画面中 / 呈现 / 逐渐 / 强调” narration. It also protected literal SUPER text.

This worked because language review stayed attached to the shot's production
function and exact source copy. Humanizer output alone was not treated as
approval.

## Integration decision

- `de-AI-writing` remains the optional inline bounded fidelity refiner; it is
  not a second Skill Stack owner.
- Explicit “说人话 / 去 AI 味 / 自然一点”, or a draft that still reads like a
  template, selects `shuorenhua` through `human_language_revision`.
- `humanizer-zh` remains diagnostic-only when validation is needed.
- One pass owns the rewrite. Do not stack multiple naturalizers by default.
- Build a `VOICE PROFILE` from approved samples before genre-sensitive work.
- Protect facts, exact claims, literal SUPER, names, coined terms, character
  diction, genre register and intentional poetic rhythm.
- Judge naturalness against the real speaker and deliverable: character,
  narrator, screenwriter, storyboard artist, client PPT or production report.

The desired result is authored, readable text with stable meaning. It is not
uniform casual language and it does not imitate either source project's copy.
