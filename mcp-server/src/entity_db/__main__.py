"""Entry point for `uv run entity-db` and `python -m entity_db`."""
import asyncio

from entity_db.server import _init_db, mcp


def main() -> None:
    asyncio.run(_init_db())
    mcp.run()


if __name__ == "__main__":
    main()
