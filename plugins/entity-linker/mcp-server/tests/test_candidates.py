"""Tests for candidates module — sliding window generation, DoD Task 6."""
import asyncio
from pathlib import Path

import pytest

from entity_db.db import open_db, upsert_alias
from entity_db.matching.candidates import generate_candidates


async def _seed_entity(conn, eid: str, etype: str, cname: str, alias: str) -> None:
    """Insert entity + alias + rebuild indices."""
    from entity_db.matching.normalize import normalize_text

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


@pytest.mark.asyncio
async def test_generate_candidates_finds_exact_match(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await _seed_entity(conn, "stefan-weber", "person", "Stefan Weber", "Stefan")

    text = "So I synced with Stefan yesterday about QuantumAI rollout"
    candidates = await generate_candidates(text, conn)

    entity_ids = {c.entity_id for c in candidates}
    assert "stefan-weber" in entity_ids, (
        f"Expected stefan-weber in candidates; found {entity_ids}"
    )
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_generate_candidates_span_offsets_correct(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await _seed_entity(conn, "vb", "person", "Stefan Weber", "Stefan")

    text = "Hello Stefan world"
    candidates = await generate_candidates(text, conn)

    vb_spans = [c for c in candidates if c.entity_id == "vb"]
    assert vb_spans, "Expected at least one span for 'vb'"
    span = vb_spans[0]
    # "Stefan" starts at char 6 in "Hello Stefan world"
    assert span.span_start == 6
    assert text[span.span_start : span.span_end] == "Stefan"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_generate_candidates_stopwords_excluded(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    # "the" is a stopword — should never be a candidate even if in DB
    await _seed_entity(conn, "the-entity", "other", "The", "the")

    text = "the quick brown fox"
    candidates = await generate_candidates(text, conn)
    assert not any(c.entity_id == "the-entity" for c in candidates)
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_generate_candidates_two_token_window(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await _seed_entity(conn, "quantum-ai", "project", "Quantum AI", "Quantum AI")

    text = "working on Quantum AI rollout"
    candidates = await generate_candidates(text, conn)
    entity_ids = {c.entity_id for c in candidates}
    assert "quantum-ai" in entity_ids
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_generate_candidates_empty_text(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    candidates = await generate_candidates("", conn)
    assert candidates == []
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_generate_candidates_short_alias_requires_exact(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    # "AI" is a 2-char alias — exact match only
    await _seed_entity(conn, "ai-entity", "acronym", "AI", "AI")

    # Fuzzy text that would match phonetically but not exactly
    text = "some unrelated context"
    candidates = await generate_candidates(text, conn)
    assert not any(c.entity_id == "ai-entity" for c in candidates)
    await asyncio.to_thread(conn.close)
