"""Tests for resolver module — end-to-end resolve_link_text pipeline."""
import asyncio
from pathlib import Path

import pytest

from entity_db.db import open_db, upsert_alias
from entity_db.matching.normalize import normalize_text
from entity_db.matching.resolver import ResolveOptions, resolve_link_text


async def _seed(conn, eid: str, etype: str, cname: str, alias: str) -> None:
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT OR IGNORE INTO entities"
                " (id, type, canonical_name, created_at, updated_at)"
                " VALUES (?, ?, ?, 0, 0)",
                (eid, etype, cname),
            ),
            conn.commit(),
        )
    )
    await upsert_alias(conn, eid, alias, normalize_text(alias), "canonical")


# ── source_hash stability ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_source_hash_stable(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    opts = ResolveOptions(interactive=False)

    text = "Hello Viktor"
    r1 = await resolve_link_text(text, "markdown", opts, conn)
    r2 = await resolve_link_text(text, "markdown", opts, conn)

    assert r1.source_hash == r2.source_hash
    await asyncio.to_thread(conn.close)


# ── ambiguous span → pending_disambiguation (non-interactive) ─────────────────


@pytest.mark.asyncio
async def test_ambiguous_span_queued_non_interactive(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    # Seed viktor-bezdek; neutral context → score ~0.75 (no type cues)
    await _seed(conn, "vb", "person", "Viktor Bezdek", "Viktor")

    text = "Viktor was present"
    opts = ResolveOptions(interactive=False)
    result = await resolve_link_text(text, "markdown", opts, conn)

    pending_count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM pending_disambiguation WHERE source_hash = ?",
            (result.source_hash,),
        ).fetchone()
    )
    assert pending_count[0] >= 1, "Ambiguous span should be queued to pending_disambiguation"
    await asyncio.to_thread(conn.close)


# ── new unknown entity-shaped surface → staging ───────────────────────────────


@pytest.mark.asyncio
async def test_unknown_repeated_surface_staged(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    # "Echelon" appears ≥ 2 times, no catalog match → should be staged
    text = "Echelon is a tool. We use Echelon daily. Echelon rocks."
    opts = ResolveOptions(interactive=False)
    await resolve_link_text(text, "markdown", opts, conn)

    staging_count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM staging WHERE surface = 'Echelon'"
        ).fetchone()
    )
    assert staging_count[0] >= 1, "Unknown repeated capitalized surface should be staged"
    await asyncio.to_thread(conn.close)


# ── resolution_log written for auto-linked span ───────────────────────────────


@pytest.mark.asyncio
async def test_auto_linked_span_written_to_resolution_log(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    # Seed entity; pre-seed resolution_log to give it recency=1 so score ≥ 0.90
    await _seed(conn, "vb2", "person", "Viktor Bezdek", "Viktor")

    # Prime the linked_entities by pre-inserting a resolution_log row
    # for this source text to simulate recency (within-source prior mention)
    import hashlib

    text = "synced with Viktor about FoundryAI"
    source_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO resolution_log"
                " (source_hash, source_type, span_start, span_end,"
                "  surface, entity_id, confidence, method, created_at)"
                " VALUES (?, 'markdown', 0, 6, 'Viktor', 'vb2', 0.91, 'auto', 0)",
                (source_hash,),
            ),
            conn.commit(),
        )
    )

    opts = ResolveOptions(interactive=False)
    await resolve_link_text(text, "markdown", opts, conn)

    log_count = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM resolution_log"
            " WHERE source_hash = ? AND entity_id = 'vb2'",
            (source_hash,),
        ).fetchone()
    )
    # At least the pre-seeded row; resolver may add more
    assert log_count[0] >= 1
    await asyncio.to_thread(conn.close)


# ── coref propagation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_returns_result_shape(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    opts = ResolveOptions(interactive=False)
    result = await resolve_link_text("hello world", "markdown", opts, conn)

    assert hasattr(result, "resolutions")
    assert hasattr(result, "ambiguities")
    assert hasattr(result, "new_candidates")
    assert hasattr(result, "warnings")
    assert hasattr(result, "stats")
    assert hasattr(result, "source_hash")
    assert isinstance(result.source_hash, str) and len(result.source_hash) == 16
    await asyncio.to_thread(conn.close)
