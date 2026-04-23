"""Output renderers: markdown, XML, and sidecar JSON for entity-annotated text."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity_db.matching.resolver import Resolution


def _sort_spans(resolutions: list[Resolution]) -> list[Resolution]:
    """Sort resolutions by span_start descending (right-to-left replacement)."""
    return sorted(resolutions, key=lambda r: r.span_start, reverse=True)


def to_markdown(text: str, resolutions: list[Resolution]) -> str:
    """Return annotated markdown: `[surface](@type:entity-id)`.

    User-confirmed spans (suggest-tier) get a `?` suffix per PRD §16.
    """
    result = text
    for r in _sort_spans(resolutions):
        suffix = "?" if r.method == "user-confirmed" else ""
        tag = f"[{r.surface}](@{r.entity_type}:{r.entity_id}{suffix})"
        result = result[: r.span_start] + tag + result[r.span_end :]
    return result


def to_xml(text: str, resolutions: list[Resolution]) -> str:
    """Return annotated XML per PRD §16."""
    result = text
    for r in _sort_spans(resolutions):
        tag = (
            f'<entity id="{r.entity_id}" type="{r.entity_type}"'
            f' confidence="{r.confidence:.2f}">{r.surface}</entity>'
        )
        result = result[: r.span_start] + tag + result[r.span_end :]
    return result


def to_sidecar(
    text: str, resolutions: list[Resolution]
) -> tuple[str, dict[str, object]]:
    """Return (original_text_unchanged, sidecar_json_dict).

    Sidecar carries byte-offset spans; applying them to the unchanged text
    reproduces the same annotations as to_markdown().
    """
    sidecar: dict[str, object] = {
        "resolutions": [
            {
                "start": r.span_start,
                "end": r.span_end,
                "surface": r.surface,
                "entity_id": r.entity_id,
                "type": r.entity_type,
                "confidence": r.confidence,
                "method": r.method,
            }
            for r in sorted(resolutions, key=lambda r: r.span_start)
        ]
    }
    return text, sidecar
