"""Auto-pipeline endpoints: fire-and-forget full run + SSE progress stream."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.services.session_events import registry, SSEEvent
from src.services.thinking_service import run_layer_streaming, LayerResult
from src.services.data_sources import fetch_real_news, fetch_real_stocks
from src.api.thinking import StartRequest, StartResponse

log = get_logger("api.thinking_auto")
router = APIRouter(prefix="/api/thinking", tags=["thinking"])

PIPELINE_TIMEOUT_S = 300


@router.post("/auto", response_model=StartResponse)
async def auto_think(req: StartRequest):
    """Full auto pipeline: create session -> stream all layers -> match.
    Returns session_id. Connect to GET /thinking/:id/events for SSE stream."""
    session_id = uuid4().hex[:12]
    log.info(
        "AUTO session %s for %s/%s max_depth=%d",
        session_id,
        req.date,
        req.market,
        req.max_depth,
    )

    # Load pools — DB first, fall back to live APIs
    pools_col = mongodb.get_collection("pools")
    news_pool = await pools_col.find_one(
        {"type": "news", "date": req.date, "market": req.market}, {"_id": 0}
    )
    value_pool = await pools_col.find_one(
        {"type": "value", "date": req.date, "market": req.market}, {"_id": 0}
    )

    news_items = (news_pool or {}).get("items", [])
    value_items = (value_pool or {}).get("items", [])

    if not news_items:
        news_items = await fetch_real_news(limit=10, topics="financial_markets")
    if not value_items:
        value_items = await asyncio.to_thread(fetch_real_stocks)

    sorted_news = sorted(news_items, key=lambda n: n.get("confidence", 0), reverse=True)
    selected = sorted_news[:5]
    log.info("Auto-selected %d/%d news by impact", len(selected), len(news_items))

    nodes = [
        {
            "id": news["id"],
            "layer": 0,
            "type": "news",
            "content": news.get("title", news.get("summary", "")),
            "reasoning": "",
            "sources": [news.get("url", "")],
            "parents": [],
            "selected": True,
            "metadata": {
                k: v
                for k, v in news.items()
                if k not in ("id", "title", "summary", "url")
            },
        }
        for news in selected
    ]

    session = {
        "id": session_id,
        "date": req.date,
        "market": req.market,
        "max_depth": req.max_depth,
        "nodes": nodes,
        "edges": [],
        "status": "thinking",
        "current_layer": 0,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "news_pool": news_items,
        "value_pool": value_items,
        "chain_summaries": {},
        "confidence_threshold": 35,
    }

    col = mongodb.get_collection("thinking_sessions")
    await col.insert_one(session)

    async def _run_streaming_pipeline():
        """Run the full pipeline using streaming layer runner."""
        chain_summary = ""
        all_layer_nodes: list[list[dict]] = [nodes]  # layer 0 = seeds

        for layer in range(1, req.max_depth + 1):
            # Collect parent nodes from all prior layers
            parent_nodes = []
            for layer_nodes in all_layer_nodes:
                parent_nodes.extend(n for n in layer_nodes if n.get("selected", False))

            result: LayerResult = await run_layer_streaming(
                session_id=session_id,
                registry=registry,
                chain_summary=chain_summary,
                parent_nodes=parent_nodes,
                news_pool=news_items,
                value_pool=value_items,
                layer=layer,
                max_depth=req.max_depth,
            )

            # Persist nodes/edges to MongoDB
            new_nodes = (
                result.effect_nodes + result.fetch_nodes + result.opportunity_nodes
            )
            update: dict = {
                "$set": {"current_layer": layer, "status": "thinking"},
            }
            if new_nodes:
                update["$push"] = {
                    "nodes": {"$each": new_nodes},
                    "edges": {"$each": result.all_edges},
                }
            await col.update_one({"id": session_id}, update)
            log.info(
                "AUTO %s: layer %d — %d nodes",
                session_id,
                layer,
                len(new_nodes),
            )

            # Accumulate for future parent collection
            all_layer_nodes.append(new_nodes)
            chain_summary = result.controller_decision.get("summary", chain_summary)

            # Controller says stop?
            if not result.controller_decision.get("continue", False):
                log.info(
                    "AUTO %s: controller stopped at layer %d: %s",
                    session_id,
                    layer,
                    result.controller_decision.get("reasoning", ""),
                )
                break

        await col.update_one({"id": session_id}, {"$set": {"status": "complete"}})
        entry = registry.get(session_id)
        if entry:
            await entry.queue.put(
                SSEEvent(
                    event="session_complete",
                    data={"status": "complete"},
                    id="session:complete",
                )
            )
        log.info("AUTO %s: complete", session_id)

    async def _run_with_lifecycle():
        """Wrap pipeline with timeout and error handling."""
        try:
            await asyncio.wait_for(
                _run_streaming_pipeline(), timeout=PIPELINE_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            log.warning(
                "AUTO %s: pipeline timed out after %ds",
                session_id,
                PIPELINE_TIMEOUT_S,
            )
            await col.update_one({"id": session_id}, {"$set": {"status": "timeout"}})
            entry = registry.get(session_id)
            if entry:
                await entry.queue.put(
                    SSEEvent(
                        event="error",
                        data={
                            "error": f"Pipeline timed out after {PIPELINE_TIMEOUT_S}s"
                        },
                        id="session:error",
                    )
                )
        except asyncio.CancelledError:
            log.info("AUTO %s: cancelled", session_id)
            await col.update_one({"id": session_id}, {"$set": {"status": "cancelled"}})
            entry = registry.get(session_id)
            if entry:
                await entry.queue.put(
                    SSEEvent(
                        event="session_complete",
                        data={"status": "cancelled"},
                        id="session:complete",
                    )
                )
        except Exception as e:
            log.error("AUTO %s: failed — %s", session_id, e)
            await col.update_one(
                {"id": session_id},
                {"$set": {"status": "error", "error": str(e)}},
            )
            entry = registry.get(session_id)
            if entry:
                await entry.queue.put(
                    SSEEvent(
                        event="error",
                        data={"error": str(e)},
                        id="session:error",
                    )
                )

    # Create task FIRST, then register in registry
    task = asyncio.create_task(_run_with_lifecycle())
    registry.create(session_id, task)

    return StartResponse(session_id=session_id, status="thinking")


@router.get("/{session_id}/events")
async def session_events(session_id: str, request: Request):
    """SSE stream — live from queue if session is active, replay from DB if complete."""

    async def _live_stream(session_id: str):
        """Stream events from the session queue with disconnect detection."""
        try:
            while True:
                if await request.is_disconnected():
                    log.info("SSE client disconnected for %s", session_id)
                    registry.remove(session_id)
                    return

                entry = registry.get(session_id)
                if entry is None:
                    # Session was removed (completed/cancelled) — stop
                    return

                try:
                    event = await asyncio.wait_for(entry.queue.get(), timeout=1.0)
                    yield event.serialize()
                    if event.event in ("session_complete", "error"):
                        return
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            # Clean up registry on exit
            registry.remove(session_id)

    async def _replay_from_db(session_id: str):
        """Replay a completed session from MongoDB — instant, no animation."""
        col = mongodb.get_collection("thinking_sessions")
        session = await col.find_one({"id": session_id}, {"_id": 0})
        if not session:
            yield SSEEvent(
                event="error",
                data={"error": "Session not found"},
                id="session:error",
            ).serialize()
            return

        # Emit all nodes as node_start + node_complete (instant replay)
        for i, node in enumerate(session.get("nodes", [])):
            layer = node.get("layer", 0)
            node_type = node.get("type", "unknown")
            event_id = f"l:{layer}:n:{i}"
            yield SSEEvent(
                event="node_start",
                data={
                    "id": node.get("id", ""),
                    "layer": layer,
                    "type": node_type,
                },
                id=event_id,
            ).serialize()
            yield SSEEvent(
                event="node_complete",
                data=node,
                id=f"{event_id}:done",
            ).serialize()

        # Emit edges
        edges = session.get("edges", [])
        if edges:
            yield SSEEvent(
                event="edges",
                data={"edges": edges, "source": "replay"},
                id="replay:edges",
            ).serialize()

        # Final event
        yield SSEEvent(
            event="session_complete",
            data={"status": session.get("status", "complete"), "replay": True},
            id="session:complete",
        ).serialize()

    # Check if session is live in registry
    entry = registry.get(session_id)
    if entry is not None:
        generator = _live_stream(session_id)
    else:
        generator = _replay_from_db(session_id)

    return StreamingResponse(generator, media_type="text/event-stream")
