# Step 02: Second call returns from cache instantly

## Description


## Preconditions


## Actions
GET /api/pools/live/2026-03-23 again. Record response time.

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Returns same data. Response time < 500ms (cache hit).
