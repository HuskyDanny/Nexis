"""Tests for Fed Rate Decision benchmark scenario definition."""

from tests.benchmark.scenarios.fed_rate_decision import SCENARIO


class TestScenarioStructure:
    """Validate top-level required fields are present."""

    def test_has_id(self):
        assert SCENARIO["id"] == "fed-rate-decision"

    def test_has_name(self):
        assert SCENARIO["name"] == "Fed Rate Decision — Rates & Housing"

    def test_has_description(self):
        assert isinstance(SCENARIO["description"], str)
        assert len(SCENARIO["description"]) > 0

    def test_has_expected_depth(self):
        assert SCENARIO["expected_depth"] == 3

    def test_has_required_sections(self):
        for key in (
            "news_pool",
            "value_pool",
            "checkpoints",
            "expected_matches",
            "expected_skills",
        ):
            assert key in SCENARIO, f"Missing required section: {key}"


class TestNewsPool:
    """Validate news_pool items."""

    def test_news_pool_min_size(self):
        assert len(SCENARIO["news_pool"]) >= 3

    def test_news_items_have_required_fields(self):
        required = {"id", "title", "summary", "url", "source", "tickers", "sectors"}
        for item in SCENARIO["news_pool"]:
            assert required.issubset(
                item.keys()
            ), f"News item {item.get('id')} missing fields: {required - item.keys()}"

    def test_news_summaries_are_multi_sentence(self):
        for item in SCENARIO["news_pool"]:
            assert (
                item["summary"].count(".") >= 1
            ), f"News item {item.get('id')} summary appears too short"

    def test_news_sectors_are_nonempty_lists(self):
        for item in SCENARIO["news_pool"]:
            assert isinstance(item["sectors"], list)
            assert len(item["sectors"]) > 0


class TestValuePool:
    """Validate value_pool instruments."""

    def test_value_pool_has_four_instruments(self):
        assert len(SCENARIO["value_pool"]) == 4

    def test_instruments_have_required_fields(self):
        required = {
            "ticker",
            "name",
            "sector",
            "price",
            "pe_ratio",
            "market_cap",
            "price_change_pct",
            "score",
            "discount_pct",
        }
        for inst in SCENARIO["value_pool"]:
            assert required.issubset(
                inst.keys()
            ), f"Instrument {inst.get('ticker')} missing fields: {required - inst.keys()}"

    def test_instrument_tickers(self):
        tickers = {inst["ticker"] for inst in SCENARIO["value_pool"]}
        assert tickers == {"TLT", "VNQ", "KRE", "XLU"}

    def test_instrument_prices_are_positive(self):
        for inst in SCENARIO["value_pool"]:
            assert inst["price"] > 0, f"{inst['ticker']} price must be positive"


class TestCheckpoints:
    """Validate checkpoints cover all layers with >= 1 required per layer."""

    def test_checkpoints_cover_all_layers(self):
        layers = {cp["layer"] for cp in SCENARIO["checkpoints"]}
        assert layers == {1, 2, 3}

    def test_each_layer_has_at_least_one_required(self):
        for layer in (1, 2, 3):
            layer_cps = [cp for cp in SCENARIO["checkpoints"] if cp["layer"] == layer]
            required = [cp for cp in layer_cps if cp.get("required", False)]
            assert len(required) >= 1, f"Layer {layer} has no required checkpoints"

    def test_layer1_has_fed_hold_checkpoint(self):
        layer1_required = [
            cp["text"]
            for cp in SCENARIO["checkpoints"]
            if cp["layer"] == 1 and cp.get("required", False)
        ]
        assert any(
            "fed" in t.lower() or "rate" in t.lower() for t in layer1_required
        ), "Layer 1 missing Fed rate hold checkpoint"

    def test_layer2_has_yield_curve_checkpoint(self):
        layer2_required = [
            cp["text"]
            for cp in SCENARIO["checkpoints"]
            if cp["layer"] == 2 and cp.get("required", False)
        ]
        assert any(
            "yield" in t.lower() or "mortgage" in t.lower() for t in layer2_required
        ), "Layer 2 missing yield curve / mortgage checkpoint"

    def test_layer3_has_reit_or_bank_checkpoint(self):
        layer3_required = [
            cp["text"]
            for cp in SCENARIO["checkpoints"]
            if cp["layer"] == 3 and cp.get("required", False)
        ]
        assert any(
            "reit" in t.lower() or "bank" in t.lower() for t in layer3_required
        ), "Layer 3 missing REIT or bank checkpoint"

    def test_checkpoint_items_have_required_fields(self):
        for cp in SCENARIO["checkpoints"]:
            assert "layer" in cp
            assert "text" in cp
            assert "required" in cp


class TestExpectedMatches:
    """Validate expected_matches have direction."""

    def test_tlt_short_at_layer2(self):
        tlt = next(
            (m for m in SCENARIO["expected_matches"] if m["ticker"] == "TLT"), None
        )
        assert tlt is not None, "TLT not in expected_matches"
        assert tlt["direction"] == "short"
        assert tlt["layer"] == 2

    def test_vnq_long_at_layer3(self):
        vnq = next(
            (m for m in SCENARIO["expected_matches"] if m["ticker"] == "VNQ"), None
        )
        assert vnq is not None, "VNQ not in expected_matches"
        assert vnq["direction"] == "long"
        assert vnq["layer"] == 3

    def test_kre_long_at_layer3(self):
        kre = next(
            (m for m in SCENARIO["expected_matches"] if m["ticker"] == "KRE"), None
        )
        assert kre is not None, "KRE not in expected_matches"
        assert kre["direction"] == "long"
        assert kre["layer"] == 3

    def test_matches_have_valid_direction(self):
        for match in SCENARIO["expected_matches"]:
            assert "direction" in match
            assert match["direction"] in ("long", "short")


class TestExpectedSkills:
    """Validate expected_skills per layer."""

    def test_skills_have_all_layers(self):
        assert set(SCENARIO["expected_skills"].keys()) == {"L1", "L2", "L3"}

    def test_l1_has_macro_economics(self):
        assert "macro_economics" in SCENARIO["expected_skills"]["L1"]

    def test_l2_has_macro_and_sector_rotation(self):
        l2 = SCENARIO["expected_skills"]["L2"]
        assert "macro_economics" in l2
        assert "sector_rotation" in l2

    def test_l3_has_sector_rotation(self):
        assert "sector_rotation" in SCENARIO["expected_skills"]["L3"]
