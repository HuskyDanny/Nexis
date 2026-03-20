from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    NEWS_EVENT = "news_event"
    IMPACT = "impact"
    STOCK_ENDPOINT = "stock_endpoint"
    VALUE_OPPORTUNITY = "value_opportunity"
    REASON = "reason"
    CONVERGENCE = "convergence"


class Direction(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class Node(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    graph_id: str
    type: NodeType
    surface_summary: str
    direction: Direction
    confidence: float


class Layer(BaseModel):
    node_id: str
    depth: int = Field(ge=0, le=3)
    content: str
    tool_outputs: dict | None = None
    sources: list[str] | None = None


class Edge(BaseModel):
    source: str
    target: str
    label: str
    relationship_type: str | None = None
