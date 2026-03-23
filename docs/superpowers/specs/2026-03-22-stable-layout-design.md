# Stable Graph Layout on Toggle and Step

## Problem

Every time a node is toggled (deselect/re-select) or new nodes are added (step/match), `loadSession()` calls `buildThinkingGraph()` which runs `layoutGraph()` from scratch with random initial positions. The entire graph shuffles, making it impossible to track what changed.

## Core Rule

**Once a node has a position, it keeps it.** New nodes are positioned relative to existing fixed nodes.

## Scenarios

### 1. Toggle (deselect/re-select) — NO re-layout

- Re-fetch session data from backend
- Call `setSession(updatedSession)` so `usePathHighlight` and other hooks see fresh `selected` values
- Update `selected` property and visual style on existing nodes (opacity, border, color)
- If a path is currently pinned, unpin it first to avoid highlight styles conflicting with the toggle style update
- Do NOT call `buildThinkingGraph()` / `layoutGraph()`
- Positions stay exactly the same

### 2. Step (add new layer) — INCREMENTAL layout

- Re-fetch session data
- Identify new nodes (IDs not in current `positionMap`)
- Run `layoutGraph()` with existing nodes pinned via `fx`/`fy` (d3-force fixed positions)
- New nodes settle organically around fixed anchors
- After simulation, save new positions to `positionMap`

### 3. Match (add opportunities) — INCREMENTAL layout

Same as step: existing nodes pinned, new opportunity nodes positioned.

### 4. Reset (new session) — FULL layout

- Clear `positionMap` entirely
- Next `loadSession` runs full layout from scratch (all nodes are new)

**Degenerate case:** When ALL nodes are new (initial load, or empty `positionMap`), `fixedPositions` is empty so every node gets random initial positions and no `fx`/`fy`. This falls back to current behavior — no special case needed.

## Implementation

### Position Map

A `useRef<Map<string, {x: number, y: number}>>` in `ThinkingView` that persists node positions across reloads. Populated after every layout run. Survives re-renders.

### Modified `layoutGraph`

Add an optional `fixedPositions` parameter to `LayoutOptions`:

```typescript
interface LayoutOptions {
  // ... existing fields ...
  /** Pre-existing node positions to pin during simulation */
  fixedPositions?: Map<string, { x: number; y: number }>;
}
```

In the simulation setup, if a node has a fixed position, set `fx`/`fy`:

```typescript
const simNodes: ForceNode[] = nodes.map((n) => {
  const fixed = fixedPositions?.get(n.id);
  return {
    id: n.id,
    x: fixed?.x ?? center.x + (Math.random() - 0.5) * 50,
    y: fixed?.y ?? center.y + (Math.random() - 0.5) * 50,
    fx: fixed?.x,  // undefined = free, number = pinned
    fy: fixed?.y,
  };
});
```

d3-force natively respects `fx`/`fy` — pinned nodes don't move during simulation.

### Modified `ThinkingView`

Replace the single `loadSession` with two paths:

**`loadSession` (full rebuild):** Called on initial mount. Runs `buildThinkingGraph()`, saves all positions to `positionMap`.

**`refreshSession` (style-only update):** Called after toggle. Fetches session, calls `setSession()` with fresh data (critical for `usePathHighlight` which reads `session` state), updates node styles and `data.selected` without changing positions. Unpins any active path highlight before applying style updates. No layout.

**`loadSessionIncremental` (incremental layout):** Called after step/match. Fetches session, detects new nodes, runs `layoutGraph` with `fixedPositions` for existing nodes. Saves new positions.

### Modified `buildThinkingGraph`

Add optional `fixedPositions` parameter that passes through to `layoutGraph`.

## Affected Files

| File | Change |
|------|--------|
| `frontend/src/lib/layout.ts` | Add `fixedPositions` to `LayoutOptions`, set `fx`/`fy` on sim nodes |
| `frontend/src/lib/thinking-graph-builder.ts` | Pass `fixedPositions` through to `layoutGraph` |
| `frontend/src/components/ThinkingView.tsx` | Add `positionMap` ref, split `loadSession` into 3 paths, wire toggle → `refreshSession`, step/match → `loadSessionIncremental` |

## Position Map Population

`positionMap` is populated from the `layoutGraph` return value — the positioned `RFNode[]` array (layout.ts lines 107-113). Extract `node.position` for each node after layout completes.

## What Does NOT Change

- `layout.ts` force parameters (charge, link distance, radial)
- Node styling logic (`nodeStyle` function)
- Edge styling
- `usePathHighlight` hook internals (but note: it depends on `session` state being fresh, which `refreshSession` ensures)
- Backend API calls
