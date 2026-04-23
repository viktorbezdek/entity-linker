# entity-linker Runbook

End-to-end guide: install the plugin, seed the catalog, link your first file.

## 1. Install the Plugin Locally

```bash
claude plugin install-local /path/to/entitiy-memory-plugin
```

Verify the MCP server starts:
```bash
uv run --directory /path/to/entitiy-memory-plugin/mcp-server entity-db
# Should print the FastMCP banner and listen on stdio
```

## 2. Seed the Catalog

```
/catalog-import docs/examples/entities.seed.yml
```

Check it worked:
```
/entity-stats
```

Expected output:
```
Entities: 6  |  Aliases: ~30  |  Staging pending: 0
```

## 3. Link Your First File

```
/link-file docs/examples/sample-standup.md
```

The command:
1. Detects source type (markdown)
2. Calls `resolve_link_text`
3. Shows ambiguous spans (Viktor, FoundryAI, etc.) — opens the Disambiguation App
4. Writes annotated output to `docs/examples/annotated/sample-standup.md`

## 4. Review Staged Candidates

After linking, unknown entities (not in the catalog) land in the staging queue:

```
/review-staged
```

Opens the Staging Review App. For each candidate:
- **Approve as new entity** — adds to catalog, rebuilds indices
- **Merge into existing** — adds alias to existing entity
- **Reject** — dismisses candidate

## 5. Search the Catalog

```
/entity-search Viktor
/entity-search Foundry
```

## 6. Batch Process a Folder

```
/link-folder ~/transcripts/incoming/
```

Spawns the `entity-resolver` subagent. All files are processed headlessly. Ambiguities and new candidates queue for your next interactive session.

## 7. Elicitation Fallback (Claude.ai web)

If the Disambiguation App isn't available (Claude.ai web), set:
```bash
export ENTITY_LINKER_FORCE_ELICITATION=1
```

The plugin falls back to sequential elicitation forms — same workflow, text-only UI.

## 8. Run the M0 Micro-Eval

After reviewing `eval/m0-spans.yml`, run:
```bash
uv run --directory mcp-server python -m entity_db.eval eval/m0-spans.yml
```

Prints precision/recall and writes a JSON report to `eval/results/`.

## 9. Build the Apps (if modified)

```bash
cd mcp-server/apps/disambiguation && npm run build
cd mcp-server/apps/staging && npm run build
```

The built `dist/index.html` is served automatically as a `ui://` resource.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `entity-db` server fails to start | `uv sync --directory mcp-server`; check Python 3.11+ |
| No entities found in `/entity-search` | Run `/catalog-import docs/examples/entities.seed.yml` first |
| Disambiguation App doesn't open | Host may not support MCP Apps; set `ENTITY_LINKER_FORCE_ELICITATION=1` |
| `uv` not found on Cowork | Fallback: `pip install -e mcp-server && python -m entity_db` |
