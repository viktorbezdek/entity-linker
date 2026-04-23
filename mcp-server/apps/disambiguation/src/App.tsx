import { useEffect, useState } from "react";
import { onMcpMessage, postMcpReady } from "../../shared/src/mcp-app-bridge.js";
import { SpanCard } from "./components/SpanCard.js";
import type { PendingItem } from "./types.js";

export default function App(): JSX.Element {
  const [items, setItems] = useState<PendingItem[]>([]);
  const [resolved, setResolved] = useState<Set<string>>(new Set());

  useEffect(() => {
    postMcpReady();
    const unsub = onMcpMessage<PendingItem[]>((data) => {
      if (Array.isArray(data)) setItems(data);
    });
    return unsub;
  }, []);

  const pending = items.filter((i) => !resolved.has(i.id));

  return (
    <div data-testid="disambiguation-app">
      {pending.length === 0 ? (
        <p>Disambiguation App loaded — waiting for data…</p>
      ) : (
        <div>
          <h2>Disambiguate {pending.length} span(s)</h2>
          {pending.map((item) => (
            <SpanCard
              key={item.id}
              item={item}
              onResolved={(id) => setResolved((s) => new Set([...s, id]))}
            />
          ))}
        </div>
      )}
    </div>
  );
}
