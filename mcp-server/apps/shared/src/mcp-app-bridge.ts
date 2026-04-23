/**
 * MCP App bridge — shared postMessage helpers for entity-db Apps.
 *
 * Protocol:
 *  1. On mount, App calls postMcpReady() → host replays initial payload.
 *  2. App receives data via onMcpMessage().
 *  3. App posts tool calls via postMcpAction().
 */

export interface McpMessage<T = unknown> {
  type: string;
  data?: T;
  version?: string;
}

export type McpMessageCallback<T = unknown> = (data: T) => void;

let _listeners: Array<(ev: MessageEvent) => void> = [];

/** Register a callback for messages from the MCP host. */
export function onMcpMessage<T = unknown>(callback: McpMessageCallback<T>): () => void {
  const handler = (ev: MessageEvent) => {
    if (ev.data && typeof ev.data === "object") {
      callback(ev.data as T);
    }
  };
  window.addEventListener("message", handler);
  _listeners.push(handler);
  return () => {
    window.removeEventListener("message", handler);
    _listeners = _listeners.filter((l) => l !== handler);
  };
}

/** Post a tool-result action back to the MCP host. */
export function postMcpAction(tool: string, args: Record<string, unknown>): void {
  window.parent.postMessage({ type: "mcp:tool-result", tool, args }, "*");
}

/**
 * Signal the MCP host that the App is ready to receive its initial payload.
 * The host holds the payload until it sees this message, preventing race conditions.
 */
export function postMcpReady(): void {
  window.parent.postMessage({ type: "mcp:ready" }, "*");
}

/** Detect whether the App is running inside a real MCP host (vs. standalone dev). */
export function isMcpAppsHost(): boolean {
  return window.parent !== window;
}
