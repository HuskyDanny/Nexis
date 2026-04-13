/**
 * Extracted UI panels for ThinkingView — node detail with causal chain.
 */
import type { ThinkingNode, ThinkingSession } from "../types/thinking";
import { LAYER_COLORS } from "../lib/thinking-graph-builder";
import { CausalChain } from "./CausalChain";

/* ─── Layer Spectrum ─── */
export function LayerSpectrum({
  session,
}: {
  session: ThinkingSession | null;
}) {
  if (!session) return null;
  const existingLayers = new Set(session.nodes.map((n) => n.layer));
  const layers = Array.from(existingLayers).sort((a, b) => a - b);
  const layerLabels: Record<string, string> = {
    news: "News",
    effect: "Effects",
    fetch: "Fetched",
    opportunity: "Opportunities",
  };

  return (
    <div className="absolute top-[52px] left-1/2 -translate-x-1/2 z-0 flex items-center gap-1">
      {layers.map((layer, idx) => {
        const layerColor =
          LAYER_COLORS[Math.min(layer, LAYER_COLORS.length - 1)];
        const nodesInLayer = session.nodes.filter((n) => n.layer === layer);
        const mainType = nodesInLayer[0]?.type ?? "effect";
        const label =
          layer === 0 ? "News" : (layerLabels[mainType] ?? `Layer ${layer}`);
        return (
          <div key={layer} className="flex items-center gap-1">
            {idx > 0 && (
              <span className="text-text-muted text-[8px]">&rarr;</span>
            )}
            <div
              className="flex items-center gap-1 px-2 py-0.5 rounded-full"
              style={{
                background: `${layerColor}15`,
                border: `1px solid ${layerColor}30`,
              }}
            >
              <div
                className="w-2 h-2 rounded-full"
                style={{ background: layerColor }}
              />
              <span className="text-[9px]" style={{ color: layerColor }}>
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ─── Opportunities Banner ─── */
export function OpportunitiesBanner({
  session,
}: {
  session: ThinkingSession | null;
}) {
  if (!session || session.status !== "complete") return null;
  const opps = session.nodes.filter((n) => n.type === "opportunity");
  if (opps.length === 0) return null;

  return (
    <div className="absolute top-24 left-1/2 -translate-x-1/2 z-20 glass-card px-4 py-2.5 flex items-center gap-3">
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
  );
}

/* ─── Node Detail Panel ─── */
export function NodeDetailPanel({
  node,
  session,
  onClose,
  onToggle,
  onRegenerate,
}: {
  node: ThinkingNode;
  session: ThinkingSession | null;
  onClose: () => void;
  onToggle: (nodeId: string, selected: boolean) => void;
  onRegenerate?: () => void;
}) {
  return (
    <div
      className="absolute top-4 right-4 w-80 max-h-[70vh] overflow-y-auto glass-card shadow-2xl z-30"
      style={{ boxShadow: "0 8px 40px rgba(0,0,0,0.5)" }}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div>
          <span className="text-[10px] uppercase tracking-widest text-text-muted">
            Layer {node.layer} &middot; {node.type}
          </span>
          <h3 className="text-sm font-semibold mt-1">{node.content}</h3>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text">
          &times;
        </button>
      </div>
      {node.reasoning && (
        <div className="px-4 py-3 border-b border-border">
          <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">
            Reasoning
          </div>
          <p className="text-xs leading-relaxed">{node.reasoning}</p>
        </div>
      )}
      {node.sources.length > 0 && (
        <div className="px-4 py-3 border-b border-border">
          <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">
            Sources
          </div>
          {node.sources.map((s, i) => (
            <p key={i} className="text-xs" style={{ color: "#ef4444" }}>
              {s}
            </p>
          ))}
        </div>
      )}
      {session && <CausalChain node={node} session={session} />}
      <div className="px-4 py-3 flex flex-col gap-2">
        <button
          onClick={() => onToggle(node.id, !node.selected)}
          className="w-full px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          style={{
            background: node.selected
              ? "rgba(239,68,68,0.1)"
              : "rgba(34,197,94,0.1)",
            color: node.selected ? "#fca5a5" : "#86efac",
            border: `1px solid ${node.selected ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)"}`,
          }}
        >
          {node.selected ? "Deselect (prune downstream)" : "Re-select"}
        </button>
        {onRegenerate && !node.selected && (
          <button
            onClick={onRegenerate}
            className="w-full px-3 py-2 rounded-lg text-xs font-medium transition-colors"
            style={{
              background: "rgba(59,130,246,0.1)",
              color: "#93c5fd",
              border: "1px solid rgba(59,130,246,0.2)",
            }}
          >
            Regenerate from this layer
          </button>
        )}
      </div>
    </div>
  );
}
