"""Tests for staging_review_app tool."""
import asyncio
import os
from pathlib import Path

import pytest

import entity_db.tools as tools_mod
from entity_db.db import open_db
from entity_db.tools.app_staging import staging_review_app
from entity_db.tools.staging import staging_stage


@pytest.fixture
async def conn(tmp_db_path: Path):
    c = await open_db(tmp_db_path)
    tools_mod.set_conn(c)
    yield c
    tools_mod.set_conn(None)  # type: ignore[arg-type]
    await asyncio.to_thread(c.close)


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_staging_review_app_returns_pending(conn) -> None:
    await staging_stage("Echelon", proposed_type="project")
    os.environ.pop("ENTITY_LINKER_FORCE_ELICITATION", None)
    result = await staging_review_app(ctx=_FakeCtx())
    assert len(result) >= 1
    assert any(r.get("surface") == "Echelon" for r in result)


@pytest.mark.asyncio
async def test_staging_review_app_filters_by_ids(conn) -> None:
    r1 = await staging_stage("Echelon", proposed_type="project")
    await staging_stage("OtherApp", proposed_type="product")
    sid = r1["staging_id"]

    result = await staging_review_app(ctx=_FakeCtx(), staging_ids=[sid])
    assert len(result) == 1
    assert result[0]["id"] == sid


@pytest.mark.asyncio
async def test_staging_review_app_fallback_returns_empty(conn) -> None:
    await staging_stage("TestApp", proposed_type="product")
    os.environ["ENTITY_LINKER_FORCE_ELICITATION"] = "1"
    try:
        result = await staging_review_app(ctx=_FakeCtx())
        assert result == []
    finally:
        del os.environ["ENTITY_LINKER_FORCE_ELICITATION"]


@pytest.mark.asyncio
async def test_staging_review_app_empty_queue(conn) -> None:
    result = await staging_review_app(ctx=_FakeCtx())
    assert result == []
