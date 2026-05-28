"""Tests for normalize module — DoD from plan Task 4."""
from entity_db.matching.normalize import derive_alias_variants, normalize_text

# ── normalize_text DoD items ─────────────────────────────────────────────────


def test_normalize_czech_dative_ovi() -> None:
    assert normalize_text("Viktorovi") == "viktor"


def test_normalize_czech_possessive_ovy() -> None:
    assert normalize_text("Bezdekovy") == "bezdek"


def test_normalize_strips_diacritics() -> None:
    assert normalize_text("Tomáš") == "tomas"


def test_normalize_does_not_over_strip_short_stem() -> None:
    # "Eva" ends in "a" but stem "Ev" (2 chars) < 3 — must NOT strip
    assert normalize_text("Eva") == "eva"


# ── additional branch coverage ────────────────────────────────────────────────


def test_normalize_plain_ascii() -> None:
    assert normalize_text("hello") == "hello"


def test_normalize_strips_punctuation() -> None:
    # "Dr." → "dr", comma removed
    result = normalize_text("Dr.,")
    assert "." not in result
    assert "," not in result


def test_normalize_lowercases() -> None:
    assert normalize_text("VIKTOR") == "viktor"


def test_normalize_nfc_roundtrip() -> None:
    # é composed vs decomposed must produce same result
    assert normalize_text("café") == normalize_text("café")


def test_normalize_multiple_suffixes_stripped_iteratively() -> None:
    # "ovy" → strip "y" → "ovi" → strip "ovi" — same as Bezdekovy test
    # but use a name-like string to confirm the loop
    assert normalize_text("testovy") == "test"


def test_normalize_em_suffix() -> None:
    # "Viktorem" → strip "em" → "viktor"
    assert normalize_text("Viktorem") == "viktor"


def test_normalize_empty_string() -> None:
    assert normalize_text("") == ""


def test_normalize_whitespace_preserved() -> None:
    # Spaces are kept; suffix stripping operates on the whole string end
    result = normalize_text("Stefan Weber")
    assert " " in result


# ── derive_alias_variants DoD ─────────────────────────────────────────────────


def test_derive_variants_contains_first_name() -> None:
    variants = derive_alias_variants("Stefan Weber")
    assert "stefan" in variants


def test_derive_variants_contains_last_name() -> None:
    variants = derive_alias_variants("Stefan Weber")
    assert "weber" in variants


def test_derive_variants_contains_initials() -> None:
    variants = derive_alias_variants("Stefan Weber")
    assert "sw" in variants


def test_derive_variants_single_word() -> None:
    variants = derive_alias_variants("Groupon")
    assert "groupon" in variants


def test_derive_variants_strips_diacritics() -> None:
    # "Pavel Kolář" → must include diacritic-free forms
    variants = derive_alias_variants("Pavel Kolář")
    assert "pavel" in variants
    assert "kolar" in variants


def test_derive_variants_no_duplicates() -> None:
    variants = derive_alias_variants("Stefan Weber")
    assert len(variants) == len(set(variants))
