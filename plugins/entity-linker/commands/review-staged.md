---
description: Review and approve/reject staged entity candidates
---

# /review-staged

Opens the Staging Review App to drain the pending candidate queue (or falls back to sequential elicitation on Claude.ai web).

**In the App:**
- **Approve as new entity**: confirm type, canonical name, and aliases.
- **Merge into existing**: autocomplete search for the existing entity.
- **Reject**: dismiss the candidate.

Approved candidates are immediately added to the catalog and back-fill the `resolution_log` for every prior source that mentioned the surface.

Uses the `entity-catalog-manage` skill and `staging_review_app` MCP tool.
