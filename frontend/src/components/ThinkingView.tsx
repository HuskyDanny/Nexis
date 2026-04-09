/**
 * ThinkingView — concentric ring graph visualization for thinking sessions.
 * SSE handlers extracted to useSSEHandlers hook.
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
import { buildThinkingGraph, nodeStyle } from "../lib/thinking-graph-builder";
import { NodeDetailPanel } from "./ThinkingPanels";
import { OpportunityStrip } from "./OpportunityStrip";
import { graphApi } from "../services/api";
import { createLogger } from "../lib/logger";
import { AgentFace } from "./AgentFace";
import { usePathHighlight } from "../hooks/usePathHighlight";
import { StreamingNode } from "./StreamingNode";
import { useSSESession } from "../hooks/useSSESession";
import { useSSEHandlers } from "../hooks/useSSEHandlers";

const log = createLogger("thinking-view");

const nodeTypes = { streaming: StreamingNode };

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
  const [isPending, setIsPending] = useState(false);
  const positionMap = useRef<Map<string, { x: number; y: number }>>(new Map());
  const layerNodeCounts = useRef<Map<number, number>>(new Map());

  const {
    pinnedNodeId,
    unpinPath,
    pinPath,
    handleNodeMouseEnter,
    handleNodeMouseLeave,
  } = usePathHighlight({ session, setNodes, setEdges });

  const {
    handleNodeStart,
    handleNodeText,
    handleNodeComplete,
    handleEdges,
    handleOpportunity,
    handleLayerComplete,
    handleSessionComplete,
  } = useSSEHandlers({
    setNodes,
    setEdges,
    setSession,
    setIsPending,
    layerNodeCounts,
    positionMap,
  });

  const savePositions = useCallback((rfNodes: RFNode[]) => {
    for (const n of rfNodes) {
      positionMap.current.set(n.id, { x: n.position.x, y: n.position.y });
    }
  }, []);

  const handleNodeDragStop = useCallback(
    (_event: React.MouseEvent, node: RFNode) => {
      positionMap.current.set(node.id, {
        x: node.position.x,
        y: node.position.y,
      });
    },
    [],
  );

  // Load session on mount / sessionId change
  useEffect(() => {
    const load = async () => {
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
    };
    load();
  }, [sessionId, setNodes, setEdges, savePositions]);

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

  // Wire SSE hook — active only during "thinking" status
  const { connected } = useSSESession(
    session?.status === "thinking" ? sessionId : null,
    {
      onNodeStart: handleNodeStart,
      onNodeText: handleNodeText,
      onNodeComplete: handleNodeComplete,
      onEdges: handleEdges,
      onOpportunity: handleOpportunity,
      onLayerComplete: handleLayerComplete,
      onSessionComplete: handleSessionComplete,
      onError: (err) =>
        log.error("SSE error:", err.error ?? err.message ?? String(err)),
    },
  );

  const isThinking = session?.status === "thinking" || isPending;

  // Auto-fitView when nodes arrive during SSE streaming or session completes
  const prevNodeCount = useRef(0);
  useEffect(() => {
    const count = nodes.length;
    // Fit on first batch of nodes and when session completes
    if (
      count > 0 &&
      (prevNodeCount.current === 0 ||
        session?.status === "complete" ||
        session?.status === "paused")
    ) {
      const delay = prevNodeCount.current === 0 ? 300 : 100;
      setTimeout(
        () => rfInstance.current?.fitView({ padding: 0.15, duration: 500 }),
        delay,
      );
    }
    prevNodeCount.current = count;
  }, [nodes.length, session?.status]);

  // Polling fallback — only when SSE is not connected
  useEffect(() => {
    if (connected || session?.status !== "thinking") return;
    const interval = setInterval(() => loadSessionIncremental(), 2000);
    return () => clearInterval(interval);
  }, [connected, session?.status, loadSessionIncremental]);

  const handleStep = useCallback(async () => {
    if (isThinking || !session) return;
    setIsPending(true);
    try {
      await graphApi.thinkStep(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Step failed:", err);
    }
    setIsPending(false);
  }, [sessionId, session, isThinking, loadSessionIncremental]);

  const handleMatch = useCallback(async () => {
    if (isThinking || !session) return;
    setIsPending(true);
    try {
      await graphApi.matchValues(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Match failed:", err);
    }
    setIsPending(false);
  }, [sessionId, session, isThinking, loadSessionIncremental]);

  const handlePaneClick = useCallback(() => {
    unpinPath();
    setSelectedNode(null);
  }, [unpinPath]);

  const handleContainerClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedNode(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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
  const hasEffectNodes = nodes.some(
    (n) =>
      (n.data as Record<string, unknown>).layer !== undefined &&
      ((n.data as Record<string, unknown>).layer as number) > 0,
  );

  return (
    <div
      className="flex-1 relative h-full w-full"
      onClick={handleContainerClick}
    >
      {/* Layer color legend — bottom-left */}
      <div
        className="absolute bottom-12 left-4 z-20 flex flex-col gap-1.5"
        style={{
          background: "rgba(15, 20, 35, 0.7)",
          backdropFilter: "blur(8px)",
          border: "1px solid rgba(255,255,255,0.05)",
          borderRadius: 8,
          padding: "8px 10px",
        }}
      >
        {[
          ["#3b82f6", "News"],
          ["#8b5cf6", "Effects L1"],
          ["#f59e0b", "Effects L2"],
          ["#ef4444", "Effects L3"],
          ["#22c55e", "Opportunities"],
        ].map(([color, label]) => (
          <div key={label} className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: color, boxShadow: `0 0 4px ${color}` }}
            />
            <span className="text-[10px]" style={{ color: "#6b7394" }}>
              {label}
            </span>
          </div>
        ))}
      </div>

      {/* Minimal top-right control cluster */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
          style={{
            background: "rgba(15, 20, 35, 0.8)",
            backdropFilter: "blur(12px)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <span className="text-[11px] font-mono" style={{ color: "#6b7394" }}>
            {session?.current_layer ?? 0}/{session?.max_depth ?? 3}
          </span>
          {isThinking && (
            <span
              className="w-1.5 h-1.5 rounded-full animate-pulse"
              style={{ background: "#f97316" }}
            />
          )}
          {session?.status === "complete" && (
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: "#22c55e" }}
            />
          )}
        </div>
        {canStep && (
          <button
            onClick={handleStep}
            disabled={isThinking}
            className="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all"
            style={{
              background: "rgba(249, 115, 22, 0.1)",
              color: "#f97316",
              border: "1px solid rgba(249, 115, 22, 0.15)",
              opacity: isThinking ? 0.4 : 1,
            }}
          >
            Deeper
          </button>
        )}
        {canMatch && (
          <button
            onClick={handleMatch}
            disabled={isThinking}
            className="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all"
            style={{
              background: "rgba(34, 197, 94, 0.1)",
              color: "#22c55e",
              border: "1px solid rgba(34, 197, 94, 0.15)",
              opacity: isThinking ? 0.4 : 1,
            }}
          >
            Match
          </button>
        )}
        <button
          onClick={onReset}
          className="px-2.5 py-1.5 rounded-lg text-[11px] text-text-muted hover:text-text transition-colors"
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.05)",
          }}
        >
          Reset
        </button>
      </div>

      {/* Opportunity strip — top center, hover to expand */}
      <OpportunityStrip
        session={session}
        onHighlight={(nodeId) => pinPath(nodeId)}
        onClearHighlight={() => unpinPath()}
      />

      {/* Agent face: only while thinking AND before any effect nodes arrive */}
      {isThinking && !hasEffectNodes && (
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 pointer-events-none"
          style={{ opacity: 0.4 }}
        >
          <AgentFace size={80} />
        </div>
      )}

      <ReactFlow
        nodeTypes={nodeTypes}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onNodeMouseEnter={handleNodeMouseEnter}
        onNodeMouseLeave={handleNodeMouseLeave}
        onNodeDragStop={handleNodeDragStop}
        paneClickDistance={5}
        onPaneClick={handlePaneClick}
        onInit={(instance) => {
          rfInstance.current = instance;
        }}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.15}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(255,255,255,0.03)" gap={24} size={1} />
        <Controls />
      </ReactFlow>

      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          session={session}
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
