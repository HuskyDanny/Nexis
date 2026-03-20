/**
 * ThinkingView — the concentric ring graph visualization for thinking sessions.
 * Shows the DAG with ring guides per layer, node detail panel, and controls.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node as RFNode,
  type Edge as RFEdge,
  type ReactFlowInstance,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ThinkingSession, ThinkingNode } from "../types/thinking";
import {
  buildThinkingGraph,
  LAYER_COLORS,
} from "../lib/thinking-graph-builder";
import {
  LayerSpectrum,
  OpportunitiesBanner,
  NodeDetailPanel,
} from "./ThinkingPanels";
import { graphApi } from "../services/api";
import { createLogger } from "../lib/logger";
import { AgentFace } from "./AgentFace";

const log = createLogger("thinking-view");

interface ThinkingViewProps {
  sessionId: string;
  onReset: () => void;
}

export function ThinkingView({ sessionId, onReset }: ThinkingViewProps) {
  const [session, setSession] = useState<ThinkingSession | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const [selectedNode, setSelectedNode] = useState<ThinkingNode | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<Set<string>>(
    new Set(),
  );
  const [pinnedNodeId, setPinnedNodeId] = useState<string | null>(null);
  const rfInstance = useRef<ReactFlowInstance | null>(null);
  const [isThinking, setIsThinking] = useState(false);

  // Load session
  const loadSession = useCallback(async () => {
    try {
      const res = await graphApi.getSession(sessionId);
      const s = res.data;
      setSession(s);

      const { rfNodes, rfEdges } = buildThinkingGraph(s.nodes, s.edges);
      setNodes(rfNodes);
      setEdges(rfEdges);

      setTimeout(
        () => rfInstance.current?.fitView({ padding: 0.15, duration: 400 }),
        200,
      );
      log.info(
        "Session loaded:",
        s.nodes.length,
        "nodes,",
        s.edges.length,
        "edges",
      );
    } catch (err) {
      log.error("Failed to load session:", err);
    }
  }, [sessionId, setNodes, setEdges]);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Step to next layer
  const handleStep = useCallback(async () => {
    if (isThinking || !session) return;
    setIsThinking(true);
    log.info("Stepping to layer", session.current_layer + 1);
    try {
      await graphApi.thinkStep(sessionId);
      await loadSession();
    } catch (err) {
      log.error("Step failed:", err);
    }
    setIsThinking(false);
  }, [sessionId, session, isThinking, loadSession]);

  // Match against value pool
  const handleMatch = useCallback(async () => {
    if (isThinking || !session) return;
    setIsThinking(true);
    log.info("Matching against value pool");
    try {
      await graphApi.matchValues(sessionId);
      await loadSession();
    } catch (err) {
      log.error("Match failed:", err);
    }
    setIsThinking(false);
  }, [sessionId, session, isThinking, loadSession]);

  // Trace ancestor path from a node back to roots (for hover highlighting)
  const traceAncestors = useCallback(
    (nodeId: string): Set<string> => {
      if (!session) return new Set();
      const ancestors = new Set<string>();
      const queue = [nodeId];
      ancestors.add(nodeId);

      // Build reverse edge map: target → sources
      const parentMap: Record<string, string[]> = {};
      for (const e of session.edges) {
        (parentMap[e.target] ??= []).push(e.source);
      }

      while (queue.length > 0) {
        const current = queue.shift()!;
        for (const parent of parentMap[current] ?? []) {
          if (!ancestors.has(parent)) {
            ancestors.add(parent);
            queue.push(parent);
          }
        }
      }
      return ancestors;
    },
    [session],
  );

  // Store original styles for restore (avoids re-running d3-force on mouse leave)
  const savedStyles = useRef<{
    nodes: Map<string, React.CSSProperties>;
    edges: Map<string, { style: React.CSSProperties; animated: boolean }>;
  }>({ nodes: new Map(), edges: new Map() });

  // Hover: highlight ancestor path — ONLY for opportunity nodes (final layer)
  const handleNodeMouseEnter = useCallback(
    (_: React.MouseEvent, node: RFNode) => {
      if (!session) return;
      const thinkingNode = session.nodes.find((n) => n.id === node.id);
      if (thinkingNode?.type !== "opportunity") return; // only final nodes

      const path = traceAncestors(node.id);
      setHighlightedPath(path);

      // Save current styles before modifying
      setNodes((prev) => {
        for (const n of prev)
          savedStyles.current.nodes.set(n.id, { ...n.style });
        return prev.map((n) => ({
          ...n,
          style: {
            ...n.style,
            opacity: path.has(n.id) ? 1 : 0.15,
            transition: "opacity 0.3s ease",
          },
        }));
      });

      setEdges((prev) => {
        for (const e of prev)
          savedStyles.current.edges.set(e.id, {
            style: { ...e.style },
            animated: !!e.animated,
          });
        return prev.map((e) => {
          const isOnPath = path.has(e.source) && path.has(e.target);
          return {
            ...e,
            style: {
              ...e.style,
              stroke: isOnPath ? "#f97316" : "rgba(255,255,255,0.05)",
              strokeWidth: isOnPath ? 2.5 : 1,
            },
            animated: isOnPath,
          };
        });
      });
    },
    [session, traceAncestors, setNodes, setEdges],
  );

  const handleNodeMouseLeave = useCallback(() => {
    // Don't clear if path is pinned
    if (pinnedNodeId || highlightedPath.size === 0) return;
    setHighlightedPath(new Set());

    // Restore saved styles (no layout recalculation)
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        style: savedStyles.current.nodes.get(n.id) ?? n.style,
      })),
    );
    setEdges((prev) =>
      prev.map((e) => {
        const saved = savedStyles.current.edges.get(e.id);
        return saved
          ? { ...e, style: saved.style, animated: saved.animated }
          : e;
      }),
    );
  }, [pinnedNodeId, highlightedPath, setNodes, setEdges]);

  // Click node: show detail panel + pin/unpin path highlighting
  const handleNodeClick = useCallback(
    async (_: React.MouseEvent, node: RFNode) => {
      if (!session) return;
      const thinkingNode = session.nodes.find((n) => n.id === node.id);
      setSelectedNode(thinkingNode ?? null);

      // Pin/unpin path for opportunity nodes
      if (thinkingNode?.type === "opportunity") {
        if (pinnedNodeId === node.id) {
          // Unpin — restore styles
          setPinnedNodeId(null);
          setHighlightedPath(new Set());
          setNodes((prev) =>
            prev.map((n) => ({
              ...n,
              style: savedStyles.current.nodes.get(n.id) ?? n.style,
            })),
          );
          setEdges((prev) =>
            prev.map((e) => {
              const saved = savedStyles.current.edges.get(e.id);
              return saved
                ? { ...e, style: saved.style, animated: saved.animated }
                : e;
            }),
          );
        } else {
          // Pin — highlight stays
          setPinnedNodeId(node.id);
        }
      } else if (pinnedNodeId) {
        // Clicking a non-opportunity node unpins
        setPinnedNodeId(null);
        setHighlightedPath(new Set());
        setNodes((prev) =>
          prev.map((n) => ({
            ...n,
            style: savedStyles.current.nodes.get(n.id) ?? n.style,
          })),
        );
        setEdges((prev) =>
          prev.map((e) => {
            const saved = savedStyles.current.edges.get(e.id);
            return saved
              ? { ...e, style: saved.style, animated: saved.animated }
              : e;
          }),
        );
      }
    },
    [session, pinnedNodeId, setNodes, setEdges],
  );

  // Toggle node via detail panel
  const handleToggle = useCallback(
    async (nodeId: string, selected: boolean) => {
      try {
        await graphApi.toggleNode(sessionId, nodeId, selected);
        await loadSession();
        setSelectedNode(null);
      } catch (err) {
        log.error("Toggle failed:", err);
      }
    },
    [sessionId, loadSession],
  );

  const canStep =
    session?.status === "paused" &&
    (session?.current_layer ?? 0) < (session?.max_depth ?? 3);
  const canMatch =
    session?.status === "paused" && (session?.current_layer ?? 0) > 0;
  const maxLayer = Math.max(0, ...(session?.nodes.map((n) => n.layer) ?? [0]));

  return (
    <div className="flex-1 relative">
      {/* Ring guides — colored concentric circles per layer */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none z-0"
        style={{ opacity: 0.2 }}
      >
        {Array.from({ length: maxLayer + 2 }, (_, i) => {
          const r = i * 140;
          const layerColor = LAYER_COLORS[Math.min(i, LAYER_COLORS.length - 1)];
          return r > 0 ? (
            <circle
              key={i}
              cx="50%"
              cy="50%"
              r={r}
              fill="none"
              stroke={layerColor}
              strokeWidth={1}
              strokeDasharray="4 8"
              opacity={0.4}
            />
          ) : null;
        })}
      </svg>

      <LayerSpectrum session={session} />

      {/* Controls bar */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3">
        {/* Status */}
        <div className="glass-card px-4 py-2 flex items-center gap-3">
          <span className="text-xs text-text-muted uppercase tracking-widest">
            Layer {session?.current_layer ?? 0}/{session?.max_depth ?? 3}
          </span>
          {isThinking && (
            <span
              className="flex items-center gap-1.5 text-xs"
              style={{ color: "#f97316" }}
            >
              <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
              Thinking...
            </span>
          )}
          {session?.status === "complete" && (
            <span className="text-xs" style={{ color: "#22c55e" }}>
              Complete
            </span>
          )}
          {session?.status === "error" && (
            <span className="text-xs" style={{ color: "#ef4444" }}>
              Error: {session.error}
            </span>
          )}
        </div>

        {/* Action buttons */}
        {canStep && (
          <button
            onClick={handleStep}
            disabled={isThinking}
            className="px-4 py-2 rounded-lg text-xs font-medium tracking-wide transition-all"
            style={{
              background: "rgba(249, 115, 22, 0.12)",
              color: "#f97316",
              border: "1px solid rgba(249, 115, 22, 0.2)",
              opacity: isThinking ? 0.5 : 1,
            }}
          >
            Think Deeper
          </button>
        )}
        {canMatch && (
          <button
            onClick={handleMatch}
            disabled={isThinking}
            className="px-4 py-2 rounded-lg text-xs font-medium tracking-wide transition-all"
            style={{
              background: "rgba(34, 197, 94, 0.12)",
              color: "#22c55e",
              border: "1px solid rgba(34, 197, 94, 0.2)",
              opacity: isThinking ? 0.5 : 1,
            }}
          >
            Find Opportunities
          </button>
        )}
        <button
          onClick={onReset}
          className="px-3 py-2 rounded-lg text-xs text-text-muted hover:text-text transition-colors"
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          Reset
        </button>
      </div>

      <OpportunitiesBanner session={session} />

      {/* Agent face during thinking */}
      {isThinking && (
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 pointer-events-none"
          style={{ opacity: 0.4 }}
        >
          <AgentFace size={80} />
        </div>
      )}

      {/* React Flow graph */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onNodeMouseEnter={handleNodeMouseEnter}
        onNodeMouseLeave={handleNodeMouseLeave}
        onInit={(instance) => {
          rfInstance.current = instance;
        }}
        fitView
        fitViewOptions={{ padding: 0.1 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(255,255,255,0.03)" gap={24} size={1} />
        <Controls />
      </ReactFlow>

      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          onToggle={handleToggle}
        />
      )}
    </div>
  );
}
