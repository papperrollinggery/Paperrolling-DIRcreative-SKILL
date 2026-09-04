# Sepia, Chinese expression and Astra

Date: 2026-09-05. This is a small local qualitative evaluation, not an authorship
detector, a population benchmark or proof that one method always wins.

## Scope and evidence

The installed provider is Sepia 0.5.0. Its main Skill SHA-256 was
`f9e33423f8deacfb7f689eb3d9e350ab57d517a87ad449e0a9a02a23037c3233`.
The narrative/discourse/style method was actually read for the treatment, along
with the DIR adaptation that protects genre, voice and requested scope.

Two independent writer runs received the same three synthetic tasks. One wrote
directly; one used Sepia and DIR's existing adaptation. A third run saw anonymous
candidate labels and the requirements, without condition names or method notes.
All three were requested with `gpt-6-astra`; provider-level actual-model identity
was not independently attested. There was no human jury, repeated sampling,
audio performance test or detector measurement.

## Observed comparison

| Scenario | Blind review | Specific reason |
| --- | --- | --- |
| Short, restrained repair-worker dialogue | Both need revision; direct slightly preferable | Both over-generalized into aphorism; the Sepia version retained more written-language syntax |
| A one-minute scene with an audible threat and visible decision | Sepia-assisted preferred | Clearer action-response causality and spatial continuity; both had an unnecessary glove action |
| Client update with exact quantities and an uncertain delivery date | Sepia-assisted preferred; direct acceptable | More natural phrasing of schedule uncertainty; neither invented a promise or lost the numbers |

The direct scene contained 256 Chinese characters and the assisted scene 259.
The blind review found both within the requested range. Duration still requires
performance or audio timing. Neither shorter text nor more process was treated
as an automatic quality advantage.

## Resulting adaptation

- Obvious short edits can be completed directly from supplied context. Do not
  invoke the full humanization plan or multiple providers as a routine toll.
- The planner no longer demands a document-level author corpus before one
  bounded Chinese dialogue edit. Whole-document narrative editing retains its
  voice evidence and preservation requirements.
- Use Sepia for actual architecture, discourse or venue problems, long connected
  work and explicit requests. Run a Chinese sentence pass only for remaining
  defects. Its value here was editorial reasoning, not a list of forbidden words.
- Preserve character register, omissions, rhythm, metaphors, names and genre
  language. Test dialogue against the listener and image; test client prose
  against facts, ownership, uncertainty and next action.
- Sepia's GPT-5.4 narrative and GPT-5.6 prose tables remain historical priors for
  Astra. They are not relabeled as Astra or Chinese-language measurements.

OpenAI's current guidance recommends auditing Skill/instruction conflicts and
calibrating testing to the task. These behavioral recommendations support the
scope adjustments above; they do not establish a Chinese prose-quality ranking.
[Official Astra guidance](https://developers.openai.com/api/docs/guides/latest-model#gpt-6-astra-behavior).

Raw candidate text, the blind label map, independent critique and treatment
read/hash notes are retained in the local evaluation output. They are test
materials, not client delivery or approved film dialogue.
