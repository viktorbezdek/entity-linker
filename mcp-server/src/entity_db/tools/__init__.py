"""MCP tool modules for entity-db."""
from __future__ import annotations

import sqlite3

_conn: sqlite3.Connection | None = None


def set_conn(conn: sqlite3.Connection) -> None:
    """Set the active DB connection (used by tests and server init)."""
    global _conn
    _conn = conn


def get_conn() -> sqlite3.Connection:
    """Return the active DB connection; raises if not initialised."""
    if _conn is None:
        raise RuntimeError("DB not initialised — call set_conn() first")
    return _conn
