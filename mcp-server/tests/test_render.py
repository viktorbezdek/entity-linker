"""Tests for render module — markdown, XML, sidecar formats."""
from entity_db.matching.resolver import Resolution
from entity_db.render import to_markdown, to_sidecar, to_xml

_TEXT = "Hello Viktor world"
_RES = Resolution(
    surface="Viktor",
    span_start=6,
    span_end=12,
    entity_id="viktor-bezdek",
    entity_type="person",
    confidence=0.95,
    method="auto",
    source_hash="abc",
    source_type="markdown",
)


def test_to_markdown_golden() -> None:
    result = to_markdown(_TEXT, [_RES])
    assert result == "Hello [Viktor](@person:viktor-bezdek) world"


def test_to_markdown_user_confirmed_gets_question_mark() -> None:
    res = Resolution(
        surface="Viktor", span_start=6, span_end=12,
        entity_id="viktor-bezdek", entity_type="person",
        confidence=0.75, method="user-confirmed",
        source_hash="abc", source_type="markdown",
    )
    result = to_markdown(_TEXT, [res])
    assert result == "Hello [Viktor](@person:viktor-bezdek?) world"


def test_to_xml_golden() -> None:
    result = to_xml(_TEXT, [_RES])
    assert 'id="viktor-bezdek"' in result
    assert 'type="person"' in result
    assert "Viktor" in result
    assert result.startswith("Hello ")
    assert result.endswith(" world")


def test_to_markdown_multiple_spans() -> None:
    text = "Viktor and Tomas met"
    r1 = Resolution(
        surface="Viktor", span_start=0, span_end=6,
        entity_id="vb", entity_type="person", confidence=0.95,
        method="auto", source_hash="h", source_type="markdown",
    )
    r2 = Resolution(
        surface="Tomas", span_start=11, span_end=16,
        entity_id="tn", entity_type="person", confidence=0.92,
        method="auto", source_hash="h", source_type="markdown",
    )
    result = to_markdown(text, [r1, r2])
    assert "[Viktor](@person:vb)" in result
    assert "[Tomas](@person:tn)" in result


def test_to_sidecar_preserves_original_text() -> None:
    original, sidecar = to_sidecar(_TEXT, [_RES])
    assert original == _TEXT


def test_to_sidecar_has_correct_offsets() -> None:
    _, sidecar = to_sidecar(_TEXT, [_RES])
    assert "resolutions" in sidecar
    r = sidecar["resolutions"][0]
    assert r["start"] == 6
    assert r["end"] == 12
    assert r["entity_id"] == "viktor-bezdek"
    assert r["type"] == "person"
    assert r["confidence"] == 0.95


def test_to_sidecar_applying_offsets_matches_markdown() -> None:
    original, sidecar = to_sidecar(_TEXT, [_RES])
    # Applying sidecar offsets should reproduce the markdown output
    md = to_markdown(original, [_RES])
    assert "[Viktor](@person:viktor-bezdek)" in md


def test_to_markdown_empty_resolutions() -> None:
    result = to_markdown(_TEXT, [])
    assert result == _TEXT


def test_to_xml_empty_resolutions() -> None:
    result = to_xml(_TEXT, [])
    assert result == _TEXT
