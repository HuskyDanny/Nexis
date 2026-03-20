export type ThinkingNodeType = "news" | "effect" | "fetch" | "opportunity";
export type SessionStatus =
  | "idle"
  | "thinking"
  | "paused"
  | "complete"
  | "error";

export interface ThinkingNode {
  id: string;
  layer: number;
  type: ThinkingNodeType;
  content: string;
  reasoning: string;
  sources: string[];
  parents: string[];
  selected: boolean;
  metadata: Record<string, unknown>;
}

export interface ThinkingEdge {
  source: string;
  target: string;
  relationship: string;
}

export interface ThinkingSession {
  id: string;
  date: string;
  market: "US" | "CN";
  max_depth: number;
  nodes: ThinkingNode[];
  edges: ThinkingEdge[];
  status: SessionStatus;
  current_layer: number;
  error: string | null;
}

// SSE event types
export type ThinkingEvent =
  | { type: "layer_started"; layer: number }
  | { type: "node_created"; node: ThinkingNode }
  | { type: "layer_complete"; layer: number; node_count: number }
  | { type: "thinking_error"; layer: number; error: string }
  | { type: "match_complete"; opportunities: ThinkingNode[] };
