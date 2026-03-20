from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_graph_service
from src.core.logger import get_logger
from src.services.graph_service import GraphService

log = get_logger("api.graphs")
router = APIRouter(prefix="/api/graphs", tags=["graphs"])


@router.get("/dates")
async def get_dates(service: GraphService = Depends(get_graph_service)):
    dates = await service.get_available_dates()
    log.info("GET /dates — %d dates available", len(dates))
    return dates


@router.get("/{date}")
async def get_graph(
    date: str,
    market: str = "US",
    service: GraphService = Depends(get_graph_service),
):
    log.info("GET /graphs/%s market=%s", date, market)
    graph = await service.get_graph(date, market)
    if not graph:
        log.info("Graph not found for %s/%s", date, market)
        raise HTTPException(status_code=404, detail="No graph for this date")
    log.debug(
        "Graph loaded: %d nodes, %d edges",
        len(graph.get("nodes", [])),
        len(graph.get("edges", [])),
    )
    return graph
