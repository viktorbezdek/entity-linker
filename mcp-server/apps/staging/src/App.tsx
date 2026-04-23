import { useEffect, useState } from "react";
import { onMcpMessage, postMcpAction, postMcpReady } from "../../shared/src/mcp-app-bridge.js";

interface StagingItem {
  id: string;
  surface: string;
  proposed_type: string | null;
  frequency: number;
}

export default function App(): JSX.Element {
  const [items, setItems] = useState<StagingItem[]>([]);

  useEffect(() => {
    postMcpReady();
    const unsub = onMcpMessage<StagingItem[]>((data) => {
      if (Array.isArray(data)) setItems(data);
    });
    return unsub;
  }, []);

  const handleApprove = (id: string) => {
    postMcpAction("staging_approve", { staging_id: id });
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  const handleReject = (id: string) => {
    postMcpAction("staging_reject", { staging_id: id });
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  return (
    <div data-testid="staging-app">
      {items.length === 0 ? (
        <p>Staging Review App loaded — waiting for data…</p>
      ) : (
        <div>
          <h2>Review {items.length} candidate(s)</h2>
          {items.map((item) => (
            <div key={item.id} data-testid="candidate-row" style={{ border: "1px solid #ccc", margin: 8, padding: 12 }}>
              <strong data-testid="candidate-surface">{item.surface}</strong>
              <span> ({item.proposed_type ?? "?"})</span>
              <span> ×{item.frequency}</span>
              <div>
                <button data-testid="approve-btn" onClick={() => handleApprove(item.id)}>
                  Approve
                </button>
                <button data-testid="reject-btn" onClick={() => handleReject(item.id)}>
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
