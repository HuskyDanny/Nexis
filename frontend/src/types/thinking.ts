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

// SSE event types — matches backend event protocol
export interface SSENodeStart {
  id: string;
  layer: number;
  type: ThinkingNodeType;
  parent_ids: string[];
}

export interface SSENodeText {
  id: string;
  field: "content" | "reasoning";
  delta: string;
}

export interface SSENodeComplete {
  id: string;
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface SSELayerComplete {
  layer: number;
  controller: { continue: boolean; reasoning: string; summary: string };
}

export interface SSESessionComplete {
  status: string;
}

export interface SSEError {
  message: string;
  layer?: number;
}
