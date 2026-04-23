# Entity-Linker Plugin Implementation Plan

Created: 2026-04-23
Author: vbezdek@groupon.com
Status: PENDING
Approved: Yes
Iterations: 0
Worktree: No
Type: Feature

## Summary

**Goal:** Build the `entity-linker` Claude Code + Cowork plugin per `docs/prd/2026-04-23-entity-linker-plugin.md` — generalized text entity resolution with a FastMCP server, SQLite+FTS5 catalog, two MCP Apps (Disambiguation + Staging Review), elicitation fallback, four skills, one subagent, eight slash commands, YAML seed bootstrap, and headless queueing.

**Architecture:** Python FastMCP server (`entity-db`) owns the SQLite DB, matching engine, and UI resources. MCP Apps are React+Vite+TypeScript projects whose built `dist/index.html` is served via `@mcp.resource("ui://...")`. Skills and slash commands are thin orchestrators that call MCP tools; one subagent isolates long-input runs.

**Tech stack:** Python 3.11+, FastMCP 3.x, Pydantic v2, SQLite (WAL) + FTS5, `abydos` (Beider-Morse + Double Metaphone), `rapidfuzz` (lexical), `pyyaml`, pytest; React 18 + Vite + TypeScript for Apps; `uv` for Python packaging.

## Scope

### In Scope

- Full plugin bundle at repo root: `.claude-plugin/plugin.json`, `.mcp.json`, `skills/`, `agents/`, `commands/`, `mcp-server/`.
- FastMCP server with all tools in PRD §11: catalog (incl. `catalog_import`), staging, pending-disambiguation, and resolution tools.
- SQLite schema per PRD §10 (entities, aliases, phonetic_index, trigrams, staging with dedup_key UNIQUE, pending_disambiguation, resolution_log) + FTS5 virtual table `catalog_fts` kept in sync via Python-side triggers in `db.py`.
- Matching pipeline: normalize (incl. Czech/Slovak/Polish inflection stripping) → index (exact + Double Metaphone + Beider-Morse via `abydos` + char-trigram) → candidate generation (sliding window) → score (formula in PRD §14) → within-source coref.
- `type_fit` rule-mode with 7 cue families documented in `skills/entity-matcher/references/scoring.md`. LLM-mode scaffolded but OFF by default.
- Two MCP Apps (React+Vite+TS): `apps/disambiguation/` and `apps/staging/`, each a separate Vite project with its own build; shared postMessage helper lib.
- Elicitation fallback helpers for hosts without Apps (Claude.ai web).
- Render module: markdown (default), XML, sidecar JSON.
- Headless mode (`interactive: false`) — queues ambiguities and new candidates instead of prompting.
- Four skills: `entity-linker`, `entity-matcher` (reference), `input-preprocessing` (with ASR/email/markdown/HTML/plain sub-cleaners), `entity-catalog-manage`.
- One subagent: `entity-resolver` (isolation: worktree, plugin-compatible frontmatter).
- Eight slash commands: `/link-file`, `/link-text`, `/link-folder`, `/review-staged`, `/add-entity`, `/entity-search`, `/entity-stats`, `/catalog-import`.
- YAML seed (`entities.seed.yml` per PRD §25.3 flat list) + `catalog_import` tool.
- M0 micro-eval harness: synthesized 50-span labeled set (Viktor reviews before Task 15 runs) + precision check at threshold 0.90.
- End-to-end acceptance test on mixed-source inputs (markdown + email + transcript).

### Out of Scope

- Catalog Browser App + Stats Dashboard App (PRD §3 — deferred to v1).
- Cross-source recency priors and entity timelines (v2).
- Multi-user / team-wide catalog (v2).
- Automatic alias learning from confirmations (v1 or later).
- Speaker diarization, transcription, OCR.
- LLM-assisted `type_fit` mode (scaffolded but not enabled in v0).
- Czech-specific phonetic algorithm (v1 if abydos BMPM recall is weak on M0).
- Catalog concurrency beyond WAL + single-writer lock (v2).
- Cowork scheduled-task templates (v1 per PRD §21).
- **PRD §20 full 20-file eval** (precision ≥ 0.98, recall ≥ 0.85 on 10 transcripts + 6 emails + 4 notes). Deferred to post-M1 acceptance phase. Task 15 is the M0 scoring-weight gate only (50 synthesized spans at threshold 0.90, Viktor-reviewed); the full 20-file eval runs as a follow-up once real usage produces labeled data.
- **Email local-part as aliasing hint** (e.g. `viktor.bezdek@groupon.com` → alias `viktor.bezdek`). Deferred to v1.

## Approach

**Chosen:** Single-plan execution of PRD M0 + M1. Build bottom-up (DB → matching → tools → Apps → skills → commands) with each task independently testable.

**Why:** The PRD is highly prescriptive — architectural degrees of freedom are low. Components compose into one bundle that can't ship partial (a half-built plugin with tools but no skills is dead weight). Bottom-up builds let each task land a green test suite without waiting for UI completion. Trade-off: plan is long (16 tasks); single approval, heavier verification phase — accepted.

**Alternatives considered:**
- **Phased (MCP-core → Apps in follow-on):** smaller plans, faster partial ship via elicitation-only UI; user rejected in favor of bundled delivery.
- **M0 spike as separate plan first:** strongest gate on scoring validity; user chose to absorb M0 into this plan (Task 15) instead.
- **Four-way full split:** max decomposition; rejected for approval-cycle overhead.

## Autonomous Decisions

- **Python packaging:** `uv` (matches Pilot convention and CLAUDE.md); Python 3.11+.
- **Pydantic v2** for all tool input/output models.
- **Async FastMCP server** (`async def` tools) — elicitation is async; matches the headless vs interactive branching.
- **Apps directory location — DEVIATES FROM PRD §9.1.** Apps live at `mcp-server/apps/{disambiguation,staging}/` (OUTSIDE the Python package `src/entity_db/`), not at the PRD-specified `src/entity_db/apps/`. Rationale: Vite tooling, `node_modules/`, and TypeScript config do not belong inside the Python `src` tree; isolating JS build artifacts keeps pip/uv packaging clean. PRD §9.1 is superseded here. Resource loader resolves path as `Path(__file__).resolve().parents[2] / "apps" / "<app>" / "dist" / "index.html"` (from `src/entity_db/resources.py`, `parents[2]` = `mcp-server/`). Tested in Task 11.
- **Two separate Vite projects** under `mcp-server/apps/{disambiguation,staging}/` — each produces its own `dist/index.html` served by a distinct `ui://` resource. Rejected single-project-with-two-entry-points approach for simpler per-app builds and smaller per-iframe bundles.
- **Shared JS lib:** `mcp-server/apps/shared/` for the postMessage protocol helpers, linked as a relative dep in each App's `package.json`.
- **Test DB strategy:** pytest fixture creates per-test tmp SQLite file; in-memory (`:memory:`) variant for unit tests of `db.py`; integration tests use real file.
- **FTS5 sync:** Python-side triggers in `db.py` (rebuild affected `catalog_fts` rows on entity or alias mutation) rather than SQLite triggers — gives us control over alias-concatenation logic and keeps schema.sql simple.
- **Lexical score:** `rapidfuzz.fuzz.WRatio` for weighted token ratio (single call, cheap, works well for short strings).
- **Double Metaphone:** via `abydos.phonetic.DoubleMetaphone` (already present in abydos — no extra dep).
- **Czech inflection suffixes** applied before keying: the fixed list from PRD §14 (`-ovi, -em, -a, -e, -y, -u, -ou, -ům, -ech, -ami, -ův, -ova, -ovo`). Stripped conservatively (only if suffix + remaining stem ≥ 3 chars).
- **Pronoun coref excluded from v0.** PRD §14 step 6 ("Coref: propagate within-source") is implemented as surface-equality propagation only. Pronoun resolution ("he"/"she"/"they" → entity) is v1+ scope. Rationale: pronoun coref requires real NLP (dependency parsing or SOTA coref models) that would blow the deterministic-core principle. Documented to prevent implementer confusion on Task 7.
- **Fallback-trigger env var:** `ENTITY_LINKER_FORCE_ELICITATION=1`. Plugin-scoped, not Pilot-scoped. Used in Task 9 `should_use_elicitation()` helper, TS-007, and Goal Verification truth #6 consistently.
- **Codex adversarial review deferred.** Launched at planning time but failed in the greenfield repo (`git merge-base HEAD main: exit 128: fatal: Not a valid object name HEAD` — no commits yet to diff against). Re-runnable after Task 1 lands the first commit. Spec-review findings (fully incorporated) are sufficient for planning approval.

## Context for Implementer

> Greenfield repo. No pre-existing code to follow.

- **PRD as primary spec:** `docs/prd/2026-04-23-entity-linker-plugin.md` is the source of truth for data model, API shapes, UI behavior, and edge cases.
- **Plugin format:** `.claude-plugin/plugin.json` at repo root is the required manifest. `.mcp.json` registers the MCP server. Skills auto-discover from `skills/*/SKILL.md` (YAML frontmatter + body). Subagents auto-discover from `agents/*.md` (frontmatter name/description/tools/skills/model/isolation — **no** `hooks`, `mcpServers`, or `permissionMode` per plugin restrictions). Slash commands auto-discover from `commands/*.md`.
- **FastMCP MCP Apps pattern:**
  ```python
  @mcp.resource("ui://entity-db/disambiguation.html")
  def disambiguation_app_html() -> str:
      return (Path(__file__).parent / "apps/disambiguation/dist/index.html").read_text()

  @mcp.tool(app=AppConfig(resource_uri="ui://entity-db/disambiguation.html"))
  async def resolve_disambiguate_app(source_hash: str, ambiguity_ids: list[str] | None = None) -> dict:
      ...  # returns data; host loads iframe and sends result via postMessage
  ```
  Host renders iframe with `text/html;profile=mcp-app`; sandbox + postMessage channel is automatic.
- **Elicitation pattern** (fallback):
  ```python
  result = await ctx.elicit(message="Which entity?", response_type=DisambiguationChoice)
  if result.action == "accept":
      ...
  ```
- **Ambiguity vs staging split:** PRD §10 has `pending_disambiguation` (span-level, picks from existing candidates) separate from `staging` (surface-level, creates or merges entities). Do not merge them — workflows differ.
- **Source-type detection:** in `input-preprocessing`, use simple heuristics (presence of `From:`/`To:` headers → email; `[HH:MM:SS]` timestamps → ASR; `<html>` → HTML; else plain/markdown). User hint via `/link-file --type=...` flag overrides.
- **App ↔ server protocol:** On iframe load, host posts the tool's return value to the iframe via `window.addEventListener('message', ...)`. iframe posts user actions back via `window.parent.postMessage({type: 'mcp:tool-result', tool: 'pending_resolve', args: {...}}, '*')` — the host intercepts and calls the named tool. Shared helpers in `apps/shared/mcp-app-bridge.ts`.

## Runtime Environment

- **Start command (MCP server, dev):** `uv run --directory mcp-server entity-db`
- **Start command (Apps, dev):** `cd mcp-server/apps/disambiguation && npm run dev` (same for `staging/`)
- **Build (Apps):** `cd mcp-server/apps/disambiguation && npm run build` produces `dist/index.html` + bundled JS inline/adjacent
- **Plugin install path (local dev):** `claude plugin install-local /Users/vbezdek/Work/entitiy-memory-plugin`
- **DB path:** `~/entity-db/entities.sqlite` (overridable via `ENTITY_DB_PATH`)
- **Health check:** `uv run --directory mcp-server python -c "from entity_db.db import open_db; open_db().execute('SELECT 1')"`

## Assumptions

- **A1:** `abydos` supports Double Metaphone and Beider-Morse on Python 3.11+. abydos is sparsely maintained — last major PyPI release was 2020 (0.5.0). **Verification required before Task 5:** run `uv run python -c "from abydos.phonetic import BeiderMorse, DoubleMetaphone; bm = BeiderMorse(); print(bm.encode('Bezdek'))"` and confirm clean install + output. If abydos fails on Python 3.11+, fallback: `jellyfish` (Rust-backed) for DM + a minimal hand-rolled BMPM stub (seeded with Czech/Slavic rules) OR downgrade to DM-only (per PRD §23 open question #2). Tasks 5, 6 depend on this; spike is a required sub-step of Task 5.
- **A2:** FastMCP 3.x MCP Apps decorator signature (`@mcp.tool(app=AppConfig(resource_uri="ui://..."))`) and resource-registration pattern (`@mcp.resource("ui://...")`) — **verified via Context7 query against `/prefecthq/fastmcp` docs during planning (v3.2.x)**. Pin `fastmcp>=3.2,<4` in `pyproject.toml` via Task 2; lock via `uv.lock`. Tasks 10–12 depend on this.
- **A3:** Claude Code ≥ 2.1.76 renders `ui://` resources as iframes (PRD §12.3 host matrix). Tasks 11, 12 verification depends on this.
- **A4:** Cowork's elicitation and Apps support matches Claude Code's. Cross-host E2E validation is best-effort in v0 (TS-007 simulates web fallback).
- **A5:** `rapidfuzz.fuzz.WRatio` produces a reasonable lexical score in [0, 100] (scale to [0, 1] by dividing by 100). Task 6 depends on this.
- **A6:** User will review synthesized 50-span labeled set (Task 15) within the plan's execution window. Task 15 completion depends on this; Task 16 does not.
- **A7:** No pre-existing plugin data in `~/entity-db/entities.sqlite` — fresh-start assumed; migration not required for v0.
- **A8:** Node 20+ and `npm` available locally for Vite builds. Tasks 10–12 depend on this.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| abydos BMPM output quality is poor on Czech names (recall miss) | Medium | Medium | Measure in M0 (Task 15); if macro recall < 0.80 on Czech subset, file v1 follow-up for Czech-specific phonetic (PRD §23 open question #2) — do NOT block v0 ship. |
| abydos install fails or BMPM API missing on Python 3.11+ | Medium | High | Task 5 starts with a 10-min import spike. Fallback: `jellyfish` for DM + DM-only v0 (BMPM deferred). Documented in A1. |
| abydos BMPM latency exceeds SLO (§18: ≤10s for 30k-word input) | Medium | Medium | Pre-compute phonetic keys for all aliases at index time (Task 5 `rebuild_phonetic_for` runs once per alias mutation; not per-query). Only compute at query time for the candidate surface form (1–4 tokens, cheap). Benchmark in Task 15 on a 30k-word synthetic input; fail if > 10s. |
| FastMCP API drift between 3.x minor versions breaks resource/tool decorators | Medium | High | Pin `fastmcp>=3.2,<4` in `pyproject.toml` (Task 2); lock via `uv.lock`. Task 10 verifies AppConfig signature on the pinned version. |
| `uv` not available on Cowork's scheduled-task runtime | Medium | High | `.mcp.json` uses `uv run`. If Cowork runs without `uv` on PATH, plugin fails to start. Mitigation: document pip-install fallback in Task 16 RUNBOOK — `pip install -e mcp-server && python -m entity_db`. Smoke test in Task 16. |
| iframe cold-load postMessage race — host sends payload before iframe registers listener | Medium | Medium | Apps must post `{type: 'mcp:ready'}` to `window.parent` on mount; host protocol replays the payload after `mcp:ready`. Shared lib `mcp-app-bridge.ts` handles this; unit-test the ready handshake in Task 10. |
| MCP Apps cross-host fragmentation — Apps work on Code but not on Cowork or Claude.ai web | Medium | High | TS-007 exercises elicitation fallback path. Apps builds must never JS-error on fallback hosts; always detect MCP Apps host sentinel before calling. |
| Scoring weights off (precision < 0.98 at 0.90 threshold) on M0 micro-eval | Medium | Medium | Task 15 is a tuning task, not a gate. If precision < 0.95, surface weight-tuning as a sub-task; do not silently ship wrong weights. Document tuning results in `skills/entity-matcher/references/scoring.md`. |
| Vite build inlines too much and iframes exceed MCP resource size limits | Low | Medium | Set Vite `build.assetsInlineLimit: 0` and single-file plugin config. Bundle budget: **< 400 KB gzipped per App** (React + ReactDOM + app code realistic bound). Task 10 checkpoint: measure gzipped size after first stub build; if over budget, swap to Preact (API-compatible, ~10KB core) before Task 11/12. |
| Parallel subagent writes deadlock on SQLite writer lock | Low | Medium | Async lock in `db.py` serializes writes with ≤ 5s acquire timeout; writers that time out log and retry once. Documented limitation in PRD §17. |
| Czech inflection stripping over-strips and breaks exact match on short names (e.g. "Eva" → "Ev-") | Medium | Low | Conservative rule: only strip if stem remaining ≥ 3 chars (per Autonomous Decisions). Unit-tested with Czech name corpus in Task 4. |
| User can't review the synthesized labeled set in time (Task 15 blocks) | Medium | Low | Task 15 can run on synthesized-only data as a preliminary pass; final tuning gated on review. Task 16 (end-to-end) does not depend on Task 15. |
| Headless queue grows unbounded in batch runs | Low | Medium | `pending_disambiguation.status` and `staging.status` let us age out resolved items; add `/entity-stats` to surface queue depth. Dedup prevents surface-duplication. |
| Subagent `isolation: worktree` field not recognized by Claude Code plugin loader | Low | Low | Task 14 includes a spike: load plugin locally, spawn `entity-resolver`, check isolation actually applied. If unsupported, remove field + document: long-input isolation achieved by the parent summarizing rather than true worktree. |
| Subagent frontmatter restrictions change (new hooks fields) and break plugin load | Low | Low | Frontmatter kept minimal (name, description, tools, skills, model, isolation). Any future hook needs go at plugin level. |

⚠️ Mitigations above are commitments — verification checks they're implemented.

## Goal Verification

### Truths

1. Running `/catalog-import docs/examples/entities.seed.yml` on a fresh DB creates ≥ 5 entities with aliases, phonetic_index rows, and trigram rows, and populates `catalog_fts`.
2. `resolve_link_text` called on a 200-word markdown snippet returns a `resolutions` array with ≥ 1 auto-linked span where `confidence ≥ 0.90` and a matching `resolution_log` row is written with `method="auto"`.
3. `resolve_link_text(text, { interactive: false })` on input containing an unknown entity produces `staging` row with `status="pending"` and appropriate `dedup_key`; no elicitation is triggered.
4. Running the plugin in Claude Code and triggering `resolve_disambiguate_app` for a source with ambiguities renders the iframe; clicking a candidate card posts a message that calls `pending_resolve` and the next `resolve_link_text` on the same source auto-links that span (TS-003 passes end-to-end).
5. `/review-staged` with ≥ 2 pending candidates renders the Staging Review App; approving one backfills `resolution_log` for every prior source that contained that surface (TS-002 passes end-to-end).
6. On a simulated fallback host (`ENTITY_LINKER_FORCE_ELICITATION=1`), the same flows complete via sequential `ctx.elicit` calls and produce equivalent `resolution_log` entries (TS-007 passes).
7. `resolve_render` produces three distinct formats: (a) `to_markdown(text, R)` returns annotated markdown with entity-ID links, (b) `to_xml(text, R)` returns annotated XML, (c) `to_sidecar(text, R)` returns `(text_unchanged, sidecar_json)` where sidecar carries byte-offset spans; applying those offsets to the unchanged text to insert markdown annotations reproduces exactly `to_markdown(text, R)`.
8. M0 micro-eval (Task 15) reports precision ≥ 0.95 at threshold 0.90 on the Viktor-reviewed 50-span set, OR flags scoring-weight drift with a proposed re-tune.

### Artifacts

- `mcp-server/src/entity_db/server.py` — FastMCP server entry with all tool/resource/app registrations.
- `mcp-server/src/entity_db/matching/*.py` — full pipeline implementation.
- `mcp-server/src/entity_db/db.py` + `schema.sql` — SQLite schema + FTS5 + WAL + write-lock.
- `mcp-server/apps/disambiguation/dist/index.html` + `apps/staging/dist/index.html` — built App bundles.
- `skills/entity-linker/SKILL.md`, `skills/entity-matcher/SKILL.md` + `references/*.md`, `skills/input-preprocessing/SKILL.md` + `references/*.md`, `skills/entity-catalog-manage/SKILL.md`.
- `agents/entity-resolver.md`.
- `commands/link-file.md`, `commands/link-text.md`, `commands/link-folder.md`, `commands/review-staged.md`, `commands/add-entity.md`, `commands/entity-search.md`, `commands/entity-stats.md`, `commands/catalog-import.md`.
- `docs/examples/entities.seed.yml` — seed sample used in TS-001/TS-004.
- `eval/m0-spans.yml` — 50-span synthesized labeled set.
- `mcp-server/tests/**/test_*.py` — unit + integration test suite, ≥ 80% coverage.

## E2E Test Scenarios

### TS-001: Link a single markdown file end-to-end
**Priority:** Critical
**Preconditions:** Fresh `entities.sqlite`, `/catalog-import docs/examples/entities.seed.yml` executed successfully.
**Mapped Tasks:** Task 7, 8, 9, 13, 14, 16

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Place `docs/examples/sample-standup.md` (contains "Viktor", "FoundryAI", "Tomas") in cwd | File exists |
| 2 | Run `/link-file docs/examples/sample-standup.md` from Claude Code | Skill reads file, calls `resolve_link_text(source_type=markdown)` |
| 3 | Observe output | Annotated file at `docs/examples/annotated/sample-standup.md` contains `[Viktor](@person:viktor-bezdek)` and `[FoundryAI](@project:foundry-ai)`; unknown surface "Tomas" appears plain |
| 4 | Inspect `staging` table | One row with `surface="Tomas"`, `status="pending"`, frequency 1 |
| 5 | Inspect `resolution_log` | Rows for Viktor and FoundryAI with `method="auto"`, `confidence ≥ 0.90` |

### TS-002: Approve a staged candidate via the Staging Review App
**Priority:** Critical
**Preconditions:** TS-001 completed; `staging` contains ≥ 1 pending row.
**Mapped Tasks:** Task 8, 12

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `/review-staged` from Claude Code | `staging_review_app` tool opens iframe with pending queue |
| 2 | Click "Approve as new entity" on the "Tomas" row; fill type=person, canonical_name="Tomáš Novák", alias list=["Tomas","Tom"] | iframe posts `staging_approve` call with payload |
| 3 | Wait for tool to return | `staging` row status → `approved`; new `entities` row created; `resolution_log` back-fills for the previous TS-001 run with the new `entity_id` |
| 4 | Re-run `/link-file docs/examples/sample-standup.md` | "Tomas" now auto-links as `@person:tomas-novak` |

### TS-003: Resolve an ambiguity via the Disambiguation App
**Priority:** Critical
**Preconditions:** Catalog has two entities both matching "Viktor" (e.g. viktor-bezdek and viktor-novak) with `disambiguation_hint` set; input mentions "Viktor" with weak type cues.
**Mapped Tasks:** Task 7, 11

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `/link-file docs/examples/ambiguous-viktor.md` | Skill reports 1 ambiguity; offers to open Disambiguation App |
| 2 | Confirm → `resolve_disambiguate_app` opens iframe | Iframe shows span with ±5-token context, both candidate cards with hints, confidence numbers |
| 3 | Press keyboard `1` (or click candidate 1) | iframe posts a single `pending_resolve(pending_id, entity_id="viktor-bezdek")` call; server updates `pending_disambiguation.status="resolved"`, writes `resolution_log` with method=`user-confirmed`, returns `{ok: true}` |
| 4 | Inspect output | Annotated file contains `[Viktor](@person:viktor-bezdek)`; `pending_disambiguation.status="resolved"`; `resolution_log` gets method=`user-confirmed`. If the user had instead picked "new", `pending_resolve` would insert a staging row server-side in the same call (no host-mediated chaining). |

### TS-004: Bootstrap the catalog from a YAML seed file
**Priority:** High
**Preconditions:** Empty DB; `docs/examples/entities.seed.yml` valid (per §25.3 shape).
**Mapped Tasks:** Task 8

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `/catalog-import docs/examples/entities.seed.yml` | Tool validates YAML against schema |
| 2 | On any duplicates: elicitation fires | User picks merge-into-existing or reject per duplicate |
| 3 | Observe completion | Summary: N entities created, M aliases, K phonetic rows, J trigram rows; `catalog_fts` row count matches entities count |
| 4 | `catalog_search("Viktor")` returns the viktor-bezdek entity with fts5 bm25 ranking |

### TS-005: Headless batch run queues non-auto items
**Priority:** High
**Preconditions:** Seeded catalog; three input files in `~/inputs/incoming/` with a mix of auto, ambiguous, and unknown surfaces.
**Mapped Tasks:** Task 7, 8, 9, 14

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Spawn `entity-resolver` subagent with batch=true on the folder | Subagent runs `resolve_link_text` with `{ interactive: false }` per file |
| 2 | Observe outputs | Annotated files written; sidecar JSON reports `pending_disambiguation: N`, `new_candidates: M` per file |
| 3 | `pending_list` returns N rows across all files; `staging_list` returns M unique surfaces (dedup respected) |
| 4 | Run `/review-staged` — Staging Review App shows the accumulated backlog from the batch |

### TS-006: Czech inflection case
**Priority:** High
**Preconditions:** Catalog includes `viktor-bezdek` with canonical "Viktor Bezdek", aliases ["Viktor"].
**Mapped Tasks:** Task 4, 5, 7

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Input text: "Mluvil jsem s Viktorovi včera" (dative case) | `resolve_link_text` normalizes "Viktorovi" → "viktor" via inflection strip |
| 2 | Observe output | "Viktorovi" auto-links to `@person:viktor-bezdek`; `resolution_log` confidence ≥ 0.85 |
| 3 | Input text: "Bezdekovy plány" (possessive) | "Bezdekovy" → "bezdek" via suffix strip; auto-links |

### TS-007: Elicitation fallback when Apps unavailable
**Priority:** Medium
**Preconditions:** Env var `ENTITY_LINKER_FORCE_ELICITATION=1` set; same ambiguous input as TS-003.
**Mapped Tasks:** Task 9, 11, 12

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `/link-file docs/examples/ambiguous-viktor.md` with the env var set | `resolve_disambiguate_app` calls `should_use_elicitation(ctx)` which returns True; branches to `elicit.disambiguate_span` loop |
| 2 | Pick "viktor-bezdek" from the elicitation form | Tool returns; same `pending_disambiguation.resolved` state as TS-003; `resolution_log` method=`user-confirmed` |
| 3 | Run `/review-staged` with env var set | `staging_review_app` branches to sequential `elicit.review_staging_item` loop; user drains queue via elicitation forms identical to the App's actions |

## Progress Tracking

- [x] Task 1: Plugin scaffold & manifests
- [x] Task 2: Python MCP server scaffold + pytest harness
- [x] Task 3: DB layer (schema, FTS5, WAL, async write-lock)
- [x] Task 4: Normalize module (Czech inflection)
- [x] Task 5: Index module (phonetic + trigram + rebuild-on-mutation)
- [x] Task 6: Candidate generation + scoring + type_fit rules
- [x] Task 7: Coref + `resolve_link_text` orchestrator
- [x] Task 8: Catalog / staging / pending tools + YAML seed import
- [x] Task 9: Elicitation fallback + render module
- [x] Task 10: MCP Apps scaffold (Vite + shared postMessage lib)
- [ ] Task 11: Disambiguation App UI + tool wiring
- [ ] Task 12: Staging Review App UI + tool wiring
- [ ] Task 13: Four skills (entity-linker, entity-matcher, input-preprocessing, entity-catalog-manage)
- [ ] Task 14: Subagent + eight slash commands
- [ ] Task 15: M0 micro-eval harness + synthesized labeled set
- [ ] Task 16: End-to-end acceptance + sample artifacts

**Total Tasks:** 16 | **Completed:** 0 | **Remaining:** 16

## Implementation Tasks

### Task 1: Plugin scaffold & manifests

**Objective:** Create the on-disk structure a Claude Code / Cowork plugin host needs to load: manifests, directory skeleton, README.
**Dependencies:** None
**Mapped Scenarios:** None (foundational)

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.mcp.json`
- Create: `README.md`
- Create: `.gitignore`
- Create: `skills/entity-linker/.gitkeep`, `skills/entity-matcher/.gitkeep`, `skills/input-preprocessing/.gitkeep`, `skills/entity-catalog-manage/.gitkeep`
- Create: `agents/.gitkeep`
- Create: `commands/.gitkeep`
- Create: `mcp-server/.gitkeep`
- Create: `docs/examples/.gitkeep`
- Create: `eval/.gitkeep`

**Key Decisions / Notes:**
- `plugin.json` per PRD §25.1 (version, description, author, license, keywords).
- `.mcp.json` per PRD §25.2 — `"command": "uv"`, `"args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}/mcp-server", "entity-db"]`, env `ENTITY_DB_PATH`.
- `.gitignore` must exclude `dist/`, `node_modules/`, `__pycache__/`, `.venv/`, `*.sqlite*`, `~/entity-db/`.
- README kept minimal: purpose, install command, quickstart (seed → link → review).

**Definition of Done:**
- [ ] `cat .claude-plugin/plugin.json | python3 -m json.tool` returns valid JSON with required fields.
- [ ] `cat .mcp.json | python3 -m json.tool` valid.
- [ ] `claude plugin validate .` (or equivalent) passes.
- [ ] Directory tree matches PRD §9.1.

**Verify:**
- `python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))"`
- `python3 -c "import json; json.load(open('.mcp.json'))"`

---

### Task 2: Python MCP server scaffold + pytest harness

**Objective:** Bootstrap the FastMCP server package with `uv`, declare dependencies, register one trivial health-check tool, wire pytest with coverage.
**Dependencies:** Task 1
**Mapped Scenarios:** None (foundational)

**Files:**
- Create: `mcp-server/pyproject.toml`
- Create: `mcp-server/src/entity_db/__init__.py`
- Create: `mcp-server/src/entity_db/server.py`
- Create: `mcp-server/src/entity_db/__main__.py`
- Create: `mcp-server/tests/conftest.py`
- Create: `mcp-server/tests/test_server.py`
- Create: `mcp-server/.python-version`

**Key Decisions / Notes:**
- `pyproject.toml` dependencies (pin minor versions to avoid drift): `fastmcp>=3.2,<4`, `pydantic>=2.5,<3`, `abydos>=0.5.0,<0.6`, `rapidfuzz>=3.6,<4`, `pyyaml>=6.0,<7`, `unicodedata2>=15` (if needed for robustness; stdlib `unicodedata` usually suffices). Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`. Commit `uv.lock` in Task 2.
- Project script: `[project.scripts] entity-db = "entity_db.__main__:main"`.
- `server.py`: `mcp = FastMCP("entity-db")`; one trivial `@mcp.tool async def health() -> dict` returning `{status: "ok"}`.
- `__main__.py`: imports `server.mcp`, calls `mcp.run()`.
- `conftest.py`: common fixtures (tmp DB path, anyio backend = asyncio).
- `test_server.py`: asserts `health()` returns `{"status": "ok"}` using FastMCP's in-process client.

**Definition of Done:**
- [ ] `uv sync --directory mcp-server` installs cleanly.
- [ ] `uv run --directory mcp-server pytest -q` reports ≥ 1 passing test, 0 failures.
- [ ] `uv run --directory mcp-server entity-db --help` or invocation works (server starts and exits on SIGTERM).

**Verify:**
- `uv sync --directory mcp-server && uv run --directory mcp-server pytest -q`

---

### Task 3: DB layer — schema, FTS5, WAL, async write-lock

**Objective:** Implement the full schema (PRD §10), FTS5 virtual table, WAL + single-writer async lock, migration-on-connect, plus index-rebuild helpers (called by later tasks).
**Dependencies:** Task 2
**Mapped Scenarios:** TS-001 preconditions

**Files:**
- Create: `mcp-server/src/entity_db/schema.sql`
- Create: `mcp-server/src/entity_db/db.py`
- Create: `mcp-server/tests/test_db.py`

**Key Decisions / Notes:**
- `schema.sql`: exactly the tables from PRD §10 + `catalog_fts` virtual table with `tokenize = 'unicode61 remove_diacritics 2'`.
- `db.py` exposes:
  - `open_db(path: str | Path) -> aiosqlite.Connection`-like wrapper; uses `sqlite3` in thread-executor for v0 simplicity (not `aiosqlite` — avoid extra dep; wrap blocking calls with `asyncio.to_thread`).
  - `_write_lock: asyncio.Lock` module-level; acquired via `async with _write_lock:` by all mutating helpers.
  - `migrate(conn)`: runs `schema.sql` idempotently on open.
  - `enable_wal(conn)`: `PRAGMA journal_mode=WAL;`.
  - `rebuild_fts_for(conn, entity_id)`: deletes + re-inserts the single `catalog_fts` row for that entity (concatenates aliases).
  - `rebuild_phonetic_for(conn, alias_key)` and `rebuild_trigrams_for(conn, alias_key)`: placeholders (real logic lands in Task 5; define interfaces here).
- Tests: init on empty path; re-init idempotent; WAL pragma persisted; write-lock under concurrent writes; FTS rebuild visible via `MATCH`.

**Definition of Done:**
- [ ] `open_db(tmp_path / "x.sqlite")` succeeds; schema applied.
- [ ] `PRAGMA journal_mode` returns `wal`.
- [ ] Concurrent writes serialize (test launches 10 tasks, no corruption, all commit).
- [ ] `catalog_fts` queryable via `MATCH`.
- [ ] All tests pass; coverage ≥ 80% on `db.py`.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_db.py -q --cov=entity_db.db --cov-fail-under=80`

---

### Task 4: Normalize module (Czech inflection)

**Objective:** Pure-function normalization chain (NFC → lowercase → diacritics strip → punctuation strip → Czech/Slovak/Polish suffix strip) that produces a canonical `alias_key`.
**Dependencies:** Task 2
**Mapped Scenarios:** TS-006

**Files:**
- Create: `mcp-server/src/entity_db/matching/__init__.py`
- Create: `mcp-server/src/entity_db/matching/normalize.py`
- Create: `mcp-server/tests/test_normalize.py`

**Key Decisions / Notes:**
- `normalize_text(s: str) -> str`: deterministic, no side effects.
- Suffix list (PRD §14): `["-ovi","-em","-a","-e","-y","-u","-ou","-ům","-ech","-ami","-ův","-ova","-ovo"]`, longest first.
- Only strip if remaining stem ≥ 3 chars.
- Expose `derive_alias_variants(canonical: str) -> list[str]`: last-name-only, first-name-only, initials ("VB"), acronym-of-canonical ("FAI" for "Foundry AI Initiative"), diacritic-free.
- Test vectors: "Viktor Bezdek" → aliases include "viktor", "bezdek", "vb"; "Viktorovi" → "viktor"; "FoundryAI" → "foundryai", "fai"; "Tomáš" → "tomas" after diacritics strip; "Eva" NOT stripped past "eva".

**Definition of Done:**
- [ ] `normalize_text("Viktorovi")` == `"viktor"`.
- [ ] `normalize_text("Bezdekovy")` == `"bezdek"`.
- [ ] `normalize_text("Tomáš")` == `"tomas"`.
- [ ] `normalize_text("Eva")` == `"eva"` (no strip; stem too short).
- [ ] `derive_alias_variants("Viktor Bezdek")` contains `{"viktor", "bezdek", "vb"}`.
- [ ] 100% branch coverage on normalize.py.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_normalize.py -q --cov=entity_db.matching.normalize --cov-fail-under=95`

---

### Task 5: Index module — phonetic + trigram + rebuild-on-mutation

**Objective:** Compute phonetic keys (Double Metaphone + Beider-Morse via abydos) and char-trigrams for every alias; wire DB inserts so the index auto-rebuilds when catalog mutates.
**Dependencies:** Task 3, Task 4
**Mapped Scenarios:** TS-001, TS-006

**Files:**
- Create: `mcp-server/src/entity_db/matching/index.py`
- Create: `mcp-server/tests/test_index.py`
- Modify: `mcp-server/src/entity_db/db.py` — implement `rebuild_phonetic_for` and `rebuild_trigrams_for` using the new index module.

**Key Decisions / Notes:**
- **⛔ PRE-TASK SPIKE (required, 10 minutes, before any code):** `uv run --directory mcp-server python -c "from abydos.phonetic import BeiderMorse, DoubleMetaphone; bm = BeiderMorse(); dm = DoubleMetaphone(); print('BMPM:', bm.encode('Bezdek'), '| DM:', dm.encode('Bezdek'))"`. If this fails (import error, incompatible Python version, or empty output), STOP and apply fallback: swap `abydos` for `jellyfish` (DM only), write a minimal hand-rolled BMPM stub covering Czech/Slavic name corpus, and document in A1 + v1 backlog entry for full BMPM. Do not proceed to implementation until spike is green.
- `compute_phonetic_keys(alias_key: str) -> dict[str, list[str]]`: returns `{"dmetaphone": [...], "beider-morse": [...]}`. Multiple keys per algo (primary+secondary for DM, multi-language for BMPM). Use `abydos.phonetic.DoubleMetaphone` and `abydos.phonetic.BeiderMorse` (language hint: auto-detect or leave default). **Exact import paths confirmed in the spike.**
- `compute_trigrams(alias_key: str) -> list[str]`: char-level, padded with `^` and `$` at boundaries (`^vi`, `vik`, `ikt`, ..., `ek$`). Short aliases (< 3 chars) produce empty trigrams.
- BMPM: use `mode="approx"` for broader recall; `language_arg=0` (auto); strip empty keys.
- **Latency:** phonetic keys computed once per alias at index time (inside `rebuild_phonetic_for`). Never compute during `resolve_link_text` hot path for catalog entries. Only compute for the query-side candidate window (1–4 tokens, cheap).
- Rebuild hooks in `db.py`: `upsert_alias(entity_id, alias)` calls `rebuild_phonetic_for(alias_key)` and `rebuild_trigrams_for(alias_key)` inside the write-lock.
- Tests: Czech names ("Bezděk", "Viktor") yield phonetic keys that match ASR mis-hearings ("Besdek", "Viktor"); trigram sets overlap appropriately.

**Definition of Done:**
- [ ] `compute_phonetic_keys("bezdek")` returns non-empty DM and BMPM lists.
- [ ] `compute_phonetic_keys("besdek")` shares ≥ 1 BMPM key with `"bezdek"`.
- [ ] `compute_trigrams("foundryai")` has 10 trigrams.
- [ ] Inserting an alias via `upsert_alias` populates `phonetic_index` and `trigrams` tables.
- [ ] Deleting an alias removes its index rows.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_index.py -q --cov=entity_db.matching.index --cov-fail-under=85`

---

### Task 6: Candidate generation + scoring + type_fit rules

**Objective:** Implement the full matching score formula (PRD §14) with the 7 type_fit cue families, plus sliding-window candidate generation.
**Dependencies:** Task 5
**Mapped Scenarios:** TS-001, TS-003, TS-006

**Files:**
- Create: `mcp-server/src/entity_db/matching/candidates.py`
- Create: `mcp-server/src/entity_db/matching/score.py`
- Create: `mcp-server/src/entity_db/matching/type_fit.py`
- Create: `mcp-server/tests/test_candidates.py`
- Create: `mcp-server/tests/test_score.py`
- Create: `mcp-server/tests/test_type_fit.py`

**Key Decisions / Notes:**
- `generate_candidates(text: str, db: Connection) -> list[CandidateSpan]`:
  - Tokenize on whitespace+punctuation.
  - Sliding windows 1–4 tokens.
  - Filter: stopwords removed (English + Czech minimal set), windows whose normalized key is empty skipped, windows ≤ 2 chars require exact alias match.
  - For each window, look up matches in `aliases`, `phonetic_index`, `trigrams`; dedupe by entity.
- `score(candidate: CandidateSpan, context: Context) -> float`:
  - `lex` = `rapidfuzz.fuzz.WRatio(window, alias) / 100` — max over all matching aliases of the entity.
  - `phon` = 1.0 if any shared phonetic key, else Jaccard of phonetic-key sets.
  - `type_fit` = `type_fit.score(context_tokens, entity.type)` in [0, 1].
  - `local_recency` = 0.1 if entity already linked elsewhere in this source, else 0.
  - `short_pen` = 0.05 if alias_key length < 3, else 0.
  - `ambig_pen` = 0.05 if > 2 candidates above 0.70 for same window, else 0.
  - Clamp final to [0, 1].
- `type_fit.py` — 7 cue families per PRD §14:
  - `PERSON_CUES = ["with", "met", "called", "said", "from", honorifics...]`
  - `PROJECT_CUES = ["project", "rollout", "launch", "initiative"]`
  - `PRODUCT_CUES = ["feature", "ship", "release", "'s UI"]`
  - `TEAM_CUES = ["team", "squad", "tribe"]`
  - `COMPANY_CUES = ["at", "acquired by", "joined"]` + regex legal suffixes (`\b(Inc|LLC|AG|s\.r\.o\.)\b`)
  - `ACRONYM_CUES`: all-caps ≤ 5 chars, exact alias match
  - `CONCEPT_CUES = ["what is", "the concept of"]`
  - Returns 1.0 if any cue matches within ±3 tokens, 0.5 baseline, 0.3 if conflicting cue family.
- Full cue dictionary lives in `skills/entity-matcher/references/scoring.md` but is imported into `type_fit.py` as Python constants (Task 13 writes the reference doc; Task 6 defines the constants).

**Definition of Done:**
- [ ] Sliding window produces expected candidates on "So I synced with Viktor yesterday about FoundryAI rollout".
- [ ] Score of "Viktor" against `viktor-bezdek` with person-type cues ≥ 0.90.
- [ ] Score of "Viktor" against a project-type entity with same normalized alias ≤ 0.65 due to type_fit penalty.
- [ ] `ambig_pen` fires when 3+ candidates scored ≥ 0.70.
- [ ] Coverage ≥ 80% on all three new files.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_candidates.py tests/test_score.py tests/test_type_fit.py -q --cov=entity_db.matching --cov-fail-under=80`

---

### Task 7: Coref + `resolve_link_text` orchestrator

**Objective:** Within-source coreference pass + the end-to-end `resolve_link_text` pure-compute tool that ties normalize → candidates → score → coref → threshold-decide → shape output.
**Dependencies:** Task 6
**Mapped Scenarios:** TS-001, TS-003, TS-005, TS-006

**Files:**
- Create: `mcp-server/src/entity_db/matching/coref.py`
- Create: `mcp-server/src/entity_db/matching/resolver.py`
- Create: `mcp-server/tests/test_coref.py`
- Create: `mcp-server/tests/test_resolver.py`

**Key Decisions / Notes:**
- `coref.propagate(resolutions: list[Resolution]) -> list[Resolution]`: same surface → same entity (highest-confidence wins); emit `entity_drift` warning if two spans of same surface resolve to different entities.
- `resolver.resolve_link_text(text: str, source_type: str, options: ResolveOptions, db) -> ResolveResult`:
  - Compute `source_hash = hashlib.sha256(text.encode()).hexdigest()[:16]`.
  - Generate candidates → score → rank per span.
  - **Decide:** auto if `top ≥ 0.90 AND (top − second) ≥ 0.10`; ambiguous if `top ≥ 0.70`; new-candidate trigger if entity-shaped (capitalized, freq ≥ 2, no match).
  - Coref pass across auto-links first, then ambiguities (ambiguity may resolve to auto-link after coref — PRD §15). **v0 scope: surface-equality propagation only. No pronoun resolution (Autonomous Decisions).**
  - Contradiction check: compare context tokens against `entity.attributes_json` (light regex); warn but do not break.
  - Write `resolution_log` for auto spans with `method="auto"`; for ambiguities under `{interactive: false}` write `method="queued"` and insert `pending_disambiguation` rows; for new candidates write/upsert `staging` with dedup_key.
  - Return `{resolutions, ambiguities, new_candidates, warnings, stats, source_hash}`.
- `ResolveOptions` Pydantic model per PRD §11.
- Tests: end-to-end on a handcrafted 300-word markdown snippet with mixed auto/ambiguous/new-candidate spans; assert DB state matches expectations.

**Definition of Done:**
- [ ] `resolve_link_text(...)` on a seeded DB auto-links known entities, queues ambiguities when interactive=False, stages unknowns.
- [ ] Coref propagates: "Viktor" → `viktor-bezdek` then "he" adjacent does NOT (v0 doesn't resolve pronouns) but a second "Viktor" span inherits.
- [ ] `source_hash` stable for same input.
- [ ] `resolution_log` and `pending_disambiguation` and `staging` states correct per branch.
- [ ] Coverage ≥ 80% on resolver.py and coref.py.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_coref.py tests/test_resolver.py -q --cov=entity_db.matching.coref --cov=entity_db.matching.resolver --cov-fail-under=80`

---

### Task 8: Catalog / staging / pending tools + YAML seed import

**Objective:** Expose all MCP tools from PRD §11 (catalog_*, staging_*, pending_*) + `catalog_import` that parses YAML per §25.3 flat-list schema.
**Dependencies:** Task 7
**Mapped Scenarios:** TS-001, TS-002, TS-004, TS-005

**Files:**
- Create: `mcp-server/src/entity_db/tools/__init__.py`
- Create: `mcp-server/src/entity_db/tools/catalog.py` (includes `catalog_stats` alongside the other catalog tools)
- Create: `mcp-server/src/entity_db/tools/staging.py`
- Create: `mcp-server/src/entity_db/tools/pending.py`
- Create: `mcp-server/src/entity_db/seed.py`
- Create: `mcp-server/tests/test_tools_catalog.py` (covers `catalog_stats` too)
- Create: `mcp-server/tests/test_tools_staging.py`
- Create: `mcp-server/tests/test_tools_pending.py`
- Create: `mcp-server/tests/test_seed.py`
- Create: `docs/examples/entities.seed.yml`
- Modify: `mcp-server/src/entity_db/server.py` — register all tools.

**Key Decisions / Notes:**
- Each module exposes `register(mcp: FastMCP)` that decorates tool functions; `server.py` calls all `register`s.
- Pydantic models for every tool input with explicit field descriptions (FastMCP auto-generates MCP schemas from them).
- `catalog_import(yaml_path: str) -> ImportReport`: parse → validate (`Entity` Pydantic model) → upsert → rebuild derived aliases + indices. Duplicates surface via `DuplicateEntity` elicitation (merge/reject/overwrite). In headless mode, duplicates error.
- `catalog_stats() -> CatalogStats`: returns `{entities: int, entities_by_type: dict, aliases: int, staging_pending: int, pending_disambiguation: int, recent_resolutions: int (last 24h), last_resolution_at: timestamp}`. Powers `/entity-stats` slash command (Task 14).
- `staging_approve(staging_id, merge_into=None)`: on approve-new, create entity and alias; on merge, add alias to existing; both paths back-fill `resolution_log` for past sources (query `source_hash`s from `resolution_log` where `surface=staging.surface` and `entity_id IS NULL`).
- `pending_resolve(pending_id, entity_id_or_sentinel)`: where sentinel is a literal entity_id, `"none"`, or `"new"`. For `"new"`, **the server inserts a `staging` row itself (calls `staging_stage` internally)** and returns `{staging_id, pending_status}` so the client does not need to chain a second tool call. For `"none"`, marks `pending_disambiguation.status=abandoned`. For an entity_id, backfills `resolution_log` and re-runs coref.
- `docs/examples/entities.seed.yml` = the PRD §25.3 sketch + 3–4 more entities (Tomas, Adam, Groupon, one product). Used by TS-001/TS-004/TS-005.

**Definition of Done:**
- [ ] All tools callable via FastMCP in-process client.
- [ ] `catalog_import` on the sample YAML creates entities, derived aliases, phonetic rows, trigrams, and FTS rows.
- [ ] `catalog_stats` returns non-zero counts after seed import; test covers empty-DB and populated-DB cases.
- [ ] `staging_approve(id)` back-fills `resolution_log` for any prior source that mentioned the surface.
- [ ] `pending_resolve(..., "new")` writes a staging row and returns its id without requiring a separate client call.
- [ ] `pending_resolve` updates the row and the log.
- [ ] Coverage ≥ 80% on `tools/` and `seed.py`.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_tools_catalog.py tests/test_tools_staging.py tests/test_tools_pending.py tests/test_seed.py -q --cov=entity_db.tools --cov=entity_db.seed --cov-fail-under=80`

---

### Task 9: Elicitation fallback + render module

**Objective:** Elicitation helpers (single-select per PRD §9.4) used by Apps when host lacks App support; render module producing markdown/XML/sidecar output.
**Dependencies:** Task 7
**Mapped Scenarios:** TS-007, all (render used by every flow)

**Files:**
- Create: `mcp-server/src/entity_db/elicit.py`
- Create: `mcp-server/src/entity_db/render.py`
- Create: `mcp-server/tests/test_elicit.py`
- Create: `mcp-server/tests/test_render.py`

**Key Decisions / Notes:**
- `elicit.should_use_elicitation(ctx) -> bool`: **central fallback gate.** Returns `True` if (a) `os.environ.get("ENTITY_LINKER_FORCE_ELICITATION") == "1"` OR (b) host capability sniff indicates MCP Apps resources unsupported (check via FastMCP ctx — if `ctx.session.client_params` indicates no `experimental.apps` capability, fall back). Every App-opening tool in Task 11/12 (`resolve_disambiguate_app`, `staging_review_app`) MUST call this helper first and branch.
- `elicit.disambiguate_span(ctx, pending_row, db)`: builds a `Literal[...]` dynamic enum from candidate entity_ids + "none" + "new", calls `ctx.elicit`; returns resolution. Invoked by the App-tool fallback branch per-span in a loop.
- `elicit.review_staging_item(ctx, staging_row, db)`: sequential form via `StagingApproval` BaseModel (decision, merge_target, corrected_type, corrected_name).
- `render.to_markdown(text, resolutions)` — PRD §13 default format; `?` suffix for user-confirmed suggest-tier.
- `render.to_xml(text, resolutions)` — per PRD §13 XML format with `id`, `type`, `confidence`.
- `render.to_sidecar(text, resolutions)` — returns `(original_text, sidecar_json_dict)` where sidecar has span offsets. Round-trip: combining sidecar back against original reproduces markdown output.
- Unit tests: every format round-trips; span offsets stable under unicode input.

**Definition of Done:**
- [ ] `to_markdown` on known output matches golden string.
- [ ] `to_xml` matches golden string.
- [ ] `to_sidecar` preserves original text byte-for-byte; JSON has `resolutions: [{start, end, entity_id, type, confidence, method}]`.
- [ ] Elicit helpers return correct `Resolution` object on "accept" action; handle decline/cancel.
- [ ] Coverage ≥ 85% on elicit + render.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_elicit.py tests/test_render.py -q --cov=entity_db.elicit --cov=entity_db.render --cov-fail-under=85`

---

### Task 10: MCP Apps scaffold — Vite + shared postMessage lib

**Objective:** Set up two React+Vite+TypeScript projects under `mcp-server/apps/{disambiguation,staging}/`, plus a shared lib for the MCP host postMessage bridge; establish the build → inlined `dist/index.html` pipeline.
**Dependencies:** Task 1
**Mapped Scenarios:** None (foundational); unblocks TS-002, TS-003

**Files:**
- Create: `mcp-server/apps/shared/package.json`
- Create: `mcp-server/apps/shared/src/mcp-app-bridge.ts`
- Create: `mcp-server/apps/shared/src/index.ts`
- Create: `mcp-server/apps/shared/tsconfig.json`
- Create: `mcp-server/apps/disambiguation/package.json`
- Create: `mcp-server/apps/disambiguation/vite.config.ts`
- Create: `mcp-server/apps/disambiguation/index.html`
- Create: `mcp-server/apps/disambiguation/src/main.tsx`
- Create: `mcp-server/apps/disambiguation/src/App.tsx` (stub renders "Disambiguation App loaded")
- Create: `mcp-server/apps/disambiguation/tsconfig.json`
- Create: `mcp-server/apps/staging/package.json`
- Create: `mcp-server/apps/staging/vite.config.ts`
- Create: `mcp-server/apps/staging/index.html`
- Create: `mcp-server/apps/staging/src/main.tsx`
- Create: `mcp-server/apps/staging/src/App.tsx` (stub)
- Create: `mcp-server/apps/staging/tsconfig.json`
- Create: `mcp-server/apps/README.md`

**Key Decisions / Notes:**
- Each App's `vite.config.ts`: `build.assetsInlineLimit: 0`, `build.rollupOptions.output.inlineDynamicImports: true`, `base: './'` (important — iframe loads from arbitrary host path). Use `vite-plugin-singlefile@>=2.0` for inlining; pin in `package.json`.
- Single-file builds: `vite-plugin-singlefile` so `dist/index.html` is the only artifact.
- Shared lib exports:
  - `onMcpMessage<T>(callback: (data: T) => void)` — registers `window.addEventListener('message', ...)`.
  - `postMcpAction(tool: string, args: object)` — `window.parent.postMessage({type: 'mcp:tool-result', tool, args}, '*')`.
  - `postMcpReady()` — posts `{type: 'mcp:ready'}` to `window.parent` on mount; host replays initial payload after seeing this. Prevents iframe cold-load postMessage race.
  - `isMcpAppsHost(): boolean` — detects the MCP host via a sentinel in the received payload (the host posts `{type: 'mcp:init', version: ...}` before any tool data).
- Disambiguation App `App.tsx` stub: renders loaded state; calls `postMcpReady()` on mount; real UI in Task 11.
- Staging App stub same; real UI in Task 12.
- `npm run build` in each app produces `dist/index.html`.
- **Bundle budget:** **< 400 KB gzipped** per App (realistic for React + ReactDOM + app code). **Checkpoint after first stub build:** if over budget, swap React → Preact (API-compatible, ~10 KB core) before Task 11/12. Document swap decision in Task 11 Key Decisions.

**Definition of Done:**
- [ ] `cd mcp-server/apps/disambiguation && npm install && npm run build` → `dist/index.html` exists, single-file, < 400 KB gzipped.
- [ ] Same for `apps/staging`.
- [ ] Shared lib compiles with `tsc --noEmit`.
- [ ] Stub apps render "<App name> loaded" when opened standalone.
- [ ] `postMcpReady()` unit test: mock `window.parent.postMessage`, mount stub, assert `mcp:ready` posted exactly once.
- [ ] If bundle exceeds budget, React→Preact swap documented and re-measured.

**Verify:**
- `cd mcp-server/apps/disambiguation && npm install --silent && npm run build && test -f dist/index.html`
- `cd mcp-server/apps/staging && npm install --silent && npm run build && test -f dist/index.html`

---

### Task 11: Disambiguation App UI + tool wiring

**Objective:** Full Disambiguation App UI (span cards, candidate selection, keyboard shortcuts, "none"/"new" actions) + FastMCP tool `resolve_disambiguate_app` wired with `AppConfig(resource_uri=...)`.
**Dependencies:** Task 7, Task 9, Task 10
**Mapped Scenarios:** TS-003, TS-007 (fallback)

**Files:**
- Modify: `mcp-server/apps/disambiguation/src/App.tsx` (full UI)
- Create: `mcp-server/apps/disambiguation/src/components/SpanCard.tsx`
- Create: `mcp-server/apps/disambiguation/src/components/CandidateList.tsx`
- Create: `mcp-server/apps/disambiguation/src/styles.css`
- Create: `mcp-server/src/entity_db/tools/app_disambiguation.py`
- Create: `mcp-server/src/entity_db/resources.py` (registers `ui://entity-db/disambiguation.html`)
- Create: `mcp-server/tests/test_app_disambiguation.py`
- Modify: `mcp-server/src/entity_db/server.py` — register the resource and tool.

**Key Decisions / Notes:**
- Tool signature: `async def resolve_disambiguate_app(source_hash: str, ambiguity_ids: list[str] | None = None) -> list[PendingItem]`. Tool first calls `elicit.should_use_elicitation(ctx)` — if True, branches to per-span `elicit.disambiguate_span` loop and skips App UI. Otherwise returns the payload; host loads iframe with `ui://entity-db/disambiguation.html`; payload passed via postMessage init.
- If ambiguity_ids is None, fetch all pending for source_hash.
- Resource reads `Path(__file__).resolve().parents[2] / "apps" / "disambiguation" / "dist" / "index.html"`. From `src/entity_db/resources.py`, `parents[2]` = `mcp-server/`. Deterministic for any install path as long as the bundle preserves the `mcp-server/apps/` layout.
- UI: paginated span cards (5 per view by default; scroll through). Each card shows source excerpt with highlighted span (±5 tokens), candidate list (name, type badge, `disambiguation_hint`, confidence %), action buttons (keyboard 1–9 pick, N for none, K for skip, E for "new entity").
- Pick → `postMcpAction('pending_resolve', {pending_id, entity_id: <id>})`. "None" → `postMcpAction('pending_resolve', {pending_id, entity_id: 'none'})`. "New" → `postMcpAction('pending_resolve', {pending_id, entity_id: 'new'})`. **The server-side `pending_resolve` handles the chain-to-staging internally (see Task 8)** — the iframe makes a single call and receives `{staging_id}` in the result if applicable. No host-mediated chaining.
- On server side, the MCP host invokes the posted tool; iframe is pure presentation and doesn't know about Python — just names tools.
- If React bundle exceeded 400 KB gzipped in Task 10 checkpoint, this task uses Preact instead (imports flip from `react` → `preact/compat` or direct `preact`). Document the choice here.
- Backend test: tool returns correct payload; fallback engages when `ENTITY_LINKER_FORCE_ELICITATION=1` or when host lacks Apps capability.
- UI test: component renders expected structure given sample payload (React/Preact Testing Library).

**Definition of Done:**
- [ ] `resolve_disambiguate_app` returns correct payload for a source_hash with pending items.
- [ ] `ui://entity-db/disambiguation.html` resource returns the built HTML.
- [ ] UI renders ≥ 1 span card given mock payload.
- [ ] Keyboard shortcut 1 triggers pick; `postMcpAction` called with correct args (mocked).
- [ ] Fallback path calls `ctx.elicit` when env var set.
- [ ] Coverage ≥ 75% on tool; snapshot tests on UI components.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_app_disambiguation.py -q`
- `cd mcp-server/apps/disambiguation && npm test`

---

### Task 12: Staging Review App UI + tool wiring

**Objective:** Full Staging Review App UI (paginated queue, bulk actions, autocomplete for merge target, evidence expansion) + FastMCP `staging_review_app` tool.
**Dependencies:** Task 8, Task 9, Task 10
**Mapped Scenarios:** TS-002, TS-005 (backlog drain)

**Files:**
- Modify: `mcp-server/apps/staging/src/App.tsx`
- Create: `mcp-server/apps/staging/src/components/CandidateRow.tsx`
- Create: `mcp-server/apps/staging/src/components/EvidencePanel.tsx`
- Create: `mcp-server/apps/staging/src/components/MergeAutocomplete.tsx`
- Create: `mcp-server/apps/staging/src/styles.css`
- Create: `mcp-server/src/entity_db/tools/app_staging.py`
- Create: `mcp-server/tests/test_app_staging.py`
- Modify: `mcp-server/src/entity_db/server.py`
- Modify: `mcp-server/src/entity_db/resources.py` — register `ui://entity-db/staging.html`.

**Key Decisions / Notes:**
- Tool: `async def staging_review_app(staging_ids: list[str] | None = None) -> list[StagingItem]`. Default: all pending sorted by frequency desc.
- Autocomplete calls `catalog_search` via postMessage as the user types (debounced 150 ms).
- Bulk-reject requires a reason confirmation.
- After any decision, UI re-fetches the queue so the list updates without full iframe reload.
- Fallback: loop over items calling `elicit.review_staging_item`.

**Definition of Done:**
- [ ] Tool returns sorted queue.
- [ ] UI renders ≥ 1 row with evidence expand, merge autocomplete, approve/reject buttons.
- [ ] Approve → posts `staging_approve(staging_id, merge_into?)`; mock verifies.
- [ ] Bulk-reject posts multiple `staging_reject` calls.
- [ ] Fallback elicitation reaches same end state.
- [ ] Coverage ≥ 75% on tool.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_app_staging.py -q`
- `cd mcp-server/apps/staging && npm test`

---

### Task 13: Skills — entity-linker, entity-matcher, input-preprocessing, entity-catalog-manage

**Objective:** Write the four SKILL.md bodies and their reference files; implement `input-preprocessing` sub-cleaners (ASR, email, markdown, HTML, plain).
**Dependencies:** Task 8, Task 11, Task 12 (skills reference the tools + Apps)
**Mapped Scenarios:** TS-001, TS-004, TS-005, TS-007 (skills mediate all flows)

**Files:**
- Create: `skills/entity-linker/SKILL.md`
- Create: `skills/entity-matcher/SKILL.md`
- Create: `skills/entity-matcher/references/algorithms.md`
- Create: `skills/entity-matcher/references/scoring.md`
- Create: `skills/entity-matcher/references/edge-cases.md`
- Create: `skills/input-preprocessing/SKILL.md`
- Create: `skills/input-preprocessing/references/asr.md`
- Create: `skills/input-preprocessing/references/email.md`
- Create: `skills/input-preprocessing/references/markdown.md`
- Create: `skills/input-preprocessing/references/html.md`
- Create: `skills/input-preprocessing/references/plain.md`
- Create: `skills/entity-catalog-manage/SKILL.md`
- Create: `mcp-server/src/entity_db/preprocess/__init__.py`
- Create: `mcp-server/src/entity_db/preprocess/asr.py`
- Create: `mcp-server/src/entity_db/preprocess/email.py`
- Create: `mcp-server/src/entity_db/preprocess/markdown.py`
- Create: `mcp-server/src/entity_db/preprocess/html.py`
- Create: `mcp-server/src/entity_db/preprocess/detect.py` (heuristic source-type detection)
- Create: `mcp-server/tests/test_preprocess.py`

**Key Decisions / Notes:**
- Every SKILL.md has proper YAML frontmatter (name, description with triggers, model: inherit, tools: needed).
- `entity-linker/SKILL.md`: procedural — resolves the input file, runs preprocess, calls `resolve_link_text`, opens Apps (or falls back), writes output.
- `entity-matcher/SKILL.md`: concise reference overview; scoring formula + cue families live in `references/scoring.md` (imported constants match Task 6).
- `input-preprocessing/SKILL.md`: per-source-type cleanup; the module implements the actual functions, the skill tells Claude when to invoke which preprocessor.
- `entity-catalog-manage/SKILL.md`: wraps catalog_*/staging_* tools with user-friendly confirmations; uses Apps primary, elicitation fallback.
- Preprocess module: `clean(text: str, source_type: Literal[...]) -> str` dispatches; `detect_source_type(text: str) -> Literal[...]` uses heuristics (header regex for email; timestamps for ASR; `<html` for HTML; markdown heading patterns for markdown; else plain).
- **Email sub-items (`preprocess/email.py` — explicit scope):**
  - (a) Header strip: `From:`, `To:`, `Cc:`, `Bcc:`, `Subject:`, `Date:`, `Reply-To:`, `Message-ID:`, `MIME-Version:`, `Content-Type:` — consume leading lines until first blank.
  - (b) Signature block detection: two-newlines followed by `-- ` (RFC 3676) OR a trailing block of ≤ 6 lines matching `<name>\n<role>\n<company>\n...` heuristics. Strip.
  - (c) Quoted-reply stripping: lines prefixed with `> ` OR a block starting with `On <DATE>, <NAME> wrote:` — strip.
  - (d) **Explicit deferral:** email local-part as aliasing hint (e.g. `viktor.bezdek@groupon.com` → `viktor.bezdek`) — v1, not this task.
- SKILL.md body ≤ 500 lines per file; reference files hold the detail.

**Definition of Done:**
- [ ] All 4 SKILL.md files have valid frontmatter; each mentions the trigger phrases from PRD §10.
- [ ] `entity-matcher/references/scoring.md` contains the full 7-family cue dictionary.
- [ ] Preprocess dispatch: `clean(msg, "email")` strips headers (a), signatures (b), and quoted replies (c); `clean(html, "html")` extracts text; `clean(asr, "asr")` strips timestamps and filler tokens; etc.
- [ ] `detect_source_type` correctly classifies 5 sample strings.
- [ ] Email preprocessing has unit tests for each of (a), (b), (c).
- [ ] Preprocess tests ≥ 85% coverage.

**Verify:**
- `uv run --directory mcp-server pytest tests/test_preprocess.py -q --cov=entity_db.preprocess --cov-fail-under=85`
- `python3 -c "import yaml; yaml.safe_load(open('skills/entity-linker/SKILL.md').read().split('---')[1])"` (frontmatter validity)

---

### Task 14: Subagent + eight slash commands

**Objective:** Create the `entity-resolver` subagent and the eight slash-command dispatchers.
**Dependencies:** Task 13
**Mapped Scenarios:** TS-001 (/link-file), TS-002 (/review-staged), TS-004 (/catalog-import), TS-005 (subagent)

**Files:**
- Create: `agents/entity-resolver.md`
- Create: `commands/link-file.md`
- Create: `commands/link-text.md`
- Create: `commands/link-folder.md`
- Create: `commands/review-staged.md`
- Create: `commands/add-entity.md`
- Create: `commands/entity-search.md`
- Create: `commands/entity-stats.md`
- Create: `commands/catalog-import.md`

**Key Decisions / Notes:**
- `agents/entity-resolver.md` frontmatter (plugin-compatible — **NO** `hooks`/`mcpServers`/`permissionMode`):
  ```yaml
  ---
  name: entity-resolver
  description: >
    Resolves entity mentions in text inputs against the entity catalog.
    Use for long inputs (>5k tokens) or batch processing of folders.
    Returns a summary and paths to annotated output files.
  tools: Read, Write, Bash
  skills:
    - entity-linker
    - input-preprocessing
  model: inherit
  isolation: worktree
  ---
  ```
- Body: invoke entity-linker skill, handle folder iteration for batch, summarize results.
- Each command file has concise frontmatter (description, argument-hint) + body that tells Claude what to do. Thin — just routes to the skill or subagent.
- `/link-folder` explicitly spawns the subagent.
- `/link-file` / `/link-text` invoke the entity-linker skill inline.
- `/catalog-import`: takes path arg, calls `catalog_import` MCP tool.
- `/entity-search <query>`: calls `catalog_search`, shows results.
- `/entity-stats`: invokes the `catalog_stats` tool implemented in Task 8.
- **⛔ Pre-Task spike: `isolation: worktree` support verification.** Install the plugin locally (`claude plugin install-local /Users/vbezdek/Work/entitiy-memory-plugin`), invoke `/link-folder` on a fixture folder, observe whether the subagent actually runs in an isolated worktree (check `git worktree list`). If unsupported, remove the `isolation: worktree` field from the subagent frontmatter and document in Autonomous Decisions: "long-input isolation achieved by parent summarizing only, not true worktree isolation."

**Definition of Done:**
- [ ] `claude plugin validate` passes with agent and all 8 commands.
- [ ] Subagent frontmatter has no forbidden fields (no `hooks`, `mcpServers`, `permissionMode`).
- [ ] `isolation: worktree` verified or documented-as-unsupported.
- [ ] Every command file has frontmatter + body.
- [ ] `/link-folder` delegates to subagent.
- [ ] `/entity-stats` returns live counts from `catalog_stats`.

**Verify:**
- `python3 -c "import yaml; [yaml.safe_load(open(f).read().split('---')[1]) for f in ['agents/entity-resolver.md'] + [f'commands/{c}.md' for c in ['link-file','link-text','link-folder','review-staged','add-entity','entity-search','entity-stats','catalog-import']]]"`

---

### Task 15: M0 micro-eval — synthesized 50-span labeled set + scoring validation

**Objective:** Build a synthesized 50-span hand-labeled eval set (Viktor reviews), run scoring through it, report precision/recall at threshold 0.90. Surface weight-tuning opportunities.
**Dependencies:** Task 7
**Mapped Scenarios:** Goal Verification truth #8

**Files:**
- Create: `eval/m0-spans.yml` (synthesized 50 spans drawn from PRD examples + common Czech name set; Viktor reviews before running)
- Create: `eval/README.md`
- Create: `mcp-server/src/entity_db/eval.py` (harness)
- Create: `mcp-server/tests/test_eval.py`
- Create: `eval/results/.gitkeep`

**Key Decisions / Notes:**
- `m0-spans.yml` schema:
  ```yaml
  version: 1
  spans:
    - text: "So I synced with Viktor yesterday about FoundryAI"
      span: [19, 25]                   # byte offsets of "Viktor"
      expected_entity: viktor-bezdek   # or null for "should NOT link"
      expected_method: auto            # or "ambiguous" or "unresolved"
      source_type: markdown
      notes: "Person cue 'synced with'"
  ```
- Coverage: 15 Czech-inflected variants, 10 acronyms/partial-names, 10 ambiguous-by-type (multi-candidate), 10 should-not-link, 5 email-context, 5 transcript-ASR-variants, 5 homograph cases. Synthesized from PRD §10.3 + §13 examples + B2C EM names.
- Harness: load spans → init test DB from seed → run `resolve_link_text` per span's text → compare actual vs expected.
- Reports: precision, recall, per-category breakdown, per-score-bucket histogram.
- **Gate:** if precision @ 0.90 threshold < 0.95 → surface tuning sub-actions (e.g. "bump lex weight to 0.50") as structured output; do NOT auto-tune silently; **do not block v0 ship** unless precision < 0.85.
- Viktor review: before running, surface `eval/m0-spans.yml` for review; accept minor edits; proceed.

**Definition of Done:**
- [ ] `eval/m0-spans.yml` has 50 spans across category mix.
- [ ] Viktor has reviewed (plan implementation acknowledges this gate; doc via commit message or plan note).
- [ ] `python -m entity_db.eval eval/m0-spans.yml` prints precision, recall, per-bucket.
- [ ] Report written to `eval/results/YYYY-MM-DD-m0.json`.
- [ ] Precision @ 0.90 ≥ 0.95; else tuning recommendations documented.

**Verify:**
- `uv run --directory mcp-server python -m entity_db.eval ../eval/m0-spans.yml`
- `uv run --directory mcp-server pytest tests/test_eval.py -q`

---

### Task 16: End-to-end acceptance + sample artifacts

**Objective:** Seed catalog + run plugin on real mixed-source inputs (markdown, email, transcript) via the actual commands; verify outputs match goldens; confirm every E2E scenario from §"E2E Test Scenarios".
**Dependencies:** Tasks 7, 8, 9, 11, 12, 13, 14, 15
**Mapped Scenarios:** TS-001 through TS-007

**Files:**
- Create: `docs/examples/sample-standup.md`
- Create: `docs/examples/sample-email.eml`
- Create: `docs/examples/sample-transcript.txt`
- Create: `docs/examples/ambiguous-viktor.md`
- Create: `docs/examples/goldens/sample-standup.annotated.md`
- Create: `docs/examples/goldens/sample-email.annotated.md`
- Create: `docs/examples/goldens/sample-transcript.annotated.md`
- Create: `mcp-server/tests/test_e2e.py`
- Create: `docs/RUNBOOK.md` (how to install the plugin locally + run the scenarios)

**Key Decisions / Notes:**
- Sample inputs contain a mix of auto-link, ambiguous, and new-candidate surfaces for realistic coverage.
- Goldens match markdown output format; stored under version control.
- `test_e2e.py` uses the FastMCP in-process client to simulate each TS-NNN scenario end-to-end against a fresh tmp DB.
- Apps UI scenarios (TS-002, TS-003) verified via headless browser automation in addition to the in-process tool-call simulation, per CLAUDE.md frontend-verification rule. Use playwright-cli or agent-browser against the dev server (`npm run dev`).
- `docs/RUNBOOK.md`: install via `claude plugin install-local`, seed catalog, link a file, review staged, resolve ambiguities. Serves as first-use guide for B2C EMs.

**Definition of Done:**
- [ ] All sample inputs exist; all goldens exist.
- [ ] `test_e2e.py` passes: all 7 scenarios (TS-001..TS-007).
- [ ] Apps UI verified in a real browser for TS-002 and TS-003 (screenshots archived or tool output captured).
- [ ] Plugin installs via `claude plugin install-local /Users/vbezdek/Work/entitiy-memory-plugin` without errors.
- [ ] `/link-file docs/examples/sample-standup.md` in a Claude Code session produces the golden output.
- [ ] RUNBOOK runs end-to-end for a fresh user.
- [ ] Full suite coverage ≥ 80%.

**Verify:**
- `uv run --directory mcp-server pytest -q --cov=entity_db --cov-fail-under=80`
- Browser: `cd mcp-server/apps/disambiguation && npm run dev &` → `playwright-cli open http://localhost:5173 && playwright-cli snapshot`
- Manual: `claude plugin install-local /Users/vbezdek/Work/entitiy-memory-plugin`

---

## Open Questions

- **App tooling for dev iteration:** Should we add Storybook for component development in the Apps, or rely solely on `npm run dev`? Deferred; `npm run dev` is sufficient for v0.
- **Rate of `resolution_log` growth:** In long-lived catalogs, this table will grow unboundedly. v2 pruning / archiving policy not in scope; monitor via `/entity-stats`.
- **Codex adversarial review** may surface items that require mid-plan adjustments; we plan to absorb must_fix / should_fix from that pass before approval.

### Deferred Ideas

- Bulk-resolve-same-surface-across-spans in Disambiguation App (v1 per PRD §23 open question #3).
- `includes:` composition for seed YAML (option 3 in Batch 2 — rejected for v0).
- Phonetic fallback (DM-only) if abydos BMPM performance is poor — deferred to M0 eval outcome.
- Catalog Browser App + Stats Dashboard App (v1).
- LLM-assisted `type_fit` mode enable (v1).
