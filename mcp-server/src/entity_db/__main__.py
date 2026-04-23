"""Entry point for `uv run entity-db` and `python -m entity_db`."""
from entity_db.server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
