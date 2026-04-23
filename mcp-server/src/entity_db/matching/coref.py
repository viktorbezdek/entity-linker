"""Within-source coreference: surface-equality propagation (v0 — no pronoun resolution)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity_db.matching.resolver import Resolution


def propagate(
    resolutions: list[Resolution],
) -> tuple[list[Resolution], list[str]]:
    """Propagate surface-equality within a source: same surface → same entity.

    The entity with the highest confidence for a surface wins. If two spans
    share a surface but resolve to different entities, an ``entity_drift``
    warning is emitted and the higher-confidence entity propagates.

    Returns:
        (updated_resolutions, warnings)
    """
    if not resolutions:
        return [], []

    warnings: list[str] = []

    # Find the winning entity for each surface (highest confidence)
    surface_best: dict[str, Resolution] = {}
    for r in resolutions:
        existing = surface_best.get(r.surface)
        if existing is None:
            surface_best[r.surface] = r
        elif existing.entity_id != r.entity_id:
            winner = r if r.confidence > existing.confidence else existing
            loser = existing if r.confidence > existing.confidence else r
            warnings.append(
                f"entity_drift: surface '{r.surface}' resolved to both"
                f" '{winner.entity_id}' (conf={winner.confidence:.2f}) and"
                f" '{loser.entity_id}' (conf={loser.confidence:.2f});"
                f" keeping higher-confidence entity"
            )
            surface_best[r.surface] = winner
        # same entity — keep existing (order-stable)

    # Rebuild resolutions, replacing entity with the surface winner
    updated: list[Resolution] = []
    for r in resolutions:
        best = surface_best[r.surface]
        if r.entity_id == best.entity_id:
            updated.append(r)
        else:
            from entity_db.matching.resolver import Resolution as Res

            updated.append(
                Res(
                    surface=r.surface,
                    span_start=r.span_start,
                    span_end=r.span_end,
                    entity_id=best.entity_id,
                    entity_type=best.entity_type,
                    confidence=r.confidence,
                    method=r.method,
                    source_hash=r.source_hash,
                    source_type=r.source_type,
                )
            )

    return updated, warnings
