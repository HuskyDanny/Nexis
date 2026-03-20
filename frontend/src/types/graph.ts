export type NodeType =
  | "news_event"
  | "impact"
  | "stock_endpoint"
  | "value_opportunity"
  | "reason"
  | "convergence";
export type Direction = "bullish" | "bearish" | "neutral";
export type Market = "CN" | "US";

export interface GraphNode {
  id: string;
  type: NodeType;
  surface_summary: string;
  direction: Direction;
  confidence: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface DailyGraph {
  date: string;
  market: Market;
  status: "pending" | "complete" | "failed";
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Layer {
  node_id: string;
  depth: 0 | 1 | 2 | 3;
  content: string;
  tool_outputs?: Record<string, unknown>;
  sources?: string[];
}
