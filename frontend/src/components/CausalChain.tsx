/**
 * CausalChain — vertical mini-flowchart showing the thinking path
 * from news → effects → opportunity. Rendered inside the detail panel.
 */
import type { ThinkingNode, ThinkingSession } from "../types/thinking";
import { LAYER_COLORS } from "../lib/thinking-graph-builder";

function traceChain(nodeId: string, session: ThinkingSession): ThinkingNode[] {
  const nodeMap = new Map(session.nodes.map((n) => [n.id, n]));
  const parentMap: Record<string, string[]> = {};
  for (const e of session.edges) {
    (parentMap[e.target] ??= []).push(e.source);
  }

  // BFS backward from the node to all roots
  const visited = new Set<string>();
  const chain: ThinkingNode[] = [];
  const queue = [nodeId];
  visited.add(nodeId);

  while (queue.length > 0) {
    const current = queue.shift()!;
    const node = nodeMap.get(current);
    if (node) chain.push(node);
    for (const parent of parentMap[current] ?? []) {
      if (!visited.has(parent)) {
        visited.add(parent);
        queue.push(parent);
      }
    }
  }

  // Sort by layer ascending so news comes first
  chain.sort((a, b) => a.layer - b.layer);
  return chain;
}

export function CausalChain({
  node,
  session,
}: {
  node: ThinkingNode;
  session: ThinkingSession;
}) {
  const chain = traceChain(node.id, session);
  if (chain.length <= 1) return null;

  return (
    <div className="causal-chain">
      <div className="causal-chain__label">Thinking Chain</div>
      <div className="causal-chain__flow">
        {chain.map((n, i) => {
          const color =
            n.type === "opportunity"
              ? "#22c55e"
              : LAYER_COLORS[Math.min(n.layer, LAYER_COLORS.length - 1)];
          const isLast = i === chain.length - 1;
          return (
            <div key={n.id} className="causal-chain__step">
              <div
                className="causal-chain__card"
                style={{
                  borderColor: `${color}40`,
                  background:
                    n.type === "opportunity"
                      ? "rgba(34, 197, 94, 0.08)"
                      : "rgba(15, 20, 35, 0.6)",
                }}
              >
                <div className="causal-chain__header">
                  <span
                    className="causal-chain__dot"
                    style={{ background: color, boxShadow: `0 0 6px ${color}` }}
                  />
                  <span className="causal-chain__type" style={{ color }}>
                    {n.type === "news"
                      ? "NEWS"
                      : n.type === "opportunity"
                        ? "OPPORTUNITY"
                        : `L${n.layer} EFFECT`}
                  </span>
                  {typeof (
                    n.metadata?.confidence ?? n.metadata?.convergence_score
                  ) === "number" && (
                    <span className="causal-chain__conf">
                      {Math.round(
                        (n.metadata?.confidence ??
                          n.metadata?.convergence_score) as number,
                      )}
                      %
                    </span>
                  )}
                </div>
                <div className="causal-chain__text">{n.content}</div>
              </div>
              {!isLast && (
                <div className="causal-chain__arrow">
                  <svg width="12" height="20" viewBox="0 0 12 20">
                    <line
                      x1="6"
                      y1="0"
                      x2="6"
                      y2="14"
                      stroke={color}
                      strokeWidth="1"
                      strokeDasharray="3 2"
                      opacity="0.4"
                    />
                    <polygon
                      points="3,12 6,18 9,12"
                      fill={color}
                      opacity="0.5"
                    />
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
