# entity-db MCP Apps

Two React+Vite+TypeScript single-page applications served as `ui://` resources by the FastMCP server.

## Apps

| App | Resource URI | Description |
|-----|-------------|-------------|
| `disambiguation/` | `ui://entity-db/disambiguation.html` | Per-span entity disambiguation |
| `staging/` | `ui://entity-db/staging.html` | Staged candidate review |

## Shared lib

`shared/src/mcp-app-bridge.ts` — postMessage bridge between the iframe and the MCP host.
Key exports: `postMcpReady()`, `postMcpAction()`, `onMcpMessage()`, `isMcpAppsHost()`.

## Build

```bash
cd disambiguation && npm install && npm run build
cd staging && npm install && npm run build
```

Each app builds to `dist/index.html` (single-file, inline assets).
