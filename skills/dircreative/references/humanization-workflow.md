# Layered humanization workflow

Use this contract when the user wants text to sound authored, asks for de-AI
editing, or requests a diagnosis of machine-shaped prose. It applies to film
stories, treatments, scripts, storyboard descriptions, reports, README copy,
release notes, tickets, and production communication.

The goal is not word replacement. Determine what makes the text feel generated,
where that defect lives, and how much intervention the evidence supports. A
surface vocabulary pass cannot repair a mechanically arranged story; a story
rewrite is unjustified when only two sentences are stiff. IDs, timecodes, SUPER,
approved facts, claims, quoted material, and dialogue are protected content:
they may be revised only when the task explicitly includes that unit and the
accepted finding plus preservation contract permits it.

## Decision before editing

For an obvious short edit, DIR may write directly from the supplied text and
context. Use the planner when layered diagnosis, document-scale work or a formal
execution record is needed; do not make it an entry toll for one natural line.
Build that plan with `scripts/dircreative_humanization_plan.py`. The planner binds:

- operation: `write`, `review`, `refactor`, or `recreate`;
- text profile: narrative, general professional prose, or a supported venue;
- scope and defect depth;
- language, VOICE PROFILE, protected spans, and venue samples;
- known author/executor model identity without guessing from prose;
- the allowed depth of change and a content-addressed preservation set for a
  full rewrite;
- a document/genre guard carried into provider selection, rather than left as
  prose advice beside the execution path.

Planner status is not execution status. Every ready plan starts with
`execution_status=not_run`, `text_revision_applied=false`, and
`completion_claim_allowed=false`. For a new screenplay, build the plan before
the first full draft so the selected architecture/write owner actually governs
the text. A later self-authored review cannot retroactively prove adoption.
For new writing, an internally authored character/register note is a
`project_register_contract`, not proof of a source-author VOICE PROFILE.

Diagnosis is layered and evidence-bearing:

1. Narrative architecture or professional venue: premise delivery, causal
   tidiness, scene function, stance, relevance, and domain conventions.
2. Discourse: paragraph or scene questions, information order, middle-section
   collapse, transitions, emphasis, and structural position patterns.
3. Surface: word choice, syntax, redundancy, rhythm, cliché, specificity, and
   spoken naturalness.

Read each relevant layer separately. Every finding needs a short quote and a
finding ID, cluster ID, source span and whitelist verdict. Do not produce an
authorship probability or a combined “AI score.” Intentional voice, venue
conventions and isolated hits cannot enter the editable finding set. The deepest
confirmed cluster sets the maximum repair depth; layers without a confirmed
cluster stay unchanged. Refactor and recreate require accepted finding IDs
before any edit pass.

Short local edits can remain bounded, deriving constraints from the supplied
passage without a two-sample author corpus. Chinese contextual or voice-sensitive
edits use `shuorenhua`; an explicitly selected Chinese fidelity cleanup can use
`de-AI-writing`; short English edits use DIR's bounded method. A long narrative,
document-level revision, systemic defect, explicit Sepia request, or
venue-specific professional document selects the layered Sepia route. The
provider is chosen from language, scope, defect depth, voice risk, and requested
operation. Installation alone does not select a provider.

## Operation contracts

| Operation | Required behavior |
| --- | --- |
| `write` | Choose domain and architecture before drafting; review discourse and surface only after a complete draft exists. |
| `review` | Produce findings with short quoted evidence and stop. No editing. |
| `refactor` | Diagnose first, accept findings, then build a source-bound protected-content baseline before repairing the deepest confirmed layer. Preserve every unaffected layer and compare the baseline after the edit. |
| `recreate` | Extract actual facts, claims, intent, quotations, dialogue, and protected spans before writing fresh. Bind the source and entries by hash. Missing or self-contradictory preservation evidence blocks execution. |

`auto` is an intake convenience: new text maps to `write`; local defects map to
`refactor`; unknown defects map to `review`; systemic defects map to
`recreate` only when the preservation set is ready.

## Intervention decision

| Evidence | Decision |
| --- | --- |
| No confirmed cluster | Return the diagnosis and leave the text unchanged. |
| Local surface cluster in a short passage | Bounded revision of accepted spans, then protected-content diff. |
| Repeated discourse cluster | Layered refactor; keep architecture and unaffected paragraphs. |
| Architecture/venue failure with salvageable structure | Layered refactor from that layer downward. |
| Systemic architecture failure where surgery would cost more than rebuilding | Recreate only after the source-backed preservation set is ready. |
| Narrative voice is distinctive but no approved sample/profile exists | Diagnose, then stop before refactor/recreate until a VOICE PROFILE is derived. |
| Candidate signal is whitelisted, isolated, or intentional voice | Record it as passed/advisory; do not “fix” it. |

Do not choose depth from length alone. Length controls context and cost; defect
location controls intervention. A long clean script remains unchanged, while a
short structurally broken synopsis can require recreation.

## Two-stage edit authorization

For `refactor` and `recreate`, the first Sepia call is always `review` with
findings-only authority. Its diagnosis artifact includes the actual source text
and hash, document/profile, source-bound quotes, layer, severity, cluster,
whitelist verdict and recommended operation. The second selector call may grant
edit authority only when:

- accepted finding IDs are nonempty, unique and refer to non-whitelisted
  findings in that exact diagnosis;
- the document type maps to the selected Sepia profile;
- narrative work carries an approved VOICE PROFILE sample, while professional
  work carries venue samples or explicitly selects the domain baseline;
- refactor and recreate both carry a source-bound protected-content baseline;
- recreation has an accepted systemic architecture/venue finding and its
  preservation source matches the diagnosis source.

Missing evidence returns `humanization_edit_evidence_required`; it cannot fall
back to a generic rewrite owner.

Calibration samples must contain substantial source text, a content hash,
source kind and logical source reference; narrative voice and venue corpus modes
need at least two samples. The selector binds those references and marks host
readback required. A typed reference is not itself proof of approval: the host
must read the referenced source before applying the provider result.

The full source baseline applies to document-scale Sepia refactor/recreate. A
bounded local cleanup keeps its smaller protected-span contract and does not
inherit this document-level payload.

After provider execution, validate a separate
`humanization_execution_gate_v1` receipt with
`scripts/dircreative_humanization_execution_gate.py`. It binds the plan, draft
and result hashes, every required provider/validator run, protected-content
diff, overcorrection check and read-aloud review. `plan ready`, self-test PASS or
a prose review memo cannot replace that receipt.

## Context budget

An inline source is limited to 64 KiB. Diagnosis, accepted findings,
calibration and preservation are counted as one isolated evidence payload with a
128 KiB Studio ceiling; the receipt reports both actual and allowed bytes. A
larger source blocks with `humanization_evidence_context_budget_exceeded` (or a
source-size error) instead of silently truncating. Move long-form work to a
file-backed/chunked workflow that preserves one global architecture diagnosis
and source hash before editing chunks; do not split blindly by character count.

## Layer order

Narrative work uses architecture, discourse, then surface style. Professional
work uses the venue/domain contract, professional pass, then surface style.
Paraphrasing a structurally machine-shaped story is not a structural fix.

For narrative work, especially screenplays, corpus findings are advisory. Do
not inject a subplot, direct reader address, fourth-wall break, named reference,
nonlinear time device,
delayed revelation, or rarity move merely because it appears in a human/AI
comparison. A corpus difference is a question to inspect, not a generation
instruction. The story, genre, duration, information plan, and approved film
design decide whether a move belongs. There is no fixed quota of “human” moves.

## Calibration and false positives

- Aim at the target genre and venue band. Do not invert every suspected AI
  feature.
- One word, one em dash, one clean paragraph, or one formal sentence is not a
  defect. Rewrite only confirmed clusters or a concrete venue mismatch.
- Select a small number of useful structural moves; leave ordinary sentences
  and uneven depth where they are natural.
- Never add fake mistakes, forced slang, invented specificity, fictional
  evidence, or a casual register that conflicts with the venue.
- Preserve the author's verified habits. A declared voice method is opt-in and
  operates inside the venue/genre contract; it does not excuse repetitive
  sentence recipes or formula endings.

## Provider routing

`sepia` is the layered method owner for `sepia_humanization`; the operation,
reference profile, document type, genre guard, and preservation hash are bound
in the selector receipt. `shuorenhua` is a conditional Chinese sentence-layer
pass only when Sepia quotes a remaining cluster. `de-AI-writing` is an optional
bounded Chinese fidelity pass, not an English route and not a second structural
editor. `humanizer-zh` is findings-only validation through
`human_language_diagnosis`; it never receives rewrite authority. These
providers run in separate passes and no rewrite pass is repeated by a validator.

For a refactor/recreate provider handoff, require all of the following in the
application contract:

- `diagnosis_before_edit=true`;
- accepted finding IDs;
- document type and `humanization_guard_sha256`;
- for recreate, `source_text_sha256` and `preservation_set_sha256`;
- post-edit protected-content diff and an overcorrection check.

The preservation set carries the actual source text. Its hash is recomputed, and
every entry points to an exact source span. Hashes prove that the same source and
set reached each stage; they still do not prove that extraction was complete or
correct. Before recreation, compare every category, reject invented entries and
record why any category is `not_present`.

The supported Sepia profiles load only the needed references: narrative,
professional, release notes, developer replies, postmortems, tickets, or
technical articles. If Sepia is unavailable, an operation-bound Sepia request
blocks instead of silently claiming equivalent analysis from DIR.

## Model fingerprints

Author and executor identity are separate. Only user statements, document
metadata, or the actual system context may establish them. Never infer the
author model by reading the prose. Version-matched prose guidance can be
operative; family-only or other-version guidance is a prior; missing guidance
is `none`. Model tables guide inspection and do not prove authorship.

The installed Sepia 0.5.0 GPT prose table targets GPT-5.6 and its narrative table
targets GPT-5.4. Treat both as priors for Astra; do not relabel them as a measured
Astra fingerprint or a validated Chinese detector. Current official model
guidance can inform execution behavior without changing those research labels.

## Chinese expression

Choose the smallest intervention that improves the actual passage. Check who
would say the line, what they want from the listener, spoken stress and breath,
and whether the surrounding image already conveys the explanation. Preserve
Chinese topic omission, varied sentence length, genre diction and deliberate
restraint when they work. In client prose, retain the responsible party, facts,
uncertainty and next action. Removing a useful qualification to sound concise
is a loss, not a style improvement.

Do not translate English word lists into Chinese bans, enforce idioms or slang,
insert mistakes, remove every metaphor, or end every exchange with an aphorism.
For short dialogue the model's direct draft may already be sufficient. For a
whole scene or systemic repetition, Sepia's architecture/discourse pass can be
useful, followed only by the Chinese edits the resulting draft still needs.
Compare outputs on meaning, voice, causality and readability; no route guarantees
the best text merely because a newer model or a Skill was selected.

## User-facing controls

Expose plain controls rather than schemas:

- only diagnose / minimal revision / full rewrite / new draft;
- bounded sentence cleanup / layered structural cleanup;
- target venue or genre;
- VOICE PROFILE and protected material;
- findings grouped by layer, with quoted evidence and accept/reject controls;
- maximum allowed structural change.

The future adjustment panel can render these six controls directly. Until then,
record them in the route receipt and summarize the selected operation, deepest
confirmed layer, provider reason, preservation boundary, and next review action
in ordinary language. A user should be able to correct the decision without
editing JSON.

## Evidence boundary

This workflow adapts the installed Sepia 0.5.0 method and its cited research.
Measured corpus associations do not prove that a text is AI-authored, and the
manual workflow is not the published classifiers. Every final revision still
requires factual, voice, and read-aloud review against the actual target text.
