from typing import Protocol, runtime_checkable
from pydantic import BaseModel


class ScoreResult(BaseModel):
    score: float
    factors: dict[str, float]


class ProcessResult(BaseModel):
    action: str  # "insert" or "merge"
    entity_id: str
    merged_from: str | None = None


class PipelineResult(BaseModel):
    inserted: int = 0
    merged: int = 0
    rescored: int = 0
    removed: int = 0


@runtime_checkable
class FetchStrategy(Protocol):
    async def fetch(self, market: str) -> list[dict]: ...


@runtime_checkable
class ProcessStrategy(Protocol):
    async def process(self, raw: dict, existing: list[dict]) -> ProcessResult: ...


@runtime_checkable
class ScoreStrategy(Protocol):
    def score(self, entity: dict) -> ScoreResult: ...


@runtime_checkable
class RetainStrategy(Protocol):
    def should_retain(self, entity: dict) -> bool: ...
