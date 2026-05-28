---
description: Import entities from a YAML seed file
argument-hint: <path-to-entities.yaml>
---

# /catalog-import

Bulk-imports entities from a YAML seed file into the catalog. Each entity is validated, upserted, and its aliases, phonetic keys, and trigrams are indexed.

**Seed file format** (`entities.seed.yml`):
```yaml
version: 1
entities:
  - id: stefan-weber
    type: person
    canonical_name: Stefan Weber
    disambiguation_hint: "AI lead"
    aliases: [Stefan, SW]
```

**Example:**
```
/catalog-import docs/examples/entities.seed.yml
```

Calls `catalog_import(yaml_path)`. Reports: entities created/updated, aliases indexed, errors.
