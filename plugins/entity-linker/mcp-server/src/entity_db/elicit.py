"""Elicitation fallback helpers — used when the host lacks MCP Apps support."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


def should_use_elicitation(ctx: object) -> bool:
    """Return True if the host cannot render MCP Apps (force elicitation fallback).

    Checks:
    1. `ENTITY_LINKER_FORCE_ELICITATION=1` env var (testing / CI override).
    2. Host capability sniff via FastMCP ctx (no 'experimental.apps' capability).
    """
    if os.environ.get("ENTITY_LINKER_FORCE_ELICITATION") == "1":
        return True

    # Attempt host capability sniff; fall back to False if ctx doesn't support it
    try:
        from fastmcp import Context

        if isinstance(ctx, Context):
            params = getattr(ctx, "session", None)
            if params is not None:
                caps = getattr(getattr(params, "client_params", None), "capabilities", None)
                if caps is not None:
                    experimental = getattr(caps, "experimental", None)
                    if experimental is None or not getattr(experimental, "apps", None):
                        return True
    except Exception:
        pass

    return False


@dataclass
class DisambiguationChoice:
    """Schema for per-span disambiguation elicitation."""

    entity_id: str


@dataclass
class StagingApproval:
    """Schema for staging review elicitation."""

    decision: Literal["approve_new", "merge_existing", "reject"]
    merge_target: str = ""
    corrected_type: str = "other"
    corrected_name: str = ""


async def disambiguate_span(
    ctx: object,
    surface: str,
    candidates: list[dict[str, object]],
) -> str | None:
    """Elicit disambiguation for one ambiguous span.

    Returns the chosen entity_id, 'none', 'new', or None (if cancelled).
    """
    from fastmcp import Context

    if not isinstance(ctx, Context):
        return None

    @dataclass
    class _Choice:
        choice: str  # simplified for v0; real schema uses Literal

    result = await ctx.elicit(
        message=f'Which entity does "{surface}" refer to?',
        response_type=_Choice,
    )
    if result.action == "accept":
        return result.data.choice
    return None


async def review_staging_item(
    ctx: object,
    surface: str,
    proposed_type: str | None = None,
) -> dict[str, object] | None:
    """Elicit staging review for one candidate.

    Returns a dict with decision, merge_target, corrected_type, corrected_name.
    """
    from fastmcp import Context

    if not isinstance(ctx, Context):
        return None

    result = await ctx.elicit(
        message=f'How should "{surface}" be handled?',
        response_type=StagingApproval,
    )
    if result.action == "accept":
        data = result.data
        return {
            "decision": data.decision,
            "merge_target": data.merge_target,
            "corrected_type": data.corrected_type or proposed_type or "other",
            "corrected_name": data.corrected_name or surface,
        }
    return None
