---
name: entity-resolver
description: >
  Resolves entity mentions in text inputs against the entity catalog.
  Use for long inputs (>5k tokens) or batch processing of folders (via /link-folder).
  Runs the full entity-linker pipeline in an isolated context and returns only
  a summary + paths to annotated output files.
tools:
  - Read
  - Write
  - Bash
skills:
  - entity-linker
  - input-preprocessing
model: inherit
isolation: worktree
---

# entity-resolver Subagent

Runs the entity-linker pipeline for long inputs or batch folder jobs. The parent session spawns this subagent so its context window stays clean — only a 5-line summary returns.

## Usage

Spawned automatically by `/link-folder <path>`. Can also be spawned manually for long single files that would blow the parent context.

## What it does

1. For each input file:
   - Detect source type
   - Preprocess
   - Call `resolve_link_text` with `{interactive: false}` (headless)
   - Write annotated output to `<input_dir>/annotated/<filename>`
2. Aggregate stats: files processed, auto-linked, ambiguities queued, new candidates staged.
3. Return summary: `{processed: N, output_paths: [...], pending_review: M}`.

## Notes

- Plugin-compatible frontmatter — no `hooks`, `mcpServers`, or `permissionMode`.
- `isolation: worktree` is declared; verify support at runtime (see Task 14 in plan).
- If a file produces ambiguities, they land in `pending_disambiguation` for the user to drain via `/review-staged` in the next interactive session.
