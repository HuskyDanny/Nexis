import { ReactFlow, Background, Controls, MiniMap } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

function App() {
  return (
    <div className="h-screen w-screen flex flex-col bg-surface text-text">
      {/* TopBar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface-alt">
        <h1 className="text-lg font-semibold text-primary">
          Financial Agent v2
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-text-muted">Today</span>
        </div>
      </header>

      {/* Graph Canvas */}
      <main className="flex-1">
        <ReactFlow
          nodes={[]}
          edges={[]}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#334155" gap={20} />
          <Controls className="!bg-surface-alt !border-border" />
          <MiniMap className="!bg-surface-alt !border-border" />
        </ReactFlow>

        {/* Empty state */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <p className="text-text-muted text-lg">No graph data yet</p>
        </div>
      </main>

      {/* BottomBar */}
      <footer className="flex items-center justify-between px-6 py-2 border-t border-border bg-surface-alt text-sm text-text-muted">
        <span>Annotations: 0</span>
        <div className="flex gap-4">
          <button className="hover:text-text transition-colors">Export</button>
          <button className="hover:text-text transition-colors">Search</button>
        </div>
      </footer>
    </div>
  );
}

export default App;
