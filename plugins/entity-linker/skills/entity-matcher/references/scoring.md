# Type-Fit Cue Families

7 cue families that map surrounding context tokens to entity types. Each set of tokens — when found within ±3 positions of a candidate span — returns `type_fit = 1.0`. A token from a **different** family returns `0.0`. No type cues → neutral `0.5`.

## PERSON_CUES

```python
{"with", "met", "called", "said", "from", "told", "asked", "joined",
 "contacted", "introduced", "he", "she", "they", "his", "her",
 "mr", "mrs", "ms", "dr", "ing"}
```

Sentence patterns: "synced **with** Viktor", "**met** Tomas last week".

## PROJECT_CUES

```python
{"project", "rollout", "launch", "initiative", "program", "effort", "plan"}
```

Patterns: "the FoundryAI **project**", "the Q2 **launch**".

## PRODUCT_CUES

```python
{"feature", "ship", "release", "product", "version", "ui", "interface", "app"}
```

Patterns: "**ship** the Dashboard **feature**", "Dashboard **UI** redesign".

## TEAM_CUES

```python
{"team", "squad", "tribe", "chapter", "guild", "group", "org"}
```

Patterns: "the B2C **tribe**", "our **squad** meeting".

## COMPANY_CUES

```python
{"at", "company", "corp", "inc", "ltd", "llc", "ag", "acquired", "startup"}
```

Patterns: "working **at** Groupon", "Groupon **acquired** X". Also regex: `\b(Inc|LLC|AG|s\.r\.o\.)\b`.

## ACRONYM_CUES

Regex pattern: all-caps tokens of 2–5 characters (`[A-Z]{2,5}`). No static word set — the shape IS the cue.

Examples: `CRM`, `B2C`, `API`, `GRPN`.

## CONCEPT_CUES

```python
{"what", "concept", "methodology", "framework", "approach",
 "practice", "principle", "pattern", "process"}
```

Patterns: "**what is** Agile", "the Kanban **methodology**".

---

## Conflict Detection

If the winning cue family for a span is PERSON but the entity type is PROJECT, `type_fit = 0.0`. If no cue from any family fires → `type_fit = 0.5` (neutral).

The scoring constants live in `mcp-server/src/entity_db/matching/type_fit.py`. This file is the authoritative documentation; the Python constants must match.
