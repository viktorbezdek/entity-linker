"""FastMCP server entry point for entity-db."""
from fastmcp import FastMCP

mcp = FastMCP("entity-db")


@mcp.tool
async def health() -> dict[str, str]:
    """Health check — returns {status: ok}."""
    return {"status": "ok"}
