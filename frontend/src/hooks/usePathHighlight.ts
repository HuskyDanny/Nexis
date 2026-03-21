/**
 * usePathHighlight — manages hover/click path highlighting and pin/unpin
 * for the thinking graph. Extracted from ThinkingView to keep it focused on layout.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Node as RFNode, Edge as RFEdge } from "@xyflow/react";
import type { ThinkingSession } from "../types/thinking";
import { nodeStyle } from "../lib/thinking-graph-builder";

interface UsePathHighlightArgs {
  session: ThinkingSession | null;
  setNodes: React.Dispatch<React.SetStateAction<RFNode[]>>;
  setEdges: React.Dispatch<React.SetStateAction<RFEdge[]>>;
}

export function usePathHighlight({
  session,
  setNodes,
  setEdges,
}: UsePathHighlightArgs) {
  const [highlightedPath, setHighlightedPath] = useState<Set<string>>(
    new Set(),
  );
  const [pinnedNodeId, setPinnedNodeId] = useState<string | null>(null);

  // Store original styles for restore on hover leave
  const savedStyles = useRef<{
    nodes: Map<string, React.CSSProperties>;
    edges: Map<string, { style: React.CSSProperties; animated: boolean }>;
  }>({ nodes: new Map(), edges: new Map() });

  // Trace ancestor path from a node back to roots (BFS)
  const traceAncestors = useCallback(
    (nodeId: string): Set<string> => {
      if (!session) return new Set();
      const ancestors = new Set<string>();
      const queue = [nodeId];
      ancestors.add(nodeId);

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

  /** Apply highlight styles: dim non-path nodes, glow path edges */
  const applyHighlight = useCallback(
    (path: Set<string>) => {
      setNodes((prev) => {
        // Save original styles before modifying
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
    [setNodes, setEdges],
  );

  /** Restore styles from savedStyles (used by hover leave) */
  const restoreSavedStyles = useCallback(() => {
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
  }, [setNodes, setEdges]);

  // Hover enter: highlight ancestor path (opportunity nodes only)
  const handleNodeMouseEnter = useCallback(
    (_: React.MouseEvent, node: RFNode) => {
      if (!session) return;
      const thinkingNode = session.nodes.find((n) => n.id === node.id);
      if (thinkingNode?.type !== "opportunity") return;

      const path = traceAncestors(node.id);
      setHighlightedPath(path);
      applyHighlight(path);
    },
    [session, traceAncestors, applyHighlight],
  );

  // Hover leave: restore if not pinned
  const handleNodeMouseLeave = useCallback(() => {
    if (pinnedNodeId || highlightedPath.size === 0) return;
    setHighlightedPath(new Set());
    restoreSavedStyles();
  }, [pinnedNodeId, highlightedPath, restoreSavedStyles]);

  // Unpin: rebuild styles from session data (not savedStyles, which can be stale after pin)
  const unpinPath = useCallback(() => {
    setPinnedNodeId(null);
    setHighlightedPath(new Set());
    if (!session) return;

    const nodeMap = new Map(session.nodes.map((n) => [n.id, n]));
    setNodes((prev) =>
      prev.map((n) => {
        const src = nodeMap.get(n.id);
        return src
          ? { ...n, style: nodeStyle(src.type, src.selected, src.layer) }
          : n;
      }),
    );
    setEdges((prev) =>
      prev.map((e) => {
        const srcEdge = session.edges.find(
          (se) => se.source === e.source && se.target === e.target,
        );
        const isMatch = srcEdge?.relationship === "matches";
        const isConfirm =
          srcEdge?.relationship === "compounds" ||
          srcEdge?.relationship === "causes";
        return {
          ...e,
          animated: true,
          style: {
            ...e.style,
            stroke: isMatch
              ? "rgba(34, 197, 94, 0.4)"
              : isConfirm
                ? "rgba(255, 255, 255, 0.2)"
                : "rgba(107, 115, 148, 0.3)",
            strokeWidth: isMatch ? 2 : 1.5,
          },
        };
      }),
    );
  }, [session, setNodes, setEdges]);

  // Pin an opportunity node's path
  const pinPath = useCallback(
    (nodeId: string) => {
      setPinnedNodeId(nodeId);
      const path = traceAncestors(nodeId);
      setHighlightedPath(path);
      applyHighlight(path);
    },
    [traceAncestors, applyHighlight],
  );

  // Escape key: deselect and unpin
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") unpinPath();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [unpinPath]);

  return {
    pinnedNodeId,
    unpinPath,
    pinPath,
    handleNodeMouseEnter,
    handleNodeMouseLeave,
  };
}
