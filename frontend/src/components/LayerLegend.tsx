/** Layer color legend for the thinking graph visualization. */

const LAYERS = [
  ["#3b82f6", "News"],
  ["#8b5cf6", "Effects L1"],
  ["#f59e0b", "Effects L2"],
  ["#ef4444", "Effects L3"],
  ["#22c55e", "Opportunities"],
] as const;

export function LayerLegend() {
  return (
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
      {LAYERS.map(([color, label]) => (
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
  );
}
