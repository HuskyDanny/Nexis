# Task 2: Pass `fixedPositions` through `buildThinkingGraph`

**Files:**
- Modify: `frontend/src/lib/thinking-graph-builder.ts:61-124`

- [ ] **Step 1: Add `fixedPositions` parameter to `buildThinkingGraph`**

Change the function signature (line 61):

```typescript
export function buildThinkingGraph(
  nodes: ThinkingNode[],
  edges: ThinkingEdge[],
  fixedPositions?: Map<string, { x: number; y: number }>,
): { rfNodes: RFNode[]; rfEdges: RFEdge[] } {
```

- [ ] **Step 2: Pass `fixedPositions` to `layoutGraph` call**

Modify the `layoutGraph` call (lines 114-121) to include `fixedPositions`:

```typescript
  const layoutNodes = layoutGraph(rfNodes, rfEdges, {
    chargeStrength: -600,
    linkDistance: 150,
    collideRadius: 100,
    iterations: 150,
    layerMap,
    layerRadius: 180,
    fixedPositions,
  });
```

- [ ] **Step 3: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/thinking-graph-builder.ts
git commit -m "feat: pass fixedPositions through buildThinkingGraph to layoutGraph

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
