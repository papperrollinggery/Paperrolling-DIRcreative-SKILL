# Project Hygiene

Use this reference only when an explicit DIRcreative request operates on an
existing project directory, the user says new materials were added, or Studio
will create multiple files. Do not load it for a bounded text-only Fast task.

## Inspect without multiplying files

Run `python3 scripts/dircreative_workspace.py scan <project>` once before copying
or creating a project structure. The scan is read-only and writes nothing.

- Read supplied materials in place. Do not copy them into a DIR-specific ingest
  folder merely so they can be parsed.
- Reuse one physical owner for an identical asset. Record a path and content hash
  when another output needs the same bytes.
- Count reclaimable bytes by physical inode, not path count. Hard links and
  zero-byte files contribute zero reclaimable bytes.
- Treat `project.yml`, `AGENTS.md`, `AGENTS.override.md`, `.gitignore`, `CONTEXT.md`,
  and other root controls as policy/configuration, never as loose source media.
- Keep source, current working output, client-visible delivery, and regenerable
  QA/cache roles distinct. A version label is not a reason to duplicate bytes.
- Never move, rename, delete, hardlink, or replace a user file merely because the
  scan found a duplicate. `FinalDelivery` and equivalent protected delivery
  folders are never auto-modified and always require manual review.

If the scan finds loose root materials or exact duplicates, finish the requested
creative artifact first, then make one concise organization offer with the
counts and avoidable bytes. Do not create an audit report for the offer. When the
user wants a durable plan, run `dircreative_workspace.py plan`; it atomically
replaces the single `.dircreative/workspace-plan.json` instead of accumulating
dated reports. Actual file changes still require explicit approval of the exact
plan.

## Output lifecycle

- Fast: keep state and drafts in the answer; create no project state file.
- Studio: keep one current working file per requested deliverable. Persist only
  when pausing, resuming across sessions, or producing multiple real files.
- Delivery: create a new immutable file only for a real milestone or user-visible
  handoff. If an old immutable version already remains at a stable path, index it
  there instead of copying it into an archive.
- QA, previews, contact sheets, renders, and transport bundles are regenerable.
  Put them in one replace-current cache/staging location and retain only the
  current inspection set. Create a new immutable version only for a real
  milestone or user-visible handoff.

In an ADCO exchange, DIRcreative does not reorganize host files. Return the
duplicate/loose-material summary and recommended ownership; ADCO remains the only
host lifecycle owner.
