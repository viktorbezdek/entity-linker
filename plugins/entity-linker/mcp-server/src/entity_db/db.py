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


# ── Phonetic and trigram index rebuilds ──────────────────────────────────────


def _alias_exists(conn: sqlite3.Connection, alias_key: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM aliases WHERE alias_key = ? LIMIT 1", (alias_key,)
        ).fetchone()
        is not None
    )


async def rebuild_phonetic_for(conn: sqlite3.Connection, alias_key: str) -> None:
    """Sync phonetic_index for alias_key.

    If the alias still exists in the DB, recompute and write its phonetic keys.
    If the alias was deleted, remove any stale phonetic_index rows.
    """
    from entity_db.matching.index import compute_phonetic_keys, write_phonetic_index

    exists = await asyncio.to_thread(_alias_exists, conn, alias_key)
    if exists:
        keys = compute_phonetic_keys(alias_key)
        async with _write_lock:
            await asyncio.to_thread(write_phonetic_index, conn, alias_key, keys)
    else:
        async with _write_lock:
            await asyncio.to_thread(
                lambda: (
                    conn.execute(
                        "DELETE FROM phonetic_index WHERE alias_key = ?", (alias_key,)
                    ),
                    conn.commit(),
                )
            )


async def rebuild_trigrams_for(conn: sqlite3.Connection, alias_key: str) -> None:
    """Sync trigrams for alias_key.

    If the alias still exists, recompute. If deleted, remove stale rows.
    """
    from entity_db.matching.index import compute_trigrams, write_trigrams

    exists = await asyncio.to_thread(_alias_exists, conn, alias_key)
    if exists:
        trigrams = compute_trigrams(alias_key)
        async with _write_lock:
            await asyncio.to_thread(write_trigrams, conn, alias_key, trigrams)
    else:
        async with _write_lock:
            await asyncio.to_thread(
                lambda: (
                    conn.execute("DELETE FROM trigrams WHERE alias_key = ?", (alias_key,)),
                    conn.commit(),
                )
            )


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
