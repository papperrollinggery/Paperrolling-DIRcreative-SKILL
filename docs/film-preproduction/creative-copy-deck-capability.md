# Creative, Copy, And Deck Narrative Capability

Verified: 2026-07-10

Purpose: give DIRcreative a source-grounded creative brief, a fidelity-preserving copy workflow, and a deck narrative contract before any presentation is built.

## Scope

This capability produces decisions and specifications. It does not create a PPT, generate slide images, change the ADCO exchange contract, or treat a presentation tool as the source of creative truth.

The durable artifacts are:

- `docs/film-preproduction/schemas/project.yaml`
- `docs/film-preproduction/schemas/story-package.yaml`
- `docs/film-preproduction/schemas/deck-narrative-spec.yaml`

## Creative Foundation

Creative work starts by separating three kinds of material:

- `facts`: statements that can be traced to source evidence.
- `source_evidence`: a source type, locator, short summary, and verification status.
- `inferences`: DIRcreative judgments derived from named facts, with confidence and an audience-facing disclosure policy.

A fact without `source_evidence_ids` is not ready to support a concept, claim, or deck slide. An inference must name the fact IDs it depends on. An unverified source may remain in the project, but it cannot be presented as confirmed evidence.

The `source_evidence`, `facts`, `source_samples`, `claims`, story and deck `beats`, and `slides` collections fail closed. Each must be an array of mappings, every required ID must be a non-empty unique string, every required field must be present, and every referenced ID must resolve. Non-mapping items, duplicate IDs, blank IDs, and free-text fallback are blocking errors.

For commercial work, the brief must also lock:

- `audience_tension`: the audience's current state, felt pressure, desired change, and evidence.
- `business_objective`: the intended business result and a usable measurement signal.
- `single_minded_proposition`: one audience-facing promise supported by facts.
- `avoid_cliches`: familiar category shortcuts, visual tropes, slogans, and story moves this project will not use.

These fields are decision inputs, not copy prompts. Empty strategy language such as "build awareness" or "make it cinematic" does not pass unless the audience pressure and intended change are concrete.

`audience_tension.evidence_ids` must resolve to source evidence. `single_minded_proposition.support_fact_ids` and every inference fact reference must resolve to facts. Story source bindings must preserve the tension, proposition, and inference sources used downstream; every story beat must resolve its fact and inference IDs through those bindings. Deck source constraints must resolve through the same story binding chain.

## Concept Substitutability Gate

A concept is too generic when a competitor, another product, or another character can replace the subject without changing the story mechanism.

Before story approval:

1. Record at least two plausible `alternatives`, each with a unique `alternative_id`, subject, and proximity reason.
2. Select one alternative by ID and copy its subject into `swap_subject`.
3. Record `before_swap` and `after_swap` without changing the concept wording or beat order.
4. Record whether it `still_works_without_rewrite`.
5. Reference at least two existing `broken_dependency_ids` that make the original subject necessary.
6. Record `concept_author_id`, then require an `independent_reviewer` whose reviewer ID differs from the author ID; a self-declared independence boolean alone is insufficient.
7. Use `verdict: distinctive` only when the swap breaks the mechanism, proof, relationship, setting, or payoff.

If the swapped concept still works, return to concept development. Renaming the protagonist, product, or setting is not a creative correction.

## Copy Workflow

The copy sequence is fixed:

```text
real source samples
-> VOICE PROFILE
-> DIR professional judgment
-> de-AI fidelity refinement
-> humanizer diagnostic review
-> manual craft review and execution reconciliation
```

### 1. Real source samples

Use 5 to 20 representative samples when available. Prefer recent original writing, real client-facing text, approved launch copy, or working correspondence over generic platform examples. If fewer than five samples exist, record the shortage and lower the voice-profile confidence.

Every sample requires `sample_id`, `source_ref`, `excerpt`, `why_representative`, and `recency`. Sample IDs must be unique. Missing provenance fails the source set instead of being skipped.

Do not infer a personal or brand voice from an adjective list alone.

### 2. VOICE PROFILE

The profile must be source-derived and operational. It records author, goal, confidence, source sample IDs, rhythm, compression, capitalization, parentheticals, question use, claim style, preferred moves, banned moves, CTA rules, and channel notes.

Exactly one `voice_profile` mapping is authoritative. Its unique `source_sample_ids` must cover every collected sample; any deliberate omission requires `coverage_shortfall_reason`. A source set below five also requires `sample_shortfall_reason` and cannot retain high confidence.

The profile describes observed behavior. It must not invent quirks to make the writing appear human.

### 3. DIR professional judgment

DIRcreative then decides what the audience needs to understand, feel, believe, or choose. The judgment must state channel fit, audience effect, factual boundaries, tradeoff, and approved claim IDs.

Voice matching cannot replace this step. A faithful imitation with no useful decision or production judgment still fails.

### 4. de-AI fidelity refinement

Use `de-AI-writing` as a fidelity-preserving edit after the meaning and claims are locked. Record protected meaning points, factual additions, and whether new claims were added.

The pass condition is:

- core meaning remains intact,
- evidence and claim boundaries remain intact,
- no unsupported example, number, or conclusion is introduced,
- `factual_additions` is empty unless separately sourced and approved,
- `new_claims_added` is false unless those claims re-enter approval.

### 5. Humanizer diagnostic review

Use `humanizer` or `humanizer-zh` only as an anti-pattern diagnostic after the fidelity pass. It may flag clusters such as repeated road signs, binary contrast shells, inflated significance, vague attribution, uniform paragraph structure, or formulaic three-part phrasing.

A word-list hit is not proof of AI authorship and cannot fail copy by itself. A trace cluster produces `review`, followed by a contextual edit decision. The reviewer must preserve intentional voice, quoted language, technical terms, and approved claims.

Set:

```yaml
humanizer_diagnostic:
  authority: diagnostic_only
  manual_review_required: true
  may_fail_copy_by_itself: false
```

when a cluster is present.

The detected cluster set, `humanizer_diagnostic.trace_clusters`, `manual_craft_review.reviewed_ai_trace_clusters`, and `copy_execution.ai_trace_clusters` must agree. A detected cluster remains `review` only; it has no failure authority, and the diagnostic mapping may not add a hidden blocking or authorship authority. Separately, manual craft review must assess rhythm, abstraction, and evidence alignment. Word-list-clean copy can still fail when that professional review records `needs_revision` or evidence detachment.

## Claim Approval

Every audience-facing factual or performance claim must have a `claim_id`, `approval_status`, and evidence IDs. `copy_execution.claim_ids_used` may reference only approved claims.

Approved claims must bind verified evidence. `copy_execution.evidence_ids_used` must cover the evidence behind every used claim and resolve through the story source bindings. The audience-facing text must be non-empty, and every copy execution status must match the validated VOICE PROFILE, DIR judgment, de-AI, manual-craft, and humanizer state.

Pending, rejected, unreviewed, or missing claims block audience-facing copy and deck use. Rephrasing an unapproved claim does not make it approved.

## Deck Narrative Spec

`deck_narrative_spec` is the handoff between approved creative material and presentation production. It is required before slide authoring when the requested deliverable includes a deck.

The communication job must complete this sentence:

```text
By the end, [audience] should [outcome] because [central takeaway].
```

The story arc must name an opening tension, at least three cumulative beats, and a closing resolution. Every beat needs one audience question, one narrative job, one primary claim, evidence, an audience shift, and a transition to the next beat.

An agenda is not a story arc. Slide order must create a reason for the next slide to exist.

### Slide contract

Every slide has:

- one `beat_id`,
- one narrative job,
- one takeaway title,
- one authoritative `primary_claim_id`,
- one primary claim,
- traceable evidence,
- one layout family and composition,
- one primary visual role,
- an explicit text-density budget.

Visible copy is for the deck audience. Do not expose prompt notes, timing scaffolds, model instructions, production commentary, or internal approval language on slides unless the audience needs it.

Avoid dashboard-like card grids, pills, repeated modular panels, and dense internal worksheets by default. Image-led story proposals should use large, confident visual zones and enough negative space for the claim to read. Layout choice must follow the narrative job, not a template's decorative pattern.

The primary claim ID is authoritative; the rendered claim text may not substitute for or contradict the approved claim register. Beat and slide claim IDs, evidence IDs, and beat IDs must resolve through `source_constraints`. Slides may contain only the audience-facing narrative fields and layout metadata defined by the schema; prompt notes, model instructions, production commentary, or internal approval text fail the frontstage boundary. Deck QA records are recomputed against the arc, one-job-per-slide mapping, claims, evidence, layout, audience copy boundary, and delivery route; stale passing booleans fail.

## Presentation Routing

| Requirement | Route | Rule |
| --- | --- | --- |
| Editable PowerPoint or local deck | `Presentations` | Default. Text, charts, images, and shapes remain element-level editable. |
| Native Google Slides | `Presentations`, then the supported native import route | Build and verify the editable presentation before import. |
| Full-slide generated images accepted by the user | `codex-ppt` | Allowed only after explicit acceptance that slide contents will not be separately editable. |
| Visual taste or aesthetic references | `high-end-visual-design` may inform references only | It has no authority over PPT construction, editability, or presentation QA rules. |

`default_route` must remain `Presentations`. Selecting `codex-ppt` without `user_accepted_full_slide_images: true` is a blocking route error. Do not silently trade editability for visual consistency.

This capability stops at the narrative spec. It does not invoke either presentation route.

## Skill Responsibilities

- `idea-intake`: records facts, source evidence, inferences, audience tension, business objective, proposition, and avoid-cliches before creative direction.
- `story-development`: binds the approved foundation into the story package and runs the concept substitutability gate.
- `script-treatment`: runs the source-derived copy sequence, enforces claim approval, and prepares `deck_narrative_spec` when a deck is requested.

No skill may skip upstream story or script approval to begin slide production.

## Audit

Run:

```bash
python3 scripts/dircreative_creative_copy_deck_audit.py
```

The audit proves:

- a complete reference bundle passes,
- missing evidence or audience tension fails,
- a substitutable concept fails,
- a missing VOICE PROFILE fails,
- an unapproved claim fails,
- an AI-trace cluster produces review without a blocker,
- word-list-clean but rhythmically mechanical, abstract, evidence-detached copy fails manual craft review,
- malformed arrays, duplicate IDs, blank IDs, and cross-binding breaks fail closed,
- incomplete deck arc, layout, editability, or presentation authority fails.

Reported counts and readiness flags are computed from the executed reference, adversarial cases, fixture outcomes, and filesystem output scan. They are not hard-coded declarations.

The audit does not prove that a final concept is brilliant or that a deck has been produced. Those require professional review and, for a finished deck, the selected presentation skill's own QA.

## Integration Boundary

This capability does not modify `skills/dircreative/SKILL.md`, `scripts/validate_project.py`, release gates, state files, model docs, or the ADCO descriptor, exchange, receipt, and adoption contracts. ADCO remains unaware of these private creative schema details unless a later host-owned change explicitly negotiates them.
