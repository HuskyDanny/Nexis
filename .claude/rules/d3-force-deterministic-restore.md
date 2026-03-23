# d3-force: Never Re-run Simulation to Restore State

## The Trap
Saving node styles, then calling `buildThinkingGraph()` (which re-runs d3-force with random initial positions) to "restore" state on mouse leave. Nodes jump to completely new positions every time because d3-force is non-deterministic.

## The Solution
Save and restore styles directly via refs — never re-run the simulation to restore:

```tsx
// Save styles BEFORE modifying
const savedStyles = useRef(new Map());
for (const n of prev) savedStyles.current.set(n.id, { ...n.style });

// Restore from saved (no simulation)
setNodes(prev => prev.map(n => ({
  ...n, style: savedStyles.current.get(n.id) ?? n.style
})));
```

## Context
- **When this applies:** Any hover/highlight/temporary style change on d3-force-laid-out nodes
- **Related files:** `frontend/src/components/ThinkingView.tsx`, `frontend/src/lib/layout.ts`
- **Discovered:** 2026-03-21, nodes jumped positions on every mouse leave
