---
description: Show catalog size, staging backlog, and recent activity
---

# /entity-stats

Returns a live summary from `catalog_stats`:

- **Entities**: total non-deprecated entities in the catalog
- **Aliases**: total alias rows (includes derived + manual)
- **Staging pending**: new-entity candidates awaiting review
- **Pending disambiguation**: ambiguous spans awaiting resolution
- **Recent resolutions**: spans auto-linked or confirmed in the last 24 hours
