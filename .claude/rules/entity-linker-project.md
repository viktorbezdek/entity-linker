# Project: entity-linker

**Last Updated:** 2026-04-23

## Overview

Claude Code + Cowork plugin that resolves entity mentions in text inputs (transcripts, emails, docs, Slack) against a local SQLite catalog. Interactive disambiguation via MCP Apps (UI iframes) with elicitation fallback. Czech + English, phonetic + fuzzy + inflection-aware matching.

## Technology Stack

- **Language:** Python 3.11+ (server) + TypeScript (Apps UI)
- **Server framework:** FastMCP 3.x (stdio transport)
- **Database:** SQLite with WAL mode + FTS5 virtual table
- **Matching:** `abydos` (Beider-Morse + Double Metaphone), `rapidfuzz` (lexical)
- **Apps UI:** React 18 + Vite 5 + vite-plugin-singlefile
- **Package managers:** `uv` (Python), `npm` (JS)
- **Testing:** pytest + vitest

## Directory Structure

```
.claude-plugin/plugin.json     # Plugin manifest
.mcp.json                      # MCP server registration
skills/                        # 4 skills (entity-linker, entity-matcher, input-preprocessing, entity-catalog-manage)
agents/entity-resolver.md      # Subagent for long/batch inputs
commands/                      # 8 slash commands
mcp-server/
  pyproject.toml               # uv-managed Python deps
  src/entity_db/               # FastMCP server package
    server.py                  # Tool registration entry
    db.py                      # SQLite layer + async write-lock
    schema.sql                 # All 7 tables + catalog_fts
    matching/                  # normalize, index, candidates, score, coref, resolver
    tools/                     # catalog, staging, pending, app_* MCP tools
    preprocess/                # ASR, email, markdown, HTML cleaners
    render.py, elicit.py, seed.py, eval.py, resources.py
  tests/                       # pytest suite (145 tests, 87% coverage)
  apps/
    shared/                    # postMessage bridge
    disambiguation/            # React+Vite App (Disambiguation UI)
    staging/                   # React+Vite App (Staging Review UI)
docs/
  prd/                         # PRD
  plans/                       # /spec plans
  examples/                    # Sample inputs + goldens + entities.seed.yml
  RUNBOOK.md                   # Install + quickstart
eval/
  m0-spans.yml                 # 50-span labeled set
  results/                     # JSON reports
```

## Key Files

- **Plugin manifest:** `.claude-plugin/plugin.json`, `.mcp.json`
- **Server entry:** `mcp-server/src/entity_db/server.py`, `__main__.py`
- **DB schema:** `mcp-server/src/entity_db/schema.sql` (entities, aliases, phonetic_index, trigrams, staging, pending_disambiguation, resolution_log, catalog_fts)
- **Matching core:** `mcp-server/src/entity_db/matching/` (normalize, score, resolver)
- **Seed file:** `docs/examples/entities.seed.yml`
- **PRD:** `docs/prd/2026-04-23-entity-linker-plugin.md`

## Development Commands

| Task | Command |
|------|---------|
| Install Python deps | `uv sync --directory mcp-server` |
| Run MCP server (dev) | `uv run --directory mcp-server entity-db` |
| Run Python tests | `uv run --directory mcp-server pytest -q` |
| Test with coverage | `uv run --directory mcp-server pytest -q --cov=entity_db --cov-fail-under=80` |
| Lint Python | `uv run --directory mcp-server ruff check .` |
| Auto-fix lint | `uv run --directory mcp-server ruff check . --fix` |
| Build Disambiguation App | `cd mcp-server/apps/disambiguation && npm install && npm run build` |
| Build Staging App | `cd mcp-server/apps/staging && npm install && npm run build` |
| Run JS tests | `cd mcp-server/apps/<app> && npx vitest run` |
| Install plugin locally | `claude plugin install-local /Users/vbezdek/Work/entitiy-memory-plugin` |

## Architecture Notes

- **MCP server owns the DB.** All reads/writes go through tools. Skills and commands never touch SQLite directly.
- **Async write-lock:** All DB mutations acquire `entity_db.db._write_lock` before `asyncio.to_thread(...)`.
- **`get_conn()` pattern:** Tools import `from entity_db.tools import get_conn` — the connection is set once at server startup via `set_conn()`.
- **MCP Apps deviation from PRD §9.1:** Apps live at `mcp-server/apps/{disambiguation,staging}/` (outside the Python src tree) to keep JS tooling isolated from pip/uv packaging.
- **Tool naming:** FastMCP tools use the `name=` parameter when the Python function name has a suffix (e.g. `resolve_link_text_mcp` is registered as `resolve_link_text`).
- **Plugin subagent frontmatter:** `agents/*.md` must NOT contain `hooks`, `mcpServers`, or `permissionMode` fields — plugin-distributed subagents cannot declare them.
- **Czech inflection:** `normalize_text()` strips suffixes `[-ovi, -ovy, -em, -a, -e, -y, -u, -ou, -ům, -ech, -ami, -ův, -ova, -ovo]` iteratively if stem ≥ 3 chars.
- **Seed bootstrap:** YAML at `docs/examples/entities.seed.yml` (flat list per PRD §25.3) — run `catalog_import(yaml_path)` or `/catalog-import` to seed.
- **Auto-link threshold:** `top ≥ 0.90 AND (top − second) ≥ 0.10`. First-occurrence exact matches score 0.85 → go to `pending_disambiguation`.
