"""Tests for type_fit module — 7 entity type cue families."""
from entity_db.matching.type_fit import score_type_fit


def test_person_cue_returns_high_score() -> None:
    # "with" is a PERSON cue; entity type is person
    tokens = ["synced", "with", "Viktor", "yesterday"]
    assert score_type_fit(tokens, "person") == 1.0


def test_project_cue_returns_high_score() -> None:
    tokens = ["the", "FoundryAI", "project", "rollout"]
    assert score_type_fit(tokens, "project") == 1.0


def test_team_cue_returns_high_score() -> None:
    tokens = ["the", "B2C", "team", "agreed"]
    assert score_type_fit(tokens, "team") == 1.0


def test_company_cue_returns_high_score() -> None:
    tokens = ["working", "at", "Groupon", "now"]
    assert score_type_fit(tokens, "company") == 1.0


def test_product_cue_returns_high_score() -> None:
    tokens = ["ship", "the", "Dashboard", "feature"]
    assert score_type_fit(tokens, "product") == 1.0


def test_conflicting_cue_returns_low_score() -> None:
    # Person cues in context, but entity type is project → conflict → 0.0
    tokens = ["synced", "with", "FoundryAI", "yesterday"]
    assert score_type_fit(tokens, "project") == 0.0


def test_no_cues_returns_neutral() -> None:
    # Generic context with no type-specific cues → neutral
    tokens = ["the", "thing", "happened"]
    result = score_type_fit(tokens, "person")
    assert result == 0.5


def test_person_cue_within_short_context_returns_high() -> None:
    # score_type_fit receives pre-sliced ±3 tokens; "met" is a person cue
    tokens_within = ["he", "met", "Viktor", "yesterday"]
    assert score_type_fit(tokens_within, "person") == 1.0


def test_acronym_type_all_caps_returns_high() -> None:
    tokens = ["use", "the", "CRM", "integration"]
    # CRM is all-caps 3 chars ≤ 5 — acronym cue
    assert score_type_fit(tokens, "acronym") == 1.0


def test_concept_cue_returns_high_score() -> None:
    tokens = ["what", "is", "Agile", "methodology"]
    assert score_type_fit(tokens, "concept") == 1.0
