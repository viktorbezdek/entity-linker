"""Tests for the FastMCP server entry point."""
import json

import pytest
from fastmcp import Client

from entity_db.server import mcp


@pytest.mark.asyncio
async def test_health_returns_ok():
    async with Client(mcp) as client:
        result = await client.call_tool("health", {})
        # FastMCP 3.x returns CallToolResult; content is a list of content items
        content = result.content
        assert len(content) == 1
        data = json.loads(content[0].text)
        assert data == {"status": "ok"}
