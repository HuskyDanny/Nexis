# SSE Streaming for Thinking Pipeline

**Issue:** #16 — Replace polling with SSE for auto-run progress
**Date:** 2026-03-26
**Status:** Approved

## Problem

The auto-run thinking pipeline uses 2-second HTTP polling to track progress. This adds 0-2s latency to node appearance, floods backend logs with redundant GET requests, and provides a poor user experience — users stare at a static screen for 20-40s per layer, then see all nodes appear at once.

An SSE endpoint exists (`GET /api/thinking/{id}/events`) but is unused by the frontend and internally polls MongoDB every 0.5s (polling-disguised-as-SSE).

## Solution

Replace polling with true SSE streaming powered by LLM token-level streaming. Nodes appear on the graph **as the LLM generates them**, with content filling in word-by-word. The experience is similar to watching ChatGPT stream a response, but manifested as graph nodes.

## Architecture

### Backend: Streaming Pipeline

#### LLM Streaming

The thinker agent (the slow part, 20-40s per layer) switches from CrewAI's `crew.kickoff()` (batch) to **direct LiteLLM streaming** calls with the same prompt and system message. SiliconFlow's OpenAI-compatible API supports `stream=True`.

The matcher and controller agents stay on CrewAI `kickoff()` — they're fast (<5s each) and don't benefit from streaming.

#### Sync/Async Boundary

Currently `run_layer()` wraps synchronous CrewAI calls in `loop.run_in_executor()`. The new streaming path introduces `run_layer_streaming()` — a **natively async** function that calls `litellm.acompletion(stream=True)` directly. No executor needed.

Both functions coexist:
- **`run_layer()`** (sync via executor) — used for manual step mode (`POST /thinking/{id}/step`)
- **`run_layer_streaming()`** (async, pushes to queue) — used for auto-run mode (`POST /thinking/auto`)

The `run_pipeline()` loop calls `run_layer_streaming()` instead of `run_layer()` when in auto-run mode. The `on_layer_complete` callback is replaced by direct `queue.put()` calls from within `run_layer_streaming()`.

#### Incremental JSON Parsing

As LLM tokens arrive, an incremental parser (using `json-repair` — **new dependency, to be added to `pyproject.toml`**) attempts to extract complete node objects from the partial JSON. The parser must handle:

- **Nested arrays:** The thinker returns `{"effects": [{...}, {...}]}`. The parser tracks bracket depth to detect when a complete object within the `effects` array closes, not when the outer object closes.
- **Markdown fencing:** LLMs may wrap output in ` ```json ... ``` ` despite the prompt saying "Return ONLY valid JSON." The parser strips markdown fences from the stream prefix before attempting JSON parsing.

```
LLM stream: {"effects": [{"content": "Fed rate pause signals...
                          ↑ parser detects first node starting

LLM stream: ..."confidence": 78, "parent_ids": ["seed1"]}
                                                          ↑ first node complete → emit
```

Each complete field update is emitted as a word-level delta to the frontend.

#### Session Event Queue

Each active auto-run session gets an `asyncio.Queue`. The pipeline task pushes events into the queue; the SSE endpoint awaits events from it.

```
Pipeline task → queue.put(event) → SSE endpoint → queue.get() → browser
```

Zero polling. Instant delivery. The queue is created when auto-run starts and cleaned up when the session completes or the SSE client disconnects.

**Queue registry:**
```python
_session_queues: dict[str, asyncio.Queue] = {}
```

**Lifecycle sequencing:** The queue is created in `auto_think()` **before** `asyncio.create_task()` launches the pipeline. This guarantees no events are lost — the pipeline can push immediately, and the SSE endpoint attaches to the existing queue. If no queue exists when the SSE endpoint connects (session already complete), replay from MongoDB.

**Cancellation:** The `asyncio.Task` handle is stored alongside the queue in the session registry. On SSE disconnect or explicit cancel request, `task.cancel()` is called. The pipeline catches `asyncio.CancelledError` and cleans up gracefully (persists any completed layers to MongoDB before exiting).

```python
_session_registry: dict[str, SessionEntry] = {}

@dataclass
class SessionEntry:
    queue: asyncio.Queue
    task: asyncio.Task
    created_at: float
```

**Memory guard:** If a queue exceeds 500 items (consumer disconnected but producer keeps pushing), log a warning, cancel the pipeline task, and clean up the session. A periodic health check (every 30s) logs total queue count and any queues above 100 items.

```python
MAX_QUEUE_SIZE = 500
WARN_QUEUE_SIZE = 100

async def _queue_health_check():
    """Periodic check — runs every 30s while any sessions are active."""
    for sid, entry in list(_session_registry.items()):
        q = entry.queue
        if q.qsize() > MAX_QUEUE_SIZE:
            log.error("Session %s queue overflow (%d items) — cancelling session", sid, q.qsize())
            entry.task.cancel()
            del _session_registry[sid]
        elif q.qsize() > WARN_QUEUE_SIZE:
            log.warning("Session %s queue backpressure: %d items", sid, q.qsize())
    if _session_registry:
        log.info("Active SSE sessions: %d, total queued events: %d",
                 len(_session_registry),
                 sum(e.queue.qsize() for e in _session_registry.values()))
```

### SSE Event Protocol

All events use standard SSE format (`event:`, `data:`, `id:` fields).

#### Event Types

```
event: node_start
id: layer:1:node:0
data: {"id": "abc123", "layer": 1, "type": "effect", "parent_ids": ["seed1"]}

event: node_text
id: layer:1:node:0:text:5
data: {"id": "abc123", "field": "content", "delta": "Fed rate pause "}

event: node_text
id: layer:1:node:0:text:12
data: {"id": "abc123", "field": "reasoning", "delta": "The 25bp hold despite "}

event: node_complete
id: layer:1:node:0:done
data: {"id": "abc123", "confidence": 78, "metadata": {"sector": "economy_macro", "information_gaps": [...]}}

event: edges
id: layer:1:edges
data: [{"source": "seed1", "target": "abc123", "relationship": "causes"}, ...]

event: layer_complete
id: layer:1:complete
data: {"layer": 1, "controller": {"continue": true, "reasoning": "...", "summary": "..."}}

event: session_complete
id: session:complete
data: {"status": "complete"}

event: error
id: error
data: {"message": "Thinker agent timed out", "layer": 1}
```

#### Event Sequencing Per Layer

```
[thinker streams — slow, 20-40s]
  node_start → node_text... → node_complete   (repeat per node)

[matcher runs — fast, ~5s]
  node_start → node_complete                   (opportunity nodes, no streaming)
  edges                                         (cause + match edges)

[controller runs — fast, ~3s]
  layer_complete                                (continue/stop decision)
```

### Frontend: Streaming Graph with Animations

#### New Hook: `useSSESession(sessionId)`

Manages `EventSource` lifecycle and exposes an event-driven API:

- Opens `EventSource` to `/api/thinking/{sessionId}/events`
- Dispatches events to handler callbacks
- Handles reconnection with `Last-Event-ID` replay
- Falls back to 2s polling after 3 failed connection attempts (15s total)

#### Node Entrance Animation

1. **`node_start`** → Create React Flow node at center (0, 0) with `opacity: 0`. Calculate target position on concentric ring. Animate to target via CSS `transition: all 400ms ease-out`.

2. **`node_text`** → Append delta words to displayed content. Node component re-renders with new text (like watching someone type). Content area auto-expands.

3. **`node_complete`** → Render confidence badge, sector tag. Subtle border glow animation (200ms).

4. **`edges`** → Draw edges with animated SVG `stroke-dashoffset` (line draws from source to target over 300ms). Queue edges if target node isn't visible yet.

#### Deterministic Concentric Ring Layout

During SSE streaming, positions are calculated deterministically (no d3-force). d3-force remains for initial full-session loads (reconnect replay, manual mode refresh) where all nodes are known upfront. The deterministic layout avoids re-running the force simulation on every incoming node.

```
Layer 0 (seeds): center cluster, radius = 0
Layer 1: ring at radius = 200px, nodes evenly spaced
Layer 2: ring at radius = 400px
Layer 3: ring at radius = 600px
```

Angle per node: `(index / totalInLayer) * 2π + layerRotationOffset`

Since total nodes per layer isn't known upfront, existing nodes **re-space** as new siblings arrive (smooth 200ms CSS transition — nodes scoot over to make room).

#### Stagger Timing

- Nodes appear naturally staggered by LLM generation speed (~300ms apart)
- Minimum 200ms gap enforced between `node_start` renders (prevents visual clumping if LLM bursts)
- Text streams at LLM token rate (~50-100ms per word chunk)
- Edges appear 150ms after target node reaches full opacity

#### Manual Step Compatibility

Manual `handleStep()` still works via REST. The step response (full nodes + edges) is fed through the same animation queue for consistent entrance animations. No SSE connection needed for manual mode.

### Reconnection and Fallback

#### SSE Reconnection

`EventSource` natively reconnects on connection drop. Each event has an `id` field. On reconnect, the browser sends `Last-Event-ID`. The backend replays **completed layers** from MongoDB (nodes are persisted at layer completion). Replayed events skip animation — rendered instantly at final positions.

**Mid-layer reconnection gap:** If the client disconnects while the thinker is mid-stream, individual `node_text` deltas are NOT persisted to MongoDB. On reconnect, completed layers replay from DB; the in-progress layer's streamed nodes are only available if the queue still has unconsumed events. If the queue was cleaned up, the client sees a gap until the current layer completes and is persisted. This is acceptable — the layer will finish within seconds.

#### Polling Fallback

If `EventSource` fails to connect after 3 attempts (5s timeout each), the frontend falls back to the existing 2s polling path. The polling code stays in the codebase as the fallback path.

#### Error Handling

- **LLM timeout** (60s per agent) → `error` event with layer info. Frontend shows which layer failed.
- **Partial layer** (3 of 5 nodes generated before error) → already-streamed nodes stay visible. `error` event marks layer incomplete.
- **SSE disconnect mid-stream** → reconnect replays from `Last-Event-ID`. Already-animated nodes stay in place.
- **Queue overflow** (>500 items) → session dropped, error logged, client reconnects and gets current state from MongoDB.

## Files Changed

### Backend (modify)

| File | Change |
|------|--------|
| `backend/src/api/thinking_auto.py` | Replace polling-based SSE with queue-based SSE; add queue registry, health check, reconnection replay |
| `backend/src/services/thinking_service.py` | Add `run_layer_streaming()` — direct LiteLLM calls with `stream=True` for thinker; incremental JSON parser |
| `backend/src/agents/thinking_crew.py` | Extract thinker prompt/system message into reusable constants (shared between CrewAI and direct LiteLLM path) |
| `backend/src/agents/llm_config.py` | Add `get_litellm_params()` — returns dict with model, api_key, base_url for direct LiteLLM streaming calls |

### Backend (new)

| File | Purpose |
|------|---------|
| `backend/src/services/stream_parser.py` | Incremental JSON parser — consumes token chunks, emits complete node objects and field deltas |
| `backend/src/services/session_events.py` | Session registry (queue + task handle + created_at), event types (dataclasses), health check task, cancellation, cleanup logic |

### Frontend (modify)

| File | Change |
|------|--------|
| `frontend/src/components/ThinkingView.tsx` | Replace `setInterval` polling with `useSSESession` hook; feed events through animation queue; keep polling as fallback |
| `frontend/src/lib/thinking-graph-builder.ts` | Add `concentricPosition(layer, index, total)` layout function alongside existing d3-force (force stays for initial/manual load) |
| `frontend/src/services/api.ts` | No change — REST endpoints unchanged |

### Frontend (new)

| File | Purpose |
|------|---------|
| `frontend/src/hooks/useSSESession.ts` | EventSource lifecycle, reconnection, fallback to polling |
| `frontend/src/hooks/useAnimationQueue.ts` | Stagger node entrance timing, minimum gap enforcement |
| `frontend/src/components/StreamingNode.tsx` | Custom React Flow node component with text streaming, entrance animation, expand-on-content |

### Tests

| File | Coverage |
|------|----------|
| `backend/tests/test_stream_parser.py` | Incremental JSON parsing: partial chunks → complete nodes; malformed JSON recovery; field delta emission |
| `backend/tests/test_session_events.py` | Queue lifecycle: create, put, get, cleanup on disconnect; overflow warning/drop; health check logging |
| `backend/tests/test_sse_endpoint.py` | SSE event format; reconnection replay with Last-Event-ID; error event on LLM timeout |
| `frontend/src/hooks/__tests__/useSSESession.test.ts` | EventSource mock: events → state updates; reconnection; fallback to polling |
| `frontend/src/hooks/__tests__/useAnimationQueue.test.ts` | Stagger timing; minimum gap; queue drain |
| `frontend/src/lib/__tests__/concentric-layout.test.ts` | Position calculation: layer rings, re-spacing on new node arrival |

## What Stays Unchanged

- Manual step flow (`POST /thinking/{sessionId}/step`) — same API, response fed through animation queue
- Matcher and controller agents — still CrewAI `kickoff()`, not streaming
- MongoDB persistence — same `_on_layer_complete` writes
- Node toggle/deselect cascading — same `PATCH` endpoint
- Pool loading — unrelated to thinking session streaming
- All existing REST endpoints — SSE is additive, not replacing REST

## Scaling Path

Current design handles ~10 concurrent auto-run sessions comfortably (in-memory queues, single worker). If scaling beyond that:

1. Add uvicorn workers (`--workers 4`)
2. Swap `asyncio.Queue` for Redis pub/sub (queue lives outside process)
3. Queue registry becomes Redis-backed

The event protocol and frontend code don't change — only the queue transport layer.
