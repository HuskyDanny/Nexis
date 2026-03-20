from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class Annotation(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    node_id: str
    user_id: str
    text: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
