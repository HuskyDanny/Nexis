"""Custom edge types for Graphiti extraction.

These are Pydantic BaseModels passed to add_episode(edge_types=...).
The fact field on each edge carries the human-readable summary.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Impacts(BaseModel):
    """A causal impact from one entity to another (event impacts company/sector)."""

    magnitude: str | None = Field(
        default=None, description="Impact strength: small, medium, large"
    )
    direction: str | None = Field(
        default=None, description="Impact direction: positive, negative, neutral"
    )
    channel: str | None = Field(
        default=None,
        description="Mechanism: monetary_policy, supply_chain, demand, regulatory, sentiment",
    )


class CausedBy(BaseModel):
    """A causal chain link — an effect is caused by a parent event or effect."""

    layer: int | None = Field(default=None, description="Pipeline layer where inferred")
    confidence: float | None = Field(default=None, description="Confidence 0-100")


class Matches(BaseModel):
    """An effect matches an investment opportunity."""

    convergence_score: float | None = Field(
        default=None, description="Convergence score 0-100"
    )
    sentiment_score: float | None = Field(
        default=None, description="Sentiment alignment 0-100"
    )


class InSector(BaseModel):
    """Links an entity to its industry sector."""

    pass


class Mentions(BaseModel):
    """A news article mentions a company, event, or sector."""

    relevance: float | None = Field(default=None, description="Mention relevance 0-1")


# Lookup for passing to add_episode
NEWS_EDGE_TYPES: dict[str, type[BaseModel]] = {
    "Impacts": Impacts,
    "InSector": InSector,
    "Mentions": Mentions,
}

THINKING_EDGE_TYPES: dict[str, type[BaseModel]] = {
    "Impacts": Impacts,
    "CausedBy": CausedBy,
    "Matches": Matches,
    "InSector": InSector,
}
