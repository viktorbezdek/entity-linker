import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

const MOCK_ITEMS = [
  { id: "s1", surface: "Echelon", proposed_type: "project", frequency: 3 },
  { id: "s2", surface: "AcmeCorp", proposed_type: "company", frequency: 2 },
];

afterEach(() => { cleanup(); vi.clearAllMocks(); mcpCallback = null; });

describe("Staging Review App", () => {
  it("calls postMcpReady on mount", async () => {
    const { postMcpReady } = await import("../../shared/src/mcp-app-bridge.js");
    const { default: App } = await import("./App.js");
    render(<App />);
    expect(postMcpReady).toHaveBeenCalledTimes(1);
  });

  it("renders candidate rows when data arrives", async () => {
    const { default: App } = await import("./App.js");
    const { container } = render(<App />);
    await act(async () => { mcpCallback?.(MOCK_ITEMS); });
    const rows = container.querySelectorAll('[data-testid="candidate-row"]');
    expect(rows.length).toBe(2);
    expect(container.querySelector('[data-testid="candidate-surface"]')?.textContent).toBe("Echelon");
  });

  it("approve button calls postMcpAction with staging_approve", async () => {
    const { postMcpAction } = await import("../../shared/src/mcp-app-bridge.js");
    const { default: App } = await import("./App.js");
    const { container } = render(<App />);
    await act(async () => { mcpCallback?.(MOCK_ITEMS); });
    const btn = container.querySelector('[data-testid="approve-btn"]') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(postMcpAction).toHaveBeenCalledWith("staging_approve", { staging_id: "s1" });
  });

  it("reject button calls postMcpAction with staging_reject", async () => {
    const { postMcpAction } = await import("../../shared/src/mcp-app-bridge.js");
    const { default: App } = await import("./App.js");
    const { container } = render(<App />);
    await act(async () => { mcpCallback?.(MOCK_ITEMS); });
    const btns = container.querySelectorAll('[data-testid="reject-btn"]');
    fireEvent.click(btns[0]);
    expect(postMcpAction).toHaveBeenCalledWith("staging_reject", { staging_id: "s1" });
  });

  it("empty state shows placeholder text", async () => {
    const { default: App } = await import("./App.js");
    const { getByText } = render(<App />);
    expect(getByText(/waiting for data/i)).toBeTruthy();
  });
});
