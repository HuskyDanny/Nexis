"""Value scoring — bounce-back probability model."""

from src.models.pool_common import ScoreResult

WEIGHTS = {
    "structural_necessity": 0.20,
    "sector_position": 0.15,
    "emotional_discount": 0.20,
    "cash_flow_health": 0.20,
    "trend_alignment": 0.15,
    "macro_tailwind": 0.10,
}


class BounceBackScore:
    """Multi-factor bounce-back probability scorer.

    Quantitative factors are derived from entity data; LLM-scored factors
    use 0.5 as a placeholder until real inference is wired in.
    The final score is on a 0–100 scale.
    """

    def score(self, entity: dict) -> ScoreResult:
        price_change = entity.get("price_change_pct", 0.0)
        cash_flow = entity.get("cash_flow", 0.0)
        market_cap = entity.get("market_cap", 0.0)

        factors = {
            "structural_necessity": 0.5,  # LLM placeholder
            "sector_position": round(min(market_cap / 1e11, 1.0), 4),
            "emotional_discount": round(
                min(abs(min(price_change, 0.0)) / 20.0, 1.0), 4
            ),
            "cash_flow_health": round(min(max(0.0, cash_flow) / 1e10, 1.0), 4),
            "trend_alignment": 0.5,  # LLM placeholder
            "macro_tailwind": 0.5,  # LLM placeholder
        }
        total = round(sum(factors[k] * WEIGHTS[k] for k in WEIGHTS) * 100, 1)
        return ScoreResult(score=total, factors=factors)
