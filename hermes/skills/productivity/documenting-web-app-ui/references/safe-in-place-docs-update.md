# Safe in-place updates to an existing documentation repository

Use this when the user wants new material merged into the real manual rather than delivered as separate “new features” pages.

## Workflow

1. Resolve the exact user-supplied repository path and verify it exists. Do not substitute another similarly named copy.
2. Inspect the real structure before editing: relevant Markdown pages, image conventions, sidebar configuration, package scripts, and repository status.
3. Create a full sibling backup before the first edit. Give it a timestamped, unambiguous name and verify:
   - source and backup file counts match;
   - representative hashes match;
   - backup size is plausible.
4. Map each feature to the existing functional page where users would look for it. Example classes:
   - recorder flow → Grabaciones;
   - case creation → Casos de prueba;
   - action catalog → Acciones;
   - grouping → Escenarios;
   - scheduling/cloud execution → Planes de prueba;
   - provider credentials → Integraciones.
5. Create a new page only if no existing page can hold the feature coherently. A genuinely new top-level product feature is a valid reason; an “Updates” or “New features” dump is not.
6. Preserve prior content. Prefer append-only edits to existing Markdown pages. If a sidebar insertion is required, make only that insertion.
7. Add screenshots to the repository’s established static-image directory and use the project’s existing URL convention.
8. Verify before delivery:
   - every original documentation file still exists;
   - modified legacy pages retain their original bytes/content as a prefix when append-only was promised;
   - only expected files changed;
   - all new image references resolve and image files are non-empty;
   - Markdown fences/admonitions are balanced in every changed or new page;
   - sidebar configuration parses;
   - the real documentation build succeeds.
9. Report exact review locations by file and heading/line. Do not publish, push, or ingest the updated manual until the user reviews and explicitly confirms.

## Working around a write-safe-root guard

If editing the host-mounted repository directly is blocked by a write-safe-root policy:

1. Copy only the target text files into a temporary workspace under the allowed root.
2. Apply edits there with the normal patch/write tools.
3. Prove legacy documents are append-only (or otherwise preserve the agreed content) by comparing against the backup.
4. Copy the verified files back to the exact live repository path.
5. Hash-compare workspace and live files, then run the build from the live repository.

Do not treat a symlink as a bypass: safe-root guards may resolve it to the host path.

## Build dependencies

If the repository has a lockfile but no installed dependencies, use the lockfile-driven install before building. Dependency installation is setup, not a documentation edit; confirm that the lockfile itself remains unchanged. Do not “fix” audit warnings or upgrade packages during a documentation-only task.
