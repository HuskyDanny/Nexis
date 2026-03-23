# React Flow Hooks Require ReactFlow Parent

## The Trap
Using `useReactFlow()` in a component that's a child of `ReactFlowProvider` but NOT inside `<ReactFlow>`. This silently crashes React with a blank screen — no useful error message.

## The Solution
`useReactFlow()` must be inside a component rendered as a child of `<ReactFlow>`, not just `<ReactFlowProvider>`. For fitView from outside, use `onInit` to capture the instance ref:

```tsx
const rfInstance = useRef<ReactFlowInstance | null>(null);
<ReactFlow onInit={(instance) => { rfInstance.current = instance; }} />
// Later: rfInstance.current?.fitView({ padding: 0.15 })
```

## Context
- **When this applies:** Any React Flow interactive behavior needing fitView, zoom, or viewport control
- **Related files:** `frontend/src/components/ThinkingView.tsx`
- **Discovered:** 2026-03-20, blank screen after adding ReactFlowProvider + useReactFlow
