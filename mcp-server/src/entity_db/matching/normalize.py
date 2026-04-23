"""Text normalization: NFC → lowercase → diacritics → punctuation → Czech suffixes."""
import re
import unicodedata

# Czech/Slovak/Polish declension suffixes, sorted longest-first for greedy stripping.
# Leading "-" is a notation convention; actual suffix strings are below.
_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        # Czech/Slovak/Polish possessive and case suffixes from PRD §14 + "ovy"
        # (possessive genitive feminine — "Bezdekovy" → "Bezdek").
        ["ovi", "ovy", "ech", "ami", "ova", "ovo", "em", "ou", "ům", "ův", "a", "e", "y", "u"],
        key=len,
        reverse=True,
    )
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(s: str) -> str:
    """Return the canonical alias key for a string.

    Pipeline: NFC → lowercase → diacritics strip → punctuation strip →
    iterative Czech/Slovak/Polish suffix stripping (stem must remain ≥ 3 chars).
    """
    if not s:
        return s

    # 1. NFC
    s = unicodedata.normalize("NFC", s)

    # 2. Lowercase
    s = s.lower()

    # 3. Strip diacritics via NFD decomposition + filter combining marks
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")

    # 4. Strip punctuation (keep word chars and whitespace)
    s = _PUNCT_RE.sub("", s)
    s = s.strip()

    # 5. Iterative Czech suffix stripping (longest-first, restart after each strip)
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            if s.endswith(suffix) and len(s) - len(suffix) >= 3:
                s = s[: len(s) - len(suffix)]
                changed = True
                break  # restart with the (now shorter) string

    return s


def derive_alias_variants(canonical: str) -> list[str]:
    """Return a deduplicated list of alias key variants for a canonical entity name.

    Generates: normalized parts (per word), initials, and the full normalized form.
    """
    parts = canonical.split()
    normalized_parts = [normalize_text(p) for p in parts if p]

    variants: list[str] = []

    # Individual word forms (last-name-only, first-name-only, …)
    variants.extend(normalized_parts)

    # Initials (e.g. "Viktor Bezdek" → "vb")
    initials = "".join(p[0] for p in normalized_parts if p)
    if len(initials) > 1:
        variants.append(initials)

    # Full joined normalized form
    full = " ".join(normalized_parts)
    if full and full not in variants:
        variants.append(full)

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            result.append(v)

    return result
