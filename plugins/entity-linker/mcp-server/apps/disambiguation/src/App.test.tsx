import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PendingItem } from "./types.js";

let mcpCallback: ((data: unknown) => void) | null = null;

vi.mock("../../shared/src/mcp-app-bridge.js", () => ({
  postMcpReady: vi.fn(),
  isMcpAppsHost: () => false,
  postMcpAction: vi.fn(),
  onMcpMessage: (cb: (data: unknown) => void) => {
    mcpCallback = cb;
    return () => { mcpCallback = null; };
  },
}));

const MOCK_ITEM: PendingItem = {
  id: "p1",
  source_hash: "h1",
  surface: "Viktor",
  span_start: 0,
  span_end: 6,
  candidates: [
    { entity_id: "viktor-bezdek", confidence: 0.92 },
    { entity_id: "viktor-novak", confidence: 0.70 },
  ],
  context: { tokens: ["synced", "with", "Viktor", "yesterday"] },
};

afterEach(() => { cleanup(); vi.clearAllMocks(); mcpCallback = null; });

describe("Disambiguation App", () => {
  it("calls postMcpReady on mount", async () => {
    const { postMcpReady } = await import("../../shared/src/mcp-app-bridge.js");
    const { default: App } = await import("./App.js");
    render(<App />);
    expect(postMcpReady).toHaveBeenCalledTimes(1);
  });

  it("renders span card when data arrives", async () => {
    const { default: App } = await import("./App.js");
    const { container } = render(<App />);
    await act(async () => { mcpCallback?.([MOCK_ITEM]); });
    expect(container.querySelectorAll('[data-testid="span-card"]').length).toBe(1);
    expect(container.querySelector('[data-testid="span-surface"]')?.textContent).toBe("Viktor");
  });

  it("keyboard shortcut 1 triggers pick and calls postMcpAction", async () => {
    const { postMcpAction } = await import("../../shared/src/mcp-app-bridge.js");
    const { default: App } = await import("./App.js");
    render(<App />);
    await act(async () => { mcpCallback?.([MOCK_ITEM]); });
    fireEvent.keyDown(window, { key: "1" });
    expect(postMcpAction).toHaveBeenCalledWith(
      "pending_resolve",
      { pending_id: "p1", entity_id: "viktor-bezdek" }
    );
  });

  it("empty state shows placeholder text", async () => {
    const { default: App } = await import("./App.js");
    const { getByText } = render(<App />);
    expect(getByText(/waiting for data/i)).toBeTruthy();
  });
});
