"""Staging MCP tools: stage, list, approve, reject."""
from __future__ import annotations

import asyncio
import json
import time
import uuid

from entity_db.db import _write_lock, rebuild_fts_for, upsert_alias
from entity_db.matching.normalize import normalize_text
from entity_db.tools import get_conn


def _now() -> int:
    return int(time.time())


async def staging_stage(
    surface: str,
    proposed_type: str | None = None,
    proposed_name: str | None = None,
    evidence: dict[str, object] | None = None,
) -> dict[str, object]:
    """Add or update a new-entity candidate with evidence."""
    conn = get_conn()
    now = _now()
    dedup_key = normalize_text(surface) + "|" + (proposed_type or "other")
    ev_json = json.dumps(evidence or {})

    sql = (
        "INSERT INTO staging"
        " (id, dedup_key, surface, proposed_type, proposed_name,"
        "  evidence_json, frequency, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 1, 'pending', ?, ?)"
        " ON CONFLICT(dedup_key) DO UPDATE SET"
        " frequency = frequency + 1, updated_at = excluded.updated_at"
    )
    sid = str(uuid.uuid4())
    args = (sid, dedup_key, surface, proposed_type, proposed_name, ev_json, now, now)
    async with _write_lock:
        await asyncio.to_thread(
            lambda: (conn.execute(sql, args), conn.commit())
        )
    return {"staging_id": sid, "dedup_key": dedup_key}


async def staging_list(
    status: str = "pending", limit: int = 50, cursor: int = 0
) -> list[dict[str, object]]:
    """List staged candidates."""
    conn = get_conn()

    def _q() -> list[dict[str, object]]:
        rows = conn.execute(
            "SELECT id, surface, proposed_type, proposed_name, frequency, status"
            " FROM staging WHERE status = ? ORDER BY frequency DESC LIMIT ? OFFSET ?",
            (status, limit, cursor),
        ).fetchall()
        return [
            {
                "id": r[0], "surface": r[1], "proposed_type": r[2],
                "proposed_name": r[3], "frequency": r[4], "status": r[5],
            }
            for r in rows
        ]

    return await asyncio.to_thread(_q)


async def staging_approve(
    staging_id: str, merge_into: str | None = None
) -> dict[str, object]:
    """Approve a staged candidate as a new entity or merge alias into existing."""
    conn = get_conn()
    now = _now()

    row = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT surface, proposed_type, proposed_name FROM staging WHERE id = ?",
            (staging_id,),
        ).fetchone()
    )
    if row is None:
        return {"ok": False, "error": "staging row not found"}

    surface, proposed_type, proposed_name = row
    ak = normalize_text(surface)

    if merge_into:
        # Merge: add surface as alias to existing entity
        await upsert_alias(conn, merge_into, surface, ak, "user-confirmed")
        target_id = merge_into
    else:
        # Approve as new entity
        target_id = ak or staging_id[:8]
        from entity_db.tools.catalog import catalog_create
        await catalog_create(
            type=proposed_type or "other",
            canonical_name=proposed_name or surface,
        )
        await rebuild_fts_for(conn, target_id)

    # Update staging row
    async with _write_lock:
        await asyncio.to_thread(
            lambda: (
                conn.execute(
                    "UPDATE staging SET status='approved', merged_into=?, reviewed_at=?"
                    " WHERE id = ?",
                    (target_id if merge_into else None, now, staging_id),
                ),
                conn.commit(),
            )
        )

    # Backfill resolution_log for prior unlinked spans of this surface
    async with _write_lock:
        await asyncio.to_thread(
            lambda: (
                conn.execute(
                    "UPDATE resolution_log SET entity_id = ?, method = 'staged'"
                    " WHERE surface = ? AND entity_id IS NULL",
                    (target_id, surface),
                ),
                conn.commit(),
            )
        )

    return {"ok": True, "entity_id": target_id}


async def staging_reject(staging_id: str, reason: str | None = None) -> dict[str, object]:
    """Reject a staged candidate."""
    conn = get_conn()
    now = _now()
    async with _write_lock:
        await asyncio.to_thread(
            lambda: (
                conn.execute(
                    "UPDATE staging SET status='rejected', reviewed_at=? WHERE id=?",
                    (now, staging_id),
                ),
                conn.commit(),
            )
        )
    return {"ok": True, "staging_id": staging_id}
