"""FastMCP server entry point for entity-db."""
import os
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("entity-db")


@mcp.tool
async def health() -> dict[str, str]:
    """Health check — returns {status: ok}."""
    return {"status": "ok"}


# ── Tool registration ─────────────────────────────────────────────────────────
# Tools are registered by importing the tool modules and adding each function
# to the MCP instance. This is called once from __main__.py after DB init.

def _register_tools() -> None:
    from entity_db.tools.catalog import (
        catalog_add_alias,
        catalog_create,
        catalog_deprecate,
        catalog_get,
        catalog_import,
        catalog_list,
        catalog_search,
        catalog_stats,
    )
    from entity_db.tools.pending import pending_list, pending_resolve
    from entity_db.tools.staging import (
        staging_approve,
        staging_list,
        staging_reject,
        staging_stage,
    )

    for fn in [
        catalog_stats, catalog_list, catalog_get, catalog_search,
        catalog_create, catalog_add_alias, catalog_deprecate, catalog_import,
        staging_stage, staging_list, staging_approve, staging_reject,
        pending_list, pending_resolve,
    ]:
        mcp.add_tool(fn)  # type: ignore[attr-defined]


async def _init_db() -> None:
    """Open the DB, apply schema, and wire up the tool conn."""
    from entity_db.db import open_db
    from entity_db.tools import set_conn

    db_path = os.environ.get("ENTITY_DB_PATH", str(Path.home() / "entity-db" / "entities.sqlite"))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = await open_db(db_path)
    set_conn(conn)
    _register_tools()
