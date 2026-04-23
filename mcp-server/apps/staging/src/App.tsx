import { useEffect } from "react";
import { isMcpAppsHost, postMcpReady } from "../../shared/src/mcp-app-bridge.js";

export default function App(): JSX.Element {
  useEffect(() => {
    postMcpReady();
  }, []);

  return (
    <div data-testid="staging-app">
      <p>Staging Review App loaded</p>
      {isMcpAppsHost() && <p data-testid="mcp-host-detected">Running inside MCP host</p>}
    </div>
  );
}
