"""SQLite database layer — schema migration, WAL mode, async write-lock."""
import asyncio
import sqlite3
from pathlib import Path

# Module-level write lock — all mutating DB helpers must acquire this.
_write_lock: asyncio.Lock = asyncio.Lock()

_SCHEMA_SQL = Path(__file__).parent / "schema.sql"

_SQL_ENTITY_SELECT = "SELECT canonical_name, disambiguation_hint FROM entities WHERE id = ?"
_SQL_ALIAS_SELECT = "SELECT alias FROM aliases WHERE entity_id = ?"
_SQL_FTS_DELETE = "DELETE FROM catalog_fts WHERE entity_id = ?"
_SQL_FTS_INSERT = (
    "INSERT INTO catalog_fts"
    "(entity_id, canonical_name, disambiguation_hint, aliases_concat)"
    " VALUES (?, ?, ?, ?)"
)
_SQL_ALIAS_UPSERT = (
    "INSERT OR REPLACE INTO aliases"
    " (entity_id, alias, alias_key, origin) VALUES (?, ?, ?, ?)"
)


def _connect(path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(str(path), check_same_thread=False)


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply schema.sql idempotently (all statements use IF NOT EXISTS)."""
    sql = _SCHEMA_SQL.read_text(encoding="utf-8")
    _ = conn.executescript(sql)


def _enable_wal(conn: sqlite3.Connection) -> None:
    _ = conn.execute("PRAGMA journal_mode=WAL")
    _ = conn.execute("PRAGMA foreign_keys=ON")


async def open_db(path: str | Path) -> sqlite3.Connection:
    """Open (or create) the SQLite DB, apply schema, enable WAL, return connection."""
    conn = await asyncio.to_thread(_connect, path)
    await asyncio.to_thread(_migrate, conn)
    await asyncio.to_thread(_enable_wal, conn)
    return conn


# ── FTS5 helpers ─────────────────────────────────────────────────────────────


async def rebuild_fts_for(conn: sqlite3.Connection, entity_id: str) -> None:
    """Rebuild the catalog_fts row for the given entity from current DB state."""

    def _rebuild(c: sqlite3.Connection, eid: str) -> None:
        row = c.execute(_SQL_ENTITY_SELECT, (eid,)).fetchone()
        if row is None:
            return
        canonical_name: str = str(row[0])
        hint: str = str(row[1]) if row[1] is not None else ""
        aliases = c.execute(_SQL_ALIAS_SELECT, (eid,)).fetchall()
        aliases_concat = " ".join(str(a[0]) for a in aliases)
        _ = c.execute(_SQL_FTS_DELETE, (eid,))
        _ = c.execute(_SQL_FTS_INSERT, (eid, canonical_name, hint, aliases_concat))
        c.commit()

    async with _write_lock:
        await asyncio.to_thread(_rebuild, conn, entity_id)


# ── Index rebuild stubs (real logic lands in Task 5) ─────────────────────────


async def rebuild_phonetic_for(
    _conn: sqlite3.Connection, _alias_key: str
) -> None:
    """Rebuild phonetic_index rows for alias_key. Implemented fully in Task 5."""


async def rebuild_trigrams_for(
    _conn: sqlite3.Connection, _alias_key: str
) -> None:
    """Rebuild trigrams rows for alias_key. Implemented fully in Task 5."""


# ── Alias upsert helper (wires index rebuilds together) ──────────────────────


async def upsert_alias(
    conn: sqlite3.Connection,
    entity_id: str,
    alias: str,
    alias_key: str,
    origin: str,
) -> None:
    """Insert or replace an alias and rebuild all dependent indices."""

    def _upsert(c: sqlite3.Connection) -> None:
        _ = c.execute(_SQL_ALIAS_UPSERT, (entity_id, alias, alias_key, origin))
        c.commit()

    async with _write_lock:
        await asyncio.to_thread(_upsert, conn)

    await rebuild_phonetic_for(conn, alias_key)
    await rebuild_trigrams_for(conn, alias_key)
    await rebuild_fts_for(conn, entity_id)
