---
description: Search the entity catalog by name or alias
argument-hint: <query>
---

# /entity-search

FTS5-powered search over canonical names, disambiguation hints, and aliases. Returns the top matches with their entity IDs, types, and hints.

**Examples:**
```
/entity-search Viktor
/entity-search Foundry AI
/entity-search B2C
```

Calls `catalog_search(query)`. Uses BM25 ranking — longer, more specific queries rank better.
