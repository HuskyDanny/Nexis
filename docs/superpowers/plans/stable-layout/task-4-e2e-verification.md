# Task 4: E2E Verification

- [ ] **Step 1: Start backend and frontend**

```bash
cd backend && MONGODB_URL="mongodb://localhost:27017/financial_agent_v2" python -m uvicorn src.main:app --port 8001 &
cd frontend && npm run dev &
```

Note: `frontend/vite.config.ts` proxy must point to `http://localhost:8001`.

- [ ] **Step 2: Test toggle stability**

1. Open `http://localhost:3000`
2. Start a session (select news, date)
3. Click "Think Deeper" to generate layer 1
4. Note the positions of all nodes
5. Click a node → deselect it via the detail panel
6. **Verify:** All nodes stay in exactly the same position. Deselected node dims but doesn't move.
7. Re-select the node
8. **Verify:** Node brightens in the same position. No layout shift.

- [ ] **Step 3: Test step stability**

1. With the same session, click "Think Deeper" again (layer 2)
2. **Verify:** Existing layer 0+1 nodes stay in place. New layer 2 nodes appear in the outer ring.
3. Click "Think Deeper" one more time (layer 3)
4. **Verify:** Layers 0-2 stay put. Layer 3 settles around them.

- [ ] **Step 4: Test match stability**

1. Click "Find Opportunities"
2. **Verify:** All existing nodes stay put. New opportunity nodes appear at the outermost ring.

- [ ] **Step 5: Revert vite proxy if needed**

If `vite.config.ts` proxy was changed to `:8001`, revert to `:8000`:

```typescript
"/api": "http://localhost:8000",
```

- [ ] **Step 6: Commit any final adjustments**
