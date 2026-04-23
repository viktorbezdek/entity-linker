---
name: entity-matcher
description: >
  Reference skill for the matching pipeline: scoring model, normalization chain,
  Czech inflection rules, phonetic algorithms, and thresholds.
  TRIGGERS: "tune matching", "why did it miss this name", "explain scoring",
  "add a phonetic algorithm", "adjust thresholds", "debug matching".
model: inherit
tools:
  - Read
---

# entity-matcher Skill (Reference)

Documents the matching pipeline internals. Load on demand when debugging or tuning — not during normal linking.

## Score Formula

```
score = 0.45·lex + 0.20·phon + 0.20·type_fit + 0.10·local_recency
        − 0.05·short_pen − 0.05·ambig_pen
```

- **lex**: `rapidfuzz.WRatio(window, alias) / 100`
- **phon**: 1.0 if any shared DM/BMPM phonetic key; else Jaccard of key sets
- **type_fit**: 1.0 (matching cues) | 0.5 (neutral) | 0.0 (conflicting cues)
- **local_recency**: 1 if entity already auto-linked earlier in this source
- **short_pen**: 0.05 if alias_key < 3 chars
- **ambig_pen**: 0.05 if >2 candidates above 0.70 for same window

## Auto-link Thresholds

- **Auto**: top ≥ 0.90 AND (top − second) ≥ 0.10
- **Ambiguous**: top ≥ 0.70 (queued or shown in Disambiguation App)
- **Unresolved**: < 0.70 (may trigger new-candidate staging if entity-shaped)

## Reference Files

- `references/algorithms.md` — normalize chain, phonetic indices, trigram
- `references/scoring.md` — 7 cue families for type_fit
- `references/edge-cases.md` — Czech inflection, ASR noise, short aliases, homographs
