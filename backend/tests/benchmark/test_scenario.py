"""Tests for benchmark scenario definitions."""

import pytest
from backend.tests.benchmark.scenarios.iran_escalation import SCENARIO


class TestScenarioStructure:
    """Validate top-level required fields are present."""

    def test_has_id(self):
        assert "id" in SCENARIO
        assert SCENARIO["id"] == "iran-escalation"

    def test_has_name(self):
        assert "name" in SCENARIO
        assert SCENARIO["name"] == "Iran Escalation — Oil & Gold"

    def test_has_description(self):
        assert "description" in SCENARIO
        assert isinstance(SCENARIO["description"], str)
        assert len(SCENARIO["description"]) > 0

    def test_has_expected_depth(self):
        assert "expected_depth" in SCENARIO
        assert SCENARIO["expected_depth"] == 3

    def test_has_news_pool(self):
        assert "news_pool" in SCENARIO

    def test_has_value_pool(self):
        assert "value_pool" in SCENARIO

    def test_has_checkpoints(self):
        assert "checkpoints" in SCENARIO

    def test_has_expected_matches(self):
        assert "expected_matches" in SCENARIO

    def test_has_expected_skills(self):
        assert "expected_skills" in SCENARIO


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
            # At least 2 sentences means at least one period in the summary
            assert (
                item["summary"].count(".") >= 1
            ), f"News item {item.get('id')} summary appears too short"

    def test_news_tickers_is_list(self):
        for item in SCENARIO["news_pool"]:
            assert isinstance(item["tickers"], list)

    def test_news_sectors_is_list(self):
        for item in SCENARIO["news_pool"]:
            assert isinstance(item["sectors"], list)
            assert len(item["sectors"]) > 0


class TestValuePool:
    """Validate value_pool instruments."""

    def test_value_pool_min_size(self):
        assert len(SCENARIO["value_pool"]) >= 3

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
        assert tickers == {"USO", "XLE", "GLD", "QQQ"}

    def test_instrument_prices_are_positive(self):
        for inst in SCENARIO["value_pool"]:
            assert inst["price"] > 0, f"{inst['ticker']} price must be positive"

    def test_uso_price(self):
        uso = next(i for i in SCENARIO["value_pool"] if i["ticker"] == "USO")
        assert uso["price"] == 72.50

    def test_xle_price(self):
        xle = next(i for i in SCENARIO["value_pool"] if i["ticker"] == "XLE")
        assert xle["price"] == 88.30

    def test_gld_price(self):
        gld = next(i for i in SCENARIO["value_pool"] if i["ticker"] == "GLD")
        assert gld["price"] == 215.40

    def test_qqq_price(self):
        qqq = next(i for i in SCENARIO["value_pool"] if i["ticker"] == "QQQ")
        assert qqq["price"] == 485.20


class TestCheckpoints:
    """Validate checkpoints cover all layers with >= 1 required per layer."""

    def test_checkpoints_cover_all_layers(self):
        layers = {cp["layer"] for cp in SCENARIO["checkpoints"]}
        assert layers == {1, 2, 3}, f"Expected layers 1,2,3 but got {layers}"

    def test_each_layer_has_at_least_one_required(self):
        for layer in (1, 2, 3):
            layer_cps = [cp for cp in SCENARIO["checkpoints"] if cp["layer"] == layer]
            required = [cp for cp in layer_cps if cp.get("required", False)]
            assert len(required) >= 1, f"Layer {layer} has no required checkpoints"

    def test_layer1_required_checkpoints(self):
        layer1_required = [
            cp["text"]
            for cp in SCENARIO["checkpoints"]
            if cp["layer"] == 1 and cp.get("required", False)
        ]
        assert any(
            "military strike" in t.lower() or "attack on iran" in t.lower()
            for t in layer1_required
        ), "Layer 1 missing military strike checkpoint"
        assert any(
            "political" in t.lower() for t in layer1_required
        ), "Layer 1 missing political timing checkpoint"

    def test_layer2_required_checkpoints(self):
        layer2_required = [
            cp["text"]
            for cp in SCENARIO["checkpoints"]
            if cp["layer"] == 2 and cp.get("required", False)
        ]
        assert any(
            "oil" in t.lower() for t in layer2_required
        ), "Layer 2 missing oil price checkpoint"
        assert any(
            "iran" in t.lower() or "hormuz" in t.lower() or "exporter" in t.lower()
            for t in layer2_required
        ), "Layer 2 missing Iran/Hormuz checkpoint"

    def test_layer3_required_checkpoints(self):
        layer3_required = [
            cp["text"]
            for cp in SCENARIO["checkpoints"]
            if cp["layer"] == 3 and cp.get("required", False)
        ]
        assert any(
            "inflation" in t.lower() for t in layer3_required
        ), "Layer 3 missing inflation checkpoint"
        assert any(
            "interest rate" in t.lower() or "fed" in t.lower() for t in layer3_required
        ), "Layer 3 missing interest rates/Fed checkpoint"
        assert any(
            "gold" in t.lower() or "gld" in t.lower() for t in layer3_required
        ), "Layer 3 missing gold checkpoint"

    def test_checkpoint_items_have_required_fields(self):
        for cp in SCENARIO["checkpoints"]:
            assert "layer" in cp
            assert "text" in cp
            assert "required" in cp


class TestExpectedMatches:
    """Validate expected_matches have direction."""

    def test_uso_long_at_layer2(self):
        uso_match = next(
            (m for m in SCENARIO["expected_matches"] if m["ticker"] == "USO"), None
        )
        assert uso_match is not None, "USO not in expected_matches"
        assert uso_match["direction"] == "long"
        assert uso_match["layer"] == 2

    def test_gld_short_at_layer3(self):
        gld_match = next(
            (m for m in SCENARIO["expected_matches"] if m["ticker"] == "GLD"), None
        )
        assert gld_match is not None, "GLD not in expected_matches"
        assert gld_match["direction"] == "short"
        assert gld_match["layer"] == 3

    def test_matches_have_direction_field(self):
        for match in SCENARIO["expected_matches"]:
            assert (
                "direction" in match
            ), f"Match for {match.get('ticker')} missing direction"
            assert match["direction"] in (
                "long",
                "short",
            ), f"Direction must be 'long' or 'short', got {match['direction']}"


class TestExpectedSkills:
    """Validate expected_skills per layer."""

    def test_skills_have_all_layers(self):
        assert set(SCENARIO["expected_skills"].keys()) == {"L1", "L2", "L3"}

    def test_l1_has_geopolitical_risk(self):
        assert "geopolitical_risk" in SCENARIO["expected_skills"]["L1"]

    def test_l2_has_supply_chain_and_geopolitical_risk(self):
        l2 = SCENARIO["expected_skills"]["L2"]
        assert "supply_chain" in l2
        assert "geopolitical_risk" in l2

    def test_l3_has_macro_economics(self):
        assert "macro_economics" in SCENARIO["expected_skills"]["L3"]
