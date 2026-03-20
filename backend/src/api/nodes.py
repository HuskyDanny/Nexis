from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_graph_service
from src.services.graph_service import GraphService

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("/{node_id}/layers")
async def get_layers(
    node_id: str,
    service: GraphService = Depends(get_graph_service),
):
    layers = await service.get_node_layers(node_id)
    if layers is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return layers
