import { useState } from "react";
import type { PoolItem } from "../services/api";
import { TYPE_COLORS, DIR_ICON } from "../lib/graph-builder";

const DIR_COLOR: Record<string, string> = {
  bullish: "#22c55e",
  bearish: "#ef4444",
  neutral: "#6b7394",
};

export function PoolCard({
  item,
  side,
  selected,
  onSelect,
  floating,
}: {
  item: PoolItem;
  side: "left" | "right";
  selected: boolean;
  onSelect: (id: string) => void;
  floating: boolean;
}) {
  const color = TYPE_COLORS[item.type] ?? "#6b7394";
  const dir = DIR_ICON[item.direction] ?? "";
  const dirColor = DIR_COLOR[item.direction] ?? "#6b7394";
  const title = item.title ?? `${item.ticker} — $${item.price}`;
  const [anim] = useState(() => ({
    delay: `${Math.random() * 3}s`,
    duration: `${3 + Math.random() * 2}s`,
  }));
  const isFloating = floating && !selected;
  const edge = `1px solid ${selected ? color : "rgba(255,255,255,0.06)"}`;
  const accent = `3px solid ${color}`;

  return (
    <button
      onClick={() => onSelect(item.id)}
      className="w-full text-left"
      style={{
        background: selected
          ? "rgba(255,255,255,0.08)"
          : "rgba(15, 20, 35, 0.7)",
        backdropFilter: "blur(8px)",
        borderTop: edge,
        borderBottom: edge,
        borderLeft: side === "left" ? accent : edge,
        borderRight: side === "right" ? accent : edge,
        borderRadius: 10,
        padding: "10px 14px",
        boxShadow: selected ? `0 0 20px ${color}30` : "none",
        transition: "border-color 0.3s, box-shadow 0.3s, background 0.3s",
        animation: isFloating
          ? `float ${anim.duration} ease-in-out ${anim.delay} infinite`
          : "none",
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium" style={{ color }}>
          {item.type === "news_event" ? item.source : item.ticker}
        </span>
        <span className="text-xs" style={{ color: dirColor }}>
          {dir} {item.confidence}%
        </span>
      </div>
      <p className="text-xs text-text leading-snug">{title}</p>
      <p className="text-[10px] text-text-muted mt-1 leading-snug">
        {item.summary}
      </p>
      {item.discount_pct && (
        <span
          className="text-[10px] mt-1 inline-block px-1.5 py-0.5 rounded"
          style={{ background: "rgba(34,197,94,0.1)", color: "#22c55e" }}
        >
          {item.discount_pct}% off 52w
        </span>
      )}
    </button>
  );
}
