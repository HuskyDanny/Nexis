# Step 02: GET pools without stale (default)

## Description


## Preconditions


## Actions
GET http://localhost:8000/api/pools/2026-03-22?market=US

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Response has news_entities with only 1 active entity, stale entity excluded
