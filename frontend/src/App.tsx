import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { graphApi, type PoolItem } from "./services/api";
import { createLogger } from "./lib/logger";
import { TYPE_COLORS, DIR_ICON, type Convergence } from "./lib/graph-builder";
import { AgentFace } from "./components/AgentFace";
import { ThinkingView } from "./components/ThinkingView";

const log = createLogger("app");

function todayDate(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const DIR_COLOR: Record<string, string> = {
  bullish: "#22c55e",
  bearish: "#ef4444",
  neutral: "#6b7394",
};

/* ─── Pool Card ─── */
function PoolCard({
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
  const anim = useMemo(
    () => ({
      delay: `${Math.random() * 3}s`,
      duration: `${3 + Math.random() * 2}s`,
    }),
    [],
  );
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

/* ─── Main App ─── */
function App() {
  const [newsPool, setNewsPool] = useState<PoolItem[]>([]);
  const [valuePool, setValuePool] = useState<PoolItem[]>([]);
  const [selectedNews, setSelectedNews] = useState<Set<string>>(new Set());
  const [selectedValues, setSelectedValues] = useState<Set<string>>(new Set());
  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const [phase, setPhase] = useState<
    "pools" | "connecting" | "done" | "thinking"
  >("pools");
  const [convergences, setConvergences] = useState<Convergence[]>([]);
  const connectingRef = useRef(false);
  const rfInstance = useRef<ReactFlowInstance | null>(null);
  const [thinkingSessionId, setThinkingSessionId] = useState<string | null>(
    null,
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const date = todayDate();
    log.info("Loading live pools for", date);
    setLoading(true);
    graphApi
      .getLivePools(date)
      .then((res) => {
        setNewsPool(res.data.news);
        setValuePool(res.data.value);
        log.info(
          "Pools loaded:",
          res.data.news.length,
          "news,",
          res.data.value.length,
          "values",
        );
      })
      .catch((err) => log.error("Failed to load pools:", err))
      .finally(() => setLoading(false));
  }, []);

  const toggleNews = useCallback((id: string) => {
    setSelectedNews((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const toggleValue = useCallback((id: string) => {
    setSelectedValues((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  // Auto-run: select top news → think all layers → match (one click)
  const autoRun = useCallback(async () => {
    log.info("Auto-run: full pipeline");
    try {
      const res = await graphApi.autoThink(todayDate(), "US", 3);
      setThinkingSessionId(res.data.session_id);
      setPhase("thinking");
      log.info("Auto session started:", res.data.session_id);
    } catch (err) {
      log.error("Auto-run failed:", err);
    }
  }, []);

  // Start thinking session (manual selection)
  const startThinking = useCallback(async () => {
    if (selectedNews.size === 0) return;
    log.info("Starting thinking session with", selectedNews.size, "news");
    try {
      const newsIds = Array.from(selectedNews);
      const res = await graphApi.startThinking(todayDate(), "US", 3, newsIds);
      setThinkingSessionId(res.data.session_id);
      setPhase("thinking");
      log.info("Thinking session started:", res.data.session_id);
    } catch (err) {
      log.error("Failed to start thinking:", err);
    }
  }, [selectedNews]);

  const reset = useCallback(() => {
    setPhase("pools");
    setNodes([]);
    setEdges([]);
    setConvergences([]);
    setSelectedNews(new Set());
    setSelectedValues(new Set());
    setThinkingSessionId(null);
    connectingRef.current = false;
  }, [setNodes, setEdges]);

  return (
    <div className="h-screen w-screen flex flex-col bg-surface text-text">
      {/* TopBar */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b border-border"
        style={{
          background: "rgba(8, 11, 20, 0.9)",
          backdropFilter: "blur(12px)",
        }}
      >
        <h1
          className="text-lg font-bold tracking-wide"
          style={{ color: "#ef4444" }}
        >
          Nexis
          <span className="text-text-muted font-normal text-sm ml-2 tracking-widest uppercase">
            AI
          </span>
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-text-muted tracking-wide">
            {todayDate()}
          </span>
          <span
            className="text-xs px-2 py-0.5 rounded-full border"
            style={{
              borderColor: "rgba(255,255,255,0.08)",
              background: "rgba(255,255,255,0.04)",
              color: "#6b7394",
            }}
          >
            US
          </span>
          {phase === "connecting" && (
            <span
              className="text-xs px-2.5 py-0.5 rounded-full font-medium flex items-center gap-1.5"
              style={{
                background: "rgba(249, 115, 22, 0.12)",
                color: "#f97316",
                border: "1px solid rgba(249,115,22,0.2)",
              }}
            >
              <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
              Reasoning...
            </span>
          )}
          {phase === "done" && (
            <span
              className="text-xs px-2.5 py-0.5 rounded-full font-medium"
              style={{
                background: "rgba(34,197,94,0.12)",
                color: "#22c55e",
                border: "1px solid rgba(34,197,94,0.2)",
              }}
            >
              Complete
            </span>
          )}
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {/* News Pool — Left: always rendered, slides in on hover during graph phase */}
        <div
          className={`flex-shrink-0 border-r border-border overflow-y-auto transition-all duration-300 ${phase === "pools" ? "w-72" : "w-0 hover:w-72 group/news"}`}
          style={{
            background: "rgba(8, 11, 20, 0.85)",
            backdropFilter: "blur(12px)",
          }}
        >
          <div
            className="px-4 py-3 border-b border-border sticky top-0 z-10"
            style={{
              background: "rgba(8, 11, 20, 0.95)",
              backdropFilter: "blur(8px)",
            }}
          >
            <div className="flex items-center justify-between">
              <h2
                className="text-xs font-semibold tracking-widest uppercase"
                style={{ color: TYPE_COLORS.news_event }}
              >
                News Pool
              </h2>
              <span className="text-[10px] text-text-muted">
                {selectedNews.size} selected
              </span>
            </div>
          </div>
          <div className="p-3 flex flex-col gap-2.5">
            {newsPool.map((item) => (
              <PoolCard
                key={item.id}
                item={item}
                side="left"
                selected={selectedNews.has(item.id)}
                onSelect={toggleNews}
                floating={phase === "pools"}
              />
            ))}
          </div>
        </div>

        {/* Center — Graph or ThinkingView */}
        {phase === "thinking" && thinkingSessionId ? (
          <ThinkingView sessionId={thinkingSessionId} onReset={reset} />
        ) : (
          <div className="flex-1 relative">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
                <div className="flex flex-col items-center gap-4">
                  <div
                    className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
                    style={{
                      borderColor: "rgba(34,197,94,0.6)",
                      borderTopColor: "transparent",
                    }}
                  />
                  <p className="text-text-muted text-xs tracking-widest uppercase">
                    Loading pools…
                  </p>
                </div>
              </div>
            )}
            {!loading && phase === "pools" && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
                <div className="flex flex-col items-center gap-6 pointer-events-auto">
                  <AgentFace size={64} />
                  <p className="text-text-muted text-sm tracking-wide">
                    Select news manually, or auto-run
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={autoRun}
                      className="px-6 py-2.5 rounded-lg text-sm font-medium tracking-wide transition-all duration-300"
                      style={{
                        background: "rgba(34, 197, 94, 0.15)",
                        color: "#22c55e",
                        border: "1px solid rgba(34,197,94,0.3)",
                        boxShadow: "0 0 20px rgba(34,197,94,0.1)",
                      }}
                    >
                      Run Auto
                    </button>
                    <button
                      onClick={startThinking}
                      disabled={selectedNews.size === 0}
                      className="px-5 py-2.5 rounded-lg text-xs font-medium tracking-wide transition-all duration-300"
                      style={{
                        background:
                          selectedNews.size > 0
                            ? "rgba(249, 115, 22, 0.15)"
                            : "rgba(255,255,255,0.03)",
                        color: selectedNews.size > 0 ? "#f97316" : "#6b7394",
                        border: `1px solid ${selectedNews.size > 0 ? "rgba(249,115,22,0.3)" : "rgba(255,255,255,0.06)"}`,
                        cursor:
                          selectedNews.size > 0 ? "pointer" : "not-allowed",
                      }}
                    >
                      {selectedNews.size > 0
                        ? `Manual (${selectedNews.size})`
                        : "Select news"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {phase === "done" && convergences.length > 0 && (
              <div
                className="absolute top-4 left-1/2 -translate-x-1/2 z-20 glass-card px-4 py-2.5 flex items-center gap-3"
                style={{ boxShadow: "0 0 30px rgba(239,68,68,0.15)" }}
              >
                <span className="text-xs text-text-muted uppercase tracking-widest">
                  Convergences:
                </span>
                {convergences.map((c) => (
                  <span
                    key={c.ticker}
                    className="text-xs px-2 py-1 rounded-full font-medium"
                    style={{
                      background: "rgba(239,68,68,0.12)",
                      color: "#fca5a5",
                      border: "1px solid rgba(239,68,68,0.2)",
                    }}
                  >
                    {c.ticker} {c.score}%
                  </span>
                ))}
              </div>
            )}

            {phase === "done" && (
              <button
                onClick={reset}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 text-xs text-text-muted hover:text-text px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                Reset
              </button>
            )}

            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onInit={(instance) => {
                rfInstance.current = instance;
              }}
              fitView={phase !== "pools"}
              fitViewOptions={{ padding: 0.05 }}
              minZoom={0.3}
              maxZoom={2}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="rgba(255,255,255,0.03)" gap={24} size={1} />
              {(phase === "connecting" || phase === "done") && <Controls />}
            </ReactFlow>
          </div>
        )}

        {/* Value Pool — Right: slides in on hover during graph phase */}
        <div
          className={`flex-shrink-0 border-l border-border overflow-y-auto transition-all duration-300 ${phase === "pools" ? "w-72" : "w-0 hover:w-72"}`}
          style={{
            background: "rgba(8, 11, 20, 0.85)",
            backdropFilter: "blur(12px)",
          }}
        >
          <div
            className="px-4 py-3 border-b border-border sticky top-0 z-10"
            style={{
              background: "rgba(8, 11, 20, 0.95)",
              backdropFilter: "blur(8px)",
            }}
          >
            <div className="flex items-center justify-between">
              <h2
                className="text-xs font-semibold tracking-widest uppercase"
                style={{ color: TYPE_COLORS.value_opportunity }}
              >
                Value Pool
              </h2>
              <span className="text-[10px] text-text-muted">
                {selectedValues.size} selected
              </span>
            </div>
          </div>
          <div className="p-3 flex flex-col gap-2.5">
            {valuePool.map((item) => (
              <PoolCard
                key={item.id}
                item={item}
                side="right"
                selected={selectedValues.has(item.id)}
                onSelect={toggleValue}
                floating={phase === "pools"}
              />
            ))}
          </div>
        </div>
      </main>

      {/* BottomBar */}
      <footer
        className="flex items-center justify-between px-6 py-2.5 border-t border-border"
        style={{
          background: "rgba(8, 11, 20, 0.9)",
          backdropFilter: "blur(12px)",
        }}
      >
        <span className="text-xs text-text-muted tracking-wide">
          {phase === "pools" &&
            `${newsPool.length} news \u00B7 ${valuePool.length} values`}
          {phase === "connecting" && "Analyzing connections..."}
          {phase === "done" &&
            `${nodes.length} nodes \u00B7 ${edges.length} edges \u00B7 ${convergences.length} convergences`}
        </span>
        <div className="flex gap-4">
          <button className="text-xs text-text-muted hover:text-text transition-colors tracking-wide uppercase">
            Export
          </button>
          <button className="text-xs text-text-muted hover:text-text transition-colors tracking-wide uppercase">
            Search
          </button>
        </div>
      </footer>
    </div>
  );
}

export default App;
