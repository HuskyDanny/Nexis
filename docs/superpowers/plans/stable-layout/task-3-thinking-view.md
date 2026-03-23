# Task 3: Split `ThinkingView` into Three Reload Paths

The core change. Replace single `loadSession` with three functions + `positionMap` ref.

**Files:**
- Modify: `frontend/src/components/ThinkingView.tsx:39-176`

- [ ] **Step 1: Add `positionMap` ref and `nodeStyle` import**

After existing refs (line 44), add:

```typescript
  const positionMap = useRef<Map<string, { x: number; y: number }>>(new Map());
```

Add `nodeStyle` to the import from `thinking-graph-builder.ts`:

```typescript
import {
  buildThinkingGraph,
  nodeStyle,
  LAYER_COLORS,
} from "../lib/thinking-graph-builder";
```

- [ ] **Step 2: Create helper to save positions from nodes**

Add after the `positionMap` ref:

```typescript
  const savePositions = useCallback((rfNodes: RFNode[]) => {
    for (const n of rfNodes) {
      positionMap.current.set(n.id, { x: n.position.x, y: n.position.y });
    }
  }, []);
```

- [ ] **Step 3: Modify `loadSession` to save positions after layout**

Replace existing `loadSession` (lines 56-80):

```typescript
  const loadSession = useCallback(async () => {
    try {
      const res = await graphApi.getSession(sessionId);
      const s = res.data;
      setSession(s);

      // Clear stale positions from previous session
      positionMap.current.clear();

      const { rfNodes, rfEdges } = buildThinkingGraph(s.nodes, s.edges);
      savePositions(rfNodes);
      setNodes(rfNodes);
      setEdges(rfEdges);

      setTimeout(
        () => rfInstance.current?.fitView({ padding: 0.15, duration: 400 }),
        200,
      );
      log.info("Session loaded:", s.nodes.length, "nodes,", s.edges.length, "edges");
    } catch (err) {
      log.error("Failed to load session:", err);
    }
  }, [sessionId, setNodes, setEdges, savePositions]);
```

- [ ] **Step 4: Add `refreshSession` (style-only, no layout)**

Add after `loadSession`:

```typescript
  const refreshSession = useCallback(async () => {
    try {
      const res = await graphApi.getSession(sessionId);
      const s = res.data;
      setSession(s);
      unpinPath();

      const selectedMap = new Map(s.nodes.map((n) => [n.id, n]));
      setNodes((prev) =>
        prev.map((rfNode) => {
          const tn = selectedMap.get(rfNode.id);
          if (!tn) return rfNode;
          return {
            ...rfNode,
            data: { ...rfNode.data, selected: tn.selected },
            style: nodeStyle(tn.type, tn.selected, tn.layer),
          };
        }),
      );
      log.info("Session refreshed (style-only)");
    } catch (err) {
      log.error("Failed to refresh session:", err);
    }
  }, [sessionId, setNodes, setSession, unpinPath]);
```

- [ ] **Step 5: Add `loadSessionIncremental` (incremental layout)**

Add after `refreshSession`:

```typescript
  const loadSessionIncremental = useCallback(async () => {
    try {
      const res = await graphApi.getSession(sessionId);
      const s = res.data;
      setSession(s);

      const newNodeIds = s.nodes.filter((n) => !positionMap.current.has(n.id));

      if (newNodeIds.length === 0) {
        const selectedMap = new Map(s.nodes.map((n) => [n.id, n]));
        setNodes((prev) =>
          prev.map((rfNode) => {
            const tn = selectedMap.get(rfNode.id);
            if (!tn) return rfNode;
            return {
              ...rfNode,
              data: { ...rfNode.data, selected: tn.selected },
              style: nodeStyle(tn.type, tn.selected, tn.layer),
            };
          }),
        );
        return;
      }

      const { rfNodes, rfEdges } = buildThinkingGraph(
        s.nodes, s.edges, positionMap.current,
      );
      savePositions(rfNodes);
      setNodes(rfNodes);
      setEdges(rfEdges);

      setTimeout(
        () => rfInstance.current?.fitView({ padding: 0.15, duration: 400 }),
        200,
      );
      log.info("Session loaded incrementally:", newNodeIds.length, "new nodes");
    } catch (err) {
      log.error("Failed to load session incrementally:", err);
    }
  }, [sessionId, setNodes, setEdges, setSession, savePositions]);
```

- [ ] **Step 6: Wire `handleToggle` → `refreshSession`**

```typescript
  const handleToggle = useCallback(
    async (nodeId: string, selected: boolean) => {
      try {
        await graphApi.toggleNode(sessionId, nodeId, selected);
        await refreshSession();
        setSelectedNode(null);
      } catch (err) {
        log.error("Toggle failed:", err);
      }
    },
    [sessionId, refreshSession],
  );
```

- [ ] **Step 7: Wire `handleStep` + `handleMatch` → `loadSessionIncremental`**

```typescript
  const handleStep = useCallback(async () => {
    if (isThinking || !session) return;
    setIsThinking(true);
    log.info("Stepping to layer", session.current_layer + 1);
    try {
      await graphApi.thinkStep(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Step failed:", err);
    }
    setIsThinking(false);
  }, [sessionId, session, isThinking, loadSessionIncremental]);

  const handleMatch = useCallback(async () => {
    if (isThinking || !session) return;
    setIsThinking(true);
    log.info("Matching against value pool");
    try {
      await graphApi.matchValues(sessionId);
      await loadSessionIncremental();
    } catch (err) {
      log.error("Match failed:", err);
    }
    setIsThinking(false);
  }, [sessionId, session, isThinking, loadSessionIncremental]);
```

- [ ] **Step 8: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ThinkingView.tsx
git commit -m "feat: stable layout — style-only refresh on toggle, incremental on step/match

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
