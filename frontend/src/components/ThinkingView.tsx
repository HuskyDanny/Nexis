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
import { buildThinkingGraph } from "../lib/thinking-graph-builder";
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

  // Toggle node selection
  const handleNodeClick = useCallback(
    async (_: React.MouseEvent, node: RFNode) => {
      if (!session) return;
      const thinkingNode = session.nodes.find((n) => n.id === node.id);
      setSelectedNode(thinkingNode ?? null);
    },
    [session],
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
      {/* Ring guides — subtle concentric circles */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none z-0"
        style={{ opacity: 0.15 }}
      >
        {Array.from({ length: maxLayer + 2 }, (_, i) => {
          const r = i * 140;
          return r > 0 ? (
            <circle
              key={i}
              cx="50%"
              cy="50%"
              r={r}
              fill="none"
              stroke="rgba(255,255,255,0.15)"
              strokeWidth={1}
              strokeDasharray="4 8"
            />
          ) : null;
        })}
      </svg>

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

      {/* Opportunities banner */}
      {session?.status === "complete" &&
        (() => {
          const opps = session.nodes.filter((n) => n.type === "opportunity");
          return opps.length > 0 ? (
            <div className="absolute top-16 left-1/2 -translate-x-1/2 z-20 glass-card px-4 py-2.5 flex items-center gap-3">
              <span className="text-xs text-text-muted uppercase tracking-widest">
                Opportunities:
              </span>
              {opps.map((o) => (
                <span
                  key={o.id}
                  className="text-xs px-2 py-1 rounded-full font-medium"
                  style={{
                    background: "rgba(34,197,94,0.12)",
                    color: "#86efac",
                    border: "1px solid rgba(34,197,94,0.2)",
                  }}
                >
                  {o.content}
                </span>
              ))}
            </div>
          ) : null;
        })()}

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

      {/* Node detail panel */}
      {selectedNode && (
        <div
          className="absolute top-4 right-4 w-80 max-h-[70vh] overflow-y-auto glass-card shadow-2xl z-30"
          style={{ boxShadow: "0 8px 40px rgba(0,0,0,0.5)" }}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div>
              <span className="text-[10px] uppercase tracking-widest text-text-muted">
                Layer {selectedNode.layer} · {selectedNode.type}
              </span>
              <h3 className="text-sm font-semibold mt-1">
                {selectedNode.content}
              </h3>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-text-muted hover:text-text"
            >
              &times;
            </button>
          </div>
          {selectedNode.reasoning && (
            <div className="px-4 py-3 border-b border-border">
              <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">
                Reasoning
              </div>
              <p className="text-xs leading-relaxed">
                {selectedNode.reasoning}
              </p>
            </div>
          )}
          {selectedNode.sources.length > 0 && (
            <div className="px-4 py-3 border-b border-border">
              <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">
                Sources
              </div>
              {selectedNode.sources.map((s, i) => (
                <p key={i} className="text-xs" style={{ color: "#ef4444" }}>
                  {s}
                </p>
              ))}
            </div>
          )}
          <div className="px-4 py-3">
            <button
              onClick={() =>
                handleToggle(selectedNode.id, !selectedNode.selected)
              }
              className="w-full px-3 py-2 rounded-lg text-xs font-medium transition-colors"
              style={{
                background: selectedNode.selected
                  ? "rgba(239,68,68,0.1)"
                  : "rgba(34,197,94,0.1)",
                color: selectedNode.selected ? "#fca5a5" : "#86efac",
                border: `1px solid ${selectedNode.selected ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)"}`,
              }}
            >
              {selectedNode.selected
                ? "Deselect (prune downstream)"
                : "Re-select"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
