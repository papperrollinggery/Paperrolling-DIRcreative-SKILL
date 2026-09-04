# v0.7.1 60-second preproduction regression

Date: 2026-09-04

Scope: a real local 60-second narrative project derived from the reference-video workflow; source media and project assets remain outside the public repository.

## Result

`BLOCKED_S07_SCENE_SUPPORT_TRUTH`

The project contains 18 technical shots, 30 action panels, two characters, three continuity props, two scenes, four Seedance 2.5 units, and six Seedance 2.0 units. Current DIRcreative validation preserved the complete design while rejecting two S07 image candidates that placed a hanging bell on a generated horizontal surface.

Fresh checks:

- design coverage: `valid`, 18 shots and 30 declared action phases;
- image coverage: 28/30 locally selectable; S07-P01/P02 remain `needs_revision` and `blocked_must_not_upload`;
- Seedance 2.5/2.0 visual-plan structure: `PASS` after creating a self-contained, hash-bound evidence snapshot for the current validator;
- generation units containing S07: blocked;
- video generation, platform binding, formal voice, human/client approval, and publication: absent.

This is the intended behavior. File existence, unique hashes, and readable hand action do not override a false scene/support relationship. The repair stays local to S07 and its two downstream model units; the story, other shots, and 28 accepted panels are not reset. The user explicitly deferred S07 regeneration, so this test stops at the truthful blocker.

The full local test report and visual evidence bundle are retained with the project. They are not copied into this repository and are not presented as a public reproducible fixture.
