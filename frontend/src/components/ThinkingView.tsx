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
  concentricPosition,
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
import { StreamingNode } from "./StreamingNode";
import { useSSESession } from "../hooks/useSSESession";
import type {
  SSENodeStart,
  SSENodeText,
  SSENodeComplete,
  SSELayerComplete,
  SSESessionComplete,
  SSEEdgesPayload,
} from "../types/thinking";

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

  // --- SSE streaming handlers ---

  const handleNodeStart = useCallback(
    (data: SSENodeStart) => {
      const { id, layer, type, parent_ids } = data;
      const count = (layerNodeCounts.current.get(layer) ?? 0) + 1;
      layerNodeCounts.current.set(layer, count);
      const idx = count - 1;

      // Re-space existing nodes on this layer
      setNodes((prev) => {
        const updated = prev.map((n) => {
          if (n.data.layer !== layer) return n;
          const existingIdx = prev
            .filter((p) => p.data.layer === layer)
            .indexOf(n);
          const pos = concentricPosition(layer, existingIdx, count);
          positionMap.current.set(n.id, pos);
          return { ...n, position: pos };
        });

        // Add the new streaming node
        const pos = concentricPosition(layer, idx, count);
        positionMap.current.set(id, pos);
        const newNode: RFNode = {
          id,
          type: "streaming",
          position: pos,
          data: {
            label: "",
            type,
            layer,
            selected: true,
            reasoning: "",
            streaming: true,
            parent_ids,
          },
          style: nodeStyle(type, true, layer),
        };
        return [...updated, newNode];
      });

      // Also track in session
      setSession((prev) => {
        if (!prev) return prev;
        const newThinkingNode: ThinkingNode = {
          id,
          layer,
          type: type as ThinkingNode["type"],
          content: "",
          reasoning: "",
          sources: [],
          parents: parent_ids,
          selected: true,
          metadata: {},
        };
        return {
          ...prev,
          nodes: [...prev.nodes, newThinkingNode],
          current_layer: Math.max(prev.current_layer, layer),
        };
      });
    },
    [setNodes],
  );

  const handleNodeText = useCallback(
    (data: SSENodeText) => {
      const { id, field, delta } = data;
      setNodes((prev) =>
        prev.map((n) => {
          if (n.id !== id) return n;
          if (field === "content") {
            return {
              ...n,
              data: { ...n.data, label: (n.data.label ?? "") + delta },
            };
          }
          return {
            ...n,
            data: { ...n.data, reasoning: (n.data.reasoning ?? "") + delta },
          };
        }),
      );

      // Keep session in sync
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          nodes: prev.nodes.map((n) => {
            if (n.id !== id) return n;
            if (field === "content")
              return { ...n, content: n.content + delta };
            return { ...n, reasoning: n.reasoning + delta };
          }),
        };
      });
    },
    [setNodes],
  );

  const handleNodeComplete = useCallback(
    (data: SSENodeComplete) => {
      const { id, confidence, metadata } = data;
      setNodes((prev) =>
        prev.map((n) => {
          if (n.id !== id) return n;
          return {
            ...n,
            data: { ...n.data, streaming: false, confidence },
          };
        }),
      );

      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          nodes: prev.nodes.map((n) =>
            n.id !== id
              ? n
              : { ...n, metadata: { ...n.metadata, ...metadata, confidence } },
          ),
        };
      });
    },
    [setNodes],
  );

  const handleEdges = useCallback(
    (payload: SSEEdgesPayload) => {
      const data = payload.edges;
      const newEdges: RFEdge[] = data.map((e, i) => {
        const isMatch = e.relationship === "matches";
        const isConfirm =
          e.relationship === "compounds" || e.relationship === "causes";
        return {
          id: `sse-e-${Date.now()}-${i}-${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          label: e.relationship,
          type: "smoothstep",
          animated: true,
          markerEnd: {
            type: "arrowclosed" as const,
            color: isMatch
              ? "rgba(34, 197, 94, 0.6)"
              : "rgba(255, 255, 255, 0.3)",
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
      setEdges((prev) => [...prev, ...newEdges]);

      // Keep session edges in sync
      setSession((prev) => {
        if (!prev) return prev;
        return { ...prev, edges: [...prev.edges, ...data] };
      });
    },
    [setEdges],
  );

  const handleLayerComplete = useCallback((data: SSELayerComplete) => {
    setSession((prev) => {
      if (!prev) return prev;
      return { ...prev, current_layer: data.layer };
    });
    log.info("Layer", data.layer, "complete:", data.controller.summary);
  }, []);

  const handleSessionComplete = useCallback((data: SSESessionComplete) => {
    setSession((prev) => {
      if (!prev) return prev;
      return { ...prev, status: data.status as ThinkingSession["status"] };
    });
    setIsPending(false);
    log.info("Session complete:", data.status);
  }, []);

  // Wire SSE hook — active only during "thinking" status
  const { connected } = useSSESession(
    session?.status === "thinking" ? sessionId : null,
    {
      onNodeStart: handleNodeStart,
      onNodeText: handleNodeText,
      onNodeComplete: handleNodeComplete,
      onEdges: handleEdges,
      onLayerComplete: handleLayerComplete,
      onSessionComplete: handleSessionComplete,
      onError: (err) =>
        log.error("SSE error:", err.error ?? err.message ?? String(err)),
    },
  );

  const isThinking = session?.status === "thinking" || isPending;

  // Polling fallback — only when SSE is not connected
  useEffect(() => {
    if (connected || session?.status !== "thinking") return;
    const interval = setInterval(() => loadSessionIncremental(), 2000);
    return () => clearInterval(interval);
  }, [connected, session?.status, loadSessionIncremental]);

  // Step to next layer
  const handleStep = useCallback(async () => {
    if (isThinking || !session) return;
    setIsPending(true);
    log.info("Stepping to layer", session.current_layer + 1);
    try {
      await graphApi.thinkStep(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Step failed:", err);
    }
    setIsPending(false);
  }, [sessionId, session, isThinking, loadSessionIncremental]);

  // Match against value pool
  const handleMatch = useCallback(async () => {
    if (isThinking || !session) return;
    setIsPending(true);
    log.info("Matching against value pool");
    try {
      await graphApi.matchValues(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Match failed:", err);
    }
    setIsPending(false);
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

      {/* Agent face: only while thinking AND before any effect nodes arrive */}
      {isThinking &&
        !nodes.some(
          (n) =>
            (n.data as Record<string, unknown>).layer !== undefined &&
            ((n.data as Record<string, unknown>).layer as number) > 0,
        ) && (
          <div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 pointer-events-none"
            style={{ opacity: 0.4 }}
          >
            <AgentFace size={80} />
          </div>
        )}

      {/* React Flow graph */}
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
