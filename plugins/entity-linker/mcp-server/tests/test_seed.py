"""Tests for seed.py — YAML catalog import."""
import asyncio
from pathlib import Path

import pytest

from entity_db.db import open_db
from entity_db.seed import import_seed

SEED_PATH = Path(__file__).parents[2] / "docs" / "examples" / "entities.seed.yml"


@pytest.mark.asyncio
async def test_import_seed_creates_entities(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    stats = await import_seed(conn, SEED_PATH)
    assert stats["entities"] >= 5, f"Expected ≥ 5 entities, got {stats}"
    assert stats["errors"] == 0

    count = await asyncio.to_thread(
        lambda: conn.execute("SELECT COUNT(*) FROM entities").fetchone()
    )
    assert count[0] >= 5
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_import_seed_creates_aliases(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await import_seed(conn, SEED_PATH)

    count = await asyncio.to_thread(
        lambda: conn.execute("SELECT COUNT(*) FROM aliases").fetchone()
    )
    assert count[0] >= 10, f"Expected ≥ 10 alias rows, got {count[0]}"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_import_seed_creates_phonetic_index(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await import_seed(conn, SEED_PATH)

    count = await asyncio.to_thread(
        lambda: conn.execute("SELECT COUNT(*) FROM phonetic_index").fetchone()
    )
    assert count[0] >= 5, "Expected phonetic_index rows after seed import"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_import_seed_creates_trigrams(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await import_seed(conn, SEED_PATH)

    count = await asyncio.to_thread(
        lambda: conn.execute("SELECT COUNT(*) FROM trigrams").fetchone()
    )
    assert count[0] >= 5
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_import_seed_populates_fts(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await import_seed(conn, SEED_PATH)

    rows = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT entity_id FROM catalog_fts WHERE catalog_fts MATCH 'Stefan'"
        ).fetchall()
    )
    assert any(r[0] == "stefan-weber" for r in rows)
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_import_seed_idempotent(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    stats1 = await import_seed(conn, SEED_PATH)
    stats2 = await import_seed(conn, SEED_PATH)
    assert stats2["errors"] == 0
    # Second import should not double-count entities (INSERT OR REPLACE)
    count = await asyncio.to_thread(
        lambda: conn.execute("SELECT COUNT(*) FROM entities").fetchone()
    )
    assert count[0] == stats1["entities"]
    await asyncio.to_thread(conn.close)
