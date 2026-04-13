import { memo, useEffect, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

interface StreamingNodeData {
  label: string;
  type: string;
  layer: number;
  selected: boolean;
  reasoning: string;
  streaming?: boolean;
  confidence?: number;
}

function StreamingNodeComponent({ data }: NodeProps) {
  const d = data as unknown as StreamingNodeData;
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  const isOpp = d.type === "opportunity";
  const isNews = d.type === "news";
  const hasConf =
    typeof d.confidence === "number" &&
    !Number.isNaN(d.confidence) &&
    !d.streaming;

  return (
    <div
      className="nexis-node"
      data-type={d.type}
      data-layer={d.layer}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "scale(1)" : "scale(0.85)",
        transition: "opacity 350ms ease-out, transform 350ms ease-out",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />

      {isOpp ? (
        /* ─── Opportunity: ticker + conviction front and center ─── */
        <div className="nexis-node__opp">
          <div className="nexis-node__opp-label">{d.label}</div>
          {hasConf && (
            <div className="nexis-node__opp-conf">{d.confidence}%</div>
          )}
        </div>
      ) : (
        /* ─── News / Effect: compact pill ─── */
        <div className="nexis-node__body">
          {/* Type dot */}
          <span className="nexis-node__dot" />
          <div className="nexis-node__content">
            <div className="nexis-node__text">{d.label}</div>
            {d.streaming && <span className="nexis-node__cursor" />}
            {hasConf && !isNews && (
              <span className="nexis-node__conf">{d.confidence}%</span>
            )}
          </div>
        </div>
      )}

      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

export const StreamingNode = memo(StreamingNodeComponent);
