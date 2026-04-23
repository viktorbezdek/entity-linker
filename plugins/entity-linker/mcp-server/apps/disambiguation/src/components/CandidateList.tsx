import type { Candidate } from "../types.js";

interface Props {
  candidates: Candidate[];
  onPick: (entityId: string) => void;
}

export function CandidateList({ candidates, onPick }: Props): JSX.Element {
  return (
    <ul data-testid="candidate-list" style={{ listStyle: "none", padding: 0 }}>
      {candidates.map((c, idx) => (
        <li key={c.entity_id} style={{ marginBottom: 4 }}>
          <button
            data-testid={`candidate-${idx + 1}`}
            onClick={() => onPick(c.entity_id)}
            title={`Press ${idx + 1} to pick`}
          >
            [{idx + 1}] {c.entity_id} ({(c.confidence * 100).toFixed(0)}%)
          </button>
        </li>
      ))}
      <li>
        <button data-testid="candidate-none" onClick={() => onPick("none")}>
          [N] None of these
        </button>
      </li>
      <li>
        <button data-testid="candidate-new" onClick={() => onPick("new")}>
          [E] New entity
        </button>
      </li>
    </ul>
  );
}
