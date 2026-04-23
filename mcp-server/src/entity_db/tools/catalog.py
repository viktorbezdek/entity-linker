"""Catalog MCP tools: list, get, search, create, update, deprecate, stats, import."""
from __future__ import annotations

import asyncio
import json
import re
import time

from entity_db.db import rebuild_fts_for, upsert_alias
from entity_db.matching.normalize import derive_alias_variants, normalize_text
from entity_db.tools import get_conn


def _now() -> int:
    return int(time.time())


def _slug(name: str) -> str:
    """Generate a URL-safe entity ID from a canonical name."""
    slug = normalize_text(name).strip().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug or name.lower()[:20]


async def catalog_stats() -> dict[str, int]:
    """Return catalog size, queue depths, and recent activity."""
    conn = get_conn()

    def _query() -> dict[str, int]:
        e = conn.execute("SELECT COUNT(*) FROM entities WHERE deprecated = 0").fetchone()[0]
        a = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
        sp = conn.execute("SELECT COUNT(*) FROM staging WHERE status = 'pending'").fetchone()[0]
        pd = conn.execute(
            "SELECT COUNT(*) FROM pending_disambiguation WHERE status = 'pending'"
        ).fetchone()[0]
        recent = conn.execute(
            "SELECT COUNT(*) FROM resolution_log"
            " WHERE created_at >= strftime('%s','now','-1 day')"
        ).fetchone()[0]
        return {
            "entities": e,
            "aliases": a,
            "staging_pending": sp,
            "pending_disambiguation": pd,
            "recent_resolutions": recent,
        }

    return await asyncio.to_thread(_query)


async def catalog_list(
    type: str | None = None,
    limit: int = 50,
    cursor: int = 0,
) -> list[dict[str, object]]:
    """Paginated list of entities, optionally filtered by type."""
    conn = get_conn()

    def _query() -> list[dict[str, object]]:
        if type:
            rows = conn.execute(
                "SELECT id, type, canonical_name, disambiguation_hint FROM entities"
                " WHERE deprecated = 0 AND type = ? LIMIT ? OFFSET ?",
                (type, limit, cursor),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, type, canonical_name, disambiguation_hint FROM entities"
                " WHERE deprecated = 0 LIMIT ? OFFSET ?",
                (limit, cursor),
            ).fetchall()
        return [
            {"id": r[0], "type": r[1], "canonical_name": r[2], "hint": r[3]}
            for r in rows
        ]

    return await asyncio.to_thread(_query)


async def catalog_get(entity_id: str) -> dict[str, object] | None:
    """Return full entity record including aliases."""
    conn = get_conn()

    def _query() -> dict[str, object] | None:
        row = conn.execute(
            "SELECT id, type, canonical_name, disambiguation_hint, attributes_json"
            " FROM entities WHERE id = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            return None
        aliases = conn.execute(
            "SELECT alias, origin FROM aliases WHERE entity_id = ?", (entity_id,)
        ).fetchall()
        return {
            "id": row[0],
            "type": row[1],
            "canonical_name": row[2],
            "hint": row[3],
            "attributes": json.loads(row[4]) if row[4] else None,
            "aliases": [{"alias": a[0], "origin": a[1]} for a in aliases],
        }

    return await asyncio.to_thread(_query)


async def catalog_search(
    query: str, type: str | None = None
) -> list[dict[str, object]]:
    """FTS5 search over canonical names and aliases."""
    conn = get_conn()

    def _query() -> list[dict[str, object]]:
        fts_query = query.replace('"', '""')
        if type:
            rows = conn.execute(
                "SELECT f.entity_id, e.type, e.canonical_name, e.disambiguation_hint"
                " FROM catalog_fts f JOIN entities e ON e.id = f.entity_id"
                " WHERE catalog_fts MATCH ? AND e.type = ? AND e.deprecated = 0"
                " ORDER BY rank LIMIT 20",
                (fts_query, type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT f.entity_id, e.type, e.canonical_name, e.disambiguation_hint"
                " FROM catalog_fts f JOIN entities e ON e.id = f.entity_id"
                " WHERE catalog_fts MATCH ? AND e.deprecated = 0"
                " ORDER BY rank LIMIT 20",
                (fts_query,),
            ).fetchall()
        return [
            {"id": r[0], "type": r[1], "canonical_name": r[2], "hint": r[3]}
            for r in rows
        ]

    return await asyncio.to_thread(_query)


async def catalog_create(
    type: str,
    canonical_name: str,
    aliases: list[str] | None = None,
    attributes: dict[str, object] | None = None,
    disambiguation_hint: str | None = None,
) -> dict[str, object]:
    """Create a new entity directly (skips staging)."""
    from entity_db.db import _write_lock

    conn = get_conn()
    now = _now()
    eid = _slug(canonical_name)
    attrs_json = json.dumps(attributes) if attributes else None

    async with _write_lock:
        await asyncio.to_thread(
            lambda: (
                conn.execute(
                    "INSERT OR REPLACE INTO entities"
                    " (id, type, canonical_name, disambiguation_hint,"
                    "  attributes_json, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (eid, type, canonical_name, disambiguation_hint, attrs_json, now, now),
                ),
                conn.commit(),
            )
        )

    all_aliases = list(aliases or []) + derive_alias_variants(canonical_name)
    for alias in set(all_aliases):
        ak = normalize_text(alias)
        if ak:
            origin = "manual" if alias in (aliases or []) else "derived"
            await upsert_alias(conn, eid, alias, ak, origin)

    await rebuild_fts_for(conn, eid)
    return {"id": eid, "canonical_name": canonical_name, "type": type}


async def catalog_add_alias(
    entity_id: str, alias: str, origin: str = "manual"
) -> dict[str, object]:
    """Add an alias to an existing entity."""
    conn = get_conn()
    ak = normalize_text(alias)
    if not ak:
        return {"ok": False, "error": "alias normalises to empty string"}
    await upsert_alias(conn, entity_id, alias, ak, origin)
    return {"ok": True, "entity_id": entity_id, "alias_key": ak}


async def catalog_deprecate(entity_id: str) -> dict[str, object]:
    """Soft-delete an entity (excluded from matching; kept for audit)."""
    conn = get_conn()
    now = _now()
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "UPDATE entities SET deprecated = 1, updated_at = ? WHERE id = ?",
                (now, entity_id),
            ),
            conn.commit(),
        )
    )
    return {"ok": True, "entity_id": entity_id, "deprecated": True}


async def catalog_import(yaml_path: str) -> dict[str, int]:
    """Import entities from a YAML seed file."""
    from entity_db.seed import import_seed

    conn = get_conn()
    return await import_seed(conn, yaml_path)
