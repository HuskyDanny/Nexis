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

// Layer colors — cool to warm as thinking deepens
const LAYER_COLORS: string[] = [
  "#3b82f6", // Layer 0: blue (news/seed)
  "#8b5cf6", // Layer 1: purple (immediate effects)
  "#f59e0b", // Layer 2: amber (compounding)
  "#ef4444", // Layer 3: red (deep compounding)
  "#22c55e", // Layer 4+: green (opportunities)
];

export { TYPE_COLORS, LAYER_COLORS };

export function nodeStyle(
  type: string,
  selected: boolean,
  layer: number = 0,
): React.CSSProperties {
  const layerColor = LAYER_COLORS[Math.min(layer, LAYER_COLORS.length - 1)];
  const color = type === "opportunity" ? TYPE_COLORS.opportunity : layerColor;
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
    borderLeft: !isOpp ? `3px solid ${color}` : undefined,
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
    transition: "background 0.3s, border-color 0.3s, color 0.3s",
  };
}

/**
 * Calculate deterministic position on a concentric ring.
 * Used during SSE streaming — avoids d3-force re-simulation.
 */
export function concentricPosition(
  layer: number,
  index: number,
  totalInLayer: number,
  layerRadius: number = 250,
): { x: number; y: number } {
  if (layer === 0) {
    const angle = (index / Math.max(totalInLayer, 1)) * 2 * Math.PI;
    const r = totalInLayer > 1 ? 60 : 0;
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  }
  const r = layer * layerRadius;
  const angle =
    (index / Math.max(totalInLayer, 1)) * 2 * Math.PI + (layer * Math.PI) / 6;
  return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
}

export function buildThinkingGraph(
  nodes: ThinkingNode[],
  edges: ThinkingEdge[],
  fixedPositions?: Map<string, { x: number; y: number }>,
): { rfNodes: RFNode[]; rfEdges: RFEdge[] } {
  // Build React Flow nodes — use StreamingNode type so confidence renders
  const rfNodes: RFNode[] = nodes.map((n) => ({
    id: n.id,
    type: "streaming",
    position: { x: 0, y: 0 },
    data: {
      label: n.content,
      type: n.type,
      layer: n.layer,
      selected: n.selected,
      reasoning: n.reasoning,
      streaming: false,
      confidence:
        ((n as unknown as Record<string, unknown>).confidence as number) ??
        (n.metadata?.confidence as number) ??
        undefined,
    },
    style: nodeStyle(n.type, n.selected, n.layer),
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
      markerEnd: {
        type: "arrowclosed" as const,
        color: isMatch ? "rgba(34, 197, 94, 0.6)" : "rgba(255, 255, 255, 0.3)",
        width: 15,
        height: 15,
      },
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

  // Apply concentric ring layout — strong repulsion to prevent overlap
  const layerMap = new Map(nodes.map((n) => [n.id, n.layer]));
  const layoutNodes = layoutGraph(rfNodes, rfEdges, {
    chargeStrength: -800,
    linkDistance: 200,
    collideRadius: 130,
    iterations: 200,
    layerMap,
    layerRadius: 250,
    fixedPositions,
  });

  return { rfNodes: layoutNodes, rfEdges };
}
