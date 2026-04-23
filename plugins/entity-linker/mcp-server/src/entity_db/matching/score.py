"""Candidate scoring — formula from PRD §14."""
from dataclasses import dataclass, field

from rapidfuzz.fuzz import WRatio

from entity_db.matching.normalize import normalize_text
from entity_db.matching.type_fit import score_type_fit

# Score formula coefficients
_W_LEX = 0.45
_W_PHON = 0.20
_W_TYPE = 0.20
_W_RECENCY = 0.10
_PEN_SHORT = 0.05
_PEN_AMBIG = 0.05


@dataclass
class ScoreContext:
    """Scoring context passed alongside a candidate."""

    context_tokens: list[str]
    linked_entities: set[str] = field(default_factory=set)
    # entity_ids of other candidates for the SAME window already scored above 0.70
    window_candidates: list[str] = field(default_factory=list)


def _phon_score(norm_window: str, alias_key: str) -> float:
    """Compute phonetic component: 1.0 if shared key, else Jaccard, else 0."""
    from entity_db.matching.index import compute_phonetic_keys

    win_keys = compute_phonetic_keys(norm_window)
    ali_keys = compute_phonetic_keys(alias_key)

    win_set = set(win_keys["dmetaphone"]) | set(win_keys["beider-morse"])
    ali_set = set(ali_keys["dmetaphone"]) | set(ali_keys["beider-morse"])

    if not win_set or not ali_set:
        return 0.0

    shared = win_set & ali_set
    if shared:
        return 1.0

    union = win_set | ali_set
    return len(shared) / len(union)  # Jaccard (0 when no overlap)


def score_candidate(
    window: str,
    alias_key: str,
    entity_id: str,
    entity_type: str,
    ctx: ScoreContext,
) -> float:
    """Return a confidence score in [0, 1] for this candidate.

    Formula: 0.45·lex + 0.20·phon + 0.20·type_fit + 0.10·recency
             − 0.05·short_pen − 0.05·ambig_pen
    """
    norm_window = normalize_text(window)

    # Lexical component
    lex = WRatio(norm_window, alias_key) / 100.0

    # Phonetic component
    phon = _phon_score(norm_window, alias_key)

    # Type-fit
    type_fit = score_type_fit(ctx.context_tokens, entity_type)

    # Local recency (boolean: entity already auto-linked in this source)
    recency = 1.0 if entity_id in ctx.linked_entities else 0.0

    # Penalties
    short_pen = _PEN_SHORT if len(alias_key) < 3 else 0.0
    ambig_pen = _PEN_AMBIG if len(ctx.window_candidates) >= 2 else 0.0

    total = (
        _W_LEX * lex
        + _W_PHON * phon
        + _W_TYPE * type_fit
        + _W_RECENCY * recency
        - short_pen
        - ambig_pen
    )
    return max(0.0, min(1.0, total))
