# External Skill update study — 2026-09-04

## Scope

This study records the two user-named Codex tasks and the installed artifacts
that may inform DIRcreative v0.7.1. It does not vendor either external Skill or
claim that installation alone proves host adoption on a future task.

## Sepia 0.5.0

- Task: `01a05cb7-0ab6-77c1-a5e1-3c2dde95b4fc`.
- The task's first install turn failed on Codex usage; its status alone is not
  install evidence.
- Current host state contains `sepia`, `sepia-write`, `sepia-review`,
  `sepia-refactor`, and `sepia-recreate` under `~/.codex/skills`.
- The initial install check matched public source commit
  `0326635aa2cee589e6f525af1ec6089d51944f3c` from
  `https://github.com/Nanako0129/sepia.git`. A later host task shortened only
  the canonical Skill's frontmatter description, so the current installation is
  no longer byte-identical to that commit. The method body, reference files and
  four operation wrappers still match the inspected source; provider selection
  binds the current installed body hash rather than reusing the earlier receipt.
- Source license: MIT, copyright Nanako Tsai. The source version check and 41
  repository unit tests passed locally.
- No executable runtime code is shipped inside the five Skill directories;
  their content is Markdown plus interface metadata. The repository's version
  checker is not copied into the installed Skill.

Useful method elements:

- explicit `write`, `review`, `refactor`, and `recreate` contracts;
- diagnosis before editing, with narrative architecture or professional venue
  before discourse and sentence style;
- venue and author-voice calibration instead of generic casualness;
- cluster-based findings, false-positive whitelists, and deliberate slack;
- model-family/version guidance only when identity is known from a legitimate
  source; no authorship inference by reading;
- preservation extraction before full recreation;
- measured findings kept separate from editorial inferences.

DIRcreative adaptation:

- `dircreative_humanization_plan.py` diagnoses architecture/venue, discourse and
  surface separately, requires source-bound cluster/whitelist findings, and lets
  the deepest accepted cluster set repair depth;
- `sepia_humanization` binds the operation, reference profile, document type,
  hashed genre guard and content-addressed preservation evidence; refactor and
  recreate split diagnosis from edit authorization and require real
  voice/venue/domain calibration on the edit call;
- screenplay guards keep corpus-level human markers advisory and block direct
  selector calls from injecting them as mandatory story devices;
- Chinese contextual, Chinese fidelity, English bounded and layered workflows
  are distinct paths; a final diagnostic provider has no rewrite authority;
- Sepia remains an external provider. DIR does not copy its reference corpus.

## mr-li-seedance-25 1.8.2

- Task: `01a06aea-1ca6-7c12-82f2-ed32d3523ae4`.
- Source inspected from the user-supplied 1.8.2 archive outside this repository.
- Archive SHA-256:
  `d89aee976313873e14ebd516f25208bea6502ef3b989d4dba5032582de2b7fa0`.
- The task atomically replaced 1.5.0 with 1.8.2 and kept the old version outside
  Skill discovery in the host backup area.
- Eighteen installed files match a fresh ZIP extraction byte for byte. Package
  audit, YAML, relative links, explicit fresh-process discovery, and an
  independent cold review passed.
- Residual provenance risk: the archive is not cryptographically signed and its
  author/supply chain is not independently verified.

Useful 1.8.2 changes:

- project visual baseline separated from scene-dynamic facts;
- reference-role tags that state what to inherit and what not to inherit;
- voice-reference questions only for speaking roles;
- one global/style block and one complete asset/audio binding block per request
  scope, followed by natural paragraphs without internal headings;
- duration treated as an upper bound with a pre-write capacity estimate;
- cross-model context divided into rules, project truth, runtime state, and
  source evidence;
- generated-image cleanliness separated from film-grain style;
- guided production and retry from the last verified save point.

DIRcreative adaptation:

- formal Seedance 2.5 compilation routes to Studio;
- the verified visual-baseline, prompt-writing, duration, and format references
  are hash-read as one bounded provider pack;
- direct prompt ownership uses isolated craft context; compiler collaboration
  uses a separate isolated method context;
- Fast remains available for small existing-prompt edits without claiming the
  full 1.8.2 method;
- model capability facts still come only from DIR's exact official model card.

## Rejected adaptations

- No external Skill becomes a second controller or source-of-truth owner.
- No fixed visual style, director, aspect ratio, soundtrack, or example asset is
  promoted into a global default.
- No corpus statistic becomes a mandatory screenplay action or structure.
- No word-list hit proves AI authorship or triggers an automatic rewrite.
- No private path, installed external body, or backup is copied into the release.
- No claim is made that an installed Skill was applied unless the host performs
  the requested full-body/reference reads and records adoption.
