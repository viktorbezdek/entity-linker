---
paths:
  - "plugins/entity-linker/mcp-server/**/*.py"
  - "plugins/entity-linker/mcp-server/**/*.ts"
  - "plugins/entity-linker/mcp-server/**/*.tsx"
---

# entity-linker Conventions

## Python (mcp-server/src/entity_db/)

**SQLite access pattern** — every mutation must go through the async write-lock:

```python
from entity_db.db import _write_lock

async with _write_lock:
    await asyncio.to_thread(
        lambda: (conn.execute(sql, args), conn.commit())
    )
```

Read-only queries don't need the lock but should still use `asyncio.to_thread` so the async event loop doesn't block on SQLite I/O.

**Tool DB connection** — tools import `get_conn()` from `entity_db.tools`. The connection is set once at server startup:

```python
from entity_db.tools import get_conn

async def my_tool(...) -> dict[str, object]:
    conn = get_conn()
    ...
```

Never open new connections inside tools — reuse the module-level one.

**String-concat SQL** — use `(...)` parentheses with adjacent strings only at module level; inside functions, use explicit `+` or (better) factor out a module-level `_SQL_*` constant. Ruff's `ISC*` rules flag implicit concat inside function bodies.

**Long SQL lines** — split INSERT/SELECT statements across multiple string pieces in a module-level constant. Max line length is 100 chars.

**Czech suffix list** — when editing `matching/normalize.py`, preserve iterative longest-first stripping AND the `stem ≥ 3 chars` guard. Removing either breaks `Bezdekovy → bezdek` (multi-pass) and `Eva → eva` (guard).

## TypeScript (mcp-server/apps/)

**MCP Apps bridge order** — inside `useEffect`, register `onMcpMessage` listener **BEFORE** calling `postMcpReady()`. Otherwise the host may replay the initial payload before the listener is attached:

```tsx
useEffect(() => {
  const unsub = onMcpMessage<T>((data) => setItems(data));
  postMcpReady();  // AFTER the listener
  return unsub;
}, []);
```

**postMcpAction arg names must match the MCP tool signature.** Posting `{ entity_id: x }` to a tool that expects `entity_id_or_sentinel` silently fails under named-arg MCP calls. Always match the Python tool's Pydantic/parameter names.

**Vitest mocks** — use `vi.mock(..., () => ({ ... }))` with `vi.fn()` inline. Don't reference top-level `const mockFoo = vi.fn()` from inside the factory — vi.mock hoists and will error "Cannot access 'mockFoo' before initialization".

## Testing

- Full suite: `uv run --directory mcp-server pytest -q`
- Coverage gate: `--cov=entity_db --cov-fail-under=80`
- Per-test-file coverage may be < 80% on `db.py` when run in isolation (other test files hit the rebuild paths) — the aggregate is what matters.
- Always run `ruff check . --fix` before committing (catches `F841` unused vars, `F401` unused imports, `E501` long lines).

## Plugin Structure

- Subagent frontmatter (`agents/*.md`) MUST NOT include `hooks`, `mcpServers`, or `permissionMode` — plugin-loaded subagents can't declare them.
- Command argument-hints with square brackets must be quoted in YAML: `argument-hint: "[--format markdown|xml]"` (unquoted, YAML parses as a flow sequence).
- SKILL.md `description` field is where trigger phrases live — the host uses it to decide when to load the skill.
