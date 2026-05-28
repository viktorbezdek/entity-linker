"""Tests for index module — phonetic keys, trigrams, DB rebuild."""
import asyncio
from pathlib import Path

import pytest

from entity_db.db import open_db, upsert_alias
from entity_db.matching.index import compute_phonetic_keys, compute_trigrams

# ── compute_phonetic_keys ─────────────────────────────────────────────────────


def test_phonetic_keys_bezdek_non_empty() -> None:
    result = compute_phonetic_keys("bezdek")
    assert len(result["dmetaphone"]) > 0
    assert len(result["beider-morse"]) > 0


def test_phonetic_keys_besdek_shares_bmpm_with_bezdek() -> None:
    keys_bezdek = compute_phonetic_keys("bezdek")
    keys_besdek = compute_phonetic_keys("besdek")
    shared = set(keys_bezdek["beider-morse"]) & set(keys_besdek["beider-morse"])
    assert len(shared) >= 1, (
        f"Expected shared BMPM key; bezdek={keys_bezdek['beider-morse']}, "
        f"besdek={keys_besdek['beider-morse']}"
    )


def test_phonetic_keys_no_empty_strings() -> None:
    for name in ("bezdek", "viktor", "tomas", "adam"):
        result = compute_phonetic_keys(name)
        assert all(k != "" for k in result["dmetaphone"]), f"Empty DM key for {name}"
        assert all(k != "" for k in result["beider-morse"]), f"Empty BMPM key for {name}"


def test_phonetic_keys_returns_expected_structure() -> None:
    result = compute_phonetic_keys("test")
    assert "dmetaphone" in result
    assert "beider-morse" in result
    assert isinstance(result["dmetaphone"], list)
    assert isinstance(result["beider-morse"], list)


# ── compute_trigrams ──────────────────────────────────────────────────────────


def test_trigrams_foundryai_count() -> None:
    # "foundryai" (9 chars) padded as "^foundryai$" (11 chars) → 11-3+1 = 9 trigrams
    trigrams = compute_trigrams("foundryai")
    assert len(trigrams) == 9, f"Expected 9 trigrams, got {len(trigrams)}: {trigrams}"


def test_trigrams_short_alias_empty() -> None:
    # aliases < 3 chars produce no trigrams
    assert compute_trigrams("vi") == []
    assert compute_trigrams("a") == []
    assert compute_trigrams("") == []


def test_trigrams_boundary_markers_present() -> None:
    trigrams = compute_trigrams("viktor")
    trigram_set = set(trigrams)
    assert "^vi" in trigram_set, "Expected leading '^vi' trigram"
    assert "or$" in trigram_set, "Expected trailing 'or$' trigram"


def test_trigrams_no_duplicates() -> None:
    trigrams = compute_trigrams("aaabbb")
    assert len(trigrams) == len(set(trigrams))


def test_trigrams_single_trigram_for_three_char_alias() -> None:
    # "abc" padded → "^abc$" → "^ab", "abc", "bc$" = 3 trigrams
    assert len(compute_trigrams("abc")) == 3


# ── DB rebuild via upsert_alias ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_alias_populates_phonetic_index(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    # Insert entity first
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                "VALUES ('vb', 'person', 'Stefan Weber', 0, 0)"
            ),
            conn.commit(),
        )
    )
    await upsert_alias(conn, "vb", "Bezdek", "bezdek", "canonical")

    rows = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM phonetic_index WHERE alias_key = 'bezdek'"
        ).fetchone()
    )
    assert rows[0] > 0, "phonetic_index must have rows after upsert_alias"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_upsert_alias_populates_trigrams(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                "VALUES ('vb2', 'person', 'Stefan Weber', 0, 0)"
            ),
            conn.commit(),
        )
    )
    await upsert_alias(conn, "vb2", "Bezdek", "bezdek", "canonical")

    rows = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM trigrams WHERE alias_key = 'bezdek'"
        ).fetchone()
    )
    assert rows[0] > 0, "trigrams must have rows after upsert_alias"
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_delete_alias_removes_phonetic_and_trigram_rows(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await asyncio.to_thread(
        lambda: (
            conn.execute(
                "INSERT INTO entities (id, type, canonical_name, created_at, updated_at) "
                "VALUES ('vb3', 'person', 'Stefan Weber', 0, 0)"
            ),
            conn.commit(),
        )
    )
    await upsert_alias(conn, "vb3", "Bezdek", "bezdek3", "canonical")

    # Verify rows exist
    phon = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM phonetic_index WHERE alias_key = 'bezdek3'"
        ).fetchone()
    )
    assert phon[0] > 0

    # Delete the alias and rebuild (via direct delete + calling rebuild functions)
    from entity_db.db import rebuild_phonetic_for, rebuild_trigrams_for

    await asyncio.to_thread(
        lambda: (
            conn.execute("DELETE FROM aliases WHERE alias_key = 'bezdek3'"),
            conn.execute("DELETE FROM phonetic_index WHERE alias_key = 'bezdek3'"),
            conn.execute("DELETE FROM trigrams WHERE alias_key = 'bezdek3'"),
            conn.commit(),
        )
    )
    await rebuild_phonetic_for(conn, "bezdek3")
    await rebuild_trigrams_for(conn, "bezdek3")

    phon_after = await asyncio.to_thread(
        lambda: conn.execute(
            "SELECT COUNT(*) FROM phonetic_index WHERE alias_key = 'bezdek3'"
        ).fetchone()
    )
    assert phon_after[0] == 0, "Rows should be gone after alias deleted and rebuild"
    await asyncio.to_thread(conn.close)
