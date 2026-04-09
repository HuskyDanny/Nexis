/**
 * OpportunityStrip — thin top bar showing green pips for each opportunity.
 * Expands on hover to reveal full list with ticker, conviction, and summary.
 * Hovering an item highlights the corresponding node in the graph.
 */
import { useState } from "react";
import type { ThinkingSession } from "../types/thinking";

export function OpportunityStrip({
  session,
  onHighlight,
  onClearHighlight,
}: {
  session: ThinkingSession | null;
  onHighlight: (nodeId: string) => void;
  onClearHighlight: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  if (!session) return null;
  const opps = session.nodes.filter((n) => n.type === "opportunity");
  if (opps.length === 0) return null;

  return (
    <div
      className="opp-strip"
      data-expanded={expanded}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => {
        setExpanded(false);
        onClearHighlight();
      }}
    >
      {/* Collapsed: just green pips */}
      <div className="opp-strip__bar">
        <span className="opp-strip__label">
          {opps.length} opportunit{opps.length === 1 ? "y" : "ies"}
        </span>
        <div className="opp-strip__pips">
          {opps.map((o) => (
            <span key={o.id} className="opp-strip__pip" />
          ))}
        </div>
      </div>

      {/* Expanded: full list */}
      {expanded && (
        <div className="opp-strip__list">
          {opps.map((o) => {
            const conf =
              (o.metadata?.convergence_score as number) ??
              (o.metadata?.confidence as number) ??
              0;
            const ticker = o.content.split("—")[0]?.trim() ?? o.content;
            return (
              <div
                key={o.id}
                className="opp-strip__item"
                onMouseEnter={() => onHighlight(o.id)}
                onMouseLeave={() => onClearHighlight()}
              >
                <div className="opp-strip__item-header">
                  <span className="opp-strip__ticker">{ticker}</span>
                  <span className="opp-strip__conv">{Math.round(conf)}%</span>
                </div>
                <div className="opp-strip__reasoning">
                  {o.reasoning?.slice(0, 120) || "No reasoning available"}
                  {(o.reasoning?.length ?? 0) > 120 ? "..." : ""}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
