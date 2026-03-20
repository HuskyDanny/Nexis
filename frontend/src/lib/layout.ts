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
  } = options;

  // Create simulation nodes
  const simNodes: ForceNode[] = nodes.map((n) => ({
    id: n.id,
    x: center.x + (Math.random() - 0.5) * 50,
    y: center.y + (Math.random() - 0.5) * 50,
  }));

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
    .force("collide", forceCollide(collideRadius))
    .stop();

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
