from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from src.models.node import Edge, Node


class Market(StrEnum):
    CN = "CN"
    US = "US"


class GraphStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class DailyGraph(BaseModel):
    date: str
    market: Market
    status: GraphStatus = GraphStatus.PENDING
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
