"""Thinking DAG API — start sessions, step through layers, toggle nodes, match values."""

import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.services.thinking_service import run_layer, run_pipeline
from src.services.data_sources import fetch_real_news, fetch_real_stocks

log = get_logger("api.thinking")
router = APIRouter(prefix="/api/thinking", tags=["thinking"])

PIPELINE_TIMEOUT_S = 300


# --- Helpers ---


async def _load_pools(date: str, market: str) -> tuple[list[dict], list[dict]]:
    """Load news/value pools from DB, falling back to live APIs."""
    pools_col = mongodb.get_collection("pools")
    news_pool = await pools_col.find_one(
        {"type": "news", "date": date, "market": market}, {"_id": 0}
    )
    value_pool = await pools_col.find_one(
        {"type": "value", "date": date, "market": market}, {"_id": 0}
    )
    news_items = (news_pool or {}).get("items", [])
    value_items = (value_pool or {}).get("items", [])
    if not news_items:
        news_items = await fetch_real_news(limit=10, topics="financial_markets")
    if not value_items:
        value_items = await asyncio.to_thread(fetch_real_stocks)
    return news_items, value_items


def _make_seed_nodes(news_list: list[dict]) -> list[dict]:
    """Create layer-0 seed nodes from news items."""
    return [
        {
            "id": n["id"],
            "layer": 0,
            "type": "news",
            "content": n.get("title", n.get("summary", "")),
            "reasoning": "",
            "sources": [n.get("url", "")],
            "parents": [],
            "selected": True,
            "metadata": {
                k: v for k, v in n.items() if k not in ("id", "title", "summary", "url")
            },
        }
        for n in news_list
    ]


def _make_session_doc(session_id, req, nodes, news_items, value_items, status="paused"):
    """Build a session document with all required fields."""
    from datetime import datetime, timezone

    return {
        "id": session_id,
        "date": req.date,
        "market": req.market,
        "max_depth": req.max_depth,
        "nodes": nodes,
        "edges": [],
        "status": status,
        "current_layer": 0,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "news_pool": news_items,
        "value_pool": value_items,
        "layer_cache": {},
        "chain_summaries": {},
        "confidence_threshold": 35,
    }


# --- Request/Response schemas ---


class StartRequest(BaseModel):
    date: str
    market: str = "US"
    max_depth: int = 3
    selected_news_ids: list[str] | None = None


class StartResponse(BaseModel):
    session_id: str
    status: str


class StepResponse(BaseModel):
    status: str
    current_layer: int


class ToggleRequest(BaseModel):
    selected: bool


class ToggleResponse(BaseModel):
    dirty_count: int
    status: str


# --- Endpoints ---


@router.post("", response_model=StartResponse)
async def start_thinking(req: StartRequest):
    """Start a new ThinkingSession."""
    from uuid import uuid4
    from datetime import datetime, timezone

    session_id = uuid4().hex[:12]
    log.info(
        "Starting session %s for %s/%s max_depth=%d",
        session_id,
        req.date,
        req.market,
        req.max_depth,
    )

    # Load pools — try MongoDB first, fall back to live APIs
    pools_col = mongodb.get_collection("pools")
    news_pool = await pools_col.find_one(
        {"type": "news", "date": req.date, "market": req.market}, {"_id": 0}
    )
    value_pool = await pools_col.find_one(
        {"type": "value", "date": req.date, "market": req.market}, {"_id": 0}
    )

    news_items = (news_pool or {}).get("items", [])
    value_items = (value_pool or {}).get("items", [])

    # If no cached data, fetch live
    if not news_items or not value_items:
        if not news_items:
            log.info("No cached news for %s, fetching live", req.date)
            news_items = await fetch_real_news(limit=10, topics="financial_markets")
        if not value_items:
            log.info("No cached values for %s, fetching live", req.date)
            value_items = await asyncio.to_thread(fetch_real_stocks)

    # If specific news IDs selected, filter; otherwise use all
    if req.selected_news_ids:
        selected_news = [n for n in news_items if n["id"] in req.selected_news_ids]
    else:
        selected_news = news_items

    # Create seed nodes (Layer 0) from selected news
    nodes = []
    for news in selected_news:
        nodes.append(
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
        )

    session = {
        "id": session_id,
        "date": req.date,
        "market": req.market,
        "max_depth": req.max_depth,
        "nodes": nodes,
        "edges": [],
        "status": "paused",  # paused after seeding, waiting for user to step
        "current_layer": 0,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "news_pool": news_items,
        "value_pool": value_items,
        "layer_cache": {},
        "chain_summaries": {},
        "confidence_threshold": 35,
    }

    col = mongodb.get_collection("thinking_sessions")
    await col.insert_one(session)
    log.info("Session %s created with %d seed nodes", session_id, len(nodes))

    return StartResponse(session_id=session_id, status="paused")


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get full ThinkingSession state."""
    col = mongodb.get_collection("thinking_sessions")
    session = await col.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/step", response_model=StepResponse)
async def think_step(session_id: str):
    """Execute one layer of thinking. Uses CAS to prevent concurrent steps."""
    from pymongo import ReturnDocument

    col = mongodb.get_collection("thinking_sessions")

    # CAS: atomically claim the session for thinking
    session = await col.find_one_and_update(
        {"id": session_id, "status": {"$in": ["paused", "idle"]}},
        {"$set": {"status": "thinking"}, "$inc": {"version": 1}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not session:
        existing = await col.find_one({"id": session_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot step: session is {existing['status']} (concurrent modification)",
        )

    current_layer = session["current_layer"]
    next_layer = current_layer + 1

    if next_layer > session["max_depth"]:
        await col.update_one({"id": session_id}, {"$set": {"status": "paused"}})
        raise HTTPException(status_code=400, detail="Max depth reached. Use /match.")

    log.info("Session %s: stepping to layer %d", session_id, next_layer)

    try:
        parent_nodes = [
            n for n in session["nodes"] if n["selected"] and n["layer"] <= current_layer
        ]
        news_pool = session.get("news_pool", [])
        value_pool = session.get("value_pool", [])
        chain_summaries = session.get("chain_summaries", {})
        chain_summary = chain_summaries.get(str(current_layer), "")

        result = await run_layer(
            chain_summary=chain_summary,
            parent_nodes=parent_nodes,
            news_pool=news_pool,
            value_pool=value_pool,
            layer=next_layer,
            max_depth=session["max_depth"],
            confidence_threshold=session.get("confidence_threshold", 35),
        )

        new_nodes = result.effect_nodes + result.fetch_nodes + result.opportunity_nodes
        new_edges = result.all_edges
        ctrl_summary = result.controller_decision.get("summary", "")

        if new_nodes:
            await col.update_one(
                {"id": session_id},
                {
                    "$push": {
                        "nodes": {"$each": new_nodes},
                        "edges": {"$each": new_edges},
                    },
                    "$set": {
                        "current_layer": next_layer,
                        "status": "paused",
                        f"chain_summaries.{next_layer}": ctrl_summary,
                    },
                },
            )
        else:
            await col.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "current_layer": next_layer,
                        "status": "paused",
                        f"chain_summaries.{next_layer}": ctrl_summary,
                    },
                },
            )

        log.info(
            "Session %s: layer %d complete — %d new nodes",
            session_id,
            next_layer,
            len(new_nodes),
        )
        return StepResponse(status="paused", current_layer=next_layer)

    except Exception as e:
        log.error(
            "Session %s: thinking error at layer %d — %s",
            session_id,
            next_layer,
            str(e),
        )
        await col.update_one(
            {"id": session_id},
            {"$set": {"status": "error", "error": str(e)}},
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{session_id}/node/{node_id}", response_model=ToggleResponse)
async def toggle_node(session_id: str, node_id: str, req: ToggleRequest):
    """Toggle node selection. Only allowed when paused/idle."""
    col = mongodb.get_collection("thinking_sessions")
    session = await col.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] not in ("paused", "idle", "complete"):
        raise HTTPException(status_code=409, detail="Cannot modify during thinking")

    # Find and update the node
    nodes = session["nodes"]
    target_node = None
    for n in nodes:
        if n["id"] == node_id:
            target_node = n
            break

    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found")

    target_node["selected"] = req.selected

    dirty_count = 0
    if not req.selected:
        # === DESELECT: BFS cascade (existing, unchanged) ===
        dirty_ids = set()
        queue = [node_id]
        edge_map: dict[str, list[str]] = {}
        for e in session["edges"]:
            edge_map.setdefault(e["source"], []).append(e["target"])

        while queue:
            current = queue.pop(0)
            for child in edge_map.get(current, []):
                if child not in dirty_ids:
                    dirty_ids.add(child)
                    queue.append(child)

        for n in nodes:
            if n["id"] in dirty_ids:
                n["selected"] = False
                dirty_count += 1

    else:
        # === RE-SELECT: check cache layer by layer ===
        from src.services.cache import parent_set_hash

        layer_cache = session.get("layer_cache", {})
        target_layer = target_node["layer"]
        max_layer = max((n["layer"] for n in nodes), default=0)

        for check_layer in range(target_layer + 1, max_layer + 1):
            selected_parents = sorted(
                n["id"]
                for n in nodes
                if n["selected"] and n["layer"] == check_layer - 1
            )
            ps_hash = parent_set_hash(selected_parents)

            cached = layer_cache.get(str(check_layer), {}).get(ps_hash)
            if not cached:
                break

            cached_ids = {cn["id"] for cn in cached["nodes"]}
            for n in nodes:
                if n["id"] in cached_ids and not n["selected"]:
                    n["selected"] = True
                    dirty_count += 1

    await col.update_one({"id": session_id}, {"$set": {"nodes": nodes}})
    log.info(
        "Session %s: node %s selected=%s, %d dirty",
        session_id,
        node_id,
        req.selected,
        dirty_count,
    )

    return ToggleResponse(dirty_count=dirty_count, status=session["status"])


@router.post("/{session_id}/match")
async def match_values(session_id: str):
    """Match final-layer effects against value pool to find opportunities."""
    col = mongodb.get_collection("thinking_sessions")
    session = await col.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_layer = session["current_layer"]
    final_effects = [
        n
        for n in session["nodes"]
        if n["selected"] and n["layer"] == current_layer and n["type"] == "effect"
    ]
    value_pool = session.get("value_pool", [])

    log.info(
        "Session %s: matching %d effects against %d values",
        session_id,
        len(final_effects),
        len(value_pool),
    )

    # Use run_matcher directly for standalone match requests
    from src.agents.thinking_crew import run_matcher

    opportunities, match_edges = run_matcher(final_effects, value_pool)

    # Persist
    if opportunities:
        await col.update_one(
            {"id": session_id},
            {
                "$push": {
                    "nodes": {"$each": opportunities},
                    "edges": {"$each": match_edges},
                },
                "$set": {"status": "complete"},
            },
        )
    else:
        await col.update_one({"id": session_id}, {"$set": {"status": "complete"}})

    log.info("Session %s: found %d opportunities", session_id, len(opportunities))
    return {"opportunities": opportunities}


@router.post("/auto", response_model=StartResponse)
async def auto_think(req: StartRequest):
    """Full auto pipeline: create session -> think all layers -> match.
    Returns session_id. Poll GET /thinking/:id to watch progress."""
    from uuid import uuid4
    from datetime import datetime, timezone

    session_id = uuid4().hex[:12]
    log.info(
        "AUTO session %s for %s/%s max_depth=%d",
        session_id,
        req.date,
        req.market,
        req.max_depth,
    )

    # Load pools
    pools_col = mongodb.get_collection("pools")
    news_pool = await pools_col.find_one(
        {"type": "news", "date": req.date, "market": req.market}, {"_id": 0}
    )
    value_pool = await pools_col.find_one(
        {"type": "value", "date": req.date, "market": req.market}, {"_id": 0}
    )

    news_items = (news_pool or {}).get("items", [])
    value_items = (value_pool or {}).get("items", [])

    if not news_items or not value_items:
        if not news_items:
            news_items = await fetch_real_news(limit=10, topics="financial_markets")
        if not value_items:
            value_items = await asyncio.to_thread(fetch_real_stocks)

    sorted_news = sorted(news_items, key=lambda n: n.get("confidence", 0), reverse=True)
    selected = sorted_news[:5]
    log.info("Auto-selected %d/%d news by impact", len(selected), len(news_items))

    nodes = []
    for news in selected:
        nodes.append(
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
        )

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
        # For MVP, just poll session status every 500ms
        col = mongodb.get_collection("thinking_sessions")
        last_status = None
        last_node_count = 0

        for _ in range(120):  # 60 seconds max
            session = await col.find_one({"id": session_id}, {"_id": 0})
            if not session:
                yield f'event: error\ndata: {{"error": "Session not found"}}\n\n'
                return

            status = session["status"]
            node_count = len(session["nodes"])

            if status != last_status:
                yield f"event: status\ndata: {{\"status\": \"{status}\", \"current_layer\": {session['current_layer']}}}\n\n"
                last_status = status

            if node_count != last_node_count:
                yield f'event: node_count\ndata: {{"count": {node_count}}}\n\n'
                last_node_count = node_count

            if status in ("complete", "error"):
                yield f'event: done\ndata: {{"status": "{status}"}}\n\n'
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
