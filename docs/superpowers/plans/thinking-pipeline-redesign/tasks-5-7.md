# Tasks 5–7: Bug Fixes & E2E Verification

Parent plan: [[2026-03-23-thinking-pipeline-redesign]]

---

## Task 5: Fix pool cache + loading UX

**Files:**
- Modify: `backend/src/api/pools.py:52-114`
- Modify: `frontend/src/App.tsx:122-139`
- Test: `backend/tests/test_pool_cache.py` (create)

- [ ] **Step 1: Write test for cache-first pool loading**

Test: when MongoDB has today's pools with recent `cached_at` timestamp, `get_live_pools()` returns them without calling external APIs. When `cached_at` > 2 hours, fetches live.

- [ ] **Step 2: Run test — verify fail**

- [ ] **Step 3: Implement cache-first logic in `get_live_pools()`**

Add `cached_at` timestamp to pool docs on write. On read: if exists and `cached_at` < 2 hours → return immediately. Parallelize news + stocks with `asyncio.gather` when fetching live.

- [ ] **Step 4: Run test — verify pass**

- [ ] **Step 5: Add loading spinner to `App.tsx`**

Add `loading` state. Show skeleton/spinner during pool fetch. Set `loading=false` when pools arrive.

- [ ] **Step 6: Verify frontend renders loading state**

Start frontend, refresh page — spinner should show briefly, then pools appear.

- [ ] **Step 7: Commit**

```bash
git add backend/src/api/pools.py backend/tests/test_pool_cache.py frontend/src/App.tsx
git commit -m "fix: cache-first pool loading + frontend loading spinner"
```

---

## Task 6: Fix layer cache key mismatch

**Files:**
- Modify: `backend/src/api/thinking.py:198-203` (write), `310` (read)
- Test: `backend/tests/test_layer_cache.py` (create)

- [ ] **Step 1: Write unit test for cache round-trip**

Test: write a cache entry via the write path (nested dict `{str(layer): {ps_hash: {nodes, edges}}}`), read it back via the read path, verify data matches. Test both cache hit and cache miss cases.

- [ ] **Step 2: Run test — verify fail**

- [ ] **Step 3: Fix cache write to use nested dict**

Change `cache_key = f"layer_cache.{next_layer}.{ps_hash}"` to store as nested dict using `$set` with `layer_cache.{layer}` as the key prefix.

- [ ] **Step 4: Fix cache read to match**

Ensure `layer_cache.get(str(check_layer), {}).get(ps_hash)` reads from the same nested structure.

- [ ] **Step 5: Run test — verify pass**

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/thinking.py
git commit -m "fix: layer cache key structure — nested dict for consistent read/write"
```

---

## Task 7: E2E verification

- [ ] **Step 1: Restart backend with env vars**

```bash
source backend/.env && export SILICONFLOW_API_KEY PERIGON_API_KEY
MONGODB_URL="mongodb://localhost:27017/financial_agent_v2" python -m uvicorn src.main:app --port 8000
```

- [ ] **Step 2: Open http://localhost:3000, verify pool loads quickly (cached)**

- [ ] **Step 3: Auto-run a thinking session**

Verify: real LLM reasoning (not template text), matches appear at multiple layers, Controller terminates intelligently.

- [ ] **Step 4: Test regenerate from a middle layer**

Deselect a Layer 1 effect → nodes downstream disappear. Reselect → cached nodes restore.

- [ ] **Step 5: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v` — Expected: ALL PASS

- [ ] **Step 6: Final commit + summary**
