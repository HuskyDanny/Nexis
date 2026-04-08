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

  return (
    <div
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "scale(1)" : "scale(0.8)",
        transition: "opacity 400ms ease-out, transform 400ms ease-out",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div
        style={{
          fontSize: 12,
          lineHeight: 1.5,
          minWidth: 140,
          maxWidth: 200,
          padding: "10px 14px",
        }}
      >
        <div>{d.label}</div>
        {d.streaming && (
          <span
            className="inline-block w-1.5 h-3 ml-0.5 bg-current animate-pulse"
            style={{ opacity: 0.6 }}
          />
        )}
        {typeof d.confidence === "number" &&
          !Number.isNaN(d.confidence) &&
          !d.streaming && (
            <div
              className="mt-1 text-[10px]"
              style={{ color: isOpp ? "#86efac" : "#9ca3af" }}
            >
              {d.confidence}% confidence
            </div>
          )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

export const StreamingNode = memo(StreamingNodeComponent);
