"""Shared test fixtures for entity-db MCP server tests."""
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a temporary path for a test SQLite database."""
    return tmp_path / "test.sqlite"


@pytest.fixture
def anyio_backend():
    return "asyncio"
