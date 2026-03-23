# Step 03: GET pools with include_stale=true

## Description


## Preconditions


## Actions
GET http://localhost:8000/api/pools/2026-03-22?market=US&include_stale=true

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Response has news_entities with 2 entities (active + stale)
