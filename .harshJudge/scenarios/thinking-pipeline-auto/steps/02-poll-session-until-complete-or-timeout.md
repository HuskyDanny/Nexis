# Step 02: Poll session until complete or timeout

## Description


## Preconditions


## Actions
GET /api/thinking/{session_id} every 10s, up to 5 minutes. Record status transitions.

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Session reaches status=complete or status=timeout. Should NOT be stuck in thinking forever.
