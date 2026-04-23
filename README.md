# entity-linker marketplace

Private Claude Code plugin marketplace hosting the `entity-linker` plugin.

## Install

```
/plugin marketplace add viktorbezdek/entity-linker
/plugin install entity-linker
```

## Plugins

| Plugin | Path | Description |
|--------|------|-------------|
| [entity-linker](./plugins/entity-linker) | `./plugins/entity-linker` | Resolves entity mentions in text (transcripts, emails, docs) against a local catalog. Interactive disambiguation via MCP Apps with elicitation fallback. Czech + English, phonetic + fuzzy + inflection-aware matching. |

## Structure

```
.claude-plugin/
  marketplace.json              # Marketplace manifest
plugins/
  entity-linker/
    .claude-plugin/plugin.json  # Plugin manifest
    .mcp.json                   # MCP server (entity-db)
    skills/                     # 4 skills
    agents/                     # entity-resolver subagent
    commands/                   # 8 slash commands
    mcp-server/                 # FastMCP Python server + React Apps
    docs/                       # PRD, RUNBOOK, examples
    eval/                       # M0 labeled span set + harness
docs/plans/                     # Spec-driven development plans (repo history)
```

See [plugins/entity-linker/docs/RUNBOOK.md](./plugins/entity-linker/docs/RUNBOOK.md) for install and quickstart.
