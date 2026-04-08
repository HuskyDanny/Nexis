"""Thinking DAG API — start sessions, step through layers, toggle nodes, match values.

Auto-pipeline and SSE endpoints live in thinking_auto.py.
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.logger import get_logger
from src.core.config import settings
from src.database.mongodb import mongodb
from src.database.repositories.news_entity_repo import NewsEntityRepo
from src.pipelines.news.quota import apply_tiered_quota
from src.services.thinking_service import run_layer
from src.services.data_sources import fetch_real_news, fetch_real_stocks

# Auto-pipeline and SSE endpoints are in thinking_auto.py

log = get_logger("api.thinking")
router = APIRouter(prefix="/api/thinking", tags=["thinking"])


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

    # News: load from news_entities (global, no market filter) with tiered quota
    news_repo = NewsEntityRepo(mongodb.get_collection("news_entities"))
    all_news = await news_repo.get_active()  # No market filter
    news_items = apply_tiered_quota(
        sorted(all_news, key=lambda x: x.get("score", 0), reverse=True),
        macro_ratio=settings.news_macro_quota_ratio,
    )

    # Value: keep legacy path (market-scoped)
    pools_col = mongodb.get_collection("pools")
    value_pool = await pools_col.find_one(
        {"type": "value", "date": req.date, "market": req.market}, {"_id": 0}
    )
    value_items = (value_pool or {}).get("items", [])

    # If no cached data, fetch live
    if not news_items:
        log.info("No active news entities for %s, fetching live", req.date)
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
            session_id=session_id,
            confidence_threshold=session.get("confidence_threshold", 35),
        )

        new_nodes = result.effect_nodes + result.fetch_nodes + result.opportunity_nodes
        new_edges = result.all_edges
        ctrl_summary = result.controller_decision.get("summary", "")

        # Compute cache key for this layer's parent set
        from src.services.cache import parent_set_hash

        # Hash only current_layer parents (matching toggle_node's read path)
        current_layer_parents = [n for n in parent_nodes if n["layer"] == current_layer]
        ps_hash = parent_set_hash(sorted(n["id"] for n in current_layer_parents))

        # Write layer_cache in nested dict format: {"layer_cache.<layer>": {ps_hash: {nodes, edges}}}
        # MongoDB dot-notation sets layer_cache[str(next_layer)] = {ps_hash: data} in the document.
        # The read path in toggle_node does: layer_cache.get(str(layer), {}).get(ps_hash)
        # which matches this nested structure.
        cache_set_key = f"layer_cache.{next_layer}"
        cache_value = {ps_hash: {"nodes": new_nodes, "edges": new_edges}}

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
                        cache_set_key: cache_value,
                    },
                },
            )

            # Fire-and-forget graph write (graceful degradation)
            from src.graph.writer import try_ingest_thinking_layer

            try_ingest_thinking_layer(session_id, next_layer, new_nodes)
        else:
            await col.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "current_layer": next_layer,
                        "status": "paused",
                        f"chain_summaries.{next_layer}": ctrl_summary,
                        cache_set_key: cache_value,
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

    # Run matcher in executor to avoid blocking the event loop
    import asyncio
    from src.agents.thinking_crew import run_matcher

    loop = asyncio.get_running_loop()
    opportunities, match_edges, _tokens = await loop.run_in_executor(
        None, lambda: run_matcher(final_effects, value_pool)
    )

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
