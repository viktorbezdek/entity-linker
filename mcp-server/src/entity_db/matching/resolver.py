"""End-to-end entity resolution pipeline: text → resolutions + queues."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass

from entity_db.matching.candidates import CandidateSpan, generate_candidates
from entity_db.matching.score import ScoreContext, score_candidate


@dataclass
class Resolution:
    """A single resolved span."""

    surface: str
    span_start: int
    span_end: int
    entity_id: str
    entity_type: str
    confidence: float
    method: str  # 'auto' | 'user-confirmed' | 'user-rejected' | 'staged' | 'queued'
    source_hash: str
    source_type: str


@dataclass
class ResolveOptions:
    """Configuration for resolve_link_text."""

    interactive: bool = True
    type_fit_mode: str = "rules"
    context_window: int = 5
    on_ambiguity: str = "prompt"    # "prompt" | "queue" | "skip"
    on_new_candidate: str = "stage"  # "stage" | "skip"
    source_path: str | None = None


@dataclass
class ResolveResult:
    """Return value of resolve_link_text."""

    resolutions: list[Resolution]
    ambiguities: list[dict[str, object]]
    new_candidates: list[dict[str, object]]
    warnings: list[str]
    stats: dict[str, int]
    source_hash: str


# Auto-link thresholds
_AUTO_SCORE = 0.90
_AUTO_GAP = 0.10
_AMBIG_SCORE = 0.70

_CAPITAL_RE = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*\b")


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _context_tokens(
    text: str, span_start: int, span_end: int, window: int
) -> list[str]:
    before = text[:span_start].split()[-window:]
    after = text[span_end:].split()[:window]
    return before + after


def _find_new_surfaces(text: str, matched: set[str]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for m in _CAPITAL_RE.finditer(text):
        surf = m.group()
        if surf not in matched:
            counts[surf] += 1
    return [s for s, n in counts.items() if n >= 2]


async def _write_resolution_log(
    conn: sqlite3.Connection, r: Resolution, now: int
) -> None:
    from entity_db.db import _write_lock

    sql = (
        "INSERT INTO resolution_log"
        " (source_hash, source_type, span_start, span_end,"
        "  surface, entity_id, confidence, method, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    args = (
        r.source_hash, r.source_type, r.span_start, r.span_end,
        r.surface, r.entity_id, r.confidence, r.method, now,
    )
    async with _write_lock:
        await asyncio.to_thread(lambda: (conn.execute(sql, args), conn.commit()))


async def _write_pending(
    conn: sqlite3.Connection,
    source_hash: str,
    source_type: str,
    source_path: str | None,
    start: int,
    end: int,
    surface: str,
    candidates_json: str,
    context_json: str,
    now: int,
) -> str:
    from entity_db.db import _write_lock

    pending_id = str(uuid.uuid4())
    sql = (
        "INSERT INTO pending_disambiguation"
        " (id, source_hash, source_type, source_path, span_start, span_end,"
        "  surface, candidates_json, context_json, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)"
    )
    args = (
        pending_id, source_hash, source_type, source_path,
        start, end, surface, candidates_json, context_json, now,
    )
    async with _write_lock:
        await asyncio.to_thread(lambda: (conn.execute(sql, args), conn.commit()))
    return pending_id


async def _upsert_staging(
    conn: sqlite3.Connection, surface: str, evidence_json: str, now: int
) -> None:
    from entity_db.db import _write_lock
    from entity_db.matching.normalize import compute_dedup_key

    dedup_key = compute_dedup_key(surface, "other")
    sql = (
        "INSERT INTO staging"
        " (id, dedup_key, surface, evidence_json, frequency, status, created_at, updated_at)"
        " VALUES (lower(hex(randomblob(8))), ?, ?, ?, 1, 'pending', ?, ?)"
        " ON CONFLICT(dedup_key) DO UPDATE SET"
        " frequency = frequency + 1, updated_at = excluded.updated_at"
    )
    args_staging = (dedup_key, surface, evidence_json, now, now)
    async with _write_lock:
        await asyncio.to_thread(
            lambda: (conn.execute(sql, args_staging), conn.commit())
        )


async def resolve_link_text(
    text: str,
    source_type: str,
    options: ResolveOptions,
    db: sqlite3.Connection,
) -> ResolveResult:
    """Run the full entity resolution pipeline on a text."""
    from entity_db.matching.coref import propagate

    src_hash = _source_hash(text)
    now = int(time.time())
    all_cands = await generate_candidates(text, db)

    span_map: dict[tuple[int, int], list[CandidateSpan]] = defaultdict(list)
    for c in all_cands:
        span_map[(c.span_start, c.span_end)].append(c)

    resolutions: list[Resolution] = []
    ambiguities: list[dict[str, object]] = []
    linked_entities: set[str] = set()
    matched_surfaces: set[str] = set()

    for (start, end) in sorted(span_map.keys()):
        cands = span_map[(start, end)]
        surface = text[start:end]
        ctx_tokens = _context_tokens(text, start, end, options.context_window)

        scored: list[tuple[float, CandidateSpan]] = []
        for c in cands:
            other_ids = [x.entity_id for x in cands if x is not c]
            ctx = ScoreContext(
                context_tokens=ctx_tokens,
                linked_entities=linked_entities,
                window_candidates=other_ids,
            )
            s = score_candidate(surface, c.alias_key, c.entity_id, c.entity_type, ctx)
            scored.append((s, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            continue

        top_score, top_cand = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0

        if top_score >= _AUTO_SCORE and (top_score - second_score) >= _AUTO_GAP:
            r = Resolution(
                surface=surface, span_start=start, span_end=end,
                entity_id=top_cand.entity_id, entity_type=top_cand.entity_type,
                confidence=top_score, method="auto",
                source_hash=src_hash, source_type=source_type,
            )
            resolutions.append(r)
            linked_entities.add(top_cand.entity_id)
            matched_surfaces.add(surface)
            await _write_resolution_log(db, r, now)

        elif top_score >= _AMBIG_SCORE:
            matched_surfaces.add(surface)
            cands_data = [{"entity_id": c.entity_id, "confidence": s} for s, c in scored[:5]]
            ctx_data = {"tokens": ctx_tokens}
            ambig: dict[str, object] = {
                "surface": surface, "span_start": start, "span_end": end,
                "candidates": cands_data, "source_hash": src_hash,
            }
            _on = "queue" if not options.interactive else options.on_ambiguity
            if _on in ("queue", "skip") or not options.interactive:
                pid = await _write_pending(
                    db, src_hash, source_type, options.source_path,
                    start, end, surface,
                    json.dumps(cands_data), json.dumps(ctx_data), now,
                )
                ambig["pending_id"] = pid
            ambiguities.append(ambig)

    resolutions, coref_warnings = propagate(resolutions)

    new_candidates: list[dict[str, object]] = []
    if options.on_new_candidate == "stage":
        for surf in _find_new_surfaces(text, matched_surfaces):
            ev = json.dumps({"surface": surf, "source_hash": src_hash})
            await _upsert_staging(db, surf, ev, now)
            new_candidates.append({"surface": surf})
            # Write unlinked (entity_id=NULL) resolution_log rows for each
            # occurrence so staging_approve can backfill them on approval.
            _sql_staged = (
                "INSERT INTO resolution_log"
                " (source_hash, source_type, span_start, span_end,"
                "  surface, entity_id, confidence, method, created_at)"
                " VALUES (?, ?, ?, ?, ?, NULL, 0.0, 'staged', ?)"
            )
            from entity_db.db import _write_lock
            for m in re.finditer(re.escape(surf), text):
                _args_staged = (src_hash, source_type, m.start(), m.end(), surf, now)
                async with _write_lock:
                    await asyncio.to_thread(
                        lambda a=_args_staged: (db.execute(_sql_staged, a), db.commit())
                    )

    return ResolveResult(
        resolutions=resolutions,
        ambiguities=ambiguities,
        new_candidates=new_candidates,
        warnings=coref_warnings,
        stats={
            "auto_linked": len(resolutions),
            "ambiguous": len(ambiguities),
            "new_candidates": len(new_candidates),
        },
        source_hash=src_hash,
    )
