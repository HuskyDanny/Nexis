# Financial Agent v2 — Design Spec

> **Status**: Draft
> **Date**: 2026-03-20
> **Author**: Allen Pan + Claude

## Vision

A daily financial investigation board visualized as an interactive mind map. The system runs overnight, captures news, performs multi-layer analysis, identifies value opportunities, and presents everything as a pre-computed graph you explore each morning.

**V1 was passive** — a chatbot you had to ask questions. You didn't use it.
**V2 is active** — it works while you sleep. You open it and the thinking is already done.

## Core Concept

### Two Branches Converge

**Branch 1: News-driven (top-down)**
News event → What sectors/stocks get impacted? → Direction (bullish/bearish) → Endpoint stocks/ETFs

**Branch 2: Value-driven (bottom-up)**
Scan for stocks that were once high, now low → Filter for unique fundamentals (inherent value floor, market position) → Why is it undervalued? → Recovery reasoning

**Convergence**: When a news event impacts a stock that's also flagged as undervalued = high-conviction signal. The mind map makes this visible as converging branches.

### Onion-Layer Depth (Every Node)

All layers are pre-computed. No loading spinners. Just click deeper.

| Layer | Content | Example |
|-------|---------|---------|
| **Surface** | 1-2 sentence summary + direction + confidence | "Fed holds rates → Financial sector bullish (82%)" |
| **Layer 1** | Key reasoning, which tools confirmed | "Lower-for-longer benefits bank margins. Sentiment: 0.72, RSI neutral" |
| **Layer 2** | Tool outputs — charts, indicators, scores | Technical chart, fundamental data table, sentiment breakdown |
| **Layer 3** | Raw sources — articles, price data | Reuters article, WSJ analysis, raw price history |

## Product Architecture

### The App IS the Mind Map

One screen. The graph is the home, the navigation, and the content. Everything else is overlays and panels.

```
┌──────────────────────────────────────────────┐
│  [Logo]  [Date Picker ◄ Today ►]  [👤 User] │  ← Minimal top bar
├──────────────────────────────────────────────┤
│                                              │
│           Interactive Mind Map               │
│           (full viewport)                    │
│                                              │
│     🔴 News ──── impacts ──── 🔵 NVDA       │
│       Branch        │                        │
│                     ├──── 🔵 AMD             │
│                     │                        │
│     🟢 Value ───────┼──── ⭐ JPM (converge) │
│       Branch        │                        │
│                     └──── 🔵 XLF             │
│                                              │
├──────────────────────────────────────────────┤
│  [🏷 Annotations: 3]  [📤 Export]  [🔍 Search] │
└──────────────────────────────────────────────┘
```

### Node Types

| Node Type | Surface Display | Visual |
|-----------|----------------|--------|
| **News Event** | Headline + timestamp | Red circle |
| **Impact** | Sector + direction arrow | Orange diamond |
| **Stock/ETF Endpoint** | Ticker + price + direction | Blue square |
| **Value Opportunity** | Ticker + "was X → now Y" | Green circle |
| **Reason** | 1-line reasoning | Gray pill |
| **Convergence** | Ticker + conviction score | Gold star (pulsing) |

### Edges

Connect nodes with labels: "impacts", "because", "confirms". Clickable to see relationship explanation.

## User Experience

### Daily Loop

1. Open app → Today's graph is ready
2. Scan — convergence nodes (gold stars) pulse to catch your eye
3. Click a convergence → see summary, reasoning from both branches
4. Peel deeper if interested → tool outputs, raw data
5. Annotate — "watching this", add a note
6. Export — share a branch as markdown or image

### Interactions

| Action | Behavior |
|--------|----------|
| **Hover node** | Surface summary tooltip |
| **Click node** | Expands Layer 1 in side panel |
| **Click deeper** | Peels to Layer 2, then Layer 3 |
| **Click edge** | Relationship label + explanation |
| **Right-click** | Context menu: annotate, export, hide, pin |
| **Scroll wheel** | Zoom in/out |
| **Drag canvas** | Pan |
| **Drag node** | Rearrange (position persists per user) |
| **Double-click empty** | Reset zoom to fit |
| **Date picker** | Switch between days |

### Annotations

- Sticky notes attached to any node
- Tags: "watching", "buying", "sold", "skeptical" (customizable)
- Annotations persist across days — same stock appears tomorrow, your notes carry over

### Export (AI-Native)

**Markdown**: Full graph or selected branch → structured markdown with headers per layer. AI-readable, pasteable into Claude/ChatGPT, shareable as newsletter.

**Image**: Render current view as PNG. Options: surface-only (clean) or expanded (with open layers). Shareable on social platforms.

## Backend Architecture

### Nightly Pipeline

```
1. NEWS COLLECTOR
   Fetch news from financial news APIs
   → Raw news events

2. VALUE SCANNER
   Scan market data for undervalued stocks
   (high-to-low, unique fundamentals, below avg P/E)
   → Raw value candidates

3. LAYER 1 ANALYSIS (per event / per candidate)
   LLM: What does this mean? What's impacted?
   → Summary, direction, affected sectors/stocks

4. LAYER 2 VERIFICATION (per impact)
   Tools: Technical indicators, sentiment scores,
   fundamental data, options flow
   → Structured tool outputs

5. LAYER 3 SOURCES
   Attach raw articles, price history, data links

6. GRAPH BUILDER
   Assemble nodes + edges + detect convergences
   Compute confidence scores on convergence nodes
   → Complete graph stored in DB

7. EXPORT PRE-RENDER
   Pre-generate markdown for each branch
   (instant export, not computed on-demand)
```

### Data Model

| Entity | Key Fields |
|--------|-----------|
| **DailyGraph** | date, status, created_at |
| **Node** | id, graph_id, type, layers[] |
| **Layer** | depth (0-3), content, tool_outputs, sources |
| **Edge** | source_node, target_node, label, relationship_type |
| **Annotation** | node_id, user_id, text, tags[], created_at |
| **Export** | graph_id, user_id, format, scope, content |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI + MongoDB + Redis |
| **Frontend** | React 18+ + TypeScript + Vite + Tailwind CSS v4 |
| **Graph Rendering** | TBD (React Flow / D3-force / Cytoscape.js) |
| **Animation** | Motion (formerly Framer Motion) |
| **Components** | shadcn/ui + Magic UI + Animate UI |
| **AI/LLM** | LangChain + LangGraph (reuse from v1) |
| **Deployment** | Docker Compose (dev), K8s (prod) |

### API (serves pre-computed data)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/graphs/:date` | Fetch daily graph (nodes + edges) |
| `GET /api/nodes/:id/layers` | Fetch all layers for a node |
| `POST /api/annotations` | Create annotation |
| `PATCH /api/annotations/:id` | Update annotation |
| `GET /api/exports/:format` | Generate/fetch export |
| `GET /api/graphs/dates` | List available graph dates |
| `POST /api/auth/*` | Auth endpoints |

## Frontend Architecture

### Component Hierarchy

```
App
├── AuthWrapper
└── GraphPage
    ├── TopBar (logo, date picker, user menu)
    ├── GraphCanvas (full viewport)
    │   ├── GraphNode (type-based styling, per node)
    │   ├── GraphEdge (labeled connections)
    │   └── ConvergenceGlow (pulse animation)
    ├── NodeDetailPanel (slide-out right)
    │   ├── LayerAccordion (expandable layers 0→3)
    │   └── AnnotationEditor (notes + tags)
    ├── BottomBar (annotations count, export, search)
    └── ExportModal (format, scope, preview)
```

### Animation Strategy

| Element | Animation |
|---------|-----------|
| Graph load | Staggered node fade-in |
| Layer expand | Spring (Motion) |
| Convergence nodes | Subtle pulse glow |
| Panel slide | Spring from right |
| Date switch | Crossfade between graphs |
| Hover node | Scale up slightly |
| Click node | Gentle bounce |

## Scope — v2 Launch

**In scope**:
- Daily mind map with news + value branches
- Convergence detection
- 4-layer onion depth on every node
- Node annotations + tags
- Markdown + image export
- Multi-user auth
- Date navigation (view previous days)

**Out of scope (future)**:
- Real-time streaming (daily batch is sufficient)
- Portfolio/broker integration
- Infinite canvas (multi-day spatial view)
- Share links (read-only graph for non-users)
- Mobile app
- Chat interface

## Success Criteria

1. You open the app daily because it's valuable
2. Every morning, the graph is ready with overnight analysis
3. You can go from "what happened?" to "what should I do?" in under 2 minutes
4. Export is instant and AI-readable
5. It looks and feels premium — fluid, interactive, modern
