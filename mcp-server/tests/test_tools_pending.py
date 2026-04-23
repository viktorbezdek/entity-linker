"""Tests for pending tools — list, resolve."""
import asyncio
import uuid
from pathlib import Path

import pytest

import entity_db.tools as tools_mod
from entity_db.db import open_db
from entity_db.tools.pending import pending_list, pending_resolve


@pytest.fixture
async def conn(tmp_db_path: Path):
    c = await open_db(tmp_db_path)
    tools_mod.set_conn(c)
    yield c
    tools_mod.set_conn(None)  # type: ignore[arg-type]
    await asyncio.to_thread(c.close)


async def _seed_pending(conn, surface: str = "Viktor") -> str:
    """Insert a pending_disambiguation row and return its id."""
    pid = str(uuid.uuid4())
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO pending_disambiguation"
                " (id, source_hash, source_type, span_start, span_end,"
                "  surface, candidates_json, context_json, status, created_at)"
                " VALUES (?, 'hash1', 'markdown', 0, 6, ?, '[]', '{}', 'pending', 0)",
                (pid, surface),
            ),
            conn.commit(),
        )
    )
    return pid


@pytest.mark.asyncio
async def test_pending_list_returns_rows(conn) -> None:
    await _seed_pending(conn, "Viktor")
    items = await pending_list()
    assert len(items) >= 1
    assert items[0]["surface"] == "Viktor"


@pytest.mark.asyncio
async def test_pending_resolve_with_entity_updates_row(conn) -> None:
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at)"
                " VALUES ('vb', 'person', 'Viktor Bezdek', 0, 0)"
            ),
            conn.commit(),
        )
    )
    pid = await _seed_pending(conn, "Viktor")
    result = await pending_resolve(pid, "vb")
    assert result["ok"] is True
    assert result.get("entity_id") == "vb"

    status = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT status, resolved_entity FROM pending_disambiguation WHERE id = ?",
            (pid,),
        ).fetchone()
    )
    assert status[0] == "resolved"
    assert status[1] == "vb"


@pytest.mark.asyncio
async def test_pending_resolve_none_marks_abandoned(conn) -> None:
    pid = await _seed_pending(conn, "Unknown")
    result = await pending_resolve(pid, "none")
    assert result["ok"] is True

    status = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT status FROM pending_disambiguation WHERE id = ?", (pid,)
        ).fetchone()
    )
    assert status[0] == "abandoned"


@pytest.mark.asyncio
async def test_pending_resolve_new_creates_staging_row(conn) -> None:
    pid = await _seed_pending(conn, "Echelon")
    result = await pending_resolve(pid, "new")
    assert result["ok"] is True
    assert "staging_id" in result

    staging = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM staging WHERE surface = 'Echelon'"
        ).fetchone()
    )
    assert staging[0] >= 1


@pytest.mark.asyncio
async def test_pending_resolve_backfills_resolution_log(conn) -> None:
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at)"
                " VALUES ('vb2', 'person', 'Viktor Bezdek', 0, 0)"
            ),
            conn.commit(),
        )
    )
    pid = await _seed_pending(conn, "Viktor")
    await pending_resolve(pid, "vb2")

    log = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM resolution_log WHERE entity_id = 'vb2'"
        ).fetchone()
    )
    assert log[0] >= 1
