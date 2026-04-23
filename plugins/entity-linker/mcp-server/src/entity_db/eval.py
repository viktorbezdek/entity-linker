"""M0 micro-eval harness — scores the matching pipeline against labeled spans."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from entity_db.matching.resolver import ResolveOptions, resolve_link_text


@dataclass
class EvalReport:
    """Summary of a micro-eval run."""

    total: int = 0
    tp: int = 0  # auto-linked to correct entity
    fp: int = 0  # auto-linked to wrong entity
    fn: int = 0  # expected auto-link but unresolved or queued
    precision: float = 0.0
    recall: float = 0.0
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _load_spans(path: str | Path) -> list[dict[str, object]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("spans", [])


def _overlaps(r_start: int, r_end: int, e_start: int, e_end: int) -> bool:
    return r_start < e_end and r_end > e_start


async def run_eval(conn: sqlite3.Connection, spans_path: str | Path) -> EvalReport:
    """Evaluate the matching pipeline against the labeled span set."""
    spans = await asyncio.to_thread(_load_spans, spans_path)
    opts = ResolveOptions(interactive=False)
    report = EvalReport()
    report.total = len(spans)

    for span_def in spans:
        text: str = str(span_def["text"])
        e_start: int = int(span_def["span"][0])  # type: ignore[index]
        e_end: int = int(span_def["span"][1])  # type: ignore[index]
        expected_entity: str | None = span_def.get("expected_entity")  # type: ignore[assignment]
        expected_method: str = str(span_def.get("expected_method", "auto"))
        source_type: str = str(span_def.get("source_type", "markdown"))
        category: str = str(span_def.get("category", "other"))

        result = await resolve_link_text(text, source_type, opts, conn)

        # Find resolutions overlapping this span
        matching = [
            r for r in result.resolutions
            if _overlaps(r.span_start, r.span_end, e_start, e_end)
        ]

        cat = report.by_category.setdefault(category, {"tp": 0, "fp": 0, "fn": 0})

        if expected_entity is None:
            # Should NOT link — any resolution is a FP
            if matching:
                report.fp += 1
                cat["fp"] += 1
        elif expected_method == "auto":
            auto_match = [m for m in matching if m.method == "auto"]
            if auto_match and auto_match[0].entity_id == expected_entity:
                report.tp += 1
                cat["tp"] += 1
            elif auto_match:
                report.fp += 1  # linked to wrong entity
                cat["fp"] += 1
            else:
                report.fn += 1  # expected auto-link, didn't get one
                cat["fn"] += 1
        # "ambiguous" / "unresolved" expected — we don't count these toward precision/recall

    # Compute precision/recall
    auto_total = report.tp + report.fp
    expected_total = report.tp + report.fn
    report.precision = report.tp / auto_total if auto_total > 0 else 1.0
    report.recall = report.tp / expected_total if expected_total > 0 else 1.0

    return report


async def main(spans_path: str, output_dir: str = "eval/results") -> None:
    """CLI entry point: `python -m entity_db.eval <spans.yml>`"""
    import os

    from entity_db.db import open_db
    from entity_db.seed import import_seed

    db_path = os.environ.get("ENTITY_DB_PATH", str(Path.home() / "entity-db" / "entities.sqlite"))
    seed_path = Path(spans_path).parents[1] / "docs" / "examples" / "entities.seed.yml"

    conn = await open_db(db_path)
    if seed_path.exists():
        await import_seed(conn, seed_path)

    report = await run_eval(conn, spans_path)
    await asyncio.to_thread(conn.close)

    print("\n=== M0 Micro-Eval Results ===")
    print(f"Total spans: {report.total}")
    print(f"TP: {report.tp}  FP: {report.fp}  FN: {report.fn}")
    print(f"Precision @ 0.90: {report.precision:.3f}")
    print(f"Recall:           {report.recall:.3f}")

    if report.precision < 0.95:
        print("\n⚠ Precision < 0.95 — consider tuning weights in matching/score.py")

    # Write JSON report
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d")
    out_path = Path(output_dir) / f"{ts}-m0.json"
    report_dict = {
        "total": report.total,
        "tp": report.tp, "fp": report.fp, "fn": report.fn,
        "precision": report.precision,
        "recall": report.recall,
        "by_category": report.by_category,
        "warnings": report.warnings,
    }
    out_path.write_text(json.dumps(report_dict, indent=2))
    print(f"\nReport written to {out_path}")
