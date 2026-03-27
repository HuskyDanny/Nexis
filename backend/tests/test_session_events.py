import asyncio
import pytest
from src.services.session_events import (
    SessionRegistry,
    SessionEntry,
    SSEEvent,
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
