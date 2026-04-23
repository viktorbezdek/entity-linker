"""Catalog bootstrap: parse entities.seed.yml and import into the DB."""
from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path
from typing import Any

import yaml

from entity_db.db import upsert_alias
from entity_db.matching.normalize import derive_alias_variants, normalize_text


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _validate_entity(entity: dict[str, Any]) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors: list[str] = []
    for field in ("id", "type", "canonical_name"):
        if not entity.get(field):
            errors.append(f"Missing required field '{field}'")
    valid_types = {
        "person", "project", "product", "team", "company", "acronym", "concept", "other"
    }
    if entity.get("type") and entity["type"] not in valid_types:
        errors.append(f"Unknown type '{entity['type']}'")
    return errors


async def import_seed(conn: sqlite3.Connection, path: str | Path) -> dict[str, int]:
    """Import entities from a YAML seed file.

    Returns a stats dict: {entities, aliases, errors}.
    """
    data = await asyncio.to_thread(_load_yaml, path)
    entities = data.get("entities", [])
    now = int(time.time())
    stats = {"entities": 0, "aliases": 0, "errors": 0}

    for raw in entities:
        errs = _validate_entity(raw)
        if errs:
            stats["errors"] += 1
            continue

        eid: str = raw["id"]
        etype: str = raw["type"]
        cname: str = raw["canonical_name"]
        hint: str | None = raw.get("disambiguation_hint")
        attributes: str | None = None
        if raw.get("attributes"):
            import json
            attributes = json.dumps(raw["attributes"])

        # Upsert entity
        await asyncio.to_thread(
            lambda e=eid, t=etype, c=cname, h=hint, a=attributes: (
                conn.execute(
                    "INSERT OR REPLACE INTO entities"
                    " (id, type, canonical_name, disambiguation_hint,"
                    "  attributes_json, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (e, t, c, h, a, now, now),
                ),
                conn.commit(),
            )
        )
        stats["entities"] += 1

        # Collect aliases: from seed YAML + auto-derived variants
        explicit: list[str] = raw.get("aliases", [])
        derived: list[str] = derive_alias_variants(cname)
        all_aliases: dict[str, str] = {}  # alias_key → origin

        for a in derived:
            ak = normalize_text(a)
            if ak:
                all_aliases[ak] = "derived"

        for a in explicit:
            ak = normalize_text(a)
            if ak:
                all_aliases[ak] = "manual"

        # Canonical name itself
        ck = normalize_text(cname)
        if ck:
            all_aliases[ck] = "canonical"

        for ak, origin in all_aliases.items():
            await upsert_alias(conn, eid, ak, ak, origin)
            stats["aliases"] += 1

    return stats
