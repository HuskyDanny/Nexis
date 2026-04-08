/**
 * useSSEHandlers — SSE event handlers for ThinkingView streaming.
 * Manages node/edge mutations in response to SSE events from the thinking pipeline.
 */
import { useCallback } from "react";
import type { Node as RFNode, Edge as RFEdge } from "@xyflow/react";
import type {
  ThinkingNode,
  ThinkingSession,
  SSENodeStart,
  SSENodeText,
  SSENodeComplete,
  SSELayerComplete,
  SSESessionComplete,
  SSEEdgesPayload,
} from "../types/thinking";
import { nodeStyle, concentricPosition } from "../lib/thinking-graph-builder";
import { createLogger } from "../lib/logger";

const log = createLogger("sse-handlers");

interface UseSSEHandlersArgs {
  setNodes: React.Dispatch<React.SetStateAction<RFNode[]>>;
  setEdges: React.Dispatch<React.SetStateAction<RFEdge[]>>;
  setSession: React.Dispatch<React.SetStateAction<ThinkingSession | null>>;
  setIsPending: React.Dispatch<React.SetStateAction<boolean>>;
  layerNodeCounts: React.MutableRefObject<Map<number, number>>;
  positionMap: React.MutableRefObject<Map<string, { x: number; y: number }>>;
}

export function useSSEHandlers({
  setNodes,
  setEdges,
  setSession,
  setIsPending,
  layerNodeCounts,
  positionMap,
}: UseSSEHandlersArgs) {
  const handleNodeStart = useCallback(
    (data: SSENodeStart) => {
      const { id, layer, type, parent_ids } = data;
      const count = (layerNodeCounts.current.get(layer) ?? 0) + 1;
      layerNodeCounts.current.set(layer, count);
      const idx = count - 1;

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
    [setNodes, setSession, layerNodeCounts, positionMap],
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
    [setNodes, setSession],
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
    [setNodes, setSession],
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

      setSession((prev) => {
        if (!prev) return prev;
        return { ...prev, edges: [...prev.edges, ...data] };
      });
    },
    [setEdges, setSession],
  );

  const handleLayerComplete = useCallback(
    (data: SSELayerComplete) => {
      setSession((prev) => {
        if (!prev) return prev;
        return { ...prev, current_layer: data.layer };
      });
      log.info("Layer", data.layer, "complete:", data.controller.summary);
    },
    [setSession],
  );

  const handleSessionComplete = useCallback(
    (data: SSESessionComplete) => {
      setSession((prev) => {
        if (!prev) return prev;
        return { ...prev, status: data.status as ThinkingSession["status"] };
      });
      setIsPending(false);
      log.info("Session complete:", data.status);
    },
    [setSession, setIsPending],
  );

  return {
    handleNodeStart,
    handleNodeText,
    handleNodeComplete,
    handleEdges,
    handleLayerComplete,
    handleSessionComplete,
  };
}
