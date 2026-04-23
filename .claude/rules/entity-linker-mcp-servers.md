# MCP Servers

## entity-db

**Purpose:** The entity catalog server this project builds. Provides tools for linking entity mentions in text against a local SQLite catalog, managing the catalog (CRUD + bulk YAML import), handling disambiguation queues, and reviewing staged candidates.

**Status:** ✅ All 16+ tools registered (verified by `test_mcp_tool_registration_includes_core_tools`).

**Consult this MCP when:**
- Running entity resolution on text input (transcripts, emails, docs) — use `resolve_link_text`
- Seeding the catalog from a YAML file — use `catalog_import`
- Reviewing the staging queue for unknown entities — use `staging_review_app` (opens App UI) or elicitation fallback
- Resolving ambiguous spans from a prior headless run — use `resolve_disambiguate_app` or `pending_resolve`
- Querying catalog size, aliases, or recent activity — use `catalog_stats`
- Searching the catalog by name or alias — use `catalog_search` (FTS5 BM25)

**Usage:** `ToolSearch(query="+entity-db <tool-name>")` then call the discovered tools directly. Tool names follow the pattern `catalog_*`, `staging_*`, `pending_*`, plus `resolve_link_text`, `resolve_render`, `resolve_disambiguate_app`, `staging_review_app`.

**Project-specific workflow context:**
- **Always seed the catalog first.** A fresh DB has no entities; `resolve_link_text` on an empty catalog returns nothing useful. Run `catalog_import` or `/catalog-import docs/examples/entities.seed.yml` before linking.
- **`resolve_link_text` is pure compute.** It doesn't open any UI. Pass `{interactive: false}` for headless runs (bot pipelines, Cowork scheduled tasks) — ambiguities go to `pending_disambiguation`, new candidates go to `staging`.
- **App tools vs direct tools.** `resolve_disambiguate_app` / `staging_review_app` open iframe UIs (or fall back to elicitation). `pending_resolve` / `staging_approve` are the underlying mutations — call them directly from scripts.
- **Elicitation fallback trigger.** Set `ENTITY_LINKER_FORCE_ELICITATION=1` to bypass MCP Apps (useful on Claude.ai web or for CI).
- **DB path:** defaults to `~/entity-db/entities.sqlite`. Override with `ENTITY_DB_PATH` env var.
- **Rebuild the Apps** if you change TypeScript source: `cd mcp-server/apps/disambiguation && npm run build` (and same for `staging/`). Served `ui://` resources read from `dist/index.html`.
