from src.pipelines.value.score import BounceBackScore


class TestBounceBackScore:
    def setup_method(self):
        self.scorer = BounceBackScore()

    def test_high_opportunity_big_drop_good_fundamentals(self):
        entity = {
            "ticker": "AAPL",
            "price_change_pct": -15.0,
            "cash_flow": 5e9,
            "market_cap": 2e11,
        }
        result = self.scorer.score(entity)
        assert result.score > 50, f"Expected >50, got {result.score}"

    def test_low_opportunity_stable_expensive(self):
        entity = {
            "ticker": "TINY",
            "price_change_pct": 2.0,
            "cash_flow": -1e8,
            "market_cap": 5e8,
        }
        result = self.scorer.score(entity)
        assert result.score < 30, f"Expected <30, got {result.score}"

    def test_emotional_discount_caps_at_one(self):
        entity = {
            "ticker": "CRASH",
            "price_change_pct": -50.0,
            "cash_flow": 1e9,
            "market_cap": 1e10,
        }
        assert self.scorer.score(entity).factors["emotional_discount"] == 1.0

    def test_positive_price_gives_zero_discount(self):
        entity = {
            "ticker": "UP",
            "price_change_pct": 10.0,
            "cash_flow": 1e9,
            "market_cap": 1e10,
        }
        assert self.scorer.score(entity).factors["emotional_discount"] == 0.0

    def test_negative_cash_flow_gives_zero_health(self):
        entity = {
            "ticker": "BURN",
            "price_change_pct": -10.0,
            "cash_flow": -5e9,
            "market_cap": 1e10,
        }
        assert self.scorer.score(entity).factors["cash_flow_health"] == 0.0

    def test_score_has_all_six_factors(self):
        entity = {
            "ticker": "T",
            "price_change_pct": -5.0,
            "cash_flow": 1e9,
            "market_cap": 5e10,
        }
        expected = {
            "structural_necessity",
            "sector_position",
            "emotional_discount",
            "cash_flow_health",
            "trend_alignment",
            "macro_tailwind",
        }
        assert set(self.scorer.score(entity).factors.keys()) == expected
