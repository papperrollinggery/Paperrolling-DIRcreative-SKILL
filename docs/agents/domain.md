# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Layout

This repo uses a single-context layout.

Expected optional files:

- `CONTEXT.md` at the repo root
- `docs/adr/` at the repo root

## Before exploring, read these

- `CONTEXT.md` at the repo root, if present.
- `docs/adr/`, if present. Read ADRs that touch the area you're about to work in.

If these files do not exist, proceed silently. Do not flag their absence or suggest creating them upfront. The producer skill `/grill-with-docs` can create them later when project terms or decisions are resolved.

## Use the glossary vocabulary

When output names a domain concept, use the term as defined in `CONTEXT.md`. Avoid drifting to synonyms the glossary explicitly rejects.

If the concept is not in the glossary yet, treat that as a signal: either the language is not part of the project yet, or there is a real documentation gap to capture later.

## Flag ADR conflicts

If output contradicts an existing ADR, surface it explicitly instead of silently overriding it.
