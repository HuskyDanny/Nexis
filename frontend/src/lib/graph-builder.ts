/**
 * Builds React Flow nodes and edges from selected pool items.
 * Handles sector matching, convergence detection, and dagre layout.
 */
import type { Node as RFNode, Edge as RFEdge } from "@xyflow/react";
import type { PoolItem } from "../services/api";
import { layoutGraph } from "./layout";

const TYPE_COLORS: Record<string, string> = {
  news_event: "#3b82f6",
  value_opportunity: "#22c55e",
  impact: "#f59e0b",
  convergence: "#ef4444",
};

const DIR_ICON: Record<string, string> = {
  bullish: "\u25B2",
  bearish: "\u25BC",
  neutral: "\u25CF",
};

export { TYPE_COLORS, DIR_ICON };

export interface Convergence {
  ticker: string;
  newsId: string;
  valueId: string;
  score: number;
  verdict: string;
}

export interface GraphResult {
  /** Nodes at center (0,0) — for explode-from-center start */
  centeredNodes: RFNode[];
  /** Nodes at dagre-computed positions — the final layout */
  layoutNodes: RFNode[];
  edges: RFEdge[];
  convergences: Convergence[];
}

function nodeStyle(type: string): React.CSSProperties {
  const color = TYPE_COLORS[type] ?? "#6b7394";
  const isConv = type === "convergence";
  return {
    background: isConv ? "rgba(239, 68, 68, 0.15)" : "rgba(15, 20, 35, 0.85)",
    backdropFilter: "blur(12px)",
    color: isConv ? "#fca5a5" : "#f0f0f5",
    border: isConv
      ? "2px solid rgba(239, 68, 68, 0.4)"
      : "1px solid rgba(255,255,255,0.08)",
    borderLeft:
      !isConv && type === "news_event" ? `3px solid ${color}` : undefined,
    borderRight:
      !isConv && type === "value_opportunity"
        ? `3px solid ${color}`
        : undefined,
    borderRadius: isConv ? 16 : 12,
    padding: isConv ? "14px 20px" : "12px 16px",
    fontSize: isConv ? 13 : 12,
    fontWeight: isConv ? 700 : 500,
    minWidth: isConv ? 140 : 150,
    maxWidth: isConv ? 160 : 180,
    textAlign: isConv ? ("center" as const) : undefined,
    boxShadow: isConv
      ? "0 0 30px rgba(239, 68, 68, 0.2), 0 4px 24px rgba(0,0,0,0.4)"
      : `0 4px 24px rgba(0,0,0,0.4), 0 0 20px ${color}15`,
    opacity: 1,
  };
}

export function buildGraph(
  selectedNews: PoolItem[],
  selectedValues: PoolItem[],
): GraphResult {
  const allNodes: RFNode[] = [];
  const allEdges: RFEdge[] = [];
  const convergences: Convergence[] = [];

  // News nodes
  for (const n of selectedNews) {
    allNodes.push({
      id: n.id,
      position: { x: 0, y: 0 },
      data: {
        label: `${DIR_ICON[n.direction] ?? ""} ${n.title}`,
        type: n.type,
      },
      style: nodeStyle("news_event"),
    });
  }

  // Value nodes
  for (const v of selectedValues) {
    allNodes.push({
      id: v.id,
      position: { x: 0, y: 0 },
      data: {
        label: `${DIR_ICON[v.direction] ?? ""} ${v.ticker} — $${v.price}`,
        type: v.type,
      },
      style: nodeStyle("value_opportunity"),
    });
  }

  // Edges: sector matching
  for (const news of selectedNews) {
    for (const val of selectedValues) {
      if ((news.sectors ?? []).includes(val.sector ?? "")) {
        allEdges.push({
          id: `${news.id}-${val.id}`,
          source: news.id,
          target: val.id,
          label: "impacts",
          type: "smoothstep",
          animated: true,
          style: { stroke: "rgba(255,255,255,0.2)", strokeWidth: 1.5 },
          labelStyle: { fill: "#6b7394", fontSize: 10 },
        });
      }
    }
  }

  // Convergence detection
  const sectorToNews: Record<string, PoolItem> = {};
  for (const n of selectedNews) {
    for (const s of n.sectors ?? []) sectorToNews[s] = n;
  }

  for (const v of selectedValues) {
    const matchedNews = sectorToNews[v.sector ?? ""];
    if (matchedNews) {
      const score = Math.round(
        matchedNews.confidence * 0.3 + (v.discount_pct ?? 0) * 0.3 + 75 * 0.4,
      );
      if (score >= 50) {
        const convId = `conv-${v.ticker}`;
        convergences.push({
          ticker: v.ticker ?? "",
          newsId: matchedNews.id,
          valueId: v.id,
          score,
          verdict: `Macro catalyst + ${v.discount_pct}% value discount`,
        });

        allNodes.push({
          id: convId,
          position: { x: 0, y: 0 },
          data: {
            label: `\u2B50 ${v.ticker} — ${score}%`,
            type: "convergence",
          },
          style: nodeStyle("convergence"),
        });

        allEdges.push(
          {
            id: `${matchedNews.id}-${convId}`,
            source: matchedNews.id,
            target: convId,
            label: "confirms",
            type: "smoothstep",
            animated: true,
            style: { stroke: "#ef4444", strokeWidth: 2 },
            labelStyle: { fill: "#fca5a5", fontSize: 10 },
          },
          {
            id: `${v.id}-${convId}`,
            source: v.id,
            target: convId,
            label: "confirms",
            type: "smoothstep",
            animated: true,
            style: { stroke: "#ef4444", strokeWidth: 2 },
            labelStyle: { fill: "#fca5a5", fontSize: 10 },
          },
        );
      }
    }
  }

  // Force-directed layout — organic positioning
  const layoutNodes = layoutGraph(allNodes, allEdges, {
    chargeStrength: -500,
    linkDistance: 180,
    collideRadius: 90,
    iterations: 120,
  });

  // Centered nodes — all at (0,0) for explode-from-center animation
  const centeredNodes = layoutNodes.map((n) => ({
    ...n,
    position: { x: 0, y: 0 },
  }));

  return { centeredNodes, layoutNodes, edges: allEdges, convergences };
}
