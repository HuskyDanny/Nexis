"""Auto-pipeline endpoints: fire-and-forget full run + SSE progress stream."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.services.thinking_service import run_pipeline
from src.services.data_sources import fetch_real_news, fetch_real_stocks
from src.api.thinking import StartRequest, StartResponse

log = get_logger("api.thinking_auto")
router = APIRouter(prefix="/api/thinking", tags=["thinking"])

PIPELINE_TIMEOUT_S = 300


@router.post("/auto", response_model=StartResponse)
async def auto_think(req: StartRequest):
    """Full auto pipeline: create session -> think all layers -> match.
    Returns session_id. Poll GET /thinking/:id to watch progress."""
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

    async def _run_with_timeout():
        async def _on_layer_complete(layer: int, result) -> None:
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
            log.info("AUTO %s: layer %d — %d nodes", session_id, layer, len(new_nodes))

        try:
            await asyncio.wait_for(
                run_pipeline(
                    session_id=session_id,
                    seeds=nodes,
                    news_pool=news_items,
                    value_pool=value_items,
                    max_depth=req.max_depth,
                    on_layer_complete=_on_layer_complete,
                ),
                timeout=PIPELINE_TIMEOUT_S,
            )
            await col.update_one({"id": session_id}, {"$set": {"status": "complete"}})
            log.info("AUTO %s: complete", session_id)
        except asyncio.TimeoutError:
            log.warning(
                "AUTO %s: pipeline timed out after %ds", session_id, PIPELINE_TIMEOUT_S
            )
            await col.update_one({"id": session_id}, {"$set": {"status": "timeout"}})
        except Exception as e:
            log.error("AUTO %s: failed — %s", session_id, e)
            await col.update_one(
                {"id": session_id}, {"$set": {"status": "error", "error": str(e)}}
            )

    asyncio.create_task(_run_with_timeout())
    return StartResponse(session_id=session_id, status="thinking")


@router.get("/{session_id}/events")
async def session_events(session_id: str):
    """SSE stream for real-time session updates (placeholder for now)."""

    async def event_stream():
        col = mongodb.get_collection("thinking_sessions")
        last_status = None
        last_node_count = 0

        for _ in range(120):  # 60 seconds max
            session = await col.find_one({"id": session_id}, {"_id": 0})
            if not session:
                yield 'event: error\ndata: {"error": "Session not found"}\n\n'
                return

            status = session["status"]
            node_count = len(session["nodes"])

            if status != last_status:
                yield (
                    f"event: status\ndata: "
                    f'{{"status": "{status}", "current_layer": {session["current_layer"]}}}\n\n'
                )
                last_status = status

            if node_count != last_node_count:
                yield f'event: node_count\ndata: {{"count": {node_count}}}\n\n'
                last_node_count = node_count

            if status in ("complete", "error"):
                yield f'event: done\ndata: {{"status": "{status}"}}\n\n'
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
