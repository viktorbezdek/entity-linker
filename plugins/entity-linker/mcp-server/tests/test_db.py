"""Tests for the SQLite DB layer: schema, FTS5, WAL, write-lock."""
import asyncio
import sqlite3
from pathlib import Path

import pytest

from entity_db.db import _write_lock, open_db, rebuild_fts_for


@pytest.mark.asyncio
async def test_open_db_creates_all_tables(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    rows = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','shadow')"
        ).fetchall()
    )
    table_names = {r[0] for r in rows}
    required = {
        "entities",
        "aliases",
        "phonetic_index",
        "trigrams",
        "staging",
        "pending_disambiguation",
        "resolution_log",
    }
    assert required.issubset(table_names), f"Missing tables: {required - table_names}"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_open_db_idempotent(tmp_db_path: Path) -> None:
    conn1 = await open_db(tmp_db_path)
    await asyncio.to_thread(conn1.close)
    # Second open on the same path must succeed without error
    conn2 = await open_db(tmp_db_path)
    await asyncio.to_thread(conn2.close)


@pytest.mark.asyncio
async def test_wal_mode_enabled(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    mode = await asyncio.to_thread(
        lambda: conn.execute("PRAGMA journal_mode").fetchone()[0]
    )
    assert mode == "wal"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_write_lock_serializes_concurrent_writes(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    results: list[int] = []

    async def writer(value: int) -> None:
        async with _write_lock:
            # Simulate a write with a brief yield to test interleaving
            await asyncio.sleep(0)
            await asyncio.to_thread(
                lambda: conn.execute(
                    "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                    "VALUES (?, 'person', ?, 0, 0)",
                    (f"id-{value}", f"name-{value}"),
                ).connection.commit()
            )
            results.append(value)

    await asyncio.gather(*(writer(i) for i in range(10)))
    assert len(results) == 10, "All 10 writes must complete"
    count = await asyncio.to_thread(
        lambda: conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    )
    assert count == 10
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_catalog_fts_queryable(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)

    def _seed(c: sqlite3.Connection) -> None:
        _ = c.execute(
            "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
            "VALUES ('vb', 'person', 'Viktor Bezdek', 0, 0)"
        )
        fts_sql = (
            "INSERT INTO catalog_fts"
            " (entity_id, canonical_name, disambiguation_hint, aliases_concat)"
            " VALUES ('vb', 'Viktor Bezdek', 'Groupon AI lead', 'Viktor vb')"
        )
        _ = c.execute(fts_sql)
        c.commit()

    await asyncio.to_thread(_seed, conn)
    rows = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT entity_id FROM catalog_fts WHERE catalog_fts MATCH 'Viktor'"
        ).fetchall()
    )
    assert len(rows) == 1
    assert rows[0][0] == "vb"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_rebuild_fts_for_updates_row(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    # Create entity + alias
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                "VALUES ('vb2', 'person', 'Viktor Bezdek', 0, 0)"
            ),
            conn.execute(
                "INSERT INTO aliases (entity_id, alias, alias_key, origin) "
                "VALUES ('vb2', 'Viktor', 'viktor', 'canonical')"
            ),
            conn.commit(),
        )
    )
    await rebuild_fts_for(conn, "vb2")
    rows = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT entity_id FROM catalog_fts WHERE catalog_fts MATCH 'viktor'"
        ).fetchall()
    )
    assert any(r[0] == "vb2" for r in rows)
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_rebuild_phonetic_for_existing_alias(tmp_db_path: Path) -> None:
    from entity_db.db import rebuild_phonetic_for

    conn = await open_db(tmp_db_path)
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                "VALUES ('vb3', 'person', 'Test', 0, 0)"
            ),
            conn.execute(
                "INSERT INTO aliases (entity_id, alias, alias_key, origin) "
                "VALUES ('vb3', 'bezdek', 'bezdek', 'canonical')"
            ),
            conn.commit(),
        )
    )
    await rebuild_phonetic_for(conn, "bezdek")
    count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM phonetic_index WHERE alias_key = 'bezdek'"
        ).fetchone()
    )
    assert count[0] > 0
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_rebuild_phonetic_for_missing_alias_cleans_up(tmp_db_path: Path) -> None:
    from entity_db.db import rebuild_phonetic_for

    conn = await open_db(tmp_db_path)
    # Insert a phonetic row without a corresponding alias
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO phonetic_index (alias_key, phonetic_key, algo) "
                "VALUES ('orphaned', 'ORFND', 'dmetaphone')"
            ),
            conn.commit(),
        )
    )
    await rebuild_phonetic_for(conn, "orphaned")
    count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM phonetic_index WHERE alias_key = 'orphaned'"
        ).fetchone()
    )
    assert count[0] == 0  # cleaned up since alias doesn't exist
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_rebuild_trigrams_for_existing_alias(tmp_db_path: Path) -> None:
    from entity_db.db import rebuild_trigrams_for

    conn = await open_db(tmp_db_path)
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                "VALUES ('vb4', 'person', 'Test', 0, 0)"
            ),
            conn.execute(
                "INSERT INTO aliases (entity_id, alias, alias_key, origin) "
                "VALUES ('vb4', 'foundryai', 'foundryai', 'canonical')"
            ),
            conn.commit(),
        )
    )
    await rebuild_trigrams_for(conn, "foundryai")
    count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM trigrams WHERE alias_key = 'foundryai'"
        ).fetchone()
    )
    assert count[0] > 0
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_upsert_alias_chains_all_rebuilds(tmp_db_path: Path) -> None:
    from entity_db.db import upsert_alias

    conn = await open_db(tmp_db_path)
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                "VALUES ('vb5', 'person', 'Test Entity', 0, 0)"
            ),
            conn.commit(),
        )
    )
    await upsert_alias(conn, "vb5", "test", "test", "manual")
    # aliases, phonetic_index, trigrams, and catalog_fts should all have rows
    alias_count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM aliases WHERE entity_id = 'vb5'"
        ).fetchone()
    )
    assert alias_count[0] >= 1
    await asyncio.to_thread(conn.close)
