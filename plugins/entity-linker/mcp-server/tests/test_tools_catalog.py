"""Tests for catalog tools — catalog_stats, catalog_search, catalog_import."""
import asyncio
from pathlib import Path

import pytest

import entity_db.tools as tools_mod
from entity_db.db import open_db
from entity_db.seed import import_seed
from entity_db.tools.catalog import catalog_create, catalog_search, catalog_stats

SEED = Path(__file__).parents[2] / "docs" / "examples" / "entities.seed.yml"


@pytest.fixture
async def seeded_conn(tmp_db_path: Path):
    conn = await open_db(tmp_db_path)
    tools_mod.set_conn(conn)
    await import_seed(conn, SEED)
    yield conn
    tools_mod.set_conn(None)  # type: ignore[arg-type]
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_catalog_stats_after_seed(seeded_conn) -> None:
    stats = await catalog_stats()
    assert stats["entities"] >= 5
    assert stats["aliases"] >= 10


@pytest.mark.asyncio
async def test_catalog_search_finds_entity(seeded_conn) -> None:
    results = await catalog_search(query="Viktor")
    ids = [r["id"] for r in results]
    assert "viktor-bezdek" in ids


@pytest.mark.asyncio
async def test_catalog_create_new_entity(seeded_conn) -> None:
    result = await catalog_create(
        type="person",
        canonical_name="Diana Test",
        aliases=["Diana"],
    )
    assert result["id"] is not None
    assert result["canonical_name"] == "Diana Test"


@pytest.mark.asyncio
async def test_catalog_stats_empty_db(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    tools_mod.set_conn(conn)
    stats = await catalog_stats()
    assert stats["entities"] == 0
    tools_mod.set_conn(None)  # type: ignore[arg-type]
    await asyncio.to_thread(conn.close)
