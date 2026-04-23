export interface Candidate {
  entity_id: string;
  confidence: number;
}

export interface PendingItem {
  id: string;
  source_hash: string;
  surface: string;
  span_start: number;
  span_end: number;
  candidates: Candidate[];
  context: { tokens: string[] };
}
