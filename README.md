# entity-linker

Resolves entity mentions in text inputs (call transcripts, emails, meeting notes, docs) against a local catalog. Interactive disambiguation via MCP Apps. Czech + English phonetic and fuzzy matching.

## Install

```bash
claude plugin install-local /path/to/entitiy-memory-plugin
```

## Quickstart

```bash
# 1. Bootstrap the catalog
/catalog-import docs/examples/entities.seed.yml

# 2. Link entities in a file
/link-file ~/transcripts/2026-04-22-standup.md

# 3. Review new-entity candidates
/review-staged
```

## Commands

| Command | Description |
|---------|-------------|
| `/link-file <path>` | Link entities in a file, write annotated output |
| `/link-text` | Link entities in pasted text |
| `/link-folder <path>` | Batch-link a folder (spawns resolver subagent) |
| `/review-staged` | Review and approve/reject staged entity candidates |
| `/add-entity` | Add a new entity to the catalog interactively |
| `/entity-search <query>` | Search the catalog |
| `/entity-stats` | Show catalog size and queue depths |
| `/catalog-import <path>` | Import entities from a YAML seed file |

## Output Formats

- **markdown** (default): inline `[Text](@type:entity-id)` annotations
- **xml**: `<entity id="..." type="..." confidence="...">Text</entity>`
- **sidecar**: original text unchanged + `.entities.json` with byte-offset spans

## MCP Server

The `entity-db` MCP server runs locally. DB stored at `~/entity-db/entities.sqlite` (override via `ENTITY_DB_PATH`).
