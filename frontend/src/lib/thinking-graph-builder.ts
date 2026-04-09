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

  if (isOpp) {
    return {
      background: "rgba(34, 197, 94, 0.08)",
      backdropFilter: "blur(16px)",
      color: "#86efac",
      border: "1.5px solid rgba(34, 197, 94, 0.35)",
      borderRadius: 14,
      boxShadow:
        "0 0 30px rgba(34, 197, 94, 0.15), 0 0 60px rgba(34, 197, 94, 0.05)",
      transition: "all 0.3s ease",
    };
  }

  return {
    background: selected ? "rgba(15, 20, 35, 0.9)" : "rgba(15, 20, 35, 0.5)",
    backdropFilter: "blur(12px)",
    color: selected ? color : "#6b7394",
    border: `1px solid ${selected ? `${color}30` : "rgba(255,255,255,0.05)"}`,
    borderRadius: 10,
    boxShadow: selected
      ? `0 0 20px ${color}12, 0 4px 16px rgba(0,0,0,0.3)`
      : "0 2px 10px rgba(0,0,0,0.2)",
    transition: "all 0.3s ease",
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
  layerRadius: number = 300,
): { x: number; y: number } {
  if (layer === 0) {
    // News stays at center — small cluster
    const r = totalInLayer > 1 ? 80 : 0;
    const angle = (index / Math.max(totalInLayer, 1)) * 2 * Math.PI;
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
  // Build React Flow nodes
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
      confidence:
        (n.metadata?.confidence as number) ??
        (n as unknown as Record<string, unknown>).confidence ??
        undefined,
    },
    style: nodeStyle(n.type, n.selected, n.layer),
  }));

  // Build React Flow edges — no labels to reduce clutter
  const rfEdges: RFEdge[] = edges.map((e, i) => {
    const isMatch = e.relationship === "matches";
    const isConfirm =
      e.relationship === "compounds" || e.relationship === "causes";
    return {
      id: `e-${i}-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      type: "smoothstep",
      animated: isMatch,
      markerEnd: {
        type: "arrowclosed" as const,
        color: isMatch ? "rgba(34, 197, 94, 0.5)" : "rgba(255, 255, 255, 0.2)",
        width: 12,
        height: 12,
      },
      style: {
        stroke: isMatch
          ? "rgba(34, 197, 94, 0.3)"
          : isConfirm
            ? "rgba(255, 255, 255, 0.12)"
            : "rgba(107, 115, 148, 0.15)",
        strokeWidth: isMatch ? 1.5 : 1,
      },
    };
  });

  // Apply concentric ring layout
  const maxLayer = Math.max(...nodes.map((n) => n.layer ?? 0), 0);
  const layerMap = new Map(
    nodes.map((n) => [
      n.id,
      n.type === "opportunity" ? maxLayer + 1 : (n.layer ?? 0),
    ]),
  );
  // Scale with node count — more nodes need more space
  const n = nodes.length;
  const scale = Math.max(1, n / 15);
  const layoutNodes = layoutGraph(rfNodes, rfEdges, {
    chargeStrength: -600 * scale,
    linkDistance: 180 * Math.sqrt(scale),
    collideRadius: 110 * Math.sqrt(scale),
    iterations: 200 + n * 2,
    layerMap,
    layerRadius: 300,
    fixedPositions,
  });

  return { rfNodes: layoutNodes, rfEdges };
}
