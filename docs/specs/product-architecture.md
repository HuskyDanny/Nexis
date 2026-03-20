# Product Architecture

## The App IS the Mind Map

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

## Node Types

| Node Type | Surface Display | Visual |
|-----------|----------------|--------|
| **News Event** | Headline + timestamp | Red circle |
| **Impact** | Sector + direction arrow | Orange diamond |
| **Stock/ETF Endpoint** | Ticker + price + direction | Blue square |
| **Value Opportunity** | Ticker + "was X → now Y" | Green circle |
| **Reason** | 1-line reasoning | Gray pill |
| **Convergence** | Ticker + conviction score | Gold star (pulsing) |

## Edges

Connect nodes with labels: "impacts", "because", "confirms". Clickable for relationship explanation.

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
- Annotations persist across days — same stock tomorrow, your notes carry over

### Export (AI-Native)

**Markdown**: Full graph or selected branch → structured markdown. AI-readable, shareable.
**Image**: Client-side canvas render (html-to-image). Surface-only or expanded options.

### Error & Empty States

- **Pipeline failed**: Banner "Last analysis incomplete — some data may be missing"
- **No convergences**: Both branches shown independently + "No high-conviction signals today"
- **No news**: Value branch only + "Quiet news day"
- **First-time user**: Guided overlay (dismissable, shown once)
