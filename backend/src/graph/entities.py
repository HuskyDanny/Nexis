"""Custom entity types for Graphiti extraction.

These are Pydantic BaseModels passed to add_episode(entity_types=...).
Graphiti uses the docstrings and Field descriptions to guide LLM extraction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Company(BaseModel):
    """A publicly traded company, ETF, or major corporation."""

    ticker: str | None = Field(
        default=None, description="Stock ticker symbol (e.g., NVDA, AAPL)"
    )
    sector: str | None = Field(
        default=None, description="Market sector (e.g., Technology, Energy)"
    )
    market: str | None = Field(default=None, description="Primary market: US or CN")


class MacroEvent(BaseModel):
    """A macroeconomic event, policy decision, or geopolitical development."""

    event_type: str | None = Field(
        default=None,
        description="Category: monetary_policy, trade, geopolitical, regulation, earnings",
    )
    scope: str | None = Field(
        default=None, description="Impact scope: global, regional, sector"
    )
    direction: str | None = Field(
        default=None, description="Market direction: bullish, bearish, neutral"
    )


class Sector(BaseModel):
    """An industry sector or sub-sector."""

    market: str | None = Field(default=None, description="Primary market: US or CN")


class Effect(BaseModel):
    """A causal market effect identified by analysis."""

    confidence: float | None = Field(default=None, description="Confidence score 0-100")
    layer: int | None = Field(default=None, description="Thinking pipeline layer (0-3)")
    sector: str | None = Field(default=None, description="Affected sector")


class Opportunity(BaseModel):
    """An investment opportunity matched to market effects."""

    ticker: str | None = Field(default=None, description="Stock ticker symbol")
    convergence_score: float | None = Field(
        default=None,
        description="How strongly effects converge on this opportunity (0-100)",
    )


class NewsArticle(BaseModel):
    """A news article or story cluster from external sources."""

    source: str | None = Field(default=None, description="Source: perigon, newsapi")
    url: str | None = Field(default=None, description="Article URL")
    scope: int | None = Field(default=None, description="Macro scope 0-5")


# Lookup for passing to add_episode
FINANCIAL_ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Company": Company,
    "MacroEvent": MacroEvent,
    "Sector": Sector,
    "Effect": Effect,
    "Opportunity": Opportunity,
    "NewsArticle": NewsArticle,
}

NEWS_ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Company": Company,
    "MacroEvent": MacroEvent,
    "Sector": Sector,
    "NewsArticle": NewsArticle,
}

THINKING_ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Company": Company,
    "MacroEvent": MacroEvent,
    "Sector": Sector,
    "Effect": Effect,
    "Opportunity": Opportunity,
}
