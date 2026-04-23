"""resolve_disambiguate_app tool — opens the Disambiguation App or falls back to elicitation."""
from __future__ import annotations

import asyncio
import json

from entity_db.elicit import should_use_elicitation
from entity_db.tools import get_conn


async def resolve_disambiguate_app(
    ctx: object,
    source_hash: str,
    ambiguity_ids: list[str] | None = None,
) -> list[dict[str, object]]:
    """Return pending disambiguation items for the given source_hash.

    If the host supports MCP Apps, the caller loads the Disambiguation App iframe
    with this data as its initial payload. If the host doesn't support Apps (or
    ENTITY_LINKER_FORCE_ELICITATION=1), falls back to sequential ctx.elicit calls.
    """
    conn = get_conn()

    def _fetch() -> list[tuple[str, str, str, int, int, str, str]]:
        if ambiguity_ids:
            placeholders = ",".join("?" * len(ambiguity_ids))
            sql = (
                "SELECT id, source_hash, surface, span_start, span_end,"
                "       candidates_json, context_json"
                f" FROM pending_disambiguation"
                f" WHERE source_hash = ? AND id IN ({placeholders}) AND status='pending'"
            )
            rows = conn.execute(sql, [source_hash] + list(ambiguity_ids)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, source_hash, surface, span_start, span_end,"
                "       candidates_json, context_json"
                " FROM pending_disambiguation"
                " WHERE source_hash = ? AND status='pending'",
                (source_hash,),
            ).fetchall()
        return rows  # type: ignore[return-value]

    rows = await asyncio.to_thread(_fetch)

    items = [
        {
            "id": r[0],
            "source_hash": r[1],
            "surface": r[2],
            "span_start": r[3],
            "span_end": r[4],
            "candidates": json.loads(r[5]),
            "context": json.loads(r[6]),
        }
        for r in rows
    ]

    if should_use_elicitation(ctx):
        from entity_db.elicit import disambiguate_span
        from entity_db.tools.pending import pending_resolve

        for item in items:
            result = await disambiguate_span(ctx, item["surface"], item["candidates"])  # type: ignore[arg-type]
            if result:
                await pending_resolve(item["id"], result)
        return []

    return items
