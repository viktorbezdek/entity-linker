"""Tests for the FastMCP server entry point — health tool and MCP tool registration."""
import asyncio
import json
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

import entity_db.tools as tools_mod
from entity_db.db import open_db
from entity_db.server import _register_tools, mcp


@pytest.mark.asyncio
async def test_health_returns_ok():
    async with Client(mcp) as client:
        result = await client.call_tool("health", {})
        # FastMCP 3.x returns CallToolResult; content is a list of content items
        content = result.content
        assert len(content) == 1
        data = json.loads(content[0].text)
        assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_mcp_tool_registration_includes_core_tools(tmp_path: Path) -> None:
    """Verify that _register_tools() registers the expected MCP surface."""
    conn = await open_db(tmp_path / "test.sqlite")
    tools_mod.set_conn(conn)

    fresh_mcp = FastMCP("test-registration")
    # Temporarily redirect mcp-level decorators to fresh instance
    import entity_db.server as srv_module
    original_mcp = srv_module.mcp
    srv_module.mcp = fresh_mcp
    try:
        _register_tools()
        async with Client(fresh_mcp) as client:
            tools_list = await client.list_tools()
            tool_names = {t.name for t in tools_list}
    finally:
        srv_module.mcp = original_mcp
        tools_mod.set_conn(None)  # type: ignore[arg-type]
        await asyncio.to_thread(conn.close)

    required = {
        "catalog_stats", "catalog_list", "catalog_search", "catalog_create",
        "resolve_link_text", "resolve_render",
        "staging_list", "staging_approve",
        "pending_list", "pending_resolve",
    }
    missing = required - tool_names
    assert not missing, f"Missing MCP tools: {missing}\nRegistered: {tool_names}"
