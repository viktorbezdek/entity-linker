---
description: Link entities in a file and write annotated output
argument-hint: <path> [--format markdown|xml|sidecar] [--type asr|email|markdown|html|plain]
---

# /link-file

Resolves entity mentions in the given file against the catalog.

**Workflow:**
1. Detect source type (or use `--type` override).
2. Preprocess text (clean ASR/email/markdown/HTML).
3. Call `resolve_link_text` with the `entity-linker` skill.
4. If ambiguities exist: open the Disambiguation App (or elicitation fallback).
5. Write annotated output to `<dir>/annotated/<filename>`.
6. Report: auto-linked, ambiguous queued, new candidates staged.

**Examples:**
```
/link-file ~/transcripts/standup.md
/link-file report.eml --format xml
/link-file recording.txt --type asr
```
