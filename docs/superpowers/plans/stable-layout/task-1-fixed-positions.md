# Task 1: Add `fixedPositions` to `layoutGraph`

**Files:**
- Modify: `frontend/src/lib/layout.ts:25-62`

- [ ] **Step 1: Add `fixedPositions` to `LayoutOptions` interface**

In `frontend/src/lib/layout.ts`, add to the `LayoutOptions` interface after `layerRadius` (line 39):

```typescript
  /** Pre-existing positions to pin via fx/fy during simulation */
  fixedPositions?: Map<string, { x: number; y: number }>;
```

- [ ] **Step 2: Destructure `fixedPositions` in `layoutGraph`**

Add to the destructuring block (after line 54 `layerRadius = 150,`):

```typescript
    fixedPositions,
```

- [ ] **Step 3: Use `fixedPositions` when creating sim nodes**

Replace the sim node creation (lines 58-62):

```typescript
  // Create simulation nodes — pin existing positions via fx/fy
  const simNodes: ForceNode[] = nodes.map((n) => {
    const fixed = fixedPositions?.get(n.id);
    return {
      id: n.id,
      x: fixed?.x ?? center.x + (Math.random() - 0.5) * 50,
      y: fixed?.y ?? center.y + (Math.random() - 0.5) * 50,
      fx: fixed?.x,
      fy: fixed?.y,
    };
  });
```

When `fx`/`fy` are `undefined` (no fixed position), d3-force treats the node as free. When set to a number, the node is pinned at that position during simulation.

- [ ] **Step 4: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/layout.ts
git commit -m "feat: add fixedPositions support to layoutGraph via d3-force fx/fy

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
