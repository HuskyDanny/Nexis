from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class ThinkingNodeType(StrEnum):
    NEWS = "news"
    EFFECT = "effect"
    FETCH = "fetch"
    OPPORTUNITY = "opportunity"


class ThinkingNode(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    layer: int = 0
    type: ThinkingNodeType
    content: str
    reasoning: str = ""
    sources: list[str] = Field(default_factory=list)
    parents: list[str] = Field(default_factory=list)
    selected: bool = True
    metadata: dict = Field(default_factory=dict)


class ThinkingEdge(BaseModel):
    source: str
    target: str
    relationship: str  # "causes", "compounds", "fetched_for", "matches"


class SessionStatus(StrEnum):
    IDLE = "idle"
    THINKING = "thinking"
    PAUSED = "paused"
    COMPLETE = "complete"
    ERROR = "error"


class ThinkingSession(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    date: str
    market: str = "US"
    max_depth: int = 3
    nodes: list[ThinkingNode] = Field(default_factory=list)
    edges: list[ThinkingEdge] = Field(default_factory=list)
    status: SessionStatus = SessionStatus.IDLE
    current_layer: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def validate_acyclicity(nodes: list[ThinkingNode], edges: list[ThinkingEdge]) -> bool:
    """Validate that all edges go from a lower layer to a strictly higher layer."""
    layer_map = {node.id: node.layer for node in nodes}
    for edge in edges:
        src_layer = layer_map.get(edge.source)
        tgt_layer = layer_map.get(edge.target)
        if src_layer is None or tgt_layer is None:
            return False
        if src_layer >= tgt_layer:
            return False
    return True
