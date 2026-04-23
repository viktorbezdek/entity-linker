-- entity-db schema — SQLite + FTS5
-- All CREATE TABLE statements use IF NOT EXISTS for idempotent migration.

CREATE TABLE IF NOT EXISTS entities (
    id                  TEXT PRIMARY KEY,
    type                TEXT NOT NULL CHECK (type IN (
                            'person','project','product','team','company',
                            'acronym','concept','other')),
    canonical_name      TEXT NOT NULL,
    disambiguation_hint TEXT,
    attributes_json     TEXT,
    created_at          INTEGER NOT NULL,
    updated_at          INTEGER NOT NULL,
    deprecated          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS aliases (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias     TEXT NOT NULL,
    alias_key TEXT NOT NULL,
    origin    TEXT NOT NULL CHECK (origin IN (
                   'canonical','manual','derived','user-confirmed')),
    PRIMARY KEY (entity_id, alias_key)
);
CREATE INDEX IF NOT EXISTS idx_aliases_key ON aliases(alias_key);

CREATE TABLE IF NOT EXISTS phonetic_index (
    alias_key    TEXT NOT NULL,
    phonetic_key TEXT NOT NULL,
    algo         TEXT NOT NULL CHECK (algo IN ('dmetaphone','beider-morse')),
    PRIMARY KEY (alias_key, phonetic_key, algo)
);
CREATE INDEX IF NOT EXISTS idx_phonetic_key ON phonetic_index(phonetic_key);

CREATE TABLE IF NOT EXISTS trigrams (
    alias_key TEXT NOT NULL,
    trigram   TEXT NOT NULL,
    PRIMARY KEY (alias_key, trigram)
);
CREATE INDEX IF NOT EXISTS idx_trigram ON trigrams(trigram);

-- FTS5 virtual table for fast catalog search
CREATE VIRTUAL TABLE IF NOT EXISTS catalog_fts USING fts5(
    entity_id UNINDEXED,
    canonical_name,
    disambiguation_hint,
    aliases_concat,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS staging (
    id            TEXT PRIMARY KEY,
    dedup_key     TEXT NOT NULL UNIQUE,
    surface       TEXT NOT NULL,
    proposed_type TEXT,
    proposed_name TEXT,
    evidence_json TEXT NOT NULL,
    frequency     INTEGER NOT NULL DEFAULT 1,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','approved','rejected','merged')),
    merged_into   TEXT REFERENCES entities(id),
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL,
    reviewed_at   INTEGER,
    reviewed_by   TEXT
);

CREATE TABLE IF NOT EXISTS pending_disambiguation (
    id              TEXT PRIMARY KEY,
    source_hash     TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    source_path     TEXT,
    span_start      INTEGER NOT NULL,
    span_end        INTEGER NOT NULL,
    surface         TEXT NOT NULL,
    candidates_json TEXT NOT NULL,
    context_json    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','resolved','abandoned')),
    created_at      INTEGER NOT NULL,
    resolved_at     INTEGER,
    resolved_entity TEXT REFERENCES entities(id)
);
CREATE INDEX IF NOT EXISTS idx_pending_source ON pending_disambiguation(source_hash);

CREATE TABLE IF NOT EXISTS resolution_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_hash TEXT NOT NULL,
    source_type TEXT NOT NULL,
    span_start  INTEGER NOT NULL,
    span_end    INTEGER NOT NULL,
    surface     TEXT NOT NULL,
    entity_id   TEXT REFERENCES entities(id),
    confidence  REAL NOT NULL,
    method      TEXT NOT NULL CHECK (method IN (
                    'auto','user-confirmed','user-rejected','staged','queued')),
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_log_source  ON resolution_log(source_hash);
CREATE INDEX IF NOT EXISTS idx_log_entity  ON resolution_log(entity_id);
