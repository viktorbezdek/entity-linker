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

    # Register resolve_link_text and resolve_render as public MCP tools
    _register_resolver_tool()
    _register_render_tool()

    # Register App resources + App-linked tools
    from entity_db.resources import register_resources
    register_resources(mcp)


def _register_resolver_tool() -> None:
    """Register resolve_link_text as a public MCP tool with DB wiring."""
    from entity_db.matching.resolver import ResolveOptions, resolve_link_text
    from entity_db.tools import get_conn

    @mcp.tool  # type: ignore[misc]
    async def resolve_link_text_mcp(
        text: str,
        source_type: str = "markdown",
        interactive: bool = True,
        on_ambiguity: str = "prompt",
        on_new_candidate: str = "stage",
        source_path: str | None = None,
    ) -> dict[str, object]:
        """Resolve entity mentions in text against the catalog."""
        opts = ResolveOptions(
            interactive=interactive,
            on_ambiguity=on_ambiguity,
            on_new_candidate=on_new_candidate,
            source_path=source_path,
        )
        result = await resolve_link_text(text, source_type, opts, get_conn())
        return {
            "resolutions": [
                {
                    "surface": r.surface,
                    "span_start": r.span_start,
                    "span_end": r.span_end,
                    "entity_id": r.entity_id,
                    "entity_type": r.entity_type,
                    "confidence": r.confidence,
                    "method": r.method,
                }
                for r in result.resolutions
            ],
            "ambiguities": result.ambiguities,
            "new_candidates": result.new_candidates,
            "warnings": result.warnings,
            "stats": result.stats,
            "source_hash": result.source_hash,
        }


def _register_render_tool() -> None:
    """Register resolve_render as a public MCP tool."""
    from entity_db.matching.resolver import Resolution
    from entity_db.render import to_markdown, to_sidecar, to_xml

    @mcp.tool  # type: ignore[misc]
    async def resolve_render(
        text: str,
        resolutions: list[dict[str, object]],
        format: str = "markdown",
    ) -> dict[str, object]:
        """Render annotated text in the requested format (markdown, xml, sidecar)."""
        res_objs = [
            Resolution(
                surface=str(r["surface"]),
                span_start=int(str(r["span_start"])),
                span_end=int(str(r["span_end"])),
                entity_id=str(r["entity_id"]),
                entity_type=str(r["entity_type"]),
                confidence=float(str(r.get("confidence", 0.9))),
                method=str(r.get("method", "auto")),
                source_hash=str(r.get("source_hash", "")),
                source_type=str(r.get("source_type", "markdown")),
            )
            for r in resolutions
        ]
        if format == "xml":
            return {"text": to_xml(text, res_objs)}
        if format == "sidecar":
            original, sidecar = to_sidecar(text, res_objs)
            return {"text": original, "sidecar": sidecar}
        return {"text": to_markdown(text, res_objs)}


async def _init_db() -> None:
    """Open the DB, apply schema, and wire up the tool conn."""
    from entity_db.db import open_db
    from entity_db.tools import set_conn

    db_path = os.environ.get("ENTITY_DB_PATH", str(Path.home() / "entity-db" / "entities.sqlite"))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = await open_db(db_path)
    set_conn(conn)
    _register_tools()
