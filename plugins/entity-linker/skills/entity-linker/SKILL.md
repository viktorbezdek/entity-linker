---
name: entity-linker
description: >
  End-to-end entity resolution: reads a text file or pasted content, runs
  preprocessing, calls resolve_link_text, handles disambiguation via the
  Disambiguation App (or elicitation fallback), and writes the annotated output.
  TRIGGERS: "link entities in this", "tag mentions", "normalize names in call",
  "resolve entities against catalog", "link-file", "link-text".
model: inherit
tools:
  - Read
  - Write
  - Bash
---

# entity-linker Skill

Resolves entity mentions in text inputs (transcripts, emails, docs, Slack) against the entity catalog.

## Workflow

1. **Detect source type** — use `detect_source_type()` or `--type` flag override.
2. **Preprocess** — call the appropriate cleaner (ASR, email, markdown, HTML, plain).
3. **Resolve** — call MCP tool `resolve_link_text(text, source_type, options)`.
4. **Handle ambiguities** — if `ambiguities` non-empty and host supports Apps, open Disambiguation App via `resolve_disambiguate_app`. Otherwise use `elicit.disambiguate_span` loop.
5. **Render output** — call `resolve_render(resolutions, text, format)` (default: markdown).
6. **Write output** — save annotated file to `annotated/` directory next to source.
7. **Report** — show auto-linked count, disambiguation count, new candidates staged.

## Options

- `--format markdown|xml|sidecar` — output format (default: markdown)
- `--type asr|email|markdown|html|plain` — force source type
- `--interactive false` — headless mode (queues all ambiguities)

## Output Location

`<input_dir>/annotated/<filename>` for `/link-file`.

## Dependencies

- MCP tools: `resolve_link_text`, `resolve_disambiguate_app`, `resolve_render`
- Skill: `input-preprocessing` (auto-invoked for source type detection)
