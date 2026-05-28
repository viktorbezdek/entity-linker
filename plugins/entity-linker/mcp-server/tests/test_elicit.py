"""Tests for elicit module — fallback gate, disambiguate_span, review_staging_item."""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from entity_db.elicit import should_use_elicitation


def test_should_use_elicitation_env_var_true() -> None:
    os.environ["ENTITY_LINKER_FORCE_ELICITATION"] = "1"
    try:
        assert should_use_elicitation(None) is True
    finally:
        del os.environ["ENTITY_LINKER_FORCE_ELICITATION"]


def test_should_use_elicitation_env_var_absent() -> None:
    os.environ.pop("ENTITY_LINKER_FORCE_ELICITATION", None)
    # Without env var and without a real FastMCP context, returns False
    assert should_use_elicitation(None) is False


def test_should_use_elicitation_non_context_object() -> None:
    os.environ.pop("ENTITY_LINKER_FORCE_ELICITATION", None)
    assert should_use_elicitation("not a context") is False


@pytest.mark.asyncio
async def test_disambiguate_span_non_context_returns_none() -> None:
    from entity_db.elicit import disambiguate_span

    result = await disambiguate_span(None, "Stefan", [])
    assert result is None


@pytest.mark.asyncio
async def test_review_staging_item_non_context_returns_none() -> None:
    from entity_db.elicit import review_staging_item

    result = await review_staging_item(None, "Test")
    assert result is None


@pytest.mark.asyncio
async def test_disambiguate_span_accept() -> None:
    from entity_db.elicit import disambiguate_span

    # Mock a FastMCP-like ctx
    mock_ctx = MagicMock()
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.data = MagicMock(choice="stefan-weber")
    mock_ctx.elicit = AsyncMock(return_value=mock_result)

    import fastmcp
    mock_ctx.__class__ = fastmcp.Context  # make isinstance pass

    result = await disambiguate_span(mock_ctx, "Stefan", [{"entity_id": "stefan-weber"}])
    assert result == "stefan-weber"


@pytest.mark.asyncio
async def test_disambiguate_span_cancel_returns_none() -> None:
    import fastmcp

    from entity_db.elicit import disambiguate_span

    mock_ctx = MagicMock()
    mock_result = MagicMock()
    mock_result.action = "cancel"
    mock_ctx.elicit = AsyncMock(return_value=mock_result)
    mock_ctx.__class__ = fastmcp.Context

    result = await disambiguate_span(mock_ctx, "Stefan", [])
    assert result is None


@pytest.mark.asyncio
async def test_review_staging_item_approve_new() -> None:
    import fastmcp

    from entity_db.elicit import review_staging_item

    mock_ctx = MagicMock()
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.data = MagicMock(
        decision="approve_new",
        merge_target="",
        corrected_type="project",
        corrected_name="Echelon AI",
    )
    mock_ctx.elicit = AsyncMock(return_value=mock_result)
    mock_ctx.__class__ = fastmcp.Context

    result = await review_staging_item(mock_ctx, "Echelon", "project")
    assert result is not None
    assert result["decision"] == "approve_new"
    assert result["corrected_name"] == "Echelon AI"


@pytest.mark.asyncio
async def test_review_staging_item_uses_surface_as_default_name() -> None:
    import fastmcp

    from entity_db.elicit import review_staging_item

    mock_ctx = MagicMock()
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.data = MagicMock(
        decision="approve_new",
        merge_target="",
        corrected_type="",
        corrected_name="",
    )
    mock_ctx.elicit = AsyncMock(return_value=mock_result)
    mock_ctx.__class__ = fastmcp.Context

    result = await review_staging_item(mock_ctx, "MySurface")
    assert result is not None
    assert result["corrected_name"] == "MySurface"
    assert result["corrected_type"] == "other"


@pytest.mark.asyncio
async def test_review_staging_item_decline_returns_none() -> None:
    import fastmcp

    from entity_db.elicit import review_staging_item

    mock_ctx = MagicMock()
    mock_result = MagicMock()
    mock_result.action = "decline"
    mock_ctx.elicit = AsyncMock(return_value=mock_result)
    mock_ctx.__class__ = fastmcp.Context

    result = await review_staging_item(mock_ctx, "Unknown")
    assert result is None
