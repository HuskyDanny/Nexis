# SSE Streaming for Thinking Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 2-second polling with SSE streaming + LLM token-level streaming, so thinking nodes appear on the graph word-by-word as the LLM generates them.

**Architecture:** Direct LiteLLM streaming for the thinker agent (bypass CrewAI), incremental JSON parsing to extract nodes mid-stream, asyncio.Queue per session for zero-poll event delivery, deterministic concentric ring layout with CSS entrance animations on the frontend.

**Tech Stack:** LiteLLM (streaming), json-repair (incremental parsing), FastAPI StreamingResponse (SSE), React Flow (graph), EventSource (browser SSE client)

**Spec:** `docs/superpowers/specs/2026-03-26-sse-streaming-thinking-design.md`

---

## File Structure

### Backend (new files)

| File | Responsibility |
|------|---------------|
| `backend/src/services/session_events.py` | Session registry (queue + task + cleanup), SSE event dataclasses, health check |
| `backend/src/services/stream_parser.py` | Incremental JSON parser — consumes LLM token chunks, emits node objects and field deltas |

### Backend (modified files)

| File | Change |
|------|--------|
| `backend/src/agents/llm_config.py` | Add `get_litellm_params()` dict for direct LiteLLM calls |
| `backend/src/agents/thinking_crew.py` | Extract thinker prompt builder into `build_thinker_prompt()` (shared between CrewAI and streaming path) |
| `backend/src/services/thinking_service.py` | Add `run_layer_streaming()` — async, pushes events to queue |
| `backend/src/api/thinking_auto.py` | Replace polling-SSE with queue-based SSE; integrate session registry; reconnection replay; pipeline loop uses `run_layer_streaming()` |
| `backend/src/main.py` | Start periodic health check background task on startup |
| `backend/pyproject.toml` | Add `json-repair` and move `litellm` to runtime dependencies |

### Frontend (new files)

| File | Responsibility |
|------|---------------|
| `frontend/src/hooks/useSSESession.ts` | EventSource lifecycle, reconnection, fallback to polling |
| `frontend/src/hooks/useAnimationQueue.ts` | Stagger node entrance timing, minimum gap enforcement |
| `frontend/src/components/StreamingNode.tsx` | Custom React Flow node with text streaming + entrance animation |

### Frontend (modified files)

| File | Change |
|------|--------|
| `frontend/src/types/thinking.ts` | Update SSE event types to match new protocol |
| `frontend/src/lib/thinking-graph-builder.ts` | Add `concentricPosition()` for deterministic layout |
| `frontend/src/components/ThinkingView.tsx` | Replace polling with `useSSESession`; use animation queue; register `StreamingNode` |

### Test files

| File | Coverage |
|------|----------|
| `backend/tests/test_stream_parser.py` | Incremental JSON parsing |
| `backend/tests/test_session_events.py` | Queue lifecycle, overflow, cleanup |
| `backend/tests/test_streaming_layer.py` | Streaming layer runner |
| `backend/tests/test_sse_endpoint.py` | SSE event format, reconnection replay |
| `frontend/src/lib/__tests__/concentric-layout.test.ts` | Deterministic position calculation |
| `frontend/src/hooks/__tests__/useSSESession.test.ts` | EventSource mock, events, reconnection |
| `frontend/src/hooks/__tests__/useAnimationQueue.test.ts` | Stagger timing, minimum gap, drain |

---

## Task 1: Session Event Registry

**Files:**
- Create: `backend/src/services/session_events.py`
- Test: `backend/tests/test_session_events.py`

- [ ] **Step 1: Write failing tests for session registry**

```python
# backend/tests/test_session_events.py
import asyncio
import pytest
from src.services.session_events import (
    SessionRegistry,
    SessionEntry,
    SSEEvent,
    MAX_QUEUE_SIZE,
    WARN_QUEUE_SIZE,
)


class TestSessionRegistry:
    @pytest.mark.asyncio
    async def test_create_and_get(self):
        reg = SessionRegistry()
        task = asyncio.ensure_future(asyncio.sleep(100))
        entry = reg.create("sess1", task)
        assert isinstance(entry, SessionEntry)
        assert reg.get("sess1") is entry
        task.cancel()

    def test_get_missing_returns_none(self):
        reg = SessionRegistry()
        assert reg.get("nope") is None

    @pytest.mark.asyncio
    async def test_remove(self):
        reg = SessionRegistry()
        task = asyncio.ensure_future(asyncio.sleep(100))
        reg.create("sess1", task)
        reg.remove("sess1")
        assert reg.get("sess1") is None

    @pytest.mark.asyncio
    async def test_active_count(self):
        reg = SessionRegistry()
        t1 = asyncio.ensure_future(asyncio.sleep(100))
        t2 = asyncio.ensure_future(asyncio.sleep(100))
        reg.create("a", t1)
        reg.create("b", t2)
        assert reg.active_count == 2
        t1.cancel()
        t2.cancel()


class TestSSEEvent:
    def test_serialize(self):
        evt = SSEEvent(event="node_start", data={"id": "abc"}, id="layer:1:node:0")
        text = evt.serialize()
        assert "event: node_start\n" in text
        assert 'data: {"id": "abc"}\n' in text
        assert "id: layer:1:node:0\n" in text

    def test_serialize_no_id(self):
        evt = SSEEvent(event="error", data={"msg": "fail"})
        text = evt.serialize()
        assert "id:" not in text


@pytest.mark.asyncio
async def test_queue_put_and_get():
    reg = SessionRegistry()
    task = asyncio.current_task()
    entry = reg.create("sess1", task)
    evt = SSEEvent(event="test", data={"x": 1})
    await entry.queue.put(evt)
    got = await asyncio.wait_for(entry.queue.get(), timeout=1.0)
    assert got.event == "test"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_session_events.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.services.session_events'`

- [ ] **Step 3: Implement session_events.py**

```python
# backend/src/services/session_events.py
"""Session event registry — queue + task per active auto-run session."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.core.logger import get_logger

log = get_logger("session_events")

MAX_QUEUE_SIZE = 500
WARN_QUEUE_SIZE = 100


@dataclass
class SSEEvent:
    """A single SSE event to push to the client."""
    event: str
    data: Any
    id: Optional[str] = None

    def serialize(self) -> str:
        parts = [f"event: {self.event}"]
        if self.id is not None:
            parts.append(f"id: {self.id}")
        payload = json.dumps(self.data, ensure_ascii=False) if not isinstance(self.data, str) else self.data
        parts.append(f"data: {payload}")
        return "\n".join(parts) + "\n\n"


@dataclass
class SessionEntry:
    """One active auto-run session."""
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: Optional[asyncio.Task] = None
    created_at: float = field(default_factory=time.time)


class SessionRegistry:
    """In-memory registry of active SSE sessions."""

    def __init__(self):
        self._sessions: dict[str, SessionEntry] = {}

    def create(self, session_id: str, task: asyncio.Task) -> SessionEntry:
        entry = SessionEntry(task=task)
        self._sessions[session_id] = entry
        log.info("Session %s registered", session_id)
        return entry

    def get(self, session_id: str) -> Optional[SessionEntry]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        entry = self._sessions.pop(session_id, None)
        if entry and entry.task and not entry.task.done():
            entry.task.cancel()
        if entry:
            log.info("Session %s removed", session_id)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    async def health_check(self) -> None:
        for sid, entry in list(self._sessions.items()):
            qsize = entry.queue.qsize()
            if qsize > MAX_QUEUE_SIZE:
                log.error("Session %s queue overflow (%d) — cancelling", sid, qsize)
                self.remove(sid)
            elif qsize > WARN_QUEUE_SIZE:
                log.warning("Session %s queue backpressure: %d items", sid, qsize)
        if self._sessions:
            total = sum(e.queue.qsize() for e in self._sessions.values())
            log.info("Active SSE sessions: %d, total queued: %d", len(self._sessions), total)


# Module-level singleton
registry = SessionRegistry()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_session_events.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/session_events.py backend/tests/test_session_events.py
git commit -m "feat(sse): add session event registry with queue + task lifecycle"
```

---

## Task 2: Incremental JSON Stream Parser

**Files:**
- Create: `backend/src/services/stream_parser.py`
- Test: `backend/tests/test_stream_parser.py`
- Modify: `backend/pyproject.toml` (add `json-repair`)

- [ ] **Step 1: Add json-repair and litellm to runtime dependencies**

In `backend/pyproject.toml`, add `"json-repair>=0.25"` and `"litellm>=1.50"` to `dependencies` list (after `httpx`). LiteLLM is currently dev-only but the streaming path calls `litellm.acompletion` at runtime. Also remove `litellm` from `[project.optional-dependencies] dev` to avoid duplication.

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_stream_parser.py
import pytest
from src.services.stream_parser import IncrementalEffectsParser


class TestIncrementalEffectsParser:
    def test_single_complete_effect(self):
        """Full JSON in one chunk → one complete node."""
        parser = IncrementalEffectsParser()
        chunk = '{"effects": [{"content": "Fed pause", "reasoning": "dovish", "confidence": 80, "parent_ids": ["s1"], "sector": "macro", "fetched_news_ids": [], "information_gaps": []}]}'
        events = parser.feed(chunk)
        # Should have node_start, node_text(s), node_complete
        starts = [e for e in events if e["type"] == "node_start"]
        completes = [e for e in events if e["type"] == "node_complete"]
        assert len(starts) == 1
        assert len(completes) == 1
        assert completes[0]["data"]["confidence"] == 80

    def test_streamed_chunks(self):
        """JSON arrives in small chunks — nodes emitted when complete."""
        parser = IncrementalEffectsParser()
        chunks = [
            '{"effects": [{"content": "Rate',
            ' cut impact", "reasoning": "Fed',
            ' signals easing", "confidence": 75,',
            ' "parent_ids": ["s1"], "sector":',
            ' "macro", "fetched_news_ids": [],',
            ' "information_gaps": []}]}',
        ]
        all_events = []
        for c in chunks:
            all_events.extend(parser.feed(c))
        completes = [e for e in all_events if e["type"] == "node_complete"]
        assert len(completes) == 1

    def test_multiple_effects(self):
        """Two effects → two complete nodes."""
        parser = IncrementalEffectsParser()
        chunk = '{"effects": [{"content": "A", "reasoning": "r1", "confidence": 70, "parent_ids": ["s1"], "sector": "tech", "fetched_news_ids": [], "information_gaps": []}, {"content": "B", "reasoning": "r2", "confidence": 60, "parent_ids": ["s2"], "sector": "energy", "fetched_news_ids": [], "information_gaps": []}]}'
        events = parser.feed(chunk)
        completes = [e for e in events if e["type"] == "node_complete"]
        assert len(completes) == 2

    def test_markdown_fence_stripped(self):
        """LLM wraps JSON in ```json ... ``` — parser handles it."""
        parser = IncrementalEffectsParser()
        chunk = '```json\n{"effects": [{"content": "X", "reasoning": "Y", "confidence": 50, "parent_ids": ["s1"], "sector": "fin", "fetched_news_ids": [], "information_gaps": []}]}\n```'
        events = parser.feed(chunk)
        completes = [e for e in events if e["type"] == "node_complete"]
        assert len(completes) == 1

    def test_text_deltas_emitted(self):
        """Content field changes emit node_text events."""
        parser = IncrementalEffectsParser()
        chunks = [
            '{"effects": [{"content": "Fed ',
            'rate pause signals dovish ',
            'pivot", "reasoning": "The hold',
            ' despite pressure", "confidence": 78,',
            ' "parent_ids": ["s1"], "sector": "macro",',
            ' "fetched_news_ids": [], "information_gaps": []}]}',
        ]
        all_events = []
        for c in chunks:
            all_events.extend(parser.feed(c))
        text_events = [e for e in all_events if e["type"] == "node_text"]
        assert len(text_events) > 0
        # Concatenated deltas should contain the full content
        content_deltas = [e["data"]["delta"] for e in text_events if e["data"].get("field") == "content"]
        assert "Fed " in "".join(content_deltas) or "rate" in "".join(content_deltas)

    def test_empty_effects(self):
        """Empty effects array → no events."""
        parser = IncrementalEffectsParser()
        events = parser.feed('{"effects": []}')
        assert len([e for e in events if e["type"] == "node_complete"]) == 0

    def test_malformed_prose_input(self):
        """LLM returns prose instead of JSON → no crash, no events."""
        parser = IncrementalEffectsParser()
        events = parser.feed("I think the main effects would be inflation and trade disruption.")
        assert len([e for e in events if e["type"] == "node_complete"]) == 0

    def test_partial_json_then_complete(self):
        """Truly broken partial JSON followed by valid completion."""
        parser = IncrementalEffectsParser()
        events1 = parser.feed('{"effects": [{"content": "partial')
        # No complete nodes yet
        assert len([e for e in events1 if e["type"] == "node_complete"]) == 0
        events2 = parser.feed('", "reasoning": "r", "confidence": 60, "parent_ids": ["s1"], "sector": "x", "fetched_news_ids": [], "information_gaps": []}]}')
        assert len([e for e in events2 if e["type"] == "node_complete"]) == 1
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_stream_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.services.stream_parser'`

- [ ] **Step 4: Implement stream_parser.py**

The parser tracks bracket depth within the `effects` array. When a top-level object in the array closes (`}` at depth 1), it extracts that object. Between closures, it emits `node_text` events as content/reasoning fields grow.

```python
# backend/src/services/stream_parser.py
"""Incremental JSON parser for LLM-streamed thinker output.

Consumes token chunks, emits events as node objects become complete.
Handles markdown fences and partial JSON gracefully.
"""

import re
from typing import Any
from json_repair import repair_json

from src.core.logger import get_logger

log = get_logger("stream_parser")

# Regex to strip ```json ... ``` fences
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?", re.MULTILINE)
_FENCE_END_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    text = _FENCE_RE.sub("", text)
    text = _FENCE_END_RE.sub("", text)
    return text


class IncrementalEffectsParser:
    """Feed LLM chunks, get back structured events.

    Events emitted:
    - {"type": "node_start", "data": {"index": int}}
    - {"type": "node_text", "data": {"index": int, "field": str, "delta": str}}
    - {"type": "node_complete", "data": {"index": int, ...full effect dict}}
    """

    def __init__(self):
        self._buffer = ""
        self._completed_count = 0
        self._last_content_len: dict[int, dict[str, int]] = {}  # index -> {field: len}

    def feed(self, chunk: str) -> list[dict[str, Any]]:
        """Feed a chunk of LLM output. Returns list of events."""
        self._buffer += chunk
        clean = _strip_fences(self._buffer)
        events: list[dict[str, Any]] = []

        # Try to extract complete effect objects using bracket tracking
        effects = self._extract_effects(clean)
        if effects is None:
            # Can't parse yet — try emitting text deltas from partial parse
            partial_events = self._emit_partial_deltas(clean)
            events.extend(partial_events)
            return events

        # Emit events for newly completed effects
        for i, effect in enumerate(effects):
            if i < self._completed_count:
                continue
            # node_start
            events.append({"type": "node_start", "data": {"index": i}})
            # node_text for content
            content = effect.get("content", "")
            if content:
                events.append({
                    "type": "node_text",
                    "data": {"index": i, "field": "content", "delta": content},
                })
            # node_text for reasoning
            reasoning = effect.get("reasoning", "")
            if reasoning:
                events.append({
                    "type": "node_text",
                    "data": {"index": i, "field": "reasoning", "delta": reasoning},
                })
            # node_complete
            events.append({"type": "node_complete", "data": {"index": i, **effect}})
            self._completed_count = i + 1

        return events

    def _extract_effects(self, text: str) -> list[dict] | None:
        """Try to parse complete effects from the buffer."""
        try:
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict) and "effects" in repaired:
                effects = repaired["effects"]
                if isinstance(effects, list):
                    # Only return effects that look complete (have content + confidence)
                    complete = [
                        e for e in effects
                        if isinstance(e, dict) and "content" in e and "confidence" in e
                    ]
                    if len(complete) > self._completed_count:
                        return complete
        except Exception:
            pass
        return None

    def _emit_partial_deltas(self, text: str) -> list[dict[str, Any]]:
        """Try to extract partial text deltas from incomplete JSON."""
        events: list[dict[str, Any]] = []
        try:
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict) and "effects" in repaired:
                effects = repaired.get("effects", [])
                if not isinstance(effects, list):
                    return events
                for i, effect in enumerate(effects):
                    if not isinstance(effect, dict):
                        continue
                    if i < self._completed_count:
                        continue
                    # Track field lengths and emit deltas
                    if i not in self._last_content_len:
                        self._last_content_len[i] = {}
                        events.append({"type": "node_start", "data": {"index": i}})
                    for field_name in ("content", "reasoning"):
                        val = effect.get(field_name, "")
                        if not val:
                            continue
                        prev_len = self._last_content_len[i].get(field_name, 0)
                        if len(val) > prev_len:
                            delta = val[prev_len:]
                            events.append({
                                "type": "node_text",
                                "data": {"index": i, "field": field_name, "delta": delta},
                            })
                            self._last_content_len[i][field_name] = len(val)
        except Exception:
            pass
        return events
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_stream_parser.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/stream_parser.py backend/tests/test_stream_parser.py backend/pyproject.toml
git commit -m "feat(sse): add incremental JSON parser for LLM-streamed thinker output"
```

---

## Task 3: LiteLLM Streaming Config + Thinker Prompt Extraction

**Files:**
- Modify: `backend/src/agents/llm_config.py` (add `get_litellm_params()`)
- Modify: `backend/src/agents/thinking_crew.py` (extract `build_thinker_prompt()`)
- Test: `backend/tests/test_agents.py` (add test for new functions)

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_agents.py`:

```python
class TestLiteLLMParams:
    def test_returns_dict_with_required_keys(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.llm_config.settings",
            type("S", (), {"siliconflow_api_key": "test-key"})(),
        )
        from src.agents.llm_config import get_litellm_params
        params = get_litellm_params()
        assert "model" in params
        assert "api_key" in params
        assert params["api_key"] == "test-key"
        assert "api_base" in params


class TestBuildThinkerPrompt:
    def test_returns_string_with_parent_context(self):
        from src.agents.thinking_crew import build_thinker_prompt
        parents = [{"id": "s1", "content": "Fed pause", "layer": 0, "type": "news", "selected": True}]
        news = [{"id": "n1", "title": "Rate news", "summary": "Summary"}]
        prompt = build_thinker_prompt(
            parent_nodes=parents, chain_summary="", news_pool=news, layer=1
        )
        assert "Fed pause" in prompt
        assert "Rate news" in prompt
        assert "Return ONLY valid JSON" in prompt
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_agents.py::TestLiteLLMParams -v
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_agents.py::TestBuildThinkerPrompt -v
```

- [ ] **Step 3: Add `get_litellm_params()` to llm_config.py**

Add after `get_small_llm()` (after line 44):

```python
def get_litellm_params() -> dict:
    """Return params dict for direct litellm.acompletion() calls."""
    return {
        "model": MAIN_MODEL,
        "api_key": _get_api_key(),
        "api_base": SILICONFLOW_BASE_URL,
        "temperature": 0.3,
    }
```

- [ ] **Step 4: Extract `build_thinker_prompt()` from thinking_crew.py**

Extract the prompt-building logic from `run_thinker()` (lines 70-107 of `thinking_crew.py`) into a standalone function. The existing `run_thinker()` should call this new function. Add before `run_thinker()`:

```python
def build_thinker_prompt(
    parent_nodes: list[dict],
    chain_summary: str,
    news_pool: list[dict],
    layer: int,
) -> str:
    """Build the thinker agent prompt. Shared between CrewAI and direct LiteLLM paths.

    NOTE: Import `prepare_parent_nodes` from `src.agents.thinking_helpers` (public name),
    not the `_prepare_parent_nodes` private alias in this file.
    """
    parents_json = json.dumps(
        prepare_parent_nodes(parent_nodes, current_layer=layer),
        ensure_ascii=False,
    )
    pool_json = json.dumps(
        [
            {
                "id": n.get("id", ""),
                "title": n.get("title", n.get("summary", "")),
                "summary": n.get("summary", ""),
            }
            for n in news_pool[:20]
        ],
        ensure_ascii=False,
    )
    chain_ctx = f"Chain summary so far:\n{chain_summary}\n\n" if chain_summary else ""
    return (
        f"{chain_ctx}"
        f"Analyze these financial events and identify their next-order "
        f"market effects.\n\n"
        f"Parent nodes (layers 0-{layer - 1}):\n{parents_json}\n\n"
        f"Available news pool:\n{pool_json}\n\n"
        f"For each effect:\n"
        f"1. Content — what happens\n"
        f"2. Reasoning — the causal chain from parent(s)\n"
        f"3. Confidence (0-100) — naturally lower for deeper chains\n"
        f"4. Parent IDs — which parent(s) cause it\n"
        f"5. Sector — affected sector\n"
        f"6. Fetched news IDs — any news from pool you reference\n"
        f"7. Information gaps — what you wish you knew\n\n"
        f"Return JSON:\n"
        f'{{"effects": [{{"content": str, "reasoning": str, '
        f'"confidence": int, "parent_ids": [str], "sector": str, '
        f'"fetched_news_ids": [str], "information_gaps": [str]}}]}}\n\n'
        f"Return ONLY valid JSON."
    )
```

Then update `run_thinker()` to call `build_thinker_prompt()` instead of inline prompt building. Replace lines 70-107 with:

```python
        description = build_thinker_prompt(
            parent_nodes=parent_nodes,
            chain_summary=chain_summary,
            news_pool=news_pool,
            layer=layer,
        )
        prompt_chars = len(description)
```

- [ ] **Step 5: Run ALL agent tests — verify they pass**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_agents.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/agents/llm_config.py backend/src/agents/thinking_crew.py backend/tests/test_agents.py
git commit -m "refactor(sse): extract thinker prompt builder + add litellm params helper"
```

---

## Task 4: Streaming Layer Runner

**Files:**
- Modify: `backend/src/services/thinking_service.py` (add `run_layer_streaming()`)
- Depends on: Task 1 (session_events), Task 2 (stream_parser), Task 3 (llm_config + prompt)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_streaming_layer.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.session_events import SessionRegistry, SSEEvent
from src.services.thinking_service import run_layer_streaming


def _mock_stream_chunks():
    """Simulate LiteLLM streaming response."""
    chunks_text = [
        '{"effects": [{"content": "Fed ',
        'rate impact", "reasoning": "The',
        ' pause signals easing", "confidence": 75,',
        ' "parent_ids": ["s1"], "sector": "macro",',
        ' "fetched_news_ids": [], "information_gaps": []}]}',
    ]
    for text in chunks_text:
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = text
        yield chunk


@pytest.mark.asyncio
async def test_run_layer_streaming_pushes_events():
    """Streaming layer pushes node events to the queue."""
    reg = SessionRegistry()
    dummy_task = asyncio.current_task()
    entry = reg.create("test-sess", dummy_task)

    parents = [{"id": "s1", "content": "News", "layer": 0, "type": "news", "selected": True}]
    news = [{"id": "n1", "title": "Test", "summary": "Sum"}]
    value = [{"ticker": "AAPL", "sector": "tech", "discount_pct": 20}]

    async def mock_acompletion(**kwargs):
        """Return an async generator of chunks."""
        async def gen():
            for c in _mock_stream_chunks():
                yield c
        return gen()

    with patch("src.services.thinking_service.litellm_acompletion", side_effect=mock_acompletion):
        # Use AsyncMock — _call_with_retry is async, so side_effect values must be awaitable
        mock_retry = AsyncMock()
        mock_retry.side_effect = [
            ([], [], 0),  # matcher returns empty
            ({"continue": False, "reasoning": "stop", "summary": ""}, 0),  # controller stops
        ]
        with patch("src.services.thinking_service._call_with_retry", mock_retry):
            await run_layer_streaming(
                session_id="test-sess",
                chain_summary="",
                parent_nodes=parents,
                news_pool=news,
                value_pool=value,
                layer=1,
                max_depth=3,
                registry=reg,
            )

    # Drain queue and check events
    events = []
    while not entry.queue.empty():
        events.append(await entry.queue.get())
    event_types = [e.event for e in events]
    assert "node_start" in event_types
    assert "node_complete" in event_types
    assert "edges" in event_types
    assert "layer_complete" in event_types
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_streaming_layer.py -v
```

- [ ] **Step 3: Implement `run_layer_streaming()` in thinking_service.py**

Add after `run_layer()` (after line 159):

```python
# Import at top of file (add these):
# from src.services.session_events import SessionRegistry, SSEEvent
# from src.services.stream_parser import IncrementalEffectsParser
# from src.agents.llm_config import get_litellm_params
# from src.agents.thinking_crew import build_thinker_prompt, _build_thinker_output, run_matcher, run_controller

async def run_layer_streaming(
    session_id: str,
    chain_summary: str,
    parent_nodes: list[dict],
    news_pool: list[dict],
    value_pool: list[dict],
    layer: int,
    max_depth: int,
    registry: "SessionRegistry",
    confidence_threshold: float = 35,
) -> LayerResult:
    """Run one pipeline layer with LLM streaming for the thinker.

    Pushes SSEEvents to the session queue as nodes are generated.
    Matcher and controller run batch (non-streaming).
    """
    entry = registry.get(session_id)
    if not entry:
        log.error("No session entry for %s — cannot stream", session_id)
        return _empty_layer_result("Session not registered for streaming")

    queue = entry.queue

    # --- Thinker (streaming) ---
    thinker_tokens = 0
    effect_nodes = []
    fetch_nodes = []
    effect_edges = []
    fetch_edges = []

    try:
        from src.agents.thinking_crew import build_thinker_prompt, _build_thinker_output
        from src.agents.skills.base import build_system_prompt_with_skills
        from src.agents.thinking_helpers import THINKER_SKILLS
        from src.agents.llm_config import get_litellm_params

        prompt = build_thinker_prompt(
            parent_nodes=parent_nodes,
            chain_summary=chain_summary,
            news_pool=news_pool,
            layer=layer,
        )
        system_prompt = build_system_prompt_with_skills(allowed_skills=THINKER_SKILLS)
        params = get_litellm_params()

        # Stream LLM response
        parser = IncrementalEffectsParser()
        full_text = ""
        node_index_to_id: dict[int, str] = {}

        response = await litellm_acompletion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=True,
            **params,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if not delta:
                continue
            full_text += delta

            events = parser.feed(delta)
            for evt in events:
                if evt["type"] == "node_start":
                    idx = evt["data"]["index"]
                    node_id = f"stream-{uuid4().hex[:8]}"
                    node_index_to_id[idx] = node_id
                    await queue.put(SSEEvent(
                        event="node_start",
                        data={"id": node_id, "layer": layer, "type": "effect", "parent_ids": [p["id"] for p in parent_nodes[:3]]},
                        id=f"layer:{layer}:node:{idx}",
                    ))
                elif evt["type"] == "node_text":
                    idx = evt["data"]["index"]
                    nid = node_index_to_id.get(idx, "")
                    await queue.put(SSEEvent(
                        event="node_text",
                        data={"id": nid, "field": evt["data"]["field"], "delta": evt["data"]["delta"]},
                        id=f"layer:{layer}:node:{idx}:text",
                    ))
                elif evt["type"] == "node_complete":
                    idx = evt["data"]["index"]
                    nid = node_index_to_id.get(idx, "")
                    await queue.put(SSEEvent(
                        event="node_complete",
                        data={"id": nid, "confidence": evt["data"].get("confidence", 50), "metadata": {"sector": evt["data"].get("sector", "general")}},
                        id=f"layer:{layer}:node:{idx}:done",
                    ))

        # Parse full response for node/edge construction
        parsed = parse_json_response(full_text)
        if isinstance(parsed, dict) and parsed.get("effects"):
            effect_nodes, fetch_nodes, effect_edges, fetch_edges = _build_thinker_output(
                parsed["effects"], parent_nodes, news_pool, layer
            )

    except asyncio.CancelledError:
        log.info("Streaming cancelled for session %s at layer %d", session_id, layer)
        raise
    except Exception as e:
        log.error("Streaming thinker failed at layer %d: %s", layer, e)
        await queue.put(SSEEvent(event="error", data={"message": str(e), "layer": layer}))
        return _empty_layer_result(f"Streaming thinker failed: {e}")

    if not effect_nodes:
        return _empty_layer_result("Thinker produced no effects")

    all_edges = list(effect_edges) + list(fetch_edges)

    # --- Matcher (batch) ---
    opportunity_nodes = []
    matcher_tokens = 0
    try:
        opportunity_nodes, match_edges, matcher_tokens = await _call_with_retry(
            run_matcher, effects=effect_nodes, value_pool=value_pool,
        )
        all_edges.extend(match_edges)
        # Push opportunity nodes as batch (non-streaming)
        for opp in opportunity_nodes:
            await queue.put(SSEEvent(
                event="node_start",
                data={"id": opp["id"], "layer": opp["layer"], "type": "opportunity", "parent_ids": opp.get("parents", [])},
            ))
            await queue.put(SSEEvent(
                event="node_complete",
                data={"id": opp["id"], "confidence": opp.get("confidence", 0), "metadata": opp.get("metadata", {})},
            ))
    except Exception as e:
        log.warning("Matcher failed at layer %d: %s", layer, e)

    # Push edges
    await queue.put(SSEEvent(event="edges", data=all_edges, id=f"layer:{layer}:edges"))

    # --- Controller (batch) ---
    controller_tokens = 0
    try:
        ctrl, controller_tokens = await _call_with_retry(
            run_controller,
            chain_summary=chain_summary,
            effects=effect_nodes,
            matches=opportunity_nodes,
            layer=layer,
            max_depth=max_depth,
            confidence_threshold=confidence_threshold,
        )
    except Exception as e:
        log.warning("Controller failed at layer %d: %s", layer, e)
        should_continue = layer < DEFAULT_STOP_LAYER
        ctrl = {"continue": should_continue, "reasoning": f"Controller failed: {e}", "summary": chain_summary}

    await queue.put(SSEEvent(
        event="layer_complete",
        data={"layer": layer, "controller": ctrl},
        id=f"layer:{layer}:complete",
    ))

    return LayerResult(
        effect_nodes=effect_nodes,
        fetch_nodes=fetch_nodes,
        opportunity_nodes=opportunity_nodes,
        all_edges=all_edges,
        controller_decision=ctrl,
        tokens_used={"thinker": thinker_tokens, "matcher": matcher_tokens, "controller": controller_tokens},
    )
```

Also add at top of `thinking_service.py`:

```python
from uuid import uuid4
from src.services.stream_parser import IncrementalEffectsParser
from src.services.session_events import SessionRegistry, SSEEvent
from src.agents.thinking_helpers import parse_json_response

# Alias for mockability in tests
try:
    from litellm import acompletion as litellm_acompletion
except ImportError:
    litellm_acompletion = None  # type: ignore
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_streaming_layer.py -v
```

- [ ] **Step 5: Run all existing tests — verify no regressions**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/ -v --ignore=tests/benchmark
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/thinking_service.py backend/tests/test_streaming_layer.py
git commit -m "feat(sse): add streaming layer runner with LiteLLM + incremental parser"
```

---

## Task 5: SSE Endpoint + Auto-Run Integration

**Files:**
- Modify: `backend/src/api/thinking_auto.py` (replace polling SSE, integrate registry)
- Test: `backend/tests/test_sse_endpoint.py`
- Depends on: Task 1, Task 4

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_sse_endpoint.py
import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.services.session_events import registry, SSEEvent


@pytest.mark.asyncio
async def test_sse_endpoint_streams_events():
    """SSE endpoint delivers events from session queue."""
    # Pre-register a session
    dummy_task = asyncio.ensure_future(asyncio.sleep(100))
    entry = registry.create("test-sse", dummy_task)

    # Push some events
    await entry.queue.put(SSEEvent(event="node_start", data={"id": "n1", "layer": 1, "type": "effect"}, id="layer:1:node:0"))
    await entry.queue.put(SSEEvent(event="session_complete", data={"status": "complete"}, id="session:complete"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/thinking/test-sse/events") as resp:
            assert resp.status_code == 200
            lines = []
            async for line in resp.aiter_lines():
                lines.append(line)
                if "session_complete" in line:
                    break
            text = "\n".join(lines)
            assert "node_start" in text
            assert "session_complete" in text

    registry.remove("test-sse")
    dummy_task.cancel()


@pytest.mark.asyncio
async def test_sse_endpoint_unknown_session_replays_from_db():
    """Unknown session falls back to MongoDB replay."""
    # Mock MongoDB find
    mock_session = {
        "id": "old-sess",
        "status": "complete",
        "current_layer": 2,
        "nodes": [{"id": "n1", "layer": 1, "type": "effect", "content": "X", "reasoning": "", "sources": [], "parents": ["s1"], "selected": True, "metadata": {}}],
        "edges": [{"source": "s1", "target": "n1", "relationship": "causes"}],
    }

    with patch("src.api.thinking_auto.mongodb") as mock_db:
        col = AsyncMock()
        col.find_one = AsyncMock(return_value=mock_session)
        mock_db.get_collection.return_value = col

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", "/api/thinking/old-sess/events") as resp:
                assert resp.status_code == 200
                lines = []
                async for line in resp.aiter_lines():
                    lines.append(line)
                    if "session_complete" in line:
                        break
                text = "\n".join(lines)
                assert "session_complete" in text
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_sse_endpoint.py -v
```

- [ ] **Step 3: Rewrite thinking_auto.py**

Replace the full file. Key changes:
1. `auto_think()`: Create queue in registry **before** `create_task()`. Pipeline loop calls `run_layer_streaming()` and pushes `session_complete` event when done.
2. `session_events()`: Read from queue if session is active; replay from MongoDB if session is complete/unknown. Cancels pipeline on client disconnect.
3. Health check background task started via FastAPI `on_event("startup")`.
4. Add `from fastapi import APIRouter, Request` import for disconnect detection.

**auto_think rewrite — pipeline loop integration:**

```python
from fastapi import APIRouter, Request
from src.services.session_events import registry, SSEEvent
from src.services.thinking_service import run_layer_streaming, LayerResult

@router.post("/auto", response_model=StartResponse)
async def auto_think(req: StartRequest):
    session_id = uuid4().hex[:12]
    # ... (pool loading + session creation same as before, lines 26-93) ...
    await col.insert_one(session)

    async def _run_streaming_pipeline():
        """Streaming pipeline loop — pushes events to queue via run_layer_streaming."""
        chain_summary = ""
        all_layer_nodes: list[list[dict]] = [nodes]  # layer 0 = seeds

        try:
            for layer in range(1, req.max_depth + 1):
                parent_nodes = []
                for layer_nodes in all_layer_nodes:
                    parent_nodes.extend(n for n in layer_nodes if n.get("selected", False))

                result = await run_layer_streaming(
                    session_id=session_id,
                    chain_summary=chain_summary,
                    parent_nodes=parent_nodes,
                    news_pool=news_items,
                    value_pool=value_items,
                    layer=layer,
                    max_depth=req.max_depth,
                    registry=registry,
                )

                # Persist to MongoDB (same as before)
                new_nodes = result.effect_nodes + result.fetch_nodes + result.opportunity_nodes
                update: dict = {"$set": {"current_layer": layer, "status": "thinking"}}
                if new_nodes:
                    update["$push"] = {"nodes": {"$each": new_nodes}, "edges": {"$each": result.all_edges}}
                await col.update_one({"id": session_id}, update)

                all_layer_nodes.append(new_nodes)
                chain_summary = result.controller_decision.get("summary", chain_summary)

                if not result.controller_decision.get("continue", False):
                    break

            await col.update_one({"id": session_id}, {"$set": {"status": "complete"}})
            entry = registry.get(session_id)
            if entry:
                await entry.queue.put(SSEEvent(event="session_complete", data={"status": "complete"}, id="session:complete"))

        except asyncio.CancelledError:
            log.info("Pipeline cancelled for session %s", session_id)
            await col.update_one({"id": session_id}, {"$set": {"status": "cancelled"}})
            entry = registry.get(session_id)
            if entry:
                await entry.queue.put(SSEEvent(event="session_complete", data={"status": "cancelled"}))
        except asyncio.TimeoutError:
            await col.update_one({"id": session_id}, {"$set": {"status": "timeout"}})
            entry = registry.get(session_id)
            if entry:
                await entry.queue.put(SSEEvent(event="error", data={"message": "Pipeline timeout"}))
        except Exception as e:
            log.error("Pipeline failed: %s", e)
            await col.update_one({"id": session_id}, {"$set": {"status": "error", "error": str(e)}})
            entry = registry.get(session_id)
            if entry:
                await entry.queue.put(SSEEvent(event="error", data={"message": str(e)}))

    # Create queue BEFORE launching task — guarantees no lost events
    task = asyncio.create_task(
        asyncio.wait_for(_run_streaming_pipeline(), timeout=PIPELINE_TIMEOUT_S)
    )
    registry.create(session_id, task)

    return StartResponse(session_id=session_id, status="thinking")
```

**SSE endpoint — with disconnect detection and cancellation:**

```python
@router.get("/{session_id}/events")
async def session_events(session_id: str, request: Request):
    entry = registry.get(session_id)

    if entry:
        # Live session — stream from queue
        async def live_stream():
            try:
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        log.info("SSE client disconnected for %s — cancelling pipeline", session_id)
                        registry.remove(session_id)  # cancels the task
                        return
                    try:
                        event = await asyncio.wait_for(entry.queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # Send keepalive comment to detect disconnects
                        yield ": keepalive\n\n"
                        continue
                    yield event.serialize()
                    if event.event in ("session_complete", "error"):
                        break
            except asyncio.CancelledError:
                pass
            finally:
                # Clean up registry if pipeline is done
                if entry.task and entry.task.done():
                    registry.remove(session_id)
        return StreamingResponse(live_stream(), media_type="text/event-stream")
    else:
        # Completed/unknown session — replay from MongoDB
        async def replay_stream():
            col = mongodb.get_collection("thinking_sessions")
            session = await col.find_one({"id": session_id}, {"_id": 0})
            if not session:
                yield SSEEvent(event="error", data={"message": "Session not found"}).serialize()
                return
            for i, node in enumerate(session.get("nodes", [])):
                yield SSEEvent(event="node_start", data=node, id=f"replay:node:{i}").serialize()
                yield SSEEvent(event="node_complete", data={"id": node["id"], "confidence": node.get("confidence", 0)}, id=f"replay:node:{i}:done").serialize()
            yield SSEEvent(event="edges", data=session.get("edges", []), id="replay:edges").serialize()
            yield SSEEvent(event="session_complete", data={"status": session.get("status", "complete")}, id="session:complete").serialize()
        return StreamingResponse(replay_stream(), media_type="text/event-stream")
```

**Health check — register on startup via main.py:**

Add to `backend/src/main.py` in the `lifespan` or `on_event("startup")`:

```python
from src.services.session_events import registry

async def _periodic_health_check():
    while True:
        await asyncio.sleep(30)
        await registry.health_check()

@app.on_event("startup")
async def start_health_check():
    asyncio.create_task(_periodic_health_check())
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/test_sse_endpoint.py -v
```

- [ ] **Step 5: Run all backend tests — no regressions**

```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/ -v --ignore=tests/benchmark
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/thinking_auto.py backend/tests/test_sse_endpoint.py
git commit -m "feat(sse): queue-based SSE endpoint with live streaming + DB replay"
```

---

## Task 6: Frontend — SSE Types + Concentric Layout

**Files:**
- Modify: `frontend/src/types/thinking.ts` (update SSE event types)
- Modify: `frontend/src/lib/thinking-graph-builder.ts` (add `concentricPosition()`)
- Test: `frontend/src/lib/__tests__/concentric-layout.test.ts`

- [ ] **Step 1: Update SSE event types**

Replace lines 39-45 of `frontend/src/types/thinking.ts`:

```typescript
// SSE event types — matches backend event protocol
export interface SSENodeStart {
  id: string;
  layer: number;
  type: ThinkingNodeType;
  parent_ids: string[];
}

export interface SSENodeText {
  id: string;
  field: "content" | "reasoning";
  delta: string;
}

export interface SSENodeComplete {
  id: string;
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface SSELayerComplete {
  layer: number;
  controller: { continue: boolean; reasoning: string; summary: string };
}

export interface SSESessionComplete {
  status: string;
}

export interface SSEError {
  message: string;
  layer?: number;
}
```

- [ ] **Step 2: Add `concentricPosition()` to thinking-graph-builder.ts**

Add after `nodeStyle()` (after line 58):

```typescript
/**
 * Calculate deterministic position on a concentric ring.
 * Used during SSE streaming — avoids d3-force re-simulation.
 */
export function concentricPosition(
  layer: number,
  index: number,
  totalInLayer: number,
  layerRadius: number = 180,
): { x: number; y: number } {
  if (layer === 0) {
    // Seeds cluster near center
    const angle = (index / Math.max(totalInLayer, 1)) * 2 * Math.PI;
    const r = totalInLayer > 1 ? 60 : 0;
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  }
  const r = layer * layerRadius;
  const angle =
    (index / Math.max(totalInLayer, 1)) * 2 * Math.PI +
    (layer * Math.PI) / 6; // Offset each ring to avoid radial alignment
  return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
}
```

- [ ] **Step 3: Write test for concentric layout**

```typescript
// frontend/src/lib/__tests__/concentric-layout.test.ts
import { describe, it, expect } from "vitest";
import { concentricPosition } from "../thinking-graph-builder";

describe("concentricPosition", () => {
  it("places layer 0 at center when single node", () => {
    const pos = concentricPosition(0, 0, 1);
    expect(pos.x).toBeCloseTo(0, 0);
    expect(pos.y).toBeCloseTo(0, 0);
  });

  it("places layer 1 nodes on a ring", () => {
    const pos = concentricPosition(1, 0, 4);
    const dist = Math.sqrt(pos.x ** 2 + pos.y ** 2);
    expect(dist).toBeCloseTo(180, 0);
  });

  it("spaces nodes evenly on ring", () => {
    const positions = Array.from({ length: 4 }, (_, i) =>
      concentricPosition(1, i, 4),
    );
    // All should be ~180px from center
    for (const p of positions) {
      expect(Math.sqrt(p.x ** 2 + p.y ** 2)).toBeCloseTo(180, 0);
    }
    // No two should overlap
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        const dx = positions[i].x - positions[j].x;
        const dy = positions[i].y - positions[j].y;
        expect(Math.sqrt(dx * dx + dy * dy)).toBeGreaterThan(50);
      }
    }
  });

  it("layer 2 has larger radius than layer 1", () => {
    const p1 = concentricPosition(1, 0, 1);
    const p2 = concentricPosition(2, 0, 1);
    const r1 = Math.sqrt(p1.x ** 2 + p1.y ** 2);
    const r2 = Math.sqrt(p2.x ** 2 + p2.y ** 2);
    expect(r2).toBeGreaterThan(r1);
  });
});
```

- [ ] **Step 4: Run frontend tests**

```bash
cd /path/to/worktree/frontend && npx vitest run src/lib/__tests__/concentric-layout.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/thinking.ts frontend/src/lib/thinking-graph-builder.ts frontend/src/lib/__tests__/concentric-layout.test.ts
git commit -m "feat(sse): add SSE event types + deterministic concentric layout"
```

---

## Task 7: Frontend — useSSESession Hook

**Files:**
- Create: `frontend/src/hooks/useSSESession.ts`
- Test: `frontend/src/hooks/__tests__/useSSESession.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/hooks/__tests__/useSSESession.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSSESession } from "../useSSESession";

// Mock EventSource
class MockEventSource {
  url: string;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  readyState = 0;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    this.readyState = 1; // OPEN
  }

  addEventListener(type: string, fn: (e: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(fn);
  }

  removeEventListener(type: string, fn: (e: MessageEvent) => void) {
    this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn);
  }

  emit(type: string, data: string, id?: string) {
    const event = new MessageEvent(type, { data, lastEventId: id });
    for (const fn of this.listeners[type] || []) fn(event);
  }
}

let mockES: MockEventSource;
vi.stubGlobal(
  "EventSource",
  vi.fn((url: string) => {
    mockES = new MockEventSource(url);
    return mockES;
  }),
);

describe("useSSESession", () => {
  it("connects to SSE endpoint", () => {
    const { result } = renderHook(() => useSSESession("sess1"));
    expect(mockES.url).toBe("/api/thinking/sess1/events");
    expect(result.current.connected).toBe(true);
  });

  it("receives node_start events", () => {
    const onNodeStart = vi.fn();
    renderHook(() => useSSESession("sess1", { onNodeStart }));
    act(() => {
      mockES.emit("node_start", JSON.stringify({ id: "n1", layer: 1, type: "effect", parent_ids: ["s1"] }));
    });
    expect(onNodeStart).toHaveBeenCalledWith(expect.objectContaining({ id: "n1" }));
  });

  it("receives node_text events", () => {
    const onNodeText = vi.fn();
    renderHook(() => useSSESession("sess1", { onNodeText }));
    act(() => {
      mockES.emit("node_text", JSON.stringify({ id: "n1", field: "content", delta: "Fed " }));
    });
    expect(onNodeText).toHaveBeenCalledWith(expect.objectContaining({ delta: "Fed " }));
  });

  it("cleans up on unmount", () => {
    const { unmount } = renderHook(() => useSSESession("sess1"));
    unmount();
    expect(mockES.close).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Implement useSSESession.ts**

```typescript
// frontend/src/hooks/useSSESession.ts
import { useEffect, useRef, useState, useCallback } from "react";
import type {
  SSENodeStart,
  SSENodeText,
  SSENodeComplete,
  SSELayerComplete,
  SSESessionComplete,
  SSEError,
} from "../types/thinking";
import type { ThinkingEdge } from "../types/thinking";

interface SSECallbacks {
  onNodeStart?: (data: SSENodeStart) => void;
  onNodeText?: (data: SSENodeText) => void;
  onNodeComplete?: (data: SSENodeComplete) => void;
  onEdges?: (data: ThinkingEdge[]) => void;
  onLayerComplete?: (data: SSELayerComplete) => void;
  onSessionComplete?: (data: SSESessionComplete) => void;
  onError?: (data: SSEError) => void;
}

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 5000;

export function useSSESession(sessionId: string | null, callbacks?: SSECallbacks) {
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);
  // Stabilize callbacks with ref — avoids reconnecting on every render
  const cbRef = useRef(callbacks);
  cbRef.current = callbacks;

  const connect = useCallback(() => {
    if (!sessionId) return;
    const url = `/api/thinking/${sessionId}/events`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("node_start", (e: MessageEvent) => {
      cbRef.current?.onNodeStart?.(JSON.parse(e.data));
    });
    es.addEventListener("node_text", (e: MessageEvent) => {
      cbRef.current?.onNodeText?.(JSON.parse(e.data));
    });
    es.addEventListener("node_complete", (e: MessageEvent) => {
      cbRef.current?.onNodeComplete?.(JSON.parse(e.data));
    });
    es.addEventListener("edges", (e: MessageEvent) => {
      cbRef.current?.onEdges?.(JSON.parse(e.data));
    });
    es.addEventListener("layer_complete", (e: MessageEvent) => {
      cbRef.current?.onLayerComplete?.(JSON.parse(e.data));
    });
    es.addEventListener("session_complete", (e: MessageEvent) => {
      cbRef.current?.onSessionComplete?.(JSON.parse(e.data));
      es.close();
      setConnected(false);
    });
    es.addEventListener("error", (e: MessageEvent) => {
      if (e.data) {
        cbRef.current?.onError?.(JSON.parse(e.data));
      }
    });

    es.onopen = () => {
      setConnected(true);
      retriesRef.current = 0;
    };
    es.onerror = () => {
      setConnected(false);
      es.close();
      if (retriesRef.current < MAX_RETRIES) {
        retriesRef.current += 1;
        setTimeout(connect, RETRY_DELAY_MS);
      } else {
        cbRef.current?.onError?.({ message: "SSE connection failed after retries" });
      }
    };
  }, [sessionId]); // Only reconnect when sessionId changes, not on callback changes

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      setConnected(false);
    };
  }, [connect]);

  return { connected };
}
```

- [ ] **Step 3: Run tests**

```bash
cd /path/to/worktree/frontend && npx vitest run src/hooks/__tests__/useSSESession.test.ts
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useSSESession.ts frontend/src/hooks/__tests__/useSSESession.test.ts
git commit -m "feat(sse): add useSSESession hook with EventSource lifecycle + reconnection"
```

---

## Task 8: Frontend — StreamingNode Component + Animation Queue

**Files:**
- Create: `frontend/src/components/StreamingNode.tsx`
- Create: `frontend/src/hooks/useAnimationQueue.ts`

- [ ] **Step 1: Implement StreamingNode.tsx**

Custom React Flow node component that supports streaming text and entrance animations:

```typescript
// frontend/src/components/StreamingNode.tsx
import { memo, useEffect, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

interface StreamingNodeData {
  label: string;
  type: string;
  layer: number;
  selected: boolean;
  reasoning: string;
  streaming?: boolean; // True while text is still arriving
  confidence?: number;
}

function StreamingNodeComponent({ data }: NodeProps) {
  const d = data as unknown as StreamingNodeData;
  const [visible, setVisible] = useState(false);

  // Entrance animation — fade in after mount
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  const isOpp = d.type === "opportunity";

  return (
    <div
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "scale(1)" : "scale(0.8)",
        transition: "opacity 400ms ease-out, transform 400ms ease-out",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div
        style={{
          fontSize: 12,
          lineHeight: 1.5,
          minWidth: 140,
          maxWidth: 200,
          padding: "10px 14px",
        }}
      >
        <div>{d.label}</div>
        {d.streaming && (
          <span
            className="inline-block w-1.5 h-3 ml-0.5 bg-current animate-pulse"
            style={{ opacity: 0.6 }}
          />
        )}
        {d.confidence != null && !d.streaming && (
          <div
            className="mt-1 text-[10px]"
            style={{ color: isOpp ? "#86efac" : "#9ca3af" }}
          >
            {d.confidence}% confidence
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

export const StreamingNode = memo(StreamingNodeComponent);
```

- [ ] **Step 2: Implement useAnimationQueue.ts**

```typescript
// frontend/src/hooks/useAnimationQueue.ts
import { useRef, useCallback } from "react";

const MIN_GAP_MS = 200;

/**
 * Queues animation callbacks with a minimum gap between executions.
 * Prevents visual clumping when multiple nodes arrive in quick succession.
 */
export function useAnimationQueue() {
  const queue = useRef<(() => void)[]>([]);
  const lastRun = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    const now = Date.now();
    const elapsed = now - lastRun.current;

    if (queue.current.length === 0) return;

    if (elapsed >= MIN_GAP_MS) {
      const fn = queue.current.shift();
      fn?.();
      lastRun.current = Date.now();
      // Schedule next if more in queue
      if (queue.current.length > 0) {
        timer.current = setTimeout(flush, MIN_GAP_MS);
      }
    } else {
      // Wait for remaining gap
      timer.current = setTimeout(flush, MIN_GAP_MS - elapsed);
    }
  }, []);

  const enqueue = useCallback(
    (fn: () => void) => {
      queue.current.push(fn);
      if (!timer.current) flush();
    },
    [flush],
  );

  return { enqueue };
}
```

- [ ] **Step 3: Write tests for useAnimationQueue**

```typescript
// frontend/src/hooks/__tests__/useAnimationQueue.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAnimationQueue } from "../useAnimationQueue";

describe("useAnimationQueue", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("executes first callback immediately", () => {
    const { result } = renderHook(() => useAnimationQueue());
    const fn = vi.fn();
    act(() => result.current.enqueue(fn));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("enforces minimum gap between callbacks", () => {
    const { result } = renderHook(() => useAnimationQueue());
    const fn1 = vi.fn();
    const fn2 = vi.fn();
    act(() => {
      result.current.enqueue(fn1);
      result.current.enqueue(fn2);
    });
    expect(fn1).toHaveBeenCalledTimes(1);
    expect(fn2).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(200));
    expect(fn2).toHaveBeenCalledTimes(1);
  });

  it("drains queue in order", () => {
    const { result } = renderHook(() => useAnimationQueue());
    const order: number[] = [];
    act(() => {
      result.current.enqueue(() => order.push(1));
      result.current.enqueue(() => order.push(2));
      result.current.enqueue(() => order.push(3));
    });
    act(() => vi.advanceTimersByTime(600));
    expect(order).toEqual([1, 2, 3]);
  });
});
```

- [ ] **Step 4: Run tests**

```bash
cd /path/to/worktree/frontend && npx vitest run src/hooks/__tests__/useAnimationQueue.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StreamingNode.tsx frontend/src/hooks/useAnimationQueue.ts frontend/src/hooks/__tests__/useAnimationQueue.test.ts
git commit -m "feat(sse): add StreamingNode component + animation queue hook with tests"
```

---

## Task 9: Frontend — Integrate SSE into ThinkingView

**Files:**
- Modify: `frontend/src/components/ThinkingView.tsx`
- Depends on: Task 6, 7, 8

This is the integration task — wire `useSSESession` into `ThinkingView`, replacing the polling loop for auto-run mode.

- [ ] **Step 1: Register StreamingNode type with React Flow**

Add to ThinkingView.tsx imports:

```typescript
import { StreamingNode } from "./StreamingNode";
```

And define nodeTypes outside the component:

```typescript
const nodeTypes = { streaming: StreamingNode };
```

Pass to `<ReactFlow nodeTypes={nodeTypes} ...>`.

- [ ] **Step 2: Add SSE integration alongside polling**

In ThinkingView, add state for SSE mode and wire `useSSESession` callbacks:

```typescript
const [sseMode, setSseMode] = useState(false);
const layerNodeCounts = useRef<Map<number, number>>(new Map());

const handleNodeStart = useCallback((data: SSENodeStart) => {
  const count = layerNodeCounts.current.get(data.layer) || 0;
  layerNodeCounts.current.set(data.layer, count + 1);
  const pos = concentricPosition(data.layer, count, count + 1);

  setNodes((prev) => [
    ...prev,
    {
      id: data.id,
      type: "streaming",
      position: pos,
      data: {
        label: "",
        type: data.type,
        layer: data.layer,
        selected: true,
        reasoning: "",
        streaming: true,
      },
      style: nodeStyle(data.type, true, data.layer),
    },
  ]);
}, [setNodes]);

const handleNodeText = useCallback((data: SSENodeText) => {
  setNodes((prev) =>
    prev.map((n) => {
      if (n.id !== data.id) return n;
      const label = ((n.data as any).label || "") + data.delta;
      return { ...n, data: { ...n.data, label } };
    }),
  );
}, [setNodes]);

// ... similar for onNodeComplete, onEdges, onSessionComplete
```

- [ ] **Step 3: Replace polling effect with SSE**

Replace the polling `useEffect` (lines 174-180) with conditional logic:

```typescript
// Use SSE for auto-run, keep polling as fallback
const { connected } = useSSESession(
  session?.status === "thinking" ? sessionId : null,
  {
    onNodeStart: handleNodeStart,
    onNodeText: handleNodeText,
    onNodeComplete: handleNodeComplete,
    onEdges: handleEdges,
    onLayerComplete: handleLayerComplete,
    onSessionComplete: handleSessionComplete,
    onError: (err) => {
      log.error("SSE error:", err.message);
      // Fall back to polling
      setSseMode(false);
    },
  },
);

// Polling fallback — only when SSE is not connected
useEffect(() => {
  if (connected || session?.status !== "thinking") return;
  const interval = setInterval(() => loadSessionIncremental(), 2000);
  return () => clearInterval(interval);
}, [connected, session?.status, loadSessionIncremental]);
```

- [ ] **Step 4: Re-space existing nodes when siblings arrive**

When a new node arrives on a ring, update positions of existing same-layer nodes:

```typescript
const handleNodeStart = useCallback((data: SSENodeStart) => {
  const count = (layerNodeCounts.current.get(data.layer) || 0) + 1;
  layerNodeCounts.current.set(data.layer, count);

  // Re-space all nodes on this layer
  setNodes((prev) => {
    const updated = prev.map((n) => {
      if ((n.data as any).layer !== data.layer) return n;
      const idx = prev.filter((p) => (p.data as any).layer === data.layer).indexOf(n);
      const pos = concentricPosition(data.layer, idx, count);
      return { ...n, position: pos };
    });

    // Add the new node
    const pos = concentricPosition(data.layer, count - 1, count);
    updated.push({
      id: data.id,
      type: "streaming",
      position: pos,
      data: {
        label: "",
        type: data.type,
        layer: data.layer,
        selected: true,
        reasoning: "",
        streaming: true,
      },
      style: nodeStyle(data.type, true, data.layer),
    });

    return updated;
  });
}, [setNodes]);
```

- [ ] **Step 5: Manual verification**

Start the app with Docker, run auto-think, and verify:
- Nodes appear one-by-one with entrance animation
- Content text streams word-by-word
- Edges draw in after both endpoints exist
- Fallback to polling works if SSE disconnects

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ThinkingView.tsx
git commit -m "feat(sse): integrate SSE streaming into ThinkingView with animation"
```

---

## Task 10: Vite Proxy Fix (from earlier session)

**Files:**
- Modify: `frontend/vite.config.ts` (already modified but uncommitted)

- [ ] **Step 1: Verify the fix is still in place**

```bash
cat frontend/vite.config.ts
```

Should show `process.env.VITE_API_URL || ...` on the apiTarget line.

- [ ] **Step 2: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "fix: read VITE_API_URL for Docker proxy target"
```

---

## Task 11: E2E Verification

- [ ] **Step 1: Rebuild and start Docker**

```bash
docker compose up --build -d
```

- [ ] **Step 2: Verify SSE endpoint works**

```bash
curl -N "http://localhost:3000/api/thinking/auto" -X POST -H "Content-Type: application/json" -d '{"date":"2026-03-26","market":"US","max_depth":2}'
# Note the session_id

curl -N "http://localhost:3000/api/thinking/{session_id}/events"
# Should see streaming SSE events
```

- [ ] **Step 3: Open browser and test**

Open http://localhost:3000, click auto-run, verify:
- Nodes appear progressively (not all at once)
- Text streams word-by-word
- Edges draw in
- Session completes successfully

- [ ] **Step 4: Test fallback — kill SSE mid-stream, verify polling resumes**

---

## Dependency Graph

```
Task 1 (session_events) ─┐
Task 2 (stream_parser) ──┤
Task 3 (llm_config) ─────┼── Task 4 (streaming layer) ── Task 5 (SSE endpoint) ──┐
                          │                                                        │
Task 6 (types + layout) ─┤                                                        │
Task 7 (useSSESession) ──┼──────────────────── Task 9 (ThinkingView integration) ─┤
Task 8 (StreamingNode) ──┘                                                        │
                                                                                   │
Task 10 (vite proxy fix) ─────────────────────────── Task 11 (E2E verification) ──┘
```

Tasks 1, 2, 3, 6, 7, 8, 10 are independent and can run in parallel.
Task 4 depends on 1, 2, 3.
Task 5 depends on 4.
Task 9 depends on 6, 7, 8.
Task 11 depends on 5, 9, 10.
