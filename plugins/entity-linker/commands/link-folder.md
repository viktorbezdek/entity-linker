---
description: Batch-link all files in a folder (spawns entity-resolver subagent)
argument-hint: <path> [--format markdown|xml|sidecar]
---

# /link-folder

Links entities in all files within the given folder. Spawns the `entity-resolver` subagent to handle batch processing in an isolated context window.

**What happens:**
1. Spawns `entity-resolver` with the folder path.
2. Each file is processed headlessly (`interactive: false`).
3. Annotated outputs go to `<folder>/annotated/`.
4. Ambiguities and new candidates queue for later review.
5. Returns a summary: files processed, auto-linked, pending.

**After batch:** Run `/review-staged` to drain the staging queue.

**Example:**
```
/link-folder ~/transcripts/incoming/
```
