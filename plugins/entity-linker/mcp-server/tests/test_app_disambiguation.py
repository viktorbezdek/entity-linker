"""Tests for resolve_disambiguate_app tool."""
import asyncio
import os
import uuid
from pathlib import Path

import pytest

import entity_db.tools as tools_mod
from entity_db.db import open_db
from entity_db.tools.app_disambiguation import resolve_disambiguate_app


@pytest.fixture
async def conn(tmp_db_path: Path):
    c = await open_db(tmp_db_path)
    tools_mod.set_conn(c)
    yield c
    tools_mod.set_conn(None)  # type: ignore[arg-type]
    await asyncio.to_thread(c.close)


async def _seed_pending(conn, source_hash: str = "abc123", surface: str = "Stefan") -> str:
    pid = str(uuid.uuid4())
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO pending_disambiguation"
                " (id, source_hash, source_type, span_start, span_end,"
                "  surface, candidates_json, context_json, status, created_at)"
                " VALUES (?, ?, 'markdown', 0, 6, ?, "
                "  '[{\"entity_id\": \"vb\", \"confidence\": 0.85}]', '{}', 'pending', 0)",
                (pid, source_hash, surface),
            ),
            conn.commit(),
        )
    )
    return pid


class _FakeCtx:
    """Minimal fake context that looks nothing like fastmcp.Context."""
    pass


@pytest.mark.asyncio
async def test_resolve_disambiguate_app_returns_pending_items(conn) -> None:
    source_hash = "abc123"
    await _seed_pending(conn, source_hash=source_hash)

    os.environ.pop("ENTITY_LINKER_FORCE_ELICITATION", None)
    result = await resolve_disambiguate_app(ctx=_FakeCtx(), source_hash=source_hash)

    assert len(result) >= 1
    assert result[0]["surface"] == "Stefan"
    assert result[0]["source_hash"] == source_hash


@pytest.mark.asyncio
async def test_resolve_disambiguate_app_filters_by_ambiguity_ids(conn) -> None:
    source_hash = "abc456"
    pid1 = await _seed_pending(conn, source_hash=source_hash, surface="Stefan")
    await _seed_pending(conn, source_hash=source_hash, surface="Pavel")

    result = await resolve_disambiguate_app(
        ctx=_FakeCtx(),
        source_hash=source_hash,
        ambiguity_ids=[pid1],
    )
    assert len(result) == 1
    assert result[0]["id"] == pid1


@pytest.mark.asyncio
async def test_resolve_disambiguate_app_returns_empty_for_unknown_hash(conn) -> None:
    result = await resolve_disambiguate_app(ctx=_FakeCtx(), source_hash="nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_resolve_disambiguate_app_fallback_elicitation(conn) -> None:
    """When ENTITY_LINKER_FORCE_ELICITATION=1, returns [] after elicitation flow."""
    source_hash = "elicit_test"
    await _seed_pending(conn, source_hash=source_hash)

    os.environ["ENTITY_LINKER_FORCE_ELICITATION"] = "1"
    try:
        result = await resolve_disambiguate_app(ctx=_FakeCtx(), source_hash=source_hash)
        # Elicitation path always returns [] (items consumed by ctx.elicit)
        assert result == []
    finally:
        del os.environ["ENTITY_LINKER_FORCE_ELICITATION"]
