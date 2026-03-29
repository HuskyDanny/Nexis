"""Tests for updated thinking API endpoints.

Covers:
- think_step() calling run_layer() and storing chain_summaries
- auto_think() using run_pipeline() with asyncio.wait_for timeout
- Stuck session cleanup on startup
- Session creation includes chain_summaries and confidence_threshold
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.thinking_service import LayerResult


# --- Fixtures ---


def _make_session(
    session_id="sess1",
    status="paused",
    current_layer=0,
    max_depth=3,
    **overrides,
):
    """Build a mock session document with new schema fields."""
    session = {
        "id": session_id,
        "status": status,
        "version": 1,
        "current_layer": current_layer,
        "max_depth": max_depth,
        "nodes": [
            {
                "id": "n1",
                "layer": 0,
                "type": "news",
                "content": "Fed raises rates",
                "selected": True,
                "parents": [],
            }
        ],
        "edges": [],
        "news_pool": [{"id": "n1", "title": "Fed raises rates"}],
        "value_pool": [{"ticker": "AAPL", "name": "Apple"}],
        "chain_summaries": {},
        "confidence_threshold": 35,
        "layer_cache": {},
        "created_at": "2026-03-23T00:00:00+00:00",
    }
    session.update(overrides)
    return session


def _make_layer_result(**overrides):
    """Build a LayerResult with sensible defaults."""
    defaults = dict(
        effect_nodes=[
            {
                "id": "e1",
                "layer": 1,
                "type": "effect",
                "content": "Tech selloff",
                "selected": True,
                "parents": ["n1"],
            }
        ],
        fetch_nodes=[],
        opportunity_nodes=[],
        all_edges=[{"source": "n1", "target": "e1"}],
        controller_decision={
            "continue": True,
            "reasoning": "More to explore",
            "summary": "Fed tightening cycle summary",
        },
    )
    defaults.update(overrides)
    return LayerResult(**defaults)


# --- think_step() tests ---


@pytest.mark.asyncio
async def test_step_calls_run_layer():
    """think_step() should call run_layer() instead of the old think_effects()."""
    mock_col = AsyncMock()
    session = _make_session()
    session["status"] = "thinking"
    session["version"] = 2
    mock_col.find_one_and_update.return_value = session

    lr = _make_layer_result()

    with (
        patch("src.api.thinking.mongodb") as mock_db,
        patch(
            "src.api.thinking.run_layer", new_callable=AsyncMock, return_value=lr
        ) as mock_rl,
    ):
        mock_db.get_collection.return_value = mock_col
        from src.api.thinking import think_step

        await think_step("sess1")

        mock_rl.assert_called_once()
        kw = mock_rl.call_args
        # Verify key arguments
        assert kw.kwargs.get("layer") == 1 or (kw.args and kw.args[4] == 1)


@pytest.mark.asyncio
async def test_step_stores_chain_summary():
    """think_step() should store the controller's summary in chain_summaries."""
    mock_col = AsyncMock()
    session = _make_session()
    session["status"] = "thinking"
    session["version"] = 2
    mock_col.find_one_and_update.return_value = session

    lr = _make_layer_result(
        controller_decision={
            "continue": True,
            "reasoning": "Exploring",
            "summary": "Layer 1 summary text",
        }
    )

    with (
        patch("src.api.thinking.mongodb") as mock_db,
        patch("src.api.thinking.run_layer", new_callable=AsyncMock, return_value=lr),
    ):
        mock_db.get_collection.return_value = mock_col
        from src.api.thinking import think_step

        await think_step("sess1")

        # Check that update_one was called with chain_summaries
        update_call = mock_col.update_one.call_args
        set_dict = update_call[0][1]["$set"]
        assert "chain_summaries.1" in set_dict
        assert set_dict["chain_summaries.1"] == "Layer 1 summary text"


@pytest.mark.asyncio
async def test_step_passes_existing_chain_summary():
    """think_step() should pass existing chain_summary for the current layer."""
    mock_col = AsyncMock()
    session = _make_session(
        current_layer=1,
        chain_summaries={"1": "Prior summary from layer 1"},
    )
    session["nodes"].append(
        {
            "id": "e1",
            "layer": 1,
            "type": "effect",
            "content": "Tech selloff",
            "selected": True,
            "parents": ["n1"],
        }
    )
    session["status"] = "thinking"
    session["version"] = 2
    mock_col.find_one_and_update.return_value = session

    lr = _make_layer_result()

    with (
        patch("src.api.thinking.mongodb") as mock_db,
        patch(
            "src.api.thinking.run_layer", new_callable=AsyncMock, return_value=lr
        ) as mock_rl,
    ):
        mock_db.get_collection.return_value = mock_col
        from src.api.thinking import think_step

        await think_step("sess1")

        call_kwargs = mock_rl.call_args.kwargs
        assert call_kwargs.get("chain_summary") == "Prior summary from layer 1"


@pytest.mark.asyncio
async def test_step_stores_all_node_types():
    """think_step() should persist effect_nodes + fetch_nodes + opportunity_nodes."""
    mock_col = AsyncMock()
    session = _make_session()
    session["status"] = "thinking"
    session["version"] = 2
    mock_col.find_one_and_update.return_value = session

    lr = _make_layer_result(
        effect_nodes=[
            {
                "id": "e1",
                "layer": 1,
                "type": "effect",
                "selected": True,
                "parents": ["n1"],
            }
        ],
        fetch_nodes=[
            {
                "id": "f1",
                "layer": 1,
                "type": "fetch",
                "selected": True,
                "parents": ["n1"],
            }
        ],
        opportunity_nodes=[
            {
                "id": "o1",
                "layer": 1,
                "type": "opportunity",
                "selected": True,
                "parents": ["e1"],
            }
        ],
        all_edges=[
            {"source": "n1", "target": "e1"},
            {"source": "n1", "target": "f1"},
            {"source": "e1", "target": "o1"},
        ],
    )

    with (
        patch("src.api.thinking.mongodb") as mock_db,
        patch("src.api.thinking.run_layer", new_callable=AsyncMock, return_value=lr),
    ):
        mock_db.get_collection.return_value = mock_col
        from src.api.thinking import think_step

        await think_step("sess1")

        update_call = mock_col.update_one.call_args
        pushed_nodes = update_call[0][1]["$push"]["nodes"]["$each"]
        node_ids = {n["id"] for n in pushed_nodes}
        assert node_ids == {"e1", "f1", "o1"}


# --- auto_think() timeout tests ---


@pytest.mark.asyncio
async def test_auto_think_timeout_sets_status():
    """auto_think() should set status='timeout' when pipeline exceeds 300s."""
    mock_col = AsyncMock()
    mock_pools_col = AsyncMock()
    mock_pools_col.find_one.return_value = None

    def get_collection(name):
        if name == "pools":
            return mock_pools_col
        return mock_col

    # Create a streaming layer that hangs (simulates timeout)
    async def slow_layer(*args, **kwargs):
        await asyncio.sleep(999)

    with (
        patch("src.api.thinking_auto.mongodb") as mock_db,
        patch("src.api.thinking_auto.run_layer_streaming", side_effect=slow_layer),
        patch(
            "src.api.thinking_auto.fetch_real_news",
            new_callable=AsyncMock,
            return_value=[{"id": "n1", "title": "Test news", "confidence": 90}],
        ),
        patch(
            "src.api.thinking_auto.fetch_real_stocks",
            return_value=[{"ticker": "AAPL", "name": "Apple"}],
        ),
        patch(
            "src.api.thinking_auto.PIPELINE_TIMEOUT_S", 0.1
        ),  # Very short timeout for test
    ):
        mock_db.get_collection.side_effect = get_collection
        from src.api.thinking_auto import auto_think
        from src.api.thinking import StartRequest

        req = StartRequest(date="2026-03-23", market="US", max_depth=3)
        resp = await auto_think(req)
        assert resp.status == "thinking"

        # Wait for the background task to complete (timeout + buffer)
        await asyncio.sleep(0.5)

        # Verify status was set to timeout
        timeout_calls = [
            c
            for c in mock_col.update_one.call_args_list
            if "$set" in c[0][1] and c[0][1]["$set"].get("status") == "timeout"
        ]
        assert len(timeout_calls) >= 1


@pytest.mark.asyncio
async def test_auto_think_session_includes_new_fields():
    """auto_think() session doc should include chain_summaries and confidence_threshold."""
    mock_col = AsyncMock()
    mock_pools_col = AsyncMock()
    mock_pools_col.find_one.return_value = None

    def get_collection(name):
        if name == "pools":
            return mock_pools_col
        return mock_col

    # Streaming layer that returns empty result (stops immediately)
    from src.services.thinking_service import LayerResult

    async def fast_layer(*args, **kwargs):
        return LayerResult(
            controller_decision={"continue": False, "reasoning": "test", "summary": ""}
        )

    with (
        patch("src.api.thinking_auto.mongodb") as mock_db,
        patch("src.api.thinking_auto.run_layer_streaming", side_effect=fast_layer),
        patch(
            "src.api.thinking_auto.fetch_real_news",
            new_callable=AsyncMock,
            return_value=[{"id": "n1", "title": "Test news", "confidence": 90}],
        ),
        patch(
            "src.api.thinking_auto.fetch_real_stocks",
            return_value=[{"ticker": "AAPL", "name": "Apple"}],
        ),
    ):
        mock_db.get_collection.side_effect = get_collection
        from src.api.thinking_auto import auto_think
        from src.api.thinking import StartRequest

        req = StartRequest(date="2026-03-23", market="US", max_depth=3)
        await auto_think(req)

        # Check insert_one was called with new fields
        insert_call = mock_col.insert_one.call_args
        doc = insert_call[0][0]
        assert doc["chain_summaries"] == {}
        assert doc["confidence_threshold"] == 35


# --- start_thinking() session schema tests ---


@pytest.mark.asyncio
async def test_start_thinking_session_includes_new_fields():
    """start_thinking() session doc should include chain_summaries and confidence_threshold."""
    mock_col = AsyncMock()
    mock_pools_col = AsyncMock()
    mock_pools_col.find_one.return_value = {
        "items": [{"id": "v1", "title": "Value", "ticker": "AAPL"}]
    }

    # news_entities collection: find().to_list() must return a list (not a coroutine)
    mock_news_col = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_news_col.find.return_value = mock_cursor

    def get_collection(name):
        if name == "pools":
            return mock_pools_col
        if name == "news_entities":
            return mock_news_col
        return mock_col

    with patch("src.api.thinking.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_collection
        from src.api.thinking import start_thinking, StartRequest

        req = StartRequest(date="2026-03-23", market="US", max_depth=3)
        await start_thinking(req)

        insert_call = mock_col.insert_one.call_args
        doc = insert_call[0][0]
        assert doc["chain_summaries"] == {}
        assert doc["confidence_threshold"] == 35


# --- Stuck session cleanup tests ---


@pytest.mark.asyncio
async def test_stuck_session_cleanup_on_startup():
    """Lifespan should mark old 'thinking' sessions as 'timeout'."""
    mock_col = AsyncMock()

    with (
        patch("src.main.mongodb") as mock_mongo,
        patch("src.main.redis_client") as mock_redis,
    ):
        mock_mongo.connect = AsyncMock()
        mock_mongo.close = AsyncMock()
        mock_mongo.get_collection.return_value = mock_col
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()

        from src.main import lifespan, app

        async with lifespan(app):
            # Verify update_many was called to sweep stuck sessions
            mock_col.update_many.assert_called_once()
            call_args = mock_col.update_many.call_args
            filter_arg = call_args[0][0]
            update_arg = call_args[0][1]
            assert filter_arg["status"] == "thinking"
            assert "$lt" in filter_arg["created_at"]
            assert update_arg["$set"]["status"] == "timeout"
