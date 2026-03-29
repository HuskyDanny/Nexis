"""Query-time exponential decay scoring. No storage mutations."""

from __future__ import annotations

import math
from datetime import datetime

from src.rag.config import RAGConfig

_LN2 = math.log(2)
_DEFAULT_HALF_LIFE = 7.0


def decay_score(
    relevance_score: float,
    node_date: datetime,
    query_date: datetime,
    node_type: str,
    config: RAGConfig,
) -> float:
    """Apply exponential time decay to a relevance score.

    Score halves every `half_life` days for the given node type.
    """
    half_life = config.half_life_map.get(node_type, _DEFAULT_HALF_LIFE)
    age_days = (query_date - node_date).total_seconds() / 86400.0
    if age_days <= 0:
        return relevance_score
    decay = math.exp(-_LN2 * age_days / half_life)
    return relevance_score * decay
