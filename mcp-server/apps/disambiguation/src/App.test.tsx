import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.js";

vi.mock("../../shared/src/mcp-app-bridge.js", () => ({
  postMcpReady: vi.fn(),
  isMcpAppsHost: () => false,
}));

afterEach(() => cleanup());

describe("Disambiguation App stub", () => {
  it("renders the app container", () => {
    const { container } = render(<App />);
    expect(container.querySelector('[data-testid="disambiguation-app"]')).not.toBeNull();
  });

  it("renders the loaded message", () => {
    const { getByText } = render(<App />);
    expect(getByText("Disambiguation App loaded")).toBeTruthy();
  });

  it("calls postMcpReady exactly once on mount", async () => {
    const bridge = await import("../../shared/src/mcp-app-bridge.js");
    vi.mocked(bridge.postMcpReady).mockClear();
    render(<App />);
    expect(bridge.postMcpReady).toHaveBeenCalledTimes(1);
  });
});
