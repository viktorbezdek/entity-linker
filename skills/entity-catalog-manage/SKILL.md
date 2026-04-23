---
name: entity-catalog-manage
description: >
  Catalog CRUD and staging review with Apps-first UX and elicitation fallback.
  TRIGGERS: "review staged entities", "approve new entities", "add entity to catalog",
  "rename entity", "deprecate entity", "import seed", "manage catalog".
model: inherit
tools:
  - Read
  - Write
  - Bash
---

# entity-catalog-manage Skill

Wraps `catalog_*`, `staging_*`, and `pending_*` MCP tools with user-friendly confirmations. Primary UI is the Staging Review App; falls back to sequential elicitation on Claude.ai web.

## Common Operations

### Add entity directly
```
/add-entity
```
Interactive creation via the `catalog_create` tool. Confirms: id, type, canonical name, aliases, disambiguation hint.

### Import from YAML seed
```
/catalog-import path/to/entities.seed.yml
```
Calls `catalog_import` → validates → upserts → rebuilds indices.

Seed YAML format (flat list, `docs/examples/entities.seed.yml`):
```yaml
version: 1
entities:
  - id: viktor-bezdek
    type: person
    canonical_name: Viktor Bezdek
    disambiguation_hint: "Groupon AI lead"
    aliases: [Viktor, VB]
```

### Review staged candidates
```
/review-staged
```
Opens the Staging Review App (or elicitation fallback). For each pending candidate: approve-new / merge-existing (with autocomplete) / reject.

### Search catalog
```
/entity-search <query>
```
Calls `catalog_search(query)` using FTS5 BM25 ranking.

### Deprecate entity
Deprecation is soft-delete — entity is excluded from matching but kept in `resolution_log` for audit. Use `catalog_deprecate(entity_id)`.

## MCP Tools Used

- `catalog_list`, `catalog_get`, `catalog_search`, `catalog_create`, `catalog_update`
- `catalog_add_alias`, `catalog_deprecate`, `catalog_import`, `catalog_stats`
- `staging_stage`, `staging_list`, `staging_approve`, `staging_reject`
- `staging_review_app`
- `pending_list`, `pending_resolve`
