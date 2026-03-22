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
  nodeStyle,
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
import { usePathHighlight } from "../hooks/usePathHighlight";

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
  const rfInstance = useRef<ReactFlowInstance | null>(null);
  const [isThinking, setIsThinking] = useState(false);
  const positionMap = useRef<Map<string, { x: number; y: number }>>(new Map());

  const {
    pinnedNodeId,
    unpinPath,
    pinPath,
    handleNodeMouseEnter,
    handleNodeMouseLeave,
  } = usePathHighlight({ session, setNodes, setEdges });

  const savePositions = useCallback((rfNodes: RFNode[]) => {
    for (const n of rfNodes) {
      positionMap.current.set(n.id, { x: n.position.x, y: n.position.y });
    }
  }, []);

  // Load session
  const loadSession = useCallback(async () => {
    try {
      const res = await graphApi.getSession(sessionId);
      const s = res.data;
      setSession(s);
      positionMap.current.clear();

      const { rfNodes, rfEdges } = buildThinkingGraph(s.nodes, s.edges);
      savePositions(rfNodes);
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
  }, [sessionId, setNodes, setEdges, savePositions]);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Poll for updates when status is "thinking" (auto mode)
  useEffect(() => {
    if (session?.status !== "thinking") return;
    const interval = setInterval(() => {
      loadSession();
    }, 2000);
    return () => clearInterval(interval);
  }, [session?.status, loadSession]);

  const refreshSession = useCallback(async () => {
    try {
      const res = await graphApi.getSession(sessionId);
      const s = res.data;
      setSession(s);
      unpinPath();

      const selectedMap = new Map(s.nodes.map((n) => [n.id, n]));
      setNodes((prev) =>
        prev.map((rfNode) => {
          const tn = selectedMap.get(rfNode.id);
          if (!tn) return rfNode;
          return {
            ...rfNode,
            data: { ...rfNode.data, selected: tn.selected },
            style: nodeStyle(tn.type, tn.selected, tn.layer),
          };
        }),
      );
      log.info("Session refreshed (style-only)");
    } catch (err) {
      log.error("Failed to refresh session:", err);
    }
  }, [sessionId, setNodes, unpinPath]);

  const loadSessionIncremental = useCallback(async () => {
    try {
      const res = await graphApi.getSession(sessionId);
      const s = res.data;
      setSession(s);

      const newNodes = s.nodes.filter((n) => !positionMap.current.has(n.id));

      if (newNodes.length === 0) {
        const selectedMap = new Map(s.nodes.map((n) => [n.id, n]));
        setNodes((prev) =>
          prev.map((rfNode) => {
            const tn = selectedMap.get(rfNode.id);
            if (!tn) return rfNode;
            return {
              ...rfNode,
              data: { ...rfNode.data, selected: tn.selected },
              style: nodeStyle(tn.type, tn.selected, tn.layer),
            };
          }),
        );
        return;
      }

      const { rfNodes, rfEdges } = buildThinkingGraph(
        s.nodes,
        s.edges,
        positionMap.current,
      );
      savePositions(rfNodes);
      setNodes(rfNodes);
      setEdges(rfEdges);

      setTimeout(
        () => rfInstance.current?.fitView({ padding: 0.15, duration: 400 }),
        200,
      );
      log.info("Session loaded incrementally:", newNodes.length, "new nodes");
    } catch (err) {
      log.error("Failed to load session incrementally:", err);
    }
  }, [sessionId, setNodes, setEdges, savePositions]);

  // Step to next layer
  const handleStep = useCallback(async () => {
    if (isThinking || !session) return;
    setIsThinking(true);
    log.info("Stepping to layer", session.current_layer + 1);
    try {
      await graphApi.thinkStep(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Step failed:", err);
    }
    setIsThinking(false);
  }, [sessionId, session, isThinking, loadSessionIncremental]);

  // Match against value pool
  const handleMatch = useCallback(async () => {
    if (isThinking || !session) return;
    setIsThinking(true);
    log.info("Matching against value pool");
    try {
      await graphApi.matchValues(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Match failed:", err);
    }
    setIsThinking(false);
  }, [sessionId, session, isThinking, loadSessionIncremental]);

  // Pane click: useCallback to avoid stale closure in React Flow
  const handlePaneClick = useCallback(() => {
    unpinPath();
    setSelectedNode(null);
  }, [unpinPath]);

  // Fallback: container div click also dismisses if target is the pane itself
  // (not a node or edge inside the pane — those are handled by onNodeClick)
  const handleContainerClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      // Only fire if clicking directly on the pane background, not on nodes/edges/UI
      if (
        target.classList.contains("react-flow__pane") ||
        target.classList.contains("react-flow__renderer")
      ) {
        unpinPath();
        setSelectedNode(null);
      }
    },
    [unpinPath],
  );

  // Escape key also clears selectedNode (hook handles unpinPath)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedNode(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Click node: show detail panel. Pin path only for opportunity nodes.
  const handleNodeClick = useCallback(
    async (_: React.MouseEvent, node: RFNode) => {
      if (!session) return;
      const thinkingNode = session.nodes.find((n) => n.id === node.id);
      setSelectedNode(thinkingNode ?? null);

      if (thinkingNode?.type === "opportunity") {
        if (pinnedNodeId === node.id) {
          unpinPath();
        } else {
          pinPath(node.id);
        }
      }
    },
    [session, pinnedNodeId, unpinPath, pinPath],
  );

  // Toggle node via detail panel
  const handleToggle = useCallback(
    async (nodeId: string, selected: boolean) => {
      try {
        await graphApi.toggleNode(sessionId, nodeId, selected);
        await refreshSession();
        setSelectedNode(null);
      } catch (err) {
        log.error("Toggle failed:", err);
      }
    },
    [sessionId, refreshSession],
  );

  const canStep =
    session?.status === "paused" &&
    (session?.current_layer ?? 0) < (session?.max_depth ?? 3);
  const canMatch =
    session?.status === "paused" && (session?.current_layer ?? 0) > 0;
  const maxLayer = Math.max(0, ...(session?.nodes.map((n) => n.layer) ?? [0]));

  return (
    <div className="flex-1 relative" onClick={handleContainerClick}>
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
        paneClickDistance={5}
        onPaneClick={handlePaneClick}
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
          onRegenerate={
            !selectedNode.selected
              ? () => {
                  handleStep();
                  setSelectedNode(null);
                }
              : undefined
          }
        />
      )}
    </div>
  );
}
