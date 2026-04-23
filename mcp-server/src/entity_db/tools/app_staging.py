"""staging_review_app tool — opens the Staging Review App or falls back to elicitation."""
from __future__ import annotations

import asyncio
import json

from entity_db.elicit import should_use_elicitation
from entity_db.tools import get_conn
from entity_db.tools.staging import staging_list


async def staging_review_app(
    ctx: object = None,
    staging_ids: list[str] | None = None,
) -> list[dict[str, object]]:
    """Return pending staging candidates for the Staging Review App.

    If the host supports MCP Apps, the caller loads the App iframe with this data.
    Falls back to sequential ctx.elicit calls if host lacks App support.
    """
    conn = get_conn()

    if staging_ids:
        def _fetch() -> list[dict[str, object]]:
            placeholders = ",".join("?" * len(staging_ids))
            rows = conn.execute(
                "SELECT id, surface, proposed_type, proposed_name, frequency, evidence_json"
                f" FROM staging WHERE id IN ({placeholders}) AND status='pending'"
                " ORDER BY frequency DESC",
                list(staging_ids),
            ).fetchall()
            return [
                {
                    "id": r[0], "surface": r[1], "proposed_type": r[2],
                    "proposed_name": r[3], "frequency": r[4],
                    "evidence": json.loads(r[5]),
                }
                for r in rows
            ]
        items: list[dict[str, object]] = await asyncio.to_thread(_fetch)
    else:
        raw = await staging_list(status="pending", limit=50)
        items = [dict(r) for r in raw]

    if should_use_elicitation(ctx):
        from entity_db.elicit import review_staging_item
        from entity_db.tools.staging import staging_approve, staging_reject

        for item in items:
            result = await review_staging_item(ctx, str(item.get("surface", "")))
            if result:
                decision = result.get("decision", "reject")
                if decision == "approve_new":
                    await staging_approve(str(item["id"]))
                elif decision == "merge_existing":
                    merge_into = str(result.get("merge_target", ""))
                    if merge_into:
                        await staging_approve(str(item["id"]), merge_into=merge_into)
                else:
                    await staging_reject(str(item["id"]))
        return []

    return items
