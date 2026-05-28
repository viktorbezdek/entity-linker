"""Tests for score module — formula, penalty logic, DoD from plan Task 6."""
from entity_db.matching.score import ScoreContext, score_candidate


def _person_context(local_recency: bool = False) -> ScoreContext:
    return ScoreContext(
        context_tokens=["synced", "with", "Stefan", "yesterday"],
        linked_entities={"stefan-weber"} if local_recency else set(),
        window_candidates=[],
    )


def _neutral_context() -> ScoreContext:
    return ScoreContext(
        context_tokens=["the", "thing", "happened"],
        linked_entities=set(),
        window_candidates=[],
    )


# ── DoD items ─────────────────────────────────────────────────────────────────


def test_score_person_entity_with_cues_and_recency_meets_threshold() -> None:
    # Person cues + already linked (recency=1) → 0.45+0.20+0.20+0.10 = 0.95 ≥ 0.90
    ctx = _person_context(local_recency=True)
    s = score_candidate(
        window="Stefan",
        alias_key="stefan",
        entity_id="stefan-weber",
        entity_type="person",
        ctx=ctx,
    )
    assert s >= 0.90, f"Expected ≥ 0.90, got {s:.3f}"


def test_score_project_entity_with_person_cues_below_threshold() -> None:
    # Person cues in context, entity is project → type_fit=0.0
    # 0.45+0.20+0 = 0.65 ≤ 0.65
    ctx = _person_context(local_recency=False)
    s = score_candidate(
        window="Stefan",
        alias_key="viktor",
        entity_id="viktor-project",
        entity_type="project",
        ctx=ctx,
    )
    assert s <= 0.65, f"Expected ≤ 0.65, got {s:.3f}"


def test_ambig_pen_fires_for_three_or_more_high_candidates() -> None:
    ctx = ScoreContext(
        context_tokens=["the", "thing", "happened"],
        linked_entities=set(),
        # Simulate 3 other candidates already scored above 0.70
        window_candidates=["entity-a", "entity-b", "entity-c"],
    )
    s_no_ambig = score_candidate("x", "x", "e1", "other", _neutral_context())
    s_with_ambig = score_candidate("x", "x", "e1", "other", ctx)
    assert s_with_ambig < s_no_ambig, "ambig_pen should reduce score"
    assert s_with_ambig <= s_no_ambig - 0.05 + 1e-9


# ── Additional formula coverage ───────────────────────────────────────────────


def test_score_clipped_to_zero_minimum() -> None:
    ctx = ScoreContext(
        context_tokens=[],
        linked_entities=set(),
        window_candidates=["a", "b", "c"],  # ambig_pen
    )
    s = score_candidate("a", "a", "e1", "other", ctx)
    assert 0.0 <= s <= 1.0


def test_score_short_alias_incurs_penalty() -> None:
    ctx = _neutral_context()
    # "ab" is a 2-char alias_key — short_pen = 0.05
    s_short = score_candidate("ab", "ab", "e1", "other", ctx)
    s_long = score_candidate("abcdef", "abcdef", "e1", "other", ctx)
    assert s_short < s_long


def test_score_exact_match_higher_than_fuzzy() -> None:
    ctx = _neutral_context()
    s_exact = score_candidate("viktor", "viktor", "vb", "person", ctx)
    s_fuzzy = score_candidate("victoor", "viktor", "vb", "person", ctx)
    assert s_exact > s_fuzzy


def test_score_returns_float_in_unit_interval() -> None:
    for window, alias in [("x", "y"), ("ab", "ab"), ("hello", "world")]:
        s = score_candidate(window, alias, "e1", "other", _neutral_context())
        assert 0.0 <= s <= 1.0, f"score={s} out of [0,1] for ({window}, {alias})"
