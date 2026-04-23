import { useEffect } from "react";
import { postMcpAction } from "../../../shared/src/mcp-app-bridge.js";
import { CandidateList } from "./CandidateList.js";
import type { PendingItem } from "../types.js";

interface Props {
  item: PendingItem;
  onResolved: (id: string) => void;
}

export function SpanCard({ item, onResolved }: Props): JSX.Element {
  const handlePick = (entityId: string) => {
    postMcpAction("pending_resolve", { pending_id: item.id, entity_id: entityId });
    onResolved(item.id);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const digit = parseInt(e.key, 10);
      if (!isNaN(digit) && digit >= 1 && digit <= item.candidates.length) {
        handlePick(item.candidates[digit - 1].entity_id);
      } else if (e.key.toLowerCase() === "n") {
        handlePick("none");
      } else if (e.key.toLowerCase() === "e") {
        handlePick("new");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item]);

  const context = item.context.tokens.join(" ");

  return (
    <div data-testid="span-card" data-pending-id={item.id} style={{ border: "1px solid #ccc", margin: 8, padding: 12 }}>
      <p>
        <em>{context.substring(0, 40)}…</em>{" "}
        <strong data-testid="span-surface">{item.surface}</strong>
      </p>
      <CandidateList candidates={item.candidates} onPick={handlePick} />
    </div>
  );
}
