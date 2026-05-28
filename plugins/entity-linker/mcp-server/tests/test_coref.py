"""Tests for coref module — within-source surface-equality propagation."""
from entity_db.matching.coref import propagate
from entity_db.matching.resolver import Resolution


def _res(surface: str, entity_id: str, confidence: float, span_start: int = 0) -> Resolution:
    return Resolution(
        surface=surface,
        span_start=span_start,
        span_end=span_start + len(surface),
        entity_id=entity_id,
        entity_type="person",
        confidence=confidence,
        method="auto",
        source_hash="abc",
        source_type="markdown",
    )


def test_propagate_same_surface_inherits_entity() -> None:
    # Two "Stefan" spans: first auto-linked, second ambiguous → second inherits
    r1 = _res("Stefan", "stefan-weber", 0.95, span_start=0)
    r2 = _res("Stefan", "stefan-weber", 0.75, span_start=20)
    out, warnings = propagate([r1, r2])
    assert all(r.entity_id == "stefan-weber" for r in out)
    assert len(warnings) == 0


def test_propagate_conflict_emits_drift_warning() -> None:
    # Same surface, different entity IDs → entity_drift warning
    r1 = _res("Stefan", "stefan-weber", 0.92, span_start=0)
    r2 = _res("Stefan", "viktor-novak", 0.80, span_start=20)
    out, warnings = propagate([r1, r2])
    assert any("entity_drift" in w for w in warnings)
    # Higher confidence wins
    assert all(r.entity_id == "stefan-weber" for r in out)


def test_propagate_different_surfaces_unchanged() -> None:
    r1 = _res("Stefan", "stefan-weber", 0.90, span_start=0)
    r2 = _res("Pavel", "pavel-kolar", 0.88, span_start=20)
    out, warnings = propagate([r1, r2])
    assert out[0].entity_id == "stefan-weber"
    assert out[1].entity_id == "pavel-kolar"
    assert len(warnings) == 0


def test_propagate_empty_list() -> None:
    out, warnings = propagate([])
    assert out == []
    assert warnings == []


def test_propagate_single_span_unchanged() -> None:
    r = _res("Stefan", "stefan-weber", 0.91)
    out, warnings = propagate([r])
    assert out[0].entity_id == "stefan-weber"
    assert len(warnings) == 0
