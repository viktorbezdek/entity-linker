"""Tests for eval harness — loads spans YAML, runs scoring, reports precision/recall."""
import asyncio
from pathlib import Path

import pytest

from entity_db.db import open_db
from entity_db.eval import EvalReport, run_eval
from entity_db.seed import import_seed

SEED = Path(__file__).parents[2] / "docs" / "examples" / "entities.seed.yml"
SPANS = Path(__file__).parents[2] / "eval" / "m0-spans.yml"


@pytest.mark.asyncio
async def test_eval_loads_and_runs(tmp_db_path: Path) -> None:
    """Eval harness runs on the full spans YAML and produces a report."""
    conn = await open_db(tmp_db_path)
    await import_seed(conn, SEED)
    report = await run_eval(conn, SPANS)
    assert isinstance(report, EvalReport)
    assert report.total >= 10  # at least 10 spans evaluated
    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_eval_precision_meets_gate(tmp_db_path: Path) -> None:
    """Auto-link precision must be ≥ 0.80 on the synthesized set at threshold 0.90."""
    conn = await open_db(tmp_db_path)
    await import_seed(conn, SEED)
    report = await run_eval(conn, SPANS)
    # Gate: precision ≥ 0.80 (may flag tuning recommendations if < 0.95)
    assert report.precision >= 0.80, (
        f"Precision {report.precision:.2f} below gate. "
        f"Tuning needed for weights in matching/score.py."
    )
    await asyncio.to_thread(conn.close)


@pytest.mark.asyncio
async def test_eval_report_has_required_fields(tmp_db_path: Path) -> None:
    conn = await open_db(tmp_db_path)
    await import_seed(conn, SEED)
    report = await run_eval(conn, SPANS)
    assert hasattr(report, "total")
    assert hasattr(report, "precision")
    assert hasattr(report, "recall")
    assert hasattr(report, "by_category")
    assert isinstance(report.by_category, dict)
    await asyncio.to_thread(conn.close)
