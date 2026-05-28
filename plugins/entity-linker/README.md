# entity-linker

**Resolve entity mentions in any text against your personal catalog. Never lose track of who "Stefan" is again.**

A [Claude Code](https://code.claude.ai) + [Cowork](https://cowork.ai) plugin that annotates entity mentions in transcripts, emails, meeting notes, and documents — linking surface forms like *"SW"* or *"the Quantum project"* to canonical entries in a local SQLite catalog. Ambiguous spans surface interactively; headless runs queue everything for later review.

```
Input:  "Synced with Stefan about Quantum AI timeline. Core team is aligned."
Output: "Synced with [Stefan](@person:stefan-weber) about [Quantum AI](@project:quantum-ai) timeline. [Core team](@team:core-team) is aligned."
```

---

## Why

Noisy text inputs — call transcripts, emails, Slack exports, 1:1 notes — carry inconsistent names, acronyms, misspellings, and cross-language variants. Downstream tools silently bake in bad references. This plugin applies disciplined matching with a local truth source, surfacing ambiguity instead of guessing.

**Key properties:**
- **No guessing.** Auto-link only when confidence ≥ 0.90 and top candidate beats #2 by ≥ 0.10. Everything else queues.
- **Deterministic core.** Normalization, fuzzy matching, and scoring are pure Python — no LLM in the hot path.
- **Czech + English.** Inflection-aware matching handles dative/instrumental/possessive forms out of the box.
- **Three hosts, one plugin.** Works in Claude Code, Cowork (scheduled/headless), and Claude Desktop.

---

## Installation

**Prerequisites:** Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Claude Code or Cowork.

```bash
# Install the plugin
claude plugin install-local /path/to/entity-linker

# Install Python dependencies
uv sync --directory mcp-server

# Verify the MCP server starts
uv run --directory mcp-server entity-db
# → FastMCP banner on stdout, listening on stdio
```

The plugin registers the `entity-db` MCP server automatically via `.mcp.json`.

---

## Quick Start

Five minutes to your first annotated file.

**1. Seed your catalog**

```
/catalog-import docs/examples/entities.seed.yml
```

**2. Check it loaded**

```
/entity-stats
```
```
Entities: 6  |  Aliases: ~30  |  Staging pending: 0
```

**3. Link a file**

```
/link-file docs/examples/sample-standup.md
```

The Disambiguation App opens for ambiguous spans. Confirm or skip each one. The annotated output lands in `docs/examples/annotated/`.

**4. Review new candidates**

Unknown entities that appeared ≥ 2 times are staged for review:
```
/review-staged
```
Approve, merge into an existing entity, or reject.

**5. Paste text inline**

```
/link-text
```
Paste any raw text (transcript, email, Slack thread). Results render directly in the conversation.

---

## Commands

| Command | What it does |
|---------|-------------|
| `/link-text` | Link entities in pasted text; output inline |
| `/link-file <path>` | Link a single file; write annotated copy |
| `/link-folder <path>` | Batch-process a folder via the `entity-resolver` subagent |
| `/catalog-import <path>` | Bulk-import entities from a YAML seed file |
| `/add-entity` | Add a single entity interactively |
| `/entity-search <query>` | Search the catalog by name or alias (FTS5 BM25) |
| `/entity-stats` | Catalog size, staging backlog, recent activity |
| `/review-staged` | Open the Staging Review App (or elicitation fallback) |

---

## How It Works

```
Text input
    │
    ▼
Preprocessing          ← ASR cleanup, email header stripping, HTML extraction
    │
    ▼
Candidate generation   ← Sliding window × catalog aliases (FTS5 + phonetic + trigram)
    │
    ▼
Scoring                ← lex + phonetic + type_fit + recency + context_cues
    │
    ├─ score ≥ 0.90 AND gap ≥ 0.10  →  auto-link
    ├─ score 0.50–0.89               →  disambiguation queue (interactive) / pending (headless)
    └─ score < 0.50                  →  unresolved; repeated unknowns → staging
    │
    ▼
Render                 ← markdown / XML / sidecar JSON
```

**Scoring formula** (weights sum to 1.0):
- `lex` — lexical similarity via RapidFuzz (0.45 weight)
- `phonetic` — Beider-Morse + Double Metaphone (0.20)
- `type_fit` — entity type matches context cues (0.20)
- `recency` — entity seen earlier in same source (0.10)
- `context_cues` — person/project/team signal words nearby (0.05)

**Czech inflection:** The normalizer strips suffixes `-ovi`, `-ovy`, `-em`, `-a`, `-e`, `-y`, `-u`, `-ou`, `-ům`, `-ech`, `-ami`, `-ův`, `-ova`, `-ovo` iteratively (stem ≥ 3 chars). `Stefanovi` → `stefan`, `Weberovy` → `weber`.

---

## Catalog Management

### Seed file format

```yaml
# docs/examples/entities.seed.yml
version: 1
entities:
  - id: stefan-weber
    type: person                         # person | project | team | company | other
    canonical_name: Stefan Weber
    disambiguation_hint: "AI lead"       # shown in Disambiguation App
    aliases: [Stefan, SW, Webber]
    attributes:                          # optional free-form metadata
      company: horizon
      team: core-team
```

**Supported types:** `person`, `project`, `team`, `company`, `other`

Import with:
```
/catalog-import path/to/seed.yml
```

### Adding entities one at a time

```
/add-entity
```
Interactive form — name, type, aliases, disambiguation hint.

### Searching

```
/entity-search Stefan
/entity-search quantum
```

Uses FTS5 BM25 over canonical names, aliases, and disambiguation hints.

---

## Output Formats

### Markdown (default)

```markdown
I synced with [Stefan](@person:stefan-weber) about the [Quantum AI](@project:quantum-ai) rollout.
User-confirmed spans get a `?` suffix: [Stefan](@person:stefan-weber?)
```

### XML

```xml
I synced with <entity id="stefan-weber" type="person" confidence="0.94">Stefan</entity> about...
```

### Sidecar JSON

Preserves the original text byte-for-byte and emits `<source>.entities.json`:
```json
{
  "source_hash": "a1b2c3...",
  "resolutions": [
    { "start": 14, "end": 20, "surface": "Stefan", "entity_id": "stefan-weber",
      "type": "person", "confidence": 0.94, "method": "auto" }
  ]
}
```
Right choice for audit-heavy pipelines — re-apply annotations without re-running the matcher.

---

## Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `ENTITY_DB_PATH` | `~/entity-db/entities.sqlite` | SQLite database location |
| `ENTITY_LINKER_FORCE_ELICITATION` | unset | Set to `1` to skip MCP Apps and use text-only elicitation (Claude.ai web) |

The `.mcp.json` file wires these up automatically for Claude Code and Cowork.

---

## Headless / Scheduled Runs

In Cowork or CI pipelines, pass `interactive=false`:

```python
# via MCP tool
result = await mcp.call("resolve_link_text", {
    "text": raw_text,
    "source_type": "markdown",
    "interactive": False
})
# → resolutions (auto-linked), ambiguities → pending_disambiguation, unknowns → staging
```

Drain the queues at your next interactive session with `/review-staged`.

---

## Architecture

```
plugins/entity-linker/
├── .claude-plugin/
│   └── plugin.json              Plugin manifest
├── .mcp.json                    MCP server registration
├── agents/
│   └── entity-resolver.md       Subagent for batch /link-folder
├── commands/                    8 slash commands
├── skills/                      4 skills
│   ├── entity-linker/           End-to-end annotation skill
│   ├── entity-matcher/          Matching pipeline reference
│   ├── entity-catalog-manage/   Catalog CRUD + staging review
│   └── input-preprocessing/     Source type detection + text cleaning
├── mcp-server/
│   ├── pyproject.toml
│   ├── src/entity_db/
│   │   ├── server.py            FastMCP server + tool registration
│   │   ├── db.py                SQLite layer + async write-lock
│   │   ├── schema.sql           7 tables + FTS5 virtual table
│   │   ├── matching/            normalize → candidates → score → coref → resolve
│   │   ├── tools/               MCP tool implementations
│   │   ├── preprocess/          ASR / email / markdown / HTML cleaners
│   │   ├── render.py            markdown / XML / sidecar output
│   │   └── elicit.py            Elicitation fallback
│   ├── tests/                   147 tests, 87% coverage
│   └── apps/
│       ├── disambiguation/      React + Vite disambiguation UI
│       └── staging/             React + Vite staging review UI
├── docs/
│   ├── RUNBOOK.md               Install + quickstart
│   ├── prd/                     Product requirements document
│   ├── plans/                   /spec implementation plans
│   └── examples/                Sample inputs, goldens, seed YAML
└── eval/
    ├── m0-spans.yml             50-span labeled evaluation set
    └── results/                 JSON evaluation reports
```

**MCP tools exposed:**

| Tool | Purpose |
|------|---------|
| `resolve_link_text` | Full annotation pipeline on text input |
| `resolve_render` | Re-render existing resolutions in a different format |
| `catalog_search` | FTS5 BM25 catalog search |
| `catalog_get` | Fetch a single entity by ID |
| `catalog_create` | Create a new catalog entity |
| `catalog_add_alias` | Add alias to existing entity |
| `catalog_import` | Bulk import from YAML |
| `catalog_deprecate` | Mark entity deprecated |
| `catalog_list` | List all entities with filters |
| `catalog_stats` | Aggregate statistics |
| `staging_list` | List pending staging candidates |
| `staging_stage` | Manually stage a candidate |
| `staging_approve` | Approve staged candidate into catalog |
| `staging_reject` | Reject staged candidate |
| `pending_list` | List pending disambiguation spans |
| `pending_resolve` | Resolve a pending span |
| `staging_review_app` | Open Staging Review MCP App |
| `resolve_disambiguate_app` | Open Disambiguation MCP App |
| `health` | MCP server health check |

---

## Development

```bash
# Python tests
cd mcp-server
uv run python -m pytest -q                    # 147 tests
uv run python -m pytest -q --cov=entity_db    # with coverage

# Linting
uv run ruff check . --fix

# Build React apps (only needed after editing TypeScript source)
cd apps/disambiguation && npm install && npm run build
cd apps/staging      && npm install && npm run build

# Run the M0 micro-eval
uv run python -m entity_db.eval ../../eval/m0-spans.yml
# → prints precision/recall, writes JSON to eval/results/
```

### Database schema overview

| Table | Purpose |
|-------|---------|
| `entities` | Canonical entity records |
| `aliases` | Name variants with normalized keys |
| `phonetic_index` | Beider-Morse + Double Metaphone keys |
| `trigrams` | 3-gram index for fuzzy lookup |
| `staging` | Pending new-entity candidates |
| `pending_disambiguation` | Ambiguous spans awaiting human decision |
| `resolution_log` | Append-only audit trail |
| `catalog_fts` | FTS5 virtual table over names + aliases |

All writes go through the async write-lock (`entity_db.db._write_lock`). Never open connections inside tool implementations — reuse the one set at startup via `get_conn()`.

---

## Evaluation

The `eval/m0-spans.yml` labeled set covers 50 spans across 7 categories:

| Category | Spans | Tests |
|----------|-------|-------|
| `person_exact` | 10 | First-name aliases, possessives, person cues |
| `czech_inflection` | 10 | Dative, instrumental, genitive, possessive forms |
| `project_exact` | 8 | Project/team/company names and acronyms |
| `should_not_link` | 10 | Common words that must NOT match |
| `asr_noise` | 7 | Timestamps, filler tokens, speaker labels |
| `email_context` | 5 | Header stripping, body extraction |

Run the eval after any matching pipeline change:
```bash
uv run python -m entity_db.eval eval/m0-spans.yml
```

Target: precision ≥ 0.90, recall ≥ 0.80 on `person_exact` + `czech_inflection`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `entity-db` fails to start | Run `uv sync --directory mcp-server`; requires Python 3.11+ |
| No results from `/entity-search` | Catalog is empty — run `/catalog-import docs/examples/entities.seed.yml` |
| Disambiguation App doesn't open | Host doesn't support MCP Apps — set `ENTITY_LINKER_FORCE_ELICITATION=1` |
| Score always below threshold | Check alias normalization: `/entity-search <surface>` to verify the alias is indexed |
| Czech names not matching | Confirm the surface form reduces to the alias key after stripping; run `normalize_text("Stefanovi")` in a Python shell |
| `uv` not found (Cowork) | `pip install -e mcp-server && python -m entity_db` as fallback |

---

## License

MIT — see [LICENSE](LICENSE).
