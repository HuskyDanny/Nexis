# Step 03: Verify real reasoning quality

## Description


## Preconditions


## Actions
GET /api/thinking/{session_id}. Inspect effect nodes at layer 1.

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Effect nodes have: (1) reasoning field with substantive causal chains (not template text like 'Compound effect from N sources'), (2) confidence scores (0-100), (3) information_gaps in metadata.
