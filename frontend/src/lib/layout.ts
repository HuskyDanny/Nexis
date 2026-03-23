/**
 * Force-directed graph layout using d3-force.
 * Produces organic, Obsidian-style node positioning.
 */
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  forceRadial,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import type { Node, Edge } from "@xyflow/react";

interface ForceNode extends SimulationNodeDatum {
  id: string;
}

interface ForceLink extends SimulationLinkDatum<ForceNode> {
  id: string;
}

interface LayoutOptions {
  /** Repulsion strength (negative = repel). Default: -400 */
  chargeStrength?: number;
  /** Link distance. Default: 200 */
  linkDistance?: number;
  /** Collision radius. Default: 80 */
  collideRadius?: number;
  /** Simulation iterations. Default: 100 */
  iterations?: number;
  /** Center position. Default: {x: 0, y: 0} */
  center?: { x: number; y: number };
  /** Map of node ID → layer number for radial constraint */
  layerMap?: Map<string, number>;
  /** Radius per layer (pixels). Default: 150 */
  layerRadius?: number;
  /** Pre-existing positions to pin via fx/fy during simulation */
  fixedPositions?: Map<string, { x: number; y: number }>;
}

export function layoutGraph(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {},
): Node[] {
  const {
    chargeStrength = -400,
    linkDistance = 200,
    collideRadius = 80,
    iterations = 100,
    center = { x: 0, y: 0 },
    layerMap,
    layerRadius = 150,
    fixedPositions,
  } = options;

  // Create simulation nodes — pin existing positions via fx/fy
  const simNodes: ForceNode[] = nodes.map((n) => {
    const fixed = fixedPositions?.get(n.id);
    return {
      id: n.id,
      x: fixed?.x ?? center.x + (Math.random() - 0.5) * 50,
      y: fixed?.y ?? center.y + (Math.random() - 0.5) * 50,
      fx: fixed?.x,
      fy: fixed?.y,
    };
  });

  // Create simulation links
  const simLinks: ForceLink[] = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
  }));

  // Run simulation
  const simulation = forceSimulation(simNodes)
    .force(
      "link",
      forceLink<ForceNode, ForceLink>(simLinks)
        .id((d) => d.id)
        .distance(linkDistance),
    )
    .force("charge", forceManyBody().strength(chargeStrength))
    .force("center", forceCenter(center.x, center.y))
    .force("collide", forceCollide(collideRadius));

  // Add radial constraint for concentric ring layout
  if (layerMap) {
    simulation.force(
      "radial",
      forceRadial<ForceNode>(
        (d) => (layerMap.get(d.id) ?? 0) * layerRadius,
        center.x,
        center.y,
      ).strength(0.8),
    );
  }

  simulation.stop();

  // Run synchronously
  for (let i = 0; i < iterations; i++) {
    simulation.tick();
  }

  // Map positions back to React Flow nodes
  const posMap = new Map(
    simNodes.map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]),
  );

  return nodes.map((node) => {
    const pos = posMap.get(node.id) ?? { x: 0, y: 0 };
    return {
      ...node,
      position: { x: pos.x, y: pos.y },
    };
  });
}
