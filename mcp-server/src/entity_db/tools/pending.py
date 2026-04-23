"""Pending-disambiguation MCP tools: list, resolve."""
from __future__ import annotations

import asyncio
import time

from entity_db.db import _write_lock
from entity_db.tools import get_conn


def _now() -> int:
    return int(time.time())


async def pending_list(
    source_hash: str | None = None, limit: int = 50, cursor: int = 0
) -> list[dict[str, object]]:
    """List queued disambiguation items."""
    conn = get_conn()

    def _q() -> list[dict[str, object]]:
        if source_hash:
            rows = conn.execute(
                "SELECT id, source_hash, source_type, span_start, span_end, surface, status"
                " FROM pending_disambiguation WHERE source_hash = ? AND status='pending'"
                " LIMIT ? OFFSET ?",
                (source_hash, limit, cursor),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, source_hash, source_type, span_start, span_end, surface, status"
                " FROM pending_disambiguation WHERE status='pending' LIMIT ? OFFSET ?",
                (limit, cursor),
            ).fetchall()
        return [
            {
                "id": r[0], "source_hash": r[1], "source_type": r[2],
                "span_start": r[3], "span_end": r[4],
                "surface": r[5], "status": r[6],
            }
            for r in rows
        ]

    return await asyncio.to_thread(_q)


async def pending_resolve(
    pending_id: str, entity_id_or_sentinel: str
) -> dict[str, object]:
    """Resolve a pending disambiguation item.

    entity_id_or_sentinel is one of:
    - an entity_id → mark resolved, backfill resolution_log
    - "none"        → mark abandoned
    - "new"         → insert a staging row and return its id
    """
    conn = get_conn()
    now = _now()

    row = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT source_hash, source_type, span_start, span_end, surface, candidates_json"
            " FROM pending_disambiguation WHERE id = ?",
            (pending_id,),
        ).fetchone()
    )
    if row is None:
        return {"ok": False, "error": "pending row not found"}

    source_hash, source_type, span_start, span_end, surface, cands_json = row
    result: dict[str, object] = {"ok": True, "pending_id": pending_id}

    if entity_id_or_sentinel == "none":
        status = "abandoned"
        resolved_entity = None
    elif entity_id_or_sentinel == "new":
        # Insert into staging (server-side chaining — no host mediation)
        from entity_db.tools.staging import staging_stage
        stage_result = await staging_stage(surface, evidence={"source_hash": source_hash})
        result["staging_id"] = stage_result["staging_id"]
        status = "resolved"
        resolved_entity = None
    else:
        status = "resolved"
        resolved_entity = entity_id_or_sentinel
        # Backfill resolution_log
        async with _write_lock:
            await asyncio.to_thread(
                lambda: (
                    conn.execute(
                        "INSERT INTO resolution_log"
                        " (source_hash, source_type, span_start, span_end, surface,"
                        "  entity_id, confidence, method, created_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, 0.85, 'user-confirmed', ?)",
                        (source_hash, source_type, span_start, span_end, surface,
                         entity_id_or_sentinel, now),
                    ),
                    conn.commit(),
                )
            )

    async with _write_lock:
        await asyncio.to_thread(
            lambda: (
                conn.execute(
                    "UPDATE pending_disambiguation SET status=?, resolved_at=?,"
                    " resolved_entity=? WHERE id=?",
                    (status, now, resolved_entity, pending_id),
                ),
                conn.commit(),
            )
        )

    result["status"] = status
    if resolved_entity:
        result["entity_id"] = resolved_entity
    return result
