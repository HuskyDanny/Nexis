# Frontend Architecture

## Tech Stack

| Layer | Technology | Context7 ID |
|-------|-----------|-------------|
| **Graph Rendering** | React Flow v12+ | TBD |
| **Graph Layout** | Dagre (hierarchical) | TBD |
| **Animation** | Motion (framer-motion) | `/websites/motion_dev` |
| **Components** | shadcn/ui | `/shadcn/ui` |
| **Animated Effects** | Magic UI | `/websites/magicui_design` |
| **Animated Primitives** | Animate UI | `/imskyleen/animate-ui` |
| **Styling** | Tailwind CSS v4 | `/tailwindlabs/tailwindcss.com` |
| **Accessibility** | Radix Primitives | `/websites/radix-ui_primitives` |
| **Build** | Vite + React 18+ + TypeScript | — |

## Component Hierarchy

```
App
├── AuthWrapper
└── GraphPage
    ├── TopBar (logo, date picker, user menu)
    ├── GraphCanvas (full viewport, React Flow)
    │   ├── GraphNode (custom node per type)
    │   ├── GraphEdge (labeled connections)
    │   └── ConvergenceGlow (pulse animation)
    ├── NodeDetailPanel (slide-out right)
    │   ├── LayerAccordion (expandable layers 0→3)
    │   └── AnnotationEditor (notes + tags)
    ├── BottomBar (annotations count, export, search)
    └── ExportModal (format, scope, preview)
```

## Graph Rendering: React Flow

- **Why**: First-class React integration, built-in custom nodes, pan/zoom/minimap, handles 200+ nodes, MIT license
- **Layout**: Dagre hierarchical. Two root nodes (News, Value) at top. Convergence nodes centered.
- **Custom nodes**: Each node type gets its own React component with type-based styling
- **Position persistence**: User drag positions saved per user in DB

## Graph Contract

- **Expected size**: 80-250 nodes, 100-300 edges per daily graph
- **Initial payload**: Nodes with surface layer only (< 100KB)
- **Deep layers**: Fetched on click via API (no upfront load of tool outputs)

## Animation Strategy

| Element | Technique |
|---------|-----------|
| Graph load | Staggered node fade-in (Motion `staggerChildren`) |
| Layer expand | Spring transition (Motion) |
| Convergence nodes | Subtle pulse glow (CSS keyframes + Motion) |
| Panel slide | Spring from right (Motion `AnimatePresence`) |
| Date switch | Crossfade between graphs (Motion) |
| Hover node | Scale 1.05 (Motion `whileHover`) |
| Click node | Gentle bounce (Motion spring) |

## Dark Mode

- Tailwind `darkMode: 'class'` strategy
- Dark-first design (financial apps look better dark)
- Toggle in TopBar with theme persistence (localStorage)
