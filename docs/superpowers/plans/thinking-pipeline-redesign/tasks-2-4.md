# Tasks 2–4: Core Pipeline Implementation

Parent plan: [[2026-03-23-thinking-pipeline-redesign]]

---

## Task 2: Rewrite `thinking_crew.py` — three agent functions

**Files:**
- Rewrite: `backend/src/agents/thinking_crew.py`
- Test: `backend/tests/test_thinking_agents.py` (create)

- [ ] **Step 1: Write unit tests for `run_thinker`**

Test that given parent nodes + chain summary + news pool, it returns effects with valid structure: each effect has `content`, `reasoning`, `confidence` (0-100), `parent_ids` (subset of input IDs), `sector`, `fetched_news_ids`, `information_gaps`. Mock the CrewAI `Crew.kickoff()` to return a known JSON string.

- [ ] **Step 2: Run test — verify fail**

Run: `cd backend && python -m pytest tests/test_thinking_agents.py -v -k "thinker"` — Expected: FAIL

- [ ] **Step 3: Implement `run_thinker()`**

New function in `thinking_crew.py`. Creates Agent with role="Financial Effects Analyst", `build_system_prompt(allowed_skills=THINKER_SKILLS)`. Prompt includes `chain_summary`, parent nodes (id, content, reasoning, confidence, metadata), news pool (top 20, id+title+summary). Returns `(effect_nodes, fetch_nodes, effect_edges, fetch_edges)`. Each effect node has `confidence` as a top-level field (new schema field alongside `content`, `reasoning`).

`THINKER_SKILLS = ["macro_economics", "geopolitical_risk", "sector_rotation", "regulatory_impact", "supply_chain", "consumer_behavior"]`

Note: Remove existing `rank_and_select_news()` — it is unused in the new pipeline. Keep `convergence_score()` as the single source of truth (remove duplicate `_score` from old `thinking_service.py`).

- [ ] **Step 4: Run test — verify pass**

- [ ] **Step 5: Write unit tests for `run_matcher`**

Test that given effects + value pool, returns matches with valid `ticker`, `effect_id`, `sentiment_score`, `agreement_score`, `reasoning`. Convergence score computed correctly. Mock `Crew.kickoff()`.

- [ ] **Step 6: Run test — verify fail**

- [ ] **Step 7: Implement `run_matcher()`**

Creates Agent with role="Value Opportunity Matcher", `build_system_prompt(allowed_skills=MATCHER_SKILLS)`. Prompt includes effect nodes (content, reasoning, confidence) + value pool (ticker, sector, discount, summary). Produces opportunity nodes at same layer as parent effect. **Remove the `seen_tickers` dedup** from old code — allow multiple matches per ticker across layers (different causal paths are distinct opportunities).

`MATCHER_SKILLS = ["company_fundamentals", "technical_momentum", "sector_rotation"]`

- [ ] **Step 8: Run test — verify pass**

- [ ] **Step 9: Write unit tests for `run_controller`**

Test continue/stop decision: returns `{continue, reasoning, summary}`. When avg confidence < threshold → stop. When layer >= max_depth → stop. Otherwise → continue with updated summary.

- [ ] **Step 10: Run test — verify fail**

- [ ] **Step 11: Implement `run_controller()`**

Creates Agent with role="Thinking Chain Evaluator", custom system prompt (no skills). Input: chain_summary, effects (content+confidence), matches (count+avg scores), layer, max_depth. Returns `{continue: bool, reasoning: str, summary: str}`.

- [ ] **Step 12: Run test — verify pass**

- [ ] **Step 13: Commit**

```bash
git add backend/src/agents/thinking_crew.py backend/tests/test_thinking_agents.py
git commit -m "feat: three-agent thinking crew — Thinker, Matcher, Controller"
```

---

## Task 3: Rewrite `thinking_service.py` — pipeline orchestrator

**Files:**
- Rewrite: `backend/src/services/thinking_service.py`
- Test: `backend/tests/test_thinking_pipeline.py` (create)

- [ ] **Step 1: Write integration test for `run_layer()`**

Test that `run_layer()` calls Thinker → Matcher → Controller in sequence, returns `(effect_nodes, fetch_nodes, opportunity_nodes, all_edges, controller_decision)`. Mock all three agent functions.

- [ ] **Step 2: Run test — verify fail**

- [ ] **Step 3: Implement `run_layer()`**

```python
async def run_layer(
    chain_summary: str,
    parent_nodes: list[dict],
    news_pool: list[dict],
    value_pool: list[dict],
    layer: int,
    max_depth: int,
    confidence_threshold: float = 35,
) -> LayerResult:
```

Calls `run_thinker()` with 60s timeout + 1 retry. If Thinker fails → return empty LayerResult with `continue=False`. Calls `run_matcher()` with timeout. If Matcher fails → no matches, continue. Calls `run_controller()` with timeout. If Controller fails → default logic (continue if layer < 3).

- [ ] **Step 4: Run test — verify pass**

- [ ] **Step 5: Write integration test for `run_pipeline()`**

Test full loop: given seeds, runs layers until Controller stops or max_depth. Verify DAG acyclicity (parent.layer < child.layer). Mock agent functions to produce 2 layers then stop.

- [ ] **Step 6: Run test — verify fail**

- [ ] **Step 7: Implement `run_pipeline()`**

```python
async def run_pipeline(
    session_id: str, seeds: list[dict], news_pool: list[dict],
    value_pool: list[dict], max_depth: int, on_layer_complete: Callable,
) -> None:
```

Loop: collect parent_nodes from all prior layers, call `run_layer()`, persist via `on_layer_complete` callback. Store `chain_summaries[layer]` per layer. Terminate on Controller stop, max_depth, or empty effects.

- [ ] **Step 8: Run test — verify pass**

- [ ] **Step 9: Write test for degraded mode (Thinker fails)**

Mock Thinker to raise. Verify pipeline stops gracefully, no crash, partial results preserved.

- [ ] **Step 10: Write test verifying no mock fallback**

Verify that when `is_llm_available()` returns False, `run_layer()` returns empty results with `continue=False` — NOT mock data. The old `_mock_think_effects` and `_mock_match` are deleted.

- [ ] **Step 11: Run tests — verify pass**

- [ ] **Step 12: Commit**

```bash
git add backend/src/services/thinking_service.py backend/tests/test_thinking_pipeline.py
git commit -m "feat: pipeline orchestrator with per-layer matching and Controller termination"
```

---

## Task 4: Update API endpoints — `thinking.py`

**Files:**
- Modify: `backend/src/api/thinking.py:146-246` (think_step), `466-540` (nested _run_pipeline inside auto_think)
- Modify: `backend/src/main.py:14-28` (lifespan — stuck cleanup)
- Modify: `backend/tests/api/test_thinking_cas.py` (update mock session schema)
- Test: `backend/tests/api/test_thinking_api.py` (create)

- [ ] **Step 1: Write tests for updated `think_step()` and pipeline timeout**

Test: `think_step()` calls `run_layer()`, stores `chain_summaries[layer]` in session doc, session includes `confidence_threshold` field. Test: `auto_think()` wraps pipeline with `asyncio.wait_for(300)` — mock a slow pipeline and verify `status="timeout"`. Test: stuck session cleanup on startup marks old "thinking" sessions as "timeout".

- [ ] **Step 2: Run tests — verify fail**

- [ ] **Step 3: Update `think_step()` to call `run_layer()`**

The step endpoint now runs the full Thinker→Matcher→Controller pipeline for one layer. Store `chain_summaries` in session doc. Add `chain_summaries: {}` and `confidence_threshold: 35` to session creation schema.

- [ ] **Step 4: Update `auto_think()` — replace nested `_run_pipeline()` with `run_pipeline()` from service**

Replace the nested function with `run_pipeline()` from thinking_service. Wrap with `asyncio.wait_for(timeout=300)`. On timeout, set status `"timeout"`.

- [ ] **Step 5: Add stuck session cleanup to `main.py` lifespan startup**

After MongoDB connect, sweep `thinking_sessions` where `status="thinking"` and `created_at` > 10 min ago → set `status="timeout"`.

- [ ] **Step 6: Update `test_thinking_cas.py` mock data**

Add `chain_summaries: {}` and `confidence_threshold: 35` to mock session documents so CAS tests pass with new schema.

- [ ] **Step 7: Run all API tests**

Run: `cd backend && python -m pytest tests/api/ -v` — Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/src/api/thinking.py backend/src/main.py backend/tests/api/
git commit -m "feat: API uses new pipeline orchestrator, adds timeout and stuck cleanup"
```
