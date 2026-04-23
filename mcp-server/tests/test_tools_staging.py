"""Tests for staging tools — stage, list, approve, reject."""
import asyncio
from pathlib import Path

import pytest

import entity_db.tools as tools_mod
from entity_db.db import open_db
from entity_db.tools.staging import staging_approve, staging_list, staging_reject, staging_stage


@pytest.fixture
async def conn(tmp_db_path: Path):
    c = await open_db(tmp_db_path)
    tools_mod.set_conn(c)
    yield c
    tools_mod.set_conn(None)  # type: ignore[arg-type]
    await asyncio.to_thread(c.close)


@pytest.mark.asyncio
async def test_staging_stage_creates_row(conn) -> None:
    result = await staging_stage("Echelon", proposed_type="project")
    assert "staging_id" in result

    count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM staging WHERE surface = 'Echelon'"
        ).fetchone()
    )
    assert count[0] == 1


@pytest.mark.asyncio
async def test_staging_stage_dedup_increments_frequency(conn) -> None:
    await staging_stage("EchoApp", proposed_type="product")
    await staging_stage("EchoApp", proposed_type="product")

    row = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT frequency FROM staging WHERE surface = 'EchoApp'"
        ).fetchone()
    )
    assert row[0] == 2


@pytest.mark.asyncio
async def test_staging_list_returns_pending(conn) -> None:
    await staging_stage("TestProject", proposed_type="project")
    items = await staging_list()
    surfaces = [i["surface"] for i in items]
    assert "TestProject" in surfaces


@pytest.mark.asyncio
async def test_staging_reject_updates_status(conn) -> None:
    result = await staging_stage("Rejected Inc", proposed_type="company")
    sid = result["staging_id"]
    rej = await staging_reject(sid)
    assert rej["ok"] is True

    status = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT status FROM staging WHERE surface = 'Rejected Inc'"
        ).fetchone()
    )
    assert status[0] == "rejected"


@pytest.mark.asyncio
async def test_staging_approve_backfills_resolution_log(conn) -> None:
    # Seed a resolution_log row with no entity_id (unlinked)
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO resolution_log"
                " (source_hash, source_type, span_start, span_end,"
                "  surface, entity_id, confidence, method, created_at)"
                " VALUES ('abc', 'markdown', 0, 5, 'Acme', NULL, 0.75, 'queued', 0)"
            ),
            conn.commit(),
        )
    )
    # Seed entity for the merge target
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at)"
                " VALUES ('acme-corp', 'company', 'Acme Corp', 0, 0)"
            ),
            conn.commit(),
        )
    )

    result = await staging_stage("Acme", proposed_type="company")
    sid = result["staging_id"]
    await staging_approve(sid, merge_into="acme-corp")

    row = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT entity_id FROM resolution_log WHERE surface = 'Acme'"
        ).fetchone()
    )
    assert row is not None and row[0] == "acme-corp"
