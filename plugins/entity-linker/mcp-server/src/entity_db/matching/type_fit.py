"""Type-fit scoring: 7 cue families that map context tokens to entity types."""
import re

# ── 7 cue family dictionaries ─────────────────────────────────────────────────
# Each value is a set of lowercase trigger tokens/patterns that, when found
# within ±3 tokens of a candidate span, raise the type_fit score to 1.0.

PERSON_CUES: frozenset[str] = frozenset(
    [
        "with", "met", "called", "said", "from", "told", "asked", "joined",
        "contacted", "introduced", "he", "she", "they", "his", "her",
        "mr", "mrs", "ms", "dr", "ing",
    ]
)

PROJECT_CUES: frozenset[str] = frozenset(
    ["project", "rollout", "launch", "initiative", "program", "effort", "plan"]
)

PRODUCT_CUES: frozenset[str] = frozenset(
    ["feature", "ship", "release", "product", "version", "ui", "interface", "app"]
)

TEAM_CUES: frozenset[str] = frozenset(
    ["team", "squad", "tribe", "chapter", "guild", "group", "org"]
)

COMPANY_CUES: frozenset[str] = frozenset(
    ["at", "company", "corp", "inc", "ltd", "llc", "ag", "acquired", "startup"]
)

# Acronym cue: all-caps token ≤ 5 chars (checked via regex, not a static set)
_ACRONYM_PATTERN = re.compile(r"^[A-Z]{2,5}$")

CONCEPT_CUES: frozenset[str] = frozenset(
    [
        "what", "concept", "methodology", "framework", "approach",
        "practice", "principle", "pattern", "process",
    ]
)

# Map entity type → its cue set (acronym handled separately)
_TYPE_TO_CUES: dict[str, frozenset[str]] = {
    "person": PERSON_CUES,
    "project": PROJECT_CUES,
    "product": PRODUCT_CUES,
    "team": TEAM_CUES,
    "company": COMPANY_CUES,
    "concept": CONCEPT_CUES,
    "other": frozenset(),
}


def _has_acronym_cue(tokens: list[str]) -> bool:
    """Return True if any token looks like an acronym (all-caps, 2–5 chars)."""
    return any(_ACRONYM_PATTERN.match(t) for t in tokens)


def score_type_fit(context_tokens: list[str], entity_type: str) -> float:
    """Score how well the entity type fits the surrounding context.

    Returns:
        1.0 — cues for this entity type are present
        0.5 — no type-specific cues (neutral)
        0.0 — cues for a *different* entity type are present (conflicting)
    """
    lower_tokens = [t.lower() for t in context_tokens]
    token_set = set(lower_tokens)

    target_cues = _TYPE_TO_CUES.get(entity_type, frozenset())

    # Check acronym type separately
    if entity_type == "acronym":
        if _has_acronym_cue(context_tokens):
            return 1.0
        # Fall through to conflict check

    # Check if target cues present
    if target_cues and (target_cues & token_set):
        return 1.0

    # Check for conflicting cues (another type's cues are present)
    for other_type, other_cues in _TYPE_TO_CUES.items():
        if other_type == entity_type:
            continue
        if other_cues and (other_cues & token_set):
            return 0.0

    # No company legal suffix check for company type
    if entity_type == "company":
        legal = re.compile(r"\b(inc|llc|ag|s\.r\.o\.)\b", re.IGNORECASE)
        if any(legal.search(t) for t in context_tokens):
            return 1.0

    return 0.5  # neutral — no cues either way
