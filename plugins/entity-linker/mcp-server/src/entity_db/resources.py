"""MCP App resource registrations — serve built HTML bundles as ui:// resources."""
from __future__ import annotations

from pathlib import Path

from fastmcp import Context, FastMCP
from fastmcp.apps import AppConfig

_APPS_DIR = Path(__file__).resolve().parents[2] / "apps"


def _read_html(app_name: str) -> str:
    path = _APPS_DIR / app_name / "dist" / "index.html"
    if not path.exists():
        return f"<html><body>{app_name} app not built. Run npm run build.</body></html>"
    return path.read_text(encoding="utf-8")


def register_resources(mcp: FastMCP) -> None:
    """Register all ui:// App resources and their linked tools."""
    from entity_db.tools.app_disambiguation import resolve_disambiguate_app
    from entity_db.tools.app_staging import staging_review_app

    @mcp.resource("ui://entity-db/disambiguation.html")
    def disambiguation_html() -> str:
        return _read_html("disambiguation")

    @mcp.tool(app=AppConfig(resource_uri="ui://entity-db/disambiguation.html"))  # type: ignore[call-arg]
    async def _resolve_disambiguate_app_mcp(
        ctx: Context,
        source_hash: str,
        ambiguity_ids: list[str] | None = None,
    ) -> list[dict[str, object]]:
        """Open the Disambiguation App (or elicitation fallback) for ambiguous spans."""
        return await resolve_disambiguate_app(
            ctx=ctx,
            source_hash=source_hash,
            ambiguity_ids=ambiguity_ids,
        )

    @mcp.resource("ui://entity-db/staging.html")
    def staging_html() -> str:
        return _read_html("staging")

    @mcp.tool(app=AppConfig(resource_uri="ui://entity-db/staging.html"))  # type: ignore[call-arg]
    async def _staging_review_app_mcp(
        ctx: Context,
        staging_ids: list[str] | None = None,
    ) -> list[dict[str, object]]:
        """Open the Staging Review App (or elicitation fallback) for pending candidates."""
        return await staging_review_app(ctx=ctx, staging_ids=staging_ids)
