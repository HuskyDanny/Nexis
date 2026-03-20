from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_graph_service
from src.services.graph_service import GraphService

router = APIRouter(prefix="/api/graphs", tags=["graphs"])


@router.get("/dates")
async def get_dates(service: GraphService = Depends(get_graph_service)):
    return await service.get_available_dates()


@router.get("/{date}")
async def get_graph(
    date: str,
    market: str = "US",
    service: GraphService = Depends(get_graph_service),
):
    graph = await service.get_graph(date, market)
    if not graph:
        raise HTTPException(status_code=404, detail="No graph for this date")
    return graph
