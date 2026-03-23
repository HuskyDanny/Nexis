# Thinking Pipeline Redesign — Multi-Agent Loop with Per-Layer Matching

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Backend thinking pipeline (`backend/src/agents/`, `backend/src/services/`, `backend/src/api/thinking.py`) + frontend loading UX

---

## Problem Statement

The current thinking pipeline has fundamental architectural issues:

1. **Context degradation** — each layer only sees its immediate parents. By Layer 3, content is recursive template nesting ("Impact on X: Impact on X: Impact on X: ...") with no access to original news or reasoning chains.
2. **Single-pass, no verification** — each layer produces effects in one shot. No hypothesis testing, no information gathering, no confidence assessment.
3. **Matching only at the end** — opportunities are discovered only after all layers complete. Obvious direct matches at Layer 1 are missed until Layer 3 finishes.
4. **No termination intelligence** — fixed `max_depth` with no assessment of whether deeper reasoning is productive.
5. **Silent mock fallback** — when the LLM fails, the system silently falls back to naive sector-grouping mock logic, producing useless output with no user feedback.

## Design

### Architecture: Three-Agent Pipeline Per Layer

Each layer executes three specialized agents in sequence:

```
Layer N:
  Thinker ──→ Matcher ──→ Controller
     │            │            │
     │            │            ├─ continue=true → Layer N+1
     │            │            └─ continue=false → DONE
     │            │
     │            └─ matches at THIS layer (not final layer)
     │
     └─ causal effects + confidence scores + information gaps
```

The **Controller** produces a running chain summary that feeds into the next Thinker — this is the key mechanism that prevents context degradation.

### Agent Definitions

#### Thinker (Causal Reasoning)

**Role:** Trace cause-effect chains one step deeper.

**Input:**
- `chain_summary` (str) — Controller's narrative from previous layer ("" for Layer 1)
- `parent_nodes` (list) — all selected nodes from Layers 0 through N-1 (effects, news, fetches). Full detail: id, content, reasoning, confidence, metadata.
- `news_pool` (list) — top 20 news items (id, title, summary). Available for reference or "fetching" into the graph.
- `layer_number` (int)

**Output (JSON):**
```json
{
  "effects": [
    {
      "content": "Housing construction slows as mortgage rates exceed 7%",
      "reasoning": "Fed rate hike -> interbank rates rise -> mortgage lenders increase rates -> demand drops below affordability threshold",
      "confidence": 82,
      "parent_ids": ["abc123", "def456"],
      "sector": "real_estate",
      "fetched_news_ids": ["av-12345"],
      "information_gaps": ["Need housing starts data to confirm demand decline"]
    }
  ]
}
```

**Skills (6):** macro_economics, geopolitical_risk, sector_rotation, regulatory_impact, supply_chain, consumer_behavior

**Key behaviors:**
- Starts from broadest scope (macro) and works downward
- Each effect has a confidence score (0-100) that naturally decays with causal depth
- Reports information gaps — future: triggers targeted data fetching
- Can reference any news from the pool (creates fetch nodes in the graph)

#### Matcher (Valuation Assessment)

**Role:** Check if any effects at this layer connect to value pool stocks.

**Input:**
- `effects` (list) — this layer's effects from Thinker (content, reasoning, confidence)
- `value_pool` (list) — all value stocks (ticker, sector, discount_pct, summary)

**Output (JSON):**
```json
{
  "matches": [
    {
      "ticker": "XOM",
      "effect_id": "eff-abc",
      "sentiment_score": 75,
      "agreement_score": 80,
      "reasoning": "Energy sector benefits from supply disruption. XOM at 22% discount with strong FCF provides margin of safety."
    }
  ]
}
```

**Skills (3):** company_fundamentals, technical_momentum, sector_rotation (shared with Thinker)

**Key behaviors:**
- Only includes high-confidence matches
- Convergence score computed deterministically: `sentiment*0.3 + discount*0.3 + agreement*0.4`
- Matches are attached to the same layer as their parent effect (layers = causal depth, not pipeline stages)

#### Controller (Meta-Reasoning)

**Role:** Evaluate reasoning quality and decide whether to continue.

**Input:**
- `chain_summary` (str) — previous summary (or original news descriptions for Layer 1)
- `this_layer_effects` (list) — Thinker output (content, confidence)
- `this_layer_matches` (list) — Matcher output (count, avg quality)
- `layer_number` (int), `max_depth` (int)

**Output (JSON):**
```json
{
  "continue": true,
  "reasoning": "Layer 2 found 3 second-order effects with avg confidence 74. Found 1 match (XOM). Causal chains into construction and consumer spending remain unexplored.",
  "summary": "Starting from Fed 75bps hike and tech wage inflation: L1 identified credit tightening (conf 88), tech margin pressure (85), energy shift (72). L2 traced credit tightening -> mortgage spike -> housing slowdown (78). Matched XOM via energy disruption. Unexplored: construction supply chain, consumer contraction."
}
```

**Skills:** None. Pure meta-reasoning.

**Termination conditions (any triggers stop):**
- Controller says `continue: false` (low novelty or high speculation)
- All effects at this layer have confidence below threshold
- Max depth reached (default 5)
- No new effects produced by Thinker

### DAG Structure

**Node types:** news (Layer 0), effect (any layer), fetch (any layer), opportunity (any layer)

**Edge types:**
- `causes` — news -> Layer 1 effect
- `compounds` — effect/fetch -> deeper effect
- `fetched_for` — parent -> fetch node
- `matches` — effect -> opportunity

**Parent constraint:** `parent.layer < child.layer` (strict, preserves acyclic property)

**Cross-branch parenting:** Any node at any earlier layer can parent any node at a later layer. A Layer 2 effect can have parents from Layer 0 (news), Layer 1 (effects), and Layer 1 (fetch nodes) simultaneously. The Thinker receives ALL selected nodes from all prior layers and decides which combinations cause each new effect.

**Opportunity placement:** Opportunities attach at the layer where the match was found. A Layer 1 direct match and a Layer 3 deep match are visually and structurally distinct in the DAG.

### Layer-to-Layer Data Flow

```
INIT:
  seeds = selected news (Layer 0)
  chain_summary = ""
  all_matches = []
  graph = DAG(nodes=seeds, edges=[])

LOOP (layer = 1 to max_depth=5):
  parent_nodes = all selected nodes from Layers 0..N-1

  effects, fetch_nodes = Thinker(chain_summary, parent_nodes, news_pool, layer)
  matches = Matcher(effects, value_pool)
  decision = Controller(chain_summary, effects, matches, layer, max_depth)

  Add effects + fetch_nodes + matches to DAG
  all_matches.extend(matches)
  chain_summary = decision.summary

  if not decision.continue:
    break

DONE: session complete with all_matches across all layers
```

**What passes between layers:**

| Data | From | To | Format |
|------|------|----|--------|
| chain_summary | Controller L(N) | Thinker L(N+1) | String — compressed narrative of full chain |
| parent_nodes | All prior layers | Thinker L(N+1) | Selected nodes: id, content, reasoning, confidence |
| news_pool | Session (constant) | Every Thinker | Top 20 items, titles + summaries |
| value_pool | Session (constant) | Every Matcher | All stocks, ticker + sector + discount |

**What does NOT pass:**
- Raw nodes from early layers are supplemented by chain_summary (not replaced — parent_nodes still has them)
- Opportunity nodes are collected separately, not fed back into thinking
- Fetch node content is absorbed into chain_summary if relevant

### Skill Assignment

| Agent | Skills | Rationale |
|-------|--------|-----------|
| Thinker | macro_economics, geopolitical_risk, sector_rotation, regulatory_impact, supply_chain, consumer_behavior | Causal chain reasoning — how events transmit through the economy |
| Matcher | company_fundamentals, technical_momentum, sector_rotation | Valuation assessment — is this stock positioned to benefit? |
| Controller | (none) | Meta-reasoning about chain quality, no domain analysis |

`sector_rotation` is shared: Thinker uses it for "where is capital flowing?", Matcher uses it for "is this stock in the receiving sector?"

Each agent sees only its assigned skills in the system prompt. The `load_skill` tool remains — agents still decide which of their available skills to load per analysis.

**Skill filtering:** `build_system_prompt(allowed_skills: list[str] | None)` in `base.py`. When provided, only those skills appear in the prompt. Each agent passes its skill list; Controller gets a custom prompt with no skills.

### Session Schema Changes

The session document gains two new fields:

```python
{
    # ... existing fields ...
    "chain_summaries": {},    # {layer_number: summary_string} — Controller output per layer
    "confidence_threshold": 35,  # configurable — below this, Controller should stop
    "status": "..."           # adds new value: "timeout" (alongside paused/thinking/error/complete/idle)
}
```

- `chain_summaries[N]` is written after Controller completes Layer N
- `chain_summaries[N-1]` is read by Thinker at start of Layer N
- On regenerate from Layer N, `chain_summaries` for layers >= N are discarded

### Duplicate Ticker Policy

A stock can match at multiple layers via different causal paths. Each match is a separate opportunity node in the DAG. A Layer 1 match ("Fed raises rates → banks benefit directly") and a Layer 3 match ("rates → housing slowdown → construction oversupply → same bank's commercial RE exposure") both appear as distinct opportunities. The frontend can group by ticker to show all causal paths leading to the same stock.

### Error Handling & Timeouts

#### Per-Agent Timeout
- 60-second timeout per CrewAI call
- 1 retry on timeout/error
- On double failure: skip agent, continue pipeline
  - Thinker fails → no new effects, Controller decides to stop
  - Matcher fails → no matches this layer, continue to next
  - Controller fails → default: continue if layer < 3, stop if >= 3

#### Pipeline-Level Timeout
- 5-minute deadline for entire `_run_pipeline()` background task
- Mechanism: wrap the task creation with `asyncio.wait_for`:
  ```python
  async def _run_with_timeout():
      try:
          await asyncio.wait_for(_run_pipeline(), timeout=300)
      except asyncio.TimeoutError:
          await col.update_one({"id": session_id}, {"$set": {"status": "timeout"}})
  asyncio.create_task(_run_with_timeout())
  ```
- On timeout: set session status to `"timeout"`, preserve all nodes/matches collected so far
- Frontend shows "Analysis timed out — showing partial results"

#### No Mock Fallback
Remove mock fallback entirely. If the LLM is down, the pipeline stops gracefully with partial results. Partial truth > complete fiction.

#### Stuck Session Cleanup
On app startup, sweep sessions stuck in `"thinking"` for >10 minutes → mark `"timeout"`.

### Bug Fixes (Bundled)

#### Fix #1: Slow Initial Load
**Backend:** Refactor inline pool loading in `get_live_pools()` to check MongoDB cache first. If today's data exists and is <2 hours old, return immediately. Only fetch live if stale/missing. Parallelize news + stocks via `asyncio.gather`.

**Frontend:** Show loading spinner while pools load.

#### Fix #3: Regenerate from Layer
"Regenerate from Layer N" means: discard all nodes at Layer N and deeper, re-run Thinker→Matcher→Controller from Layer N using current selection at Layer 0..N-1. Chain summaries up to Layer N-1 are preserved (stored per layer in session).

#### Fix: llm_config.py reads os.environ instead of settings
Change `is_llm_available()` and `_get_api_key()` to use `settings.siliconflow_api_key` from pydantic-settings.

#### Fix: Layer cache key mismatch
Store cache as nested dict `{layer: {hash: data}}`. Read and write use same structure.

### Testing Strategy

#### Unit Tests
- **Thinker:** Given parents + summary → verify effects have valid parent_ids, confidence, JSON structure
- **Matcher:** Given effects + value pool → verify matches reference valid ids, scores in range
- **Controller:** Given summary + effects + matches → verify continue/stop decision and summary content
- **Skill assignment:** Verify each agent only sees its assigned skills
- **Timeout:** Verify 60s timeout kills hung LLM calls

#### Integration Tests
- **Full pipeline:** 3 news seeds → loop → verify DAG is acyclic (parent.layer < child.layer)
- **Early termination:** Controller returns false at Layer 2 → pipeline stops, matches from L1-L2 collected
- **Max depth:** max_depth=2 → stops at Layer 2 regardless
- **Cross-branch parenting:** Effects can have parent_ids from multiple branches and layers
- **Degraded mode:** Thinker fails → pipeline stops gracefully

#### E2E
- Backend + frontend → auto-run → verify multi-layer results with real LLM
- Opportunities appear at multiple layers in DAG
- Regenerate from Layer N discards downstream and re-runs

### Migration Notes

- `thinking_crew.py` is rewritten (3 agent functions → 3 new agent functions + orchestrator)
- `thinking_service.py` mock functions removed, replaced by timeout/degraded handling
- `thinking.py` API: step endpoint changes to run full Thinker→Matcher→Controller per step
- Existing sessions in MongoDB are not migrated — they remain as-is with old schema
- Frontend DAG rendering needs minor update: opportunities can appear at any layer ring, not just outermost
