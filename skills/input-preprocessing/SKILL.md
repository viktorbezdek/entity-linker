---
name: input-preprocessing
description: >
  Standalone text cleaning for entity-linker pipelines. Detects source type and
  applies the right cleaner (ASR, email, markdown, HTML, plain).
  TRIGGERS: "clean up transcript", "parse speaker turns", "normalize timestamps",
  "strip email headers", "flatten markdown", "preprocess this text".
model: inherit
tools:
  - Read
---

# input-preprocessing Skill

Reusable text preprocessing for any pipeline that ingests text. The entity-linker skill calls this automatically; other pipelines (Echelon, intelligence agent) can also use it standalone.

## API

```python
from entity_db.preprocess import clean, detect_source_type

source_type = detect_source_type(raw_text)  # or pass --type flag
clean_text = clean(raw_text, source_type)
```

## Source Types

| Type | Detection | Cleaner |
|------|-----------|---------|
| `email` | `From: <email>` header | Strip headers, signatures, quoted replies |
| `asr` | `[HH:MM:SS]` timestamps | Strip timestamps, speaker labels, fillers |
| `markdown` | `# heading` patterns | Strip formatting, preserve text |
| `html` | `<html>` tag | Extract text, strip tags and entities |
| `plain` | fallback | Pass-through (no-op) |

## Email Preprocessing Sub-items

- **(a)** Strip `From:`, `To:`, `Cc:`, `Subject:`, `Date:`, etc. at top.
- **(b)** Strip RFC 3676 signatures (`-- ` followed by name block).
- **(c)** Strip quoted replies (`>` lines, `On DATE, wrote:` blocks).
- **Deferred to v1:** email local-part as aliasing hint.

## Reference Files

- `references/asr.md` — ASR-specific noise patterns
- `references/email.md` — email header list, signature heuristics
- `references/markdown.md` — markdown element stripping
- `references/html.md` — HTML entity handling
- `references/plain.md` — plain text conventions
