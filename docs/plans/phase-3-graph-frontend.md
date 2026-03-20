# Phase 3: Graph Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Interactive mind map with custom nodes, onion-layer side panel, animations, dark-first design.

**Architecture:** React Flow for graph rendering, Dagre for layout, Motion for animations, shadcn/ui + Magic UI for components.

**Tech Stack:** React Flow v12+, dagre, Motion, shadcn/ui, Magic UI, Animate UI, Tailwind v4

**Depends on:** Phase 1 (frontend shell + types)
**Parallel with:** Phase 2 (uses mock data until pipeline is ready)

---

## Tasks

| Task | Deliverable |
|------|-------------|
| 1: Custom Node Components | 6 node types (news, impact, stock, value, reason, convergence) with type-based styling |
| 2: Custom Edge Components | Labeled edges with relationship explanation on click |
| 3: Graph Layout | Dagre hierarchical layout with two root nodes (News, Value), convergence centered |
| 4: Node Detail Panel | Slide-out right panel with LayerAccordion (4 onion layers), spring animation |
| 5: Convergence Glow | Pulse animation on gold star nodes using Motion + CSS keyframes |
| 6: Graph Interactions | Hover tooltips, click-to-select, drag-to-rearrange, zoom/pan, position persistence |
| 7: Dark Mode | Tailwind dark: class strategy, dark-first palette, theme toggle with localStorage |
| 8: Staggered Animations | Node fade-in on graph load, crossfade on date switch, hover/click micro-interactions |
| 9: TopBar + BottomBar | Date picker, user menu placeholder, annotations count, export button, search |
| 10: Mock Data | Fixture graph data for development until Phase 2 pipeline is ready |

## Key Principles

- **Mock data first** — build the entire frontend against fixture data, swap to API later
- **Dark-first** — design in dark mode, light mode is secondary
- **Motion everywhere** — every state change animated (spring-based, not CSS transitions)
- **Accessible** — keyboard navigation, ARIA labels, focus rings via Radix primitives

## Detailed task breakdowns will be written when Phase 3 starts.
