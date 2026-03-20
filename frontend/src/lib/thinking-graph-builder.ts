/**
 * Converts ThinkingSession data to React Flow nodes/edges with concentric ring layout.
 */
import type { Node as RFNode, Edge as RFEdge } from "@xyflow/react";
import type { ThinkingNode, ThinkingEdge } from "../types/thinking";
import { layoutGraph } from "./layout";

const TYPE_COLORS: Record<string, string> = {
  news: "#3b82f6",
  effect: "#f59e0b",
  fetch: "#6b7394",
  opportunity: "#22c55e",
};

export { TYPE_COLORS };

function nodeStyle(type: string, selected: boolean): React.CSSProperties {
  const color = TYPE_COLORS[type] ?? "#6b7394";
  const isOpp = type === "opportunity";
  return {
    background: isOpp
      ? "rgba(34, 197, 94, 0.15)"
      : selected
        ? "rgba(15, 20, 35, 0.85)"
        : "rgba(15, 20, 35, 0.4)",
    backdropFilter: "blur(12px)",
    color: selected ? (isOpp ? "#86efac" : "#f0f0f5") : "#6b7394",
    border: isOpp
      ? "2px solid rgba(34, 197, 94, 0.4)"
      : `1px solid ${selected ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.04)"}`,
    borderLeft: type === "news" ? `3px solid ${color}` : undefined,
    borderRadius: isOpp ? 16 : 12,
    padding: "10px 14px",
    fontSize: 12,
    fontWeight: isOpp ? 700 : 500,
    minWidth: 140,
    maxWidth: 200,
    textAlign: isOpp ? ("center" as const) : undefined,
    boxShadow: isOpp
      ? "0 0 25px rgba(34, 197, 94, 0.2), 0 4px 20px rgba(0,0,0,0.4)"
      : `0 4px 20px rgba(0,0,0,0.3), 0 0 15px ${color}10`,
    opacity: selected ? 1 : 0.5,
    transition: "opacity 0.3s, border-color 0.3s",
  };
}

export function buildThinkingGraph(
  nodes: ThinkingNode[],
  edges: ThinkingEdge[],
): { rfNodes: RFNode[]; rfEdges: RFEdge[] } {
  // Build React Flow nodes
  const rfNodes: RFNode[] = nodes.map((n) => ({
    id: n.id,
    position: { x: 0, y: 0 },
    data: {
      label: n.content,
      type: n.type,
      layer: n.layer,
      selected: n.selected,
      reasoning: n.reasoning,
    },
    style: nodeStyle(n.type, n.selected),
  }));

  // Build React Flow edges
  const rfEdges: RFEdge[] = edges.map((e, i) => {
    const isMatch = e.relationship === "matches";
    const isConfirm =
      e.relationship === "compounds" || e.relationship === "causes";
    return {
      id: `e-${i}-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      label: e.relationship,
      type: "smoothstep",
      animated: true,
      style: {
        stroke: isMatch
          ? "rgba(34, 197, 94, 0.4)"
          : isConfirm
            ? "rgba(255, 255, 255, 0.2)"
            : "rgba(107, 115, 148, 0.3)",
        strokeWidth: isMatch ? 2 : 1.5,
      },
      labelStyle: {
        fill: isMatch ? "#86efac" : "#6b7394",
        fontSize: 10,
      },
    };
  });

  // Apply concentric ring layout
  const layerMap = new Map(nodes.map((n) => [n.id, n.layer]));
  const layoutNodes = layoutGraph(rfNodes, rfEdges, {
    chargeStrength: -300,
    linkDistance: 150,
    collideRadius: 70,
    iterations: 100,
    layerMap,
    layerRadius: 140,
  });

  return { rfNodes: layoutNodes, rfEdges };
}
