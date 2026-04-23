# PRD: `entity-linker` Plugin for Claude Code & Cowork

Created: 2026-04-23
Author: vbezdek@groupon.com
Category: Feature
Status: Final
Version: 0.2
Research: None (domain expertise; no external research pass)

---

## 1. Problem Statement

Noisy text inputs — call transcripts (Fireflies, Gong, Meet), emails, Slack exports, meeting notes, CRM blobs, internal docs — arrive with inconsistent names, acronyms, misspellings, inflection, and cross-language variants (English + Czech in particular). Downstream tooling (Echelon, meeting summaries, CRM updates, the intelligence-agent pipeline) consumes these inputs and silently bakes in bad references. A "Viktor" that should resolve to `viktor-bezdek` instead gets parsed as a new person. A "Foundry" that means `foundry-ai` gets merged with three unrelated projects. The result is polluted downstream state and degraded trust.

The failure mode isn't lack of matching; it's lack of **disciplined matching with ambiguity surfaced rather than guessed**.

## 2. Goal

Ship a Claude Code + Cowork plugin that takes **any text input** (not just transcripts) and a canonical entity catalog, produces an annotated output where every known-entity mention is tagged `@entity-type:entity-id`, and resolves ambiguities and new-entity candidates through **MCP Apps UI** (primary) with elicitation as a cross-host fallback. No guessing. Scheduled/headless runs queue everything non-auto for later human review.

## 3. Non-Goals (v0)

- Not a free-text NER system. Without a catalog, nothing gets tagged.
- Not speaker diarization. Input may carry speaker labels; preserved but not inferred.
- Not transcription or OCR. Input is text.
- Not automatic catalog mutation. Every new entity requires a deliberate human approval.
- Not cross-source recency priors or entity timelines. Those are v2.
- Not a multi-user shared catalog. Single-user v0; teams are v2.

(Previously listed as a non-goal: "MCP Apps UI" — now **promoted to v0**; see §9 and §12.)

## 4. Primary Targets

**Primary: Cowork.** The real workflow is "drop files in a folder, get annotated output back." Cowork's scheduled tasks run nightly. Those runs are **headless by design** — ambiguities and new candidates queue; a human drains the queue via the Staging Review App at their next session.

**Secondary: Claude Code.** Engineers iterating on the catalog, running one-off inputs, building pipelines on top of the MCP server. Same bundle, same components, different entry point.

**Headless: intelligence-agent pipeline.** A bot consumer calling tools via MCP with no UI. Must produce useful output without user interaction; non-auto spans queue.

All three share the plugin bundle — no divergence.

## 5. Users

- **Viktor** — primary. Runs on meetings, emails, 1:1 notes; owns the catalog.
- **B2C tribe EMs** (Tomas, Josef, Diana, Adam, Minas, Andres, Peter) — secondary. Run on their own inputs after v0 proves out.
- **Intelligence-agent pipeline** — non-human consumer. Calls MCP tools headlessly; receives `{resolutions, ambiguities, new_candidates}` shape and writes non-auto items to queues for human review.

## 6. Principles (locked)

1. **Surface ambiguity, never guess.** Top candidate must beat #2 by ≥ 0.10 *and* score ≥ 0.90 to auto-link. Otherwise ask (interactive) or queue (headless).
2. **Deterministic core, LLM at the edges.** Normalization, indexing, candidate generation, and scoring are deterministic Python. LLM only for optional `type_fit` mode and human-readable disambiguation prose.
3. **Pure skills, composable flows.** Each skill does one thing. Subagents orchestrate.
4. **Every catalog mutation is auditable.** Staging table for new entities; `resolution_log` append-only; `reviewed_by` + timestamps.
5. **The MCP server owns the DB.** All reads and writes go through tools. Skills never touch SQLite directly. Lets us swap storage later (Postgres, Turso, D1) without touching skills.
6. **Graceful degradation across hosts.** Apps UI on Cowork/Code/Desktop; elicitation fallback on Claude.ai web; structured-text output in pure headless.

## 7. Core User Flows

### Flow A: Interactive — link a single file

1. User runs `/link-file ~/inputs/2026-04-22-b2c-standup.txt` (or `/link-text` with pasted content).
2. Skill detects input type (ASR transcript, email, markdown, etc.) and runs the matching `input-preprocessing` sub-skill.
3. Skill calls `resolve_link_text(text, source_type, options)` on the MCP server.
4. Server normalizes → indexes (if catalog changed) → generates candidates → scores → runs within-source coref → returns `{auto_links, ambiguities, new_candidates}`.
5. If `ambiguities` non-empty: skill opens the **Disambiguation App** (MCP App, rendered by the host). User resolves each span via card UI; elicitation fallback engages on Claude.ai web.
6. If `new_candidates` non-empty: server writes them to `staging` (dedup-keyed). Skill notifies: "N new candidates staged. Run `/review-staged` to approve."
7. Skill calls `resolve_render(resolutions, text, format)` and writes the annotated output (markdown, xml, or sidecar JSON) to `~/inputs/annotated/`.

### Flow B: Headless — scheduled batch run

1. Cowork scheduled task fires at 03:00; processes every new file in `~/inputs/incoming/`.
2. For each file, the plugin calls `resolve_link_text(text, source_type, { interactive: false })`.
3. Auto-tier spans are linked in the output file.
4. **Ambiguous spans queue** to `pending_disambiguation` (keyed by `source_hash + span`).
5. **New-candidate spans queue** to `staging` (dedup-keyed).
6. Output files are written with partial annotations; non-auto spans appear plain with a sidecar indicating `{pending_disambiguation: N, new_candidates: M}`.
7. Next time Viktor opens Code/Cowork, the Staging Review App surfaces the accumulated backlog.

### Flow C: Catalog bootstrap (first run)

1. User runs `/catalog-import ~/entities.seed.yml` (or places `entities.seed.yml` next to the plugin and runs on first use).
2. MCP server validates the YAML, creates entities, derives aliases (last-name-only, first-initial, acronym-of-canonical, diacritic-free), builds phonetic and trigram indices.
3. Any duplicate keys surface via elicitation (or App): approve each, or abort to edit the file.
4. User runs `/entity-stats` to confirm catalog size, then runs Flow A on a real input.

### Flow D: Staging review

1. User runs `/review-staged` (or opens the Staging Review App directly from the MCP server's resource list).
2. App renders paginated list of pending candidates with evidence: surface form, normalized frequency across sources, ±5-token context snippets, list of source files.
3. For each: **approve as new entity** (confirm type + canonical name + aliases), **merge into existing entity** (autocomplete search), **reject** (reason optional).
4. On approve/merge, the server back-fills the `resolution_log` for prior source files and rebuilds indices.
5. Elicitation fallback: sequential single-item forms, one per candidate.

## 8. Scope

### In Scope (v0)

- MCP server (`entity-db`) with SQLite persistence, FTS5 for catalog search, and all tools in §9.
- Four skills: `entity-linker`, `entity-matcher` (reference), `input-preprocessing` (with pluggable sub-cleaners for ASR/email/markdown/HTML), `entity-catalog-manage`.
- One subagent: `entity-resolver`.
- Seven slash commands: `/link-file`, `/link-text`, `/link-folder`, `/review-staged`, `/add-entity`, `/entity-search`, `/entity-stats`, plus `/catalog-import`.
- **Two MCP Apps:** Disambiguation App, Staging Review App.
- **Elicitation fallback** for all Apps on hosts without App support (Claude.ai web).
- YAML seed import (`catalog_import`).
- Czech/Slovak/Polish inflection stripping; Double Metaphone + Beider-Morse phonetic; char-trigram.
- Scoring model as §14; `type_fit` in rule-based mode; LLM-assisted mode gated and off by default.
- Output formats: markdown (default), XML, sidecar JSON.
- Headless queue behavior (Flow B).
- `resolution_log` append-only audit table.

### Explicitly Out of Scope (v0)

- **Team-wide / multi-user catalog** — single-user only; concurrency via WAL + advisory lock; teams are v2.
- **Cross-source recency** — v0 recency is within-source only (see §14). Cross-source recency priors are v2.
- **Catalog Browser and Stats Apps** — deferred to v1. v0 has CRUD via slash commands + elicitation.
- **Speaker diarization or transcription.**
- **Automatic alias learning from confirmations** — deferred; v0 never adds aliases without explicit human action.
- **Free-text NER without a catalog.**

## 9. Architecture

### 9.1 Bundle Layout

```
entity-linker/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── skills/
│   ├── entity-linker/SKILL.md
│   ├── entity-matcher/
│   │   ├── SKILL.md
│   │   └── references/{algorithms,scoring,edge-cases}.md
│   ├── input-preprocessing/
│   │   ├── SKILL.md
│   │   └── references/{asr,email,markdown,html,plain}.md
│   └── entity-catalog-manage/SKILL.md
├── agents/
│   └── entity-resolver.md
├── commands/
│   ├── link-file.md
│   ├── link-text.md
│   ├── link-folder.md
│   ├── review-staged.md
│   ├── add-entity.md
│   ├── entity-search.md
│   ├── entity-stats.md
│   └── catalog-import.md
├── mcp-server/
│   ├── pyproject.toml
│   ├── src/entity_db/
│   │   ├── __init__.py
│   │   ├── server.py               # FastMCP entry
│   │   ├── db.py                   # SQLite access layer (WAL, write-serialized)
│   │   ├── schema.sql
│   │   ├── seed.py                 # YAML seed import
│   │   ├── matching/
│   │   │   ├── normalize.py
│   │   │   ├── index.py
│   │   │   ├── candidates.py
│   │   │   ├── score.py
│   │   │   ├── type_fit.py
│   │   │   └── coref.py
│   │   ├── apps/
│   │   │   ├── disambiguation/     # MCP App source (+ built assets)
│   │   │   └── staging/            # MCP App source (+ built assets)
│   │   ├── elicit.py               # Elicitation fallback helpers
│   │   └── render.py               # markdown / xml / sidecar
│   └── tests/
└── README.md
```

### 9.2 Component Responsibilities

- **MCP server (`entity-db`)** — sole DB owner; exposes matching/catalog/staging tools; serves Apps; runs elicitation fallback.
- **Skill `entity-linker`** — end-to-end flow: detect input type → preprocess → call `resolve_link_text` → open App (or elicit) → render output.
- **Skill `entity-matcher`** (reference) — scoring/algorithm docs loaded on demand when tuning or debugging.
- **Skill `input-preprocessing`** — pluggable cleaners: ASR (fillers, repeats, speaker labels), email (headers, reply-chains, signatures), markdown (strip formatting), HTML (extract text), plain (pass-through).
- **Skill `entity-catalog-manage`** — CRUD wrappers with elicitation/App UI; staging queue review.
- **Subagent `entity-resolver`** — isolation: worktree; used for long inputs (>5k tokens) and batch folders; returns summary + paths only.
- **Slash commands** — thin dispatchers.

### 9.3 Flow Composition

Interactive and headless are modeled in §7; key API contract: every MCP call takes `options: {interactive: bool, ...}`. When `interactive: false`, ambiguities and new candidates queue instead of opening Apps/elicitation.

## 10. Storage Model (SQLite + FTS5)

Path: `~/entity-db/entities.sqlite` (overridable via `ENTITY_DB_PATH`). WAL mode. Writes serialized via an async lock in `db.py`.

```sql
CREATE TABLE entities (
    id                  TEXT PRIMARY KEY,
    type                TEXT NOT NULL CHECK (type IN
                          ('person','project','product','team','company',
                           'acronym','concept','other')),
    canonical_name      TEXT NOT NULL,
    disambiguation_hint TEXT,
    attributes_json     TEXT,
    created_at          INTEGER NOT NULL,
    updated_at          INTEGER NOT NULL,
    deprecated          INTEGER DEFAULT 0
);

CREATE TABLE aliases (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias     TEXT NOT NULL,
    alias_key TEXT NOT NULL,
    origin    TEXT NOT NULL,   -- 'canonical' | 'manual' | 'derived' | 'user-confirmed'
    PRIMARY KEY (entity_id, alias_key)
);
CREATE INDEX idx_aliases_key ON aliases(alias_key);

CREATE TABLE phonetic_index (
    alias_key    TEXT NOT NULL,
    phonetic_key TEXT NOT NULL,
    algo         TEXT NOT NULL, -- 'dmetaphone' | 'beider-morse'
    PRIMARY KEY (alias_key, phonetic_key, algo)
);
CREATE INDEX idx_phonetic_key ON phonetic_index(phonetic_key);

CREATE TABLE trigrams (
    alias_key TEXT NOT NULL,
    trigram   TEXT NOT NULL,
    PRIMARY KEY (alias_key, trigram)
);
CREATE INDEX idx_trigram ON trigrams(trigram);

-- FTS5 for catalog_search (built over canonical_name + hint + aliases)
CREATE VIRTUAL TABLE catalog_fts USING fts5(
    entity_id UNINDEXED,
    canonical_name,
    disambiguation_hint,
    aliases_concat,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE staging (
    id               TEXT PRIMARY KEY,
    dedup_key        TEXT NOT NULL UNIQUE,   -- normalized_surface + '|' + proposed_type
    surface          TEXT NOT NULL,
    proposed_type    TEXT,
    proposed_name    TEXT,
    evidence_json    TEXT NOT NULL,           -- accumulates across sources (contexts, freq, files)
    frequency        INTEGER NOT NULL DEFAULT 1,
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','approved','rejected','merged')),
    merged_into      TEXT REFERENCES entities(id),
    created_at       INTEGER NOT NULL,
    updated_at       INTEGER NOT NULL,
    reviewed_at      INTEGER,
    reviewed_by      TEXT                     -- $USER or git config user.email in v0
);

CREATE TABLE pending_disambiguation (
    id               TEXT PRIMARY KEY,
    source_hash      TEXT NOT NULL,
    source_type      TEXT NOT NULL,           -- 'transcript' | 'email' | 'markdown' | ...
    source_path      TEXT,
    span_start       INTEGER NOT NULL,
    span_end         INTEGER NOT NULL,
    surface          TEXT NOT NULL,
    candidates_json  TEXT NOT NULL,           -- top N candidates with scores + hints
    context_json     TEXT NOT NULL,           -- ±5-token window
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','resolved','abandoned')),
    created_at       INTEGER NOT NULL,
    resolved_at      INTEGER,
    resolved_entity  TEXT REFERENCES entities(id)
);
CREATE INDEX idx_pending_source ON pending_disambiguation(source_hash);

CREATE TABLE resolution_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_hash     TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    span_start      INTEGER NOT NULL,
    span_end        INTEGER NOT NULL,
    surface         TEXT NOT NULL,
    entity_id       TEXT REFERENCES entities(id),
    confidence      REAL NOT NULL,
    method          TEXT NOT NULL,   -- 'auto' | 'user-confirmed' | 'user-rejected' | 'staged' | 'queued'
    created_at      INTEGER NOT NULL
);
CREATE INDEX idx_log_source ON resolution_log(source_hash);
CREATE INDEX idx_log_entity ON resolution_log(entity_id);
```

**Key choices:**
- `staging.dedup_key UNIQUE` → repeated surfaces accumulate evidence (frequency++, contexts appended) into one row. Batch runs produce a clean queue, not noise.
- `pending_disambiguation` is separate from `staging` because the schemas and workflows differ (disambiguation picks from existing candidates; staging creates or merges entities).
- `catalog_fts` replaces linear-scan search; rebuilt on mutation via triggers in `db.py`.
- `source_hash` (not `transcript_hash`) — input-agnostic.
- WAL + single-writer lock keeps concurrent reads fast; v0 accepts sequential write contention for parallel subagents.

## 11. MCP Server API

FastMCP. Python 3.11+. Stateless HTTP transport.

### Catalog

| Tool | Purpose |
|---|---|
| `catalog_import(yaml_path)` | Bulk-create entities from a seed YAML. Validates, derives aliases, builds indices. Returns counts + any duplicates for human triage. |
| `catalog_list(type?, limit?, cursor?)` | Paginated list. |
| `catalog_get(entity_id)` | Full record incl. aliases. |
| `catalog_search(query, type?)` | FTS5 search over name, hint, aliases. |
| `catalog_create(type, canonical_name, aliases?, attributes?, hint?)` | Direct create (skips staging). |
| `catalog_update(entity_id, patch)` | Update + rebuild affected indices + FTS row. |
| `catalog_add_alias(entity_id, alias, origin)` | Append alias. |
| `catalog_deprecate(entity_id)` | Soft-delete; excluded from matching, kept for audit. |

### Staging & Queues

| Tool | Purpose |
|---|---|
| `staging_stage(surface, type, proposed_name, evidence)` | Upsert by `dedup_key` (accumulates evidence). |
| `staging_list(status='pending', limit?, cursor?)` | List candidates. |
| `staging_approve(staging_id, merge_into?)` | Approve new OR merge into existing; back-fills `resolution_log`. |
| `staging_reject(staging_id, reason?)` | Reject. |
| `staging_review_app(staging_ids?)` | Opens the Staging Review App; elicitation fallback if host lacks App support. |
| `pending_list(source_hash?, limit?, cursor?)` | List queued disambiguation items. |
| `pending_resolve(pending_id, entity_id \| 'none' \| 'new')` | Resolve one queued ambiguity; back-fills `resolution_log`. |

### Resolution

| Tool | Purpose |
|---|---|
| `resolve_link_text(text, source_type, options)` | Pure compute. Returns `{resolutions, ambiguities, new_candidates, warnings, stats, source_hash}`. `options.interactive: bool` (default true) controls queue behavior. Does not itself open UI. |
| `resolve_disambiguate_app(source_hash, ambiguity_ids?)` | Opens the Disambiguation App scoped to this source. Re-runs coref after user resolves. |
| `resolve_render(resolutions, text, format)` | Produces annotated output: `markdown` (default), `xml`, or `sidecar`. Server owns authoritative byte offsets. |

### Options shape

```python
class ResolveOptions(BaseModel):
    interactive: bool = True
    type_fit_mode: Literal["rules", "llm"] = "rules"
    context_window: int = 5           # tokens on each side
    on_ambiguity: Literal["prompt", "queue", "skip"] = "prompt"
    on_new_candidate: Literal["stage", "skip"] = "stage"
    source_path: Optional[str] = None  # for traceability in the log
```

When `interactive=False`: `on_ambiguity` defaults to `queue`, `on_new_candidate` defaults to `stage`.

## 12. MCP Apps (v0)

### 12.1 Disambiguation App

Opened via `resolve_disambiguate_app`. Rendered as an MCP iframe resource by hosts that support it.

Surface:
- Scrollable list of ambiguous spans, each a card.
- Card content: source excerpt with the span highlighted, candidate list (canonical name, type badge, `disambiguation_hint`, confidence), actions: **pick**, **none of these**, **new entity** (opens staging form inline), **skip** (leaves in queue).
- Keyboard shortcuts (1–9 pick by index, N for none, S for skip).
- On submit: writes resolutions, server re-runs coref, updates output.

Fallback: sequential single-select elicitation per span (existing PRD v0.1 schema preserved).

### 12.2 Staging Review App

Opened via `staging_review_app` or `/review-staged`.

Surface:
- Paginated pending queue sorted by frequency desc.
- Each row: surface, proposed type, aliases-derived-so-far, evidence count, "view evidence" (expands to show context snippets and source files).
- Per-row actions: **approve new** (editable: type, canonical name, aliases), **merge into existing** (autocomplete search over `catalog_fts`), **reject** (reason optional).
- Bulk actions: bulk-reject (with confirmation), bulk-assign-type.
- After decisions: server back-fills `resolution_log` for all prior sources touched.

Fallback: sequential elicitation via `StagingApproval` schema (v0.1).

### 12.3 Host Support Matrix (April 2026)

| Host | Apps | Elicitation | Notes |
|---|---|---|---|
| Claude Code ≥ 2.1.76 | ✅ | ✅ | Full support |
| Cowork | ✅ | ✅ | Full support |
| Claude Desktop | ✅ | ✅ | Full support |
| Claude.ai web | ⚠ partial | ✅ | MCP Apps CSP/postMessage bugs; elicitation fallback auto-engages |

## 13. Skills

Each skill's SKILL.md body stays under ~500 lines; references live in sibling files.

### 13.1 `entity-linker`
Triggers: "link entities in this text/file/folder", "tag mentions", "resolve names against catalog".
Composes with `input-preprocessing`. Calls MCP tools on `entity-db`. Opens the Disambiguation App for ambiguous cases (elicitation fallback).

### 13.2 `entity-matcher` (reference)
Triggers: "tune matching", "explain scoring", "why did it miss X", "add a phonetic algorithm".
Progressive disclosure — details in `references/{algorithms,scoring,edge-cases}.md`.

### 13.3 `input-preprocessing`
Triggers: "clean up this text", "parse speaker turns", "strip email headers", "flatten markdown".
Pluggable sub-cleaners: `asr` (fillers, repeats, speaker labels), `email` (headers, reply-chains, signatures), `markdown` (strip formatting), `html` (extract text), `plain` (pass-through). Source-type detection by heuristics + user hint.

### 13.4 `entity-catalog-manage`
Triggers: "review staged entities", "approve new entities", "add entity", "rename entity", "deprecate entity", "import seed yaml".
Wraps `catalog_*`, `staging_*`, `pending_*` with the Apps-first, elicitation-fallback UX.

## 14. Matching Core

Deterministic; no LLM in the hot path. Full algorithm in `skills/entity-matcher/references/algorithms.md`.

1. **Normalize**: NFC → lowercase → diacritics stripped → punctuation removed. Czech/Slovak/Polish case and possessive suffixes stripped before keying: `-ovi, -em, -a, -e, -y, -u, -ou, -ům, -ech, -ami, -ův, -ova, -ovo`.
2. **Index** (rebuilt on catalog mutation): exact, Double Metaphone + Beider-Morse phonetic, char-trigram. Aliases expanded to include last-name-only, first-name-only, initials, acronym-of-canonical, diacritic-free variants.
3. **Candidates**: 1–4 token sliding windows. Aliases ≤ 2 chars require exact match. Stopword filter.
4. **Score**: `0.45·lex + 0.20·phon + 0.20·type_fit + 0.10·local_recency − 0.05·short_pen − 0.05·ambig_pen`, clipped to [0, 1].
   - **Weights are v0 defaults** and tunable via config. M0 spike runs on a 50-span hand-labeled micro-eval; if macro weights are wrong, tuning happens in /spec before M1.
   - **`local_recency`** is within-source only in v0: 0 for first occurrence of a candidate in this input, 0.10 for any subsequent occurrence. Cross-source recency is v2.
   - **`type_fit` rules** (rule-mode) — documented rule set driven by 7 cue families: **person** ("with", "called", "met", honorifics, first-then-last pattern); **project** ("the X project", "rolling out X", "X launch"); **product** ("the X feature", "ship X", "X's UI"); **team** ("the X team", "X squad", plural pronouns); **company** ("at X", "X acquired", legal suffixes); **acronym** (all caps ≤ 5 chars, exact alias hit); **concept** (abstract nouns adjacent, "what is X"). Full cue set lives in `references/scoring.md`. LLM-mode (`type_fit_mode: "llm"`) available as opt-in for weak-cue cases.
5. **Decide**: auto-link if `top ≥ 0.90 AND (top − second) ≥ 0.10`; else ambiguous if `top ≥ 0.70`; else unresolved (possibly staged as new).
6. **Coref**: propagate within-source; conflict detection emits `entity_drift` warnings.
7. **Contradiction check**: compare context against `entity.attributes`; warn but do not break the link.

Library choice for Beider-Morse is **open for /spec**: evaluate `abydos`, `phonetics`, or custom port; prefer maintained + pure-Python.

## 15. New-Entity Approval Flow

1. Linker sees an unresolvable entity-shaped surface (capitalized multi-word phrase, frequency ≥ 2, no alias hit).
2. Server writes to `staging` with `dedup_key = normalized_surface + '|' + proposed_type`. Repeated hits accumulate evidence; frequency increments.
3. Output leaves the mention plain. Output sidecar carries `new_candidates_pending: N`.
4. User runs `/review-staged` (or Staging Review App opens on next session).
5. Approve-new / merge-existing / reject.
6. On approve/merge, `resolution_log` is back-filled for all prior sources that touched this surface; indices rebuild.
7. No auto-promotion. Ever.

## 16. Output Formats

### markdown (default)
```
So I synced with [Viktor](@person:viktor-bezdek) yesterday about the
[FoundryAI](@project:foundry-ai) rollout. He wants to loop in
[Adam](@person:adam-korinek?) on the scheduling piece.
```
The `?` suffix flags a user-confirmed suggest-tier link.

### xml
```xml
<entity id="viktor-bezdek" type="person" confidence="0.94">Viktor</entity>
```

### sidecar
Preserves input byte-for-byte; emits `<source>.entities.json` with span offsets, entity IDs, confidences, and method. Right choice for audit-heavy pipelines.

## 17. Edge Cases Covered

Reference: `skills/entity-matcher/references/edge-cases.md`. Beyond v0.1: email reply-chain deduping, markdown heading vs body mentions, URL-embedded entity names ignored, signature block detection, thread-reply quoted context boost/skip policy, email address local-part as aliasing hint. Plus the existing v0.1 set (Czech inflection, ASR splits/merges, homographs, partial-name collisions, acronyms not in aliases, possessives, honorifics, self-reference, transliteration, entity drift, filler tokens, short aliases, numbers/dates, speaker-label vs body mentions).

## 18. Technical Context

- **Relevant architecture:** MCP server via FastMCP (Python 3.11+); SQLite (WAL) for persistence; FTS5 for catalog search; MCP Apps for UI with elicitation fallback.
- **Constraints:** single-user v0; single-writer SQLite (async lock serializes writes); parallel subagents OK for reads, sequential for writes.
- **Host compat:** App renders on Code / Cowork / Desktop; degrades to elicitation on Claude.ai web.
- **Existing code:** none — greenfield plugin under `~/Work/entitiy-memory-plugin`.
- **External deps to evaluate in /spec:** FastMCP, Beider-Morse library, phonetic libs, Pydantic v2, `pyyaml`, `rapidfuzz` (for `lex` score), `unicodedata` (stdlib).
- **Performance SLOs (v0):** `resolve_link_text` ≤ 2s for 5000-word input, ≤ 10s for 30k-word input on M-series laptop. Validated in M0.

## 19. Security & Trust

- Local-only: SQLite file on disk, no network in hot path.
- Plugin subagents cannot escalate permissions (protocol-enforced).
- All mutations go through explicit human action (App, elicitation, or slash command). No silent writes to catalog.
- `resolution_log` append-only audit.
- Private marketplace distribution (Groupon internal git); Anthropic-managed marketplace is NOT used — plugin contents are not vetted by Anthropic.
- `reviewed_by` populated from `$USER` or `git config user.email`. Documented v0 limitation.

## 20. Success Metrics

**Correctness (v0):**
- Auto-link precision ≥ 0.98 on 20-file hand-labeled eval set (mixed source types: 10 transcripts, 6 emails, 4 markdown notes).
- Auto-link recall ≥ 0.85 on same set.
- Zero silent catalog mutations in 30 days of use.

**UX:**
- Disambiguation App: ≤ 5 spans/input average; median time-to-resolve all spans ≤ 45s for a 3000-word input.
- Staging Review App: backlog clearable at ≤ 8s per candidate.

**Performance:**
- `resolve_link_text` meets §18 SLOs on 95% of inputs.

**Adoption:**
- Viktor uses it on every meeting transcript and ≥ 3 emails/week for 2 weeks.
- 3+ B2C EMs run it on their own content within 4 weeks of v0 release.

## 21. Rollout

**M0 — Spike (1 week)**
- MCP server stub with in-memory catalog.
- End-to-end `resolve_link_text` on one real transcript + one real email.
- No elicitation, no Apps, no persistence.
- **Exit criteria:** scoring weights validated on 50-span micro-eval (≥ 0.95 precision @ 0.90 threshold); if not met, tuning pass added to M1 scope.

**M1 — v0 (4–5 weeks)**
- SQLite persistence + FTS5.
- Full skill and subagent bundle.
- YAML seed import.
- **Disambiguation App + Staging Review App + elicitation fallback.**
- `/link-file`, `/link-text`, `/link-folder`, `/review-staged`, `/add-entity`, `/entity-search`, `/entity-stats`, `/catalog-import`.
- Czech inflection rules, Beider-Morse phonetic, full scoring.
- Markdown + XML + sidecar output formats.
- Headless queue model (Flow B).
- Private marketplace install path.

**M2 — v1 (4–6 weeks after v0)**
- Catalog Browser App + Stats Dashboard App.
- Persistent cross-source recency prior in `resolution_log`.
- Cowork scheduled-task templates.
- Optional LLM-assisted `type_fit` mode, gated.

**M3 — v2 (later)**
- Entity timelines across sources (Echelon integration).
- Multi-user catalog (team-wide shared DB, conflict resolution, real identity model).
- Automatic alias learning from confirmations (with review).
- Czech-optimized phonetic pass if Beider-Morse recall is weak.

## 22. Key Decisions

| # | Decision | Choice | Why |
|---|----------|--------|-----|
| 1 | Input scope | Any text input (generalize now) | Broader utility; preprocessing is pluggable; schema & commands input-agnostic (`source_hash`, `/link-text`). |
| 2 | Headless mode | Queue everything for later human review | Preserves principle #1 (never guess); makes bot + scheduled task first-class; drains via Staging Review App. |
| 3 | UI primary surface | **MCP Apps in v0** (Disambiguation + Staging Review) | Matches user vision of "nice UI"; elicitation as cross-host fallback; delays Catalog/Stats Apps to v1. |
| 4 | Catalog bootstrapping | YAML seed file + `catalog_import` | Fast cold-start; git-versionable; enables labeled eval set in M0. |
| 5 | Recency in v0 | Local (within-source) only | Resolves contradiction with §3 non-goals; cross-source recency in v2. |
| 6 | Scoring weights | Defaults + tunable; M0 micro-eval gate | Weights are best-guess; validated on 50-span labeled data before M1 ships. |
| 7 | `type_fit` rules | 7 cue families, documented | Closes biggest gap in the scoring model; LLM-mode stays opt-in. |
| 8 | Staging dedup | `dedup_key = normalized_surface + '|' + proposed_type` UNIQUE | Keeps review queue sane at batch scale. |
| 9 | `catalog_search` | FTS5 virtual table | Replaces linear scan; fast enough for autocomplete in Staging Review App. |
| 10 | Concurrency | WAL + async write lock | Single-user v0; reads parallel, writes serialized; documented limit. |
| 11 | `resolve_render` placement | Stays in MCP server | Server owns authoritative byte offsets for sidecar format. |
| 12 | Beider-Morse library | Decision deferred to /spec | Candidates: `abydos`, `phonetics`, custom port. |
| 13 | `reviewed_by` identity | `$USER` or `git config user.email` | v0 limitation; documented; real identity model in v2. |

## 23. Open Questions

1. **Alias learning from confirmations.** If Viktor confirms `"Besdeck" → viktor-bezdek` five times, should the plugin auto-propose `Besdeck` as an alias in staging-review? v0 no, v1 maybe.
2. **Czech-specific phonetic algorithm.** Beider-Morse is multilingual but not Czech-tuned. If recall on Czech names is weak on M0 eval, add Czech pass in v1.
3. **Bundled disambiguation.** v0 Disambiguation App lists all spans in one view but resolves one at a time; v1 could add "bulk-resolve same surface across spans."
4. **Shared catalog across Viktor's tools.** Echelon + intelligence-agent reading the same SQLite is trivial via MCP, but ownership becomes contested. v2 with team model.
5. **App tech stack.** React+Vite vs. vanilla TS+Vite vs. Preact — picked in /spec based on bundle size (Apps are iframes; smaller is better for cold load).
6. **`entities.seed.yml` schema.** Exact YAML shape (flat vs. nested types, how aliases declared) — picked in /spec.

## 24. Risks

- **Czech ASR quality varies wildly.** If Fireflies Czech output is garbage, no matcher saves us. Mitigation: user-curated `asr_corrections` override map.
- **MCP Apps cross-host fragmentation (now v0 risk).** Claude.ai web has known CSP and postMessage bugs. Mitigation: Apps target Cowork + Code + Desktop; web users get elicitation fallback automatically. Cross-host QA in /spec's verification pass.
- **App effort exceeds budget.** Two Apps with elicitation fallback doubles UI surface area. Mitigation: M1 timeline expanded from 2–3 weeks to 4–5 weeks; split Apps into separate /spec phases if needed.
- **Plugin subagent frontmatter restrictions.** No `hooks`, `mcpServers`, or `permissionMode` at the subagent level — all plugin-level. Design already respects this.
- **Catalog drift between users.** Not a v0 risk (single-user); becomes a v2 concern.
- **YAML seed pitfalls.** Hand-maintained YAML drifts; duplicate-detection + versioning in `catalog_import` help but don't solve human error. Mitigation: seed file lives in git.

## 25. Appendices

### 25.1 `plugin.json` skeleton

```json
{
  "name": "entity-linker",
  "version": "0.1.0",
  "description": "Resolves entity mentions in text inputs (transcripts, emails, docs) against a local catalog. Interactive disambiguation via MCP Apps with elicitation fallback. Czech + English, phonetic + fuzzy + inflection-aware matching.",
  "author": {
    "name": "Viktor Bezdek",
    "email": "viktor.bezdek@groupon.com"
  },
  "license": "UNLICENSED",
  "homepage": "https://github.com/viktorbezdek/entity-linker",
  "keywords": ["text", "ner", "entity-linking", "transcripts", "email", "groupon", "b2c"]
}
```

### 25.2 `.mcp.json` skeleton

```json
{
  "mcpServers": {
    "entity-db": {
      "command": "uv",
      "args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}/mcp-server", "entity-db"],
      "env": {
        "ENTITY_DB_PATH": "${HOME}/entity-db/entities.sqlite"
      }
    }
  }
}
```

### 25.3 `entities.seed.yml` sketch (to be finalized in /spec)

```yaml
version: 1
entities:
  - id: viktor-bezdek
    type: person
    canonical_name: Viktor Bezdek
    disambiguation_hint: "Groupon AI lead, Czech"
    aliases: [Viktor, VB, Besdeck]
    attributes:
      company: groupon
      team: b2c-tribe
  - id: foundry-ai
    type: project
    canonical_name: Foundry AI
    disambiguation_hint: "Internal ML platform, 2026"
    aliases: [Foundry, FoundryAI]
```
