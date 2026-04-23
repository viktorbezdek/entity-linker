"""Phonetic and trigram indexing for entity alias keys."""
import sqlite3

from abydos.phonetic import BeiderMorse, DoubleMetaphone

# Instantiate once per process — they are stateless and initialisation is slow.
_BMPM = BeiderMorse(match_mode="approx")
_DM = DoubleMetaphone()


def compute_phonetic_keys(alias_key: str) -> dict[str, list[str]]:
    """Return DM and BMPM phonetic key lists for the given normalised alias_key."""
    dm_result: tuple[str, str] = _DM.encode(alias_key)
    dm_keys = [k for k in dm_result if k]

    bmpm_raw: str = _BMPM.encode(alias_key)
    bmpm_keys = [k for k in bmpm_raw.split() if k]

    return {"dmetaphone": dm_keys, "beider-morse": bmpm_keys}


def compute_trigrams(alias_key: str) -> list[str]:
    """Return char-level trigrams with `^` / `$` boundary markers.

    Aliases shorter than 3 chars produce no trigrams (plan §6: short aliases
    require exact match only).
    """
    if len(alias_key) < 3:
        return []
    padded = f"^{alias_key}$"
    trigrams = [padded[i : i + 3] for i in range(len(padded) - 2)]
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for t in trigrams:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ── DB write helpers (called from db.rebuild_phonetic_for / rebuild_trigrams_for) ─


def write_phonetic_index(
    conn: sqlite3.Connection, alias_key: str, keys: dict[str, list[str]]
) -> None:
    """Delete stale rows then insert fresh phonetic keys for alias_key."""
    _ = conn.execute(
        "DELETE FROM phonetic_index WHERE alias_key = ?", (alias_key,)
    )
    for algo, algo_keys in keys.items():
        for key in algo_keys:
            _ = conn.execute(
                "INSERT OR IGNORE INTO phonetic_index (alias_key, phonetic_key, algo) "
                "VALUES (?, ?, ?)",
                (alias_key, key, algo),
            )
    conn.commit()


def write_trigrams(conn: sqlite3.Connection, alias_key: str, trigrams: list[str]) -> None:
    """Delete stale rows then insert fresh trigrams for alias_key."""
    _ = conn.execute("DELETE FROM trigrams WHERE alias_key = ?", (alias_key,))
    for t in trigrams:
        _ = conn.execute(
            "INSERT OR IGNORE INTO trigrams (alias_key, trigram) VALUES (?, ?)",
            (alias_key, t),
        )
    conn.commit()
