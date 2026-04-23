"""Sliding-window candidate generation from source text."""
import asyncio
import re
import sqlite3
from dataclasses import dataclass

from entity_db.matching.index import compute_phonetic_keys
from entity_db.matching.normalize import normalize_text

# Minimal English + Czech stopword set (single-token aliases from these strings
# are skipped — they're too ambiguous to be useful candidates).
STOPWORDS: frozenset[str] = frozenset(
    [
        # English
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "during",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may", "might",
        "shall", "can", "i", "you", "he", "she", "we", "they", "it", "this",
        "that", "these", "those", "so", "if", "as", "not", "no", "yes",
        # Czech / Slovak common words
        "je", "jsou", "byl", "bylo", "se", "na", "ze", "ve", "do", "po", "za",
        "ale", "tak", "jak", "pro", "pri", "tim", "toto", "tuto", "toho",
    ]
)


@dataclass
class CandidateSpan:
    """A text span that might refer to a known entity."""

    surface: str
    alias_key: str
    span_start: int
    span_end: int
    entity_id: str
    entity_type: str
    phon_match: bool  # True if matched via phonetic index (not exact)


def _tokenize(text: str) -> list[tuple[str, int, int]]:
    """Return (token, start_char, end_char) for every whitespace-delimited token."""
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]


async def _exact_lookup(
    db: sqlite3.Connection, alias_key: str
) -> list[tuple[str, str, str]]:
    """Return (entity_id, type, alias_key) rows for an exact alias_key match."""
    sql = (
        "SELECT a.entity_id, e.type, a.alias_key"
        " FROM aliases a JOIN entities e ON e.id = a.entity_id"
        " WHERE a.alias_key = ? AND e.deprecated = 0"
    )
    rows = await asyncio.to_thread(lambda: db.execute(sql, (alias_key,)).fetchall())
    return [(r[0], r[1], r[2]) for r in rows]


async def _phonetic_lookup(
    db: sqlite3.Connection, alias_key: str
) -> list[tuple[str, str, str]]:
    """Return (entity_id, type, alias_key) rows via shared phonetic keys."""
    keys = compute_phonetic_keys(alias_key)
    all_keys = list(set(keys["dmetaphone"] + keys["beider-morse"]))
    if not all_keys:
        return []
    ph = ",".join("?" * len(all_keys))
    sql = (
        "SELECT DISTINCT a.entity_id, e.type, a.alias_key"
        " FROM phonetic_index pi"
        " JOIN aliases a ON a.alias_key = pi.alias_key"
        " JOIN entities e ON e.id = a.entity_id"
        f" WHERE pi.phonetic_key IN ({ph}) AND e.deprecated = 0"
    )
    rows = await asyncio.to_thread(lambda: db.execute(sql, all_keys).fetchall())
    return [(r[0], r[1], r[2]) for r in rows]


async def generate_candidates(
    text: str, db: sqlite3.Connection
) -> list[CandidateSpan]:
    """Return candidate entity spans for all windows (1–4 tokens) in text."""
    if not text.strip():
        return []

    tokens = _tokenize(text)
    seen: dict[str, CandidateSpan] = {}  # dedup key: f"{start}:{end}:{entity_id}"

    for window_size in range(1, 5):
        for i in range(len(tokens) - window_size + 1):
            window_toks = tokens[i : i + window_size]
            span_start = window_toks[0][1]
            span_end = window_toks[-1][2]
            surface = text[span_start:span_end]
            alias_key = normalize_text(surface)

            if not alias_key:
                continue

            # Single-token stopword filter
            if window_size == 1 and alias_key in STOPWORDS:
                continue

            if len(alias_key) <= 2:
                # Short aliases: exact match only (avoids noise from fuzzy lookup)
                matches = await _exact_lookup(db, alias_key)
                for eid, etype, ak in matches:
                    k = f"{span_start}:{span_end}:{eid}"
                    if k not in seen:
                        seen[k] = CandidateSpan(
                            surface, ak, span_start, span_end, eid, etype, False
                        )
            else:
                exact = await _exact_lookup(db, alias_key)
                for eid, etype, ak in exact:
                    k = f"{span_start}:{span_end}:{eid}"
                    if k not in seen:
                        seen[k] = CandidateSpan(
                            surface, ak, span_start, span_end, eid, etype, False
                        )

                phon = await _phonetic_lookup(db, alias_key)
                for eid, etype, ak in phon:
                    if ak in STOPWORDS:
                        continue
                    k = f"{span_start}:{span_end}:{eid}"
                    if k not in seen:
                        seen[k] = CandidateSpan(
                            surface, ak, span_start, span_end, eid, etype, True
                        )

    return list(seen.values())
