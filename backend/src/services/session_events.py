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
SESSION_TTL_S = 3600  # 1 hour


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
        payload = (
            json.dumps(self.data, ensure_ascii=False)
            if not isinstance(self.data, str)
            else self.data
        )
        parts.append(f"data: {payload}")
        return "\n".join(parts) + "\n\n"


@dataclass
class SessionEntry:
    """One active auto-run session."""

    queue: asyncio.Queue = field(
        default_factory=lambda: asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    )
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

    async def shutdown_all(self) -> None:
        """Drain all active sessions — push shutdown event and remove each."""
        count = len(self._sessions)
        for sid in list(self._sessions):
            entry = self._sessions.get(sid)
            if entry:
                try:
                    entry.queue.put_nowait(
                        SSEEvent(event="error", data={"error": "Server shutting down"})
                    )
                except asyncio.QueueFull:
                    pass
            self.remove(sid)
        if count:
            log.info("Shutdown: drained %d active SSE sessions", count)

    async def health_check(self) -> None:
        now = time.time()
        for sid, entry in list(self._sessions.items()):
            # Evict completed/failed tasks
            if entry.task and entry.task.done():
                log.info("Session %s task done — evicting", sid)
                self._sessions.pop(sid, None)
                continue
            # Evict stale sessions (TTL)
            if now - entry.created_at > SESSION_TTL_S:
                log.info("Session %s expired (TTL) — evicting", sid)
                self.remove(sid)
                continue
            qsize = entry.queue.qsize()
            if qsize > MAX_QUEUE_SIZE:
                log.error("Session %s queue overflow (%d) — cancelling", sid, qsize)
                self.remove(sid)
            elif qsize > WARN_QUEUE_SIZE:
                log.warning("Session %s queue backpressure: %d items", sid, qsize)
        if self._sessions:
            total = sum(e.queue.qsize() for e in self._sessions.values())
            log.info(
                "Active SSE sessions: %d, total queued: %d",
                len(self._sessions),
                total,
            )


# Module-level singleton
registry = SessionRegistry()
