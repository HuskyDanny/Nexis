# Thinking DAG Architecture Design

**Goal:** Replace the flat graph model with a multi-layer thinking DAG where each layer is an agentic reasoning step, users can intervene between layers, and the visualization uses concentric rings.

**Architecture:** DAG (directed acyclic graph) with layered nodes. Each layer transition is a CrewAI agent step. Force-directed layout with radial constraints per layer. Selective recalculation on user modifications.

**Tech Stack:** CrewAI (agent steps), d3-force with forceRadial (layout), React Flow (rendering), MongoDB (persistence)

---

## 1. Data Model

### ThinkingNode

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique node ID |
| layer | number | 0 = seed news, 1+ = effects, final = opportunities |
| type | "news" \| "effect" \| "fetch" \| "opportunity" | What this node represents |
| content | string | Summary text |
| reasoning | string | Agent's reasoning for producing this node |
| sources | string[] | URLs, tool output references |
| parents | string[] | Parent node IDs (multiple parents allowed — DAG) |
| selected | boolean | User can deselect to prune downstream paths |
| metadata | Record<string, unknown> | Ticker, sector, confidence, tool outputs, etc. |

### ThinkingEdge

| Field | Type | Description |
|-------|------|-------------|
| source | string | Parent node ID |
| target | string | Child node ID |
| relationship | string | "causes", "compounds", "fetched_for", "matches" |

### ThinkingSession

| Field | Type | Description |
|-------|------|-------------|
| id | string | Session ID |
| date | string | Date of analysis |
| market | "US" \| "CN" | Market context |
| max_depth | number | Configurable max thinking layers (e.g. 3) |
| news_pool | PoolItem[] | Available news items |
| value_pool | PoolItem[] | Available value stocks |
| nodes | ThinkingNode[] | All nodes in the DAG |
| edges | ThinkingEdge[] | All edges |
| status | "idle" \| "thinking" \| "paused" \| "complete" | Session state |
| current_layer | number | Which layer the agent is working on |

### Key Properties

- **DAG, not tree**: A child node can have multiple parents (e.g., two news items compound into one effect)
- **Layer = agentic step**: Each layer boundary represents one agent reasoning cycle
- **Selective recalculation**: Modifying a node only invalidates its downstream paths, not the entire graph

---

## 2. Pipeline Flow

The pipeline is a loop, not a fixed sequence. Each iteration = one layer of thinking.

### Step 1: SEED (Layer 0)

- Agent auto-selects highest-impact news from the news pool
- OR user manually selects news items
- Selected items become Layer 0 nodes (type: "news")

### Step 2: THINK LOOP (Layer 1 → max_depth)

For each layer:

1. **Input**: All selected nodes from previous layers
2. **Reason**: Agent analyzes effects and compounding impacts
3. **Fetch**: Agent autonomously pulls related news from pool (these appear as "fetch" type nodes — visible to user)
4. **Produce**: Agent creates new ThinkingNodes at current layer (type: "effect")
5. **Pause point**: User can review the layer results:
   - Deselect any node → downstream paths are invalidated
   - Add a node → triggers re-reasoning for affected paths only
   - Approve → continue to next layer
6. **Recalculation scope**: Only paths connected to modified nodes recompute. Unconnected branches are untouched.

### Step 3: MATCH (Final step)

- Agent receives all final-layer effect nodes
- Agent reasons about which value pool stocks are opportunities
- Produces "opportunity" type nodes linked to their full reasoning chain
- Each opportunity traces back through the DAG to its root news

### Step 4: COMPLETE

- Full DAG persisted as ThinkingSession in MongoDB
- Frontend shows concentric ring visualization
- User can continue exploring (click deeper, add nodes, re-run layers)

### CrewAI Mapping

| Step | Crew/Agent | Tools Available |
|------|-----------|----------------|
| Auto-select | News Ranker agent | news_fetch, sentiment |
| Think (each layer) | Reasoning Crew (analyst + fetcher) | news_fetch, technical, fundamental, sentiment |
| Match | Value Matcher agent | stock_screener, fundamental, technical |

Each layer = one Crew kickoff. Agent is fully autonomous within each step — decides what to fetch, how to reason, what effects to produce.

---

## 3. Frontend Visualization

### Concentric Ring Layout

- **Layer 0** (seed news): center of canvas, tight cluster
- **Layer 1** (immediate effects): ring at radius ~150px
- **Layer 2** (compounding): ring at radius ~300px
- **Layer N**: ring at radius ~150 * N px
- **Opportunities** (value matches): outermost ring, highlighted with glow

Implementation: d3-force with `forceRadial` constraint per layer. Nodes within the same ring spread freely via charge/collision forces, but are constrained to their ring's radius.

### Visual Cues

- Subtle concentric circle guides in background (like radar rings)
- Each ring has a faint label ("Effects", "Compounding", etc.)
- Node colors by type: news=blue, effect=orange, fetch=gray, opportunity=green+glow
- Edges animate outward as each layer completes
- Currently-thinking layer ring pulses gently
- Agent face at center during thinking phase

### Interaction

| Action | Behavior |
|--------|----------|
| Click node | Detail panel: reasoning, sources, parent chain |
| Right-click / long-press | Deselect node (grays out, downstream paths fade) |
| Drag from pool to ring | Add node to that layer (ring highlights on hover during drag) |
| Pause button | Stops after current layer completes |
| Reset | Returns to pool selection phase |

### Agent Transparency

When the agent fetches additional data (news, tool outputs), those results appear as visible "fetch" nodes in the graph. The user sees everything the agent sees — full transparency into the reasoning chain.

### Ring Highlight on Drag

When dragging a node toward the graph, the target ring glows/highlights to indicate which layer the node will be placed in. Drop zones are per-ring.

---

## 4. Constraints & Rules

### Acyclicity

Edges only flow from lower layer to higher layer. A Layer 2 node cannot be a parent of a Layer 1 node. This is enforced at the data layer — reject any edge where `source.layer >= target.layer`.

### Concurrency

- Operations are queued when status is "thinking"
- User modifications (deselect, add) are only accepted when status is "paused" or "idle"
- If a CrewAI step fails mid-layer, status transitions to "error" with partial nodes preserved
- User can retry from the failed layer or roll back to the previous layer

### Error Handling

Session status includes `"error"`. On failure:
- Partial nodes from the failed layer are preserved but marked `selected: false`
- Error message stored in `ThinkingSession.error: string | null`
- User can review partial results, deselect bad nodes, and retry

### Onion Layers → Reasoning Chain

The old 4-depth onion layer model (Surface → Layer 1-3) is replaced by the DAG reasoning chain. Instead of pre-computed drill-down layers per node, the user traces the reasoning by following parent edges backward through the DAG. Each node's `reasoning` + `sources` fields provide the detail that was previously in onion layers.

### Convergence Scoring

Confidence scores remain **deterministic** (formula-based, per architecture principle "LLM interprets, code calculates"). The existing weighted formula (sentiment 0.3 + discount 0.3 + agreement 0.4) is applied to opportunity nodes. The LLM reasons about *which* opportunities to surface; the code calculates *how confident* we are.

---

## 5. Selective Recalculation

### Rules

1. **Deselect a node**: Set `selected = false`. Find all descendants (nodes reachable via edges from this node). Mark them as invalidated. Re-run the think step for the affected layer with remaining selected parents.

2. **Add a node**: Insert at target layer. Re-run the think step for that layer and all subsequent layers, but ONLY for paths that include this new node as an ancestor.

3. **Unaffected paths**: Any branch that doesn't include the modified node as an ancestor remains unchanged.

### Implementation

- Each node stores its `parents[]` — trace ancestry via BFS/DFS
- On modification, compute the "dirty set" = all descendants of modified node
- Re-run CrewAI only for dirty nodes' layers
- Replace dirty nodes with new agent outputs, preserve clean nodes

---

## 6. API

### Endpoints

| Endpoint | Method | Request Body | Response |
|----------|--------|-------------|----------|
| /api/thinking | POST | `{ date, market, max_depth?, selected_news_ids? }` | `{ session_id, status }` |
| /api/thinking/:id | GET | — | Full `ThinkingSession` |
| /api/thinking/:id/step | POST | `{ }` (executes next layer) | `{ status, current_layer }` |
| /api/thinking/:id/node/:nodeId | PATCH | `{ selected: boolean }` | `{ dirty_count, status }` |
| /api/thinking/:id/match | POST | `{ }` | `{ opportunities: ThinkingNode[] }` |
| /api/thinking/:id/events | GET (SSE) | — | Server-Sent Events stream |

### Real-Time Events (SSE)

`GET /api/thinking/:id/events` returns an SSE stream:

| Event | Data | When |
|-------|------|------|
| `layer_started` | `{ layer: number }` | Agent begins a layer |
| `node_created` | `{ node: ThinkingNode }` | Agent produces a node |
| `layer_complete` | `{ layer: number, node_count: number }` | Layer finished |
| `thinking_error` | `{ layer: number, error: string }` | Agent step failed |
| `match_complete` | `{ opportunities: ThinkingNode[] }` | Value matching done |

### Phase 2 Scope (deferred)

- `POST /api/thinking/:id/node` — user-added nodes (deferred per review recommendation — ship core loop first, add node insertion later)

### Existing Endpoints (unchanged)

- GET /api/pools/:date — still serves news and value pools
- GET /api/health — unchanged

---

## 7. Migration from Current Model

The current flat DailyGraph/Node/Edge model is replaced by ThinkingSession. The existing graph API can remain for backward compatibility but new work uses the thinking API.

| Current | New |
|---------|-----|
| DailyGraph | ThinkingSession |
| Node (flat) | ThinkingNode (layered, with parents) |
| Edge (flat) | ThinkingEdge (with relationship type) |
| Pipeline runs once | Pipeline loops per layer, pausable |
| Static convergence detection | Agent-driven opportunity matching |
