# Wire ALL SSE Event Types in the Frontend Hook

## The Trap
Backend pushes an SSE event type (e.g., `opportunity`) but the frontend `useSSESession` hook never adds an `addEventListener` for it. The events arrive silently and are discarded — no error, no warning. Features appear broken ("no opportunity nodes") when the data is actually flowing.

## The Solution
When adding a new SSE event type in the backend `_push()`, immediately add the corresponding:
1. `es.addEventListener("<event>", ...)` in `useSSESession.ts`
2. Callback in the `SSECallbacks` interface
3. Handler in `useSSEHandlers.ts`
4. Wire in `ThinkingView.tsx`

All four must be updated together. Check `thinking_service.py` for all `_push()` calls and verify each has a frontend listener.

## Context
- **When this applies:** Any new SSE event type added to the thinking pipeline
- **Related files:** `backend/src/services/thinking_service.py`, `frontend/src/hooks/useSSESession.ts`, `frontend/src/hooks/useSSEHandlers.ts`
- **Discovered:** 2026-04-09, opportunity nodes never appeared because `opportunity` event was never wired
