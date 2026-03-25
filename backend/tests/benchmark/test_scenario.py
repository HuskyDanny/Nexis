"""Parameterized tests for ALL benchmark scenario definitions.

Generic structural tests use the ``scenario`` fixture (parameterized over all
scenario modules via conftest.pytest_generate_tests).  Iran-escalation-specific
assertions live in their own classes at the bottom.
"""

import pytest
from tests.benchmark.scenarios.iran_escalation import SCENARIO as IRAN


# ---------------------------------------------------------------------------
# Generic structural tests — run against every registered scenario
# ---------------------------------------------------------------------------


class TestScenarioStructure:
    """Validate top-level required fields are present."""

    REQUIRED_KEYS = (
        "id",
        "name",
        "description",
        "expected_depth",
        "news_pool",
        "value_pool",
        "checkpoints",
        "expected_matches",
        "expected_skills",
    )

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_has_required_key(self, scenario, key):
        assert key in scenario, f"Scenario '{scenario.get('id')}' missing key: {key}"

    def test_description_is_nonempty_string(self, scenario):
        assert isinstance(scenario["description"], str)
        assert len(scenario["description"]) > 0

    def test_expected_depth_is_positive(self, scenario):
        assert scenario["expected_depth"] >= 1


class TestNewsPool:
    """Validate news_pool items."""

    def test_news_pool_min_size(self, scenario):
        assert len(scenario["news_pool"]) >= 3

    def test_news_items_have_required_fields(self, scenario):
        required = {"id", "title", "summary", "url", "source", "tickers", "sectors"}
        for item in scenario["news_pool"]:
            assert required.issubset(
                item.keys()
            ), f"News item {item.get('id')} missing fields: {required - item.keys()}"

    def test_news_summaries_are_multi_sentence(self, scenario):
        for item in scenario["news_pool"]:
            assert (
                item["summary"].count(".") >= 1
            ), f"News item {item.get('id')} summary appears too short"

    def test_news_tickers_is_list(self, scenario):
        for item in scenario["news_pool"]:
            assert isinstance(item["tickers"], list)

    def test_news_sectors_are_nonempty_lists(self, scenario):
        for item in scenario["news_pool"]:
            assert isinstance(item["sectors"], list)
            assert len(item["sectors"]) > 0


class TestValuePool:
    """Validate value_pool instruments."""

    def test_value_pool_min_size(self, scenario):
        assert len(scenario["value_pool"]) >= 3

    def test_instruments_have_required_fields(self, scenario):
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
        for inst in scenario["value_pool"]:
            assert required.issubset(
                inst.keys()
            ), f"Instrument {inst.get('ticker')} missing fields: {required - inst.keys()}"

    def test_instrument_prices_are_positive(self, scenario):
        for inst in scenario["value_pool"]:
            assert inst["price"] > 0, f"{inst['ticker']} price must be positive"


class TestCheckpoints:
    """Validate checkpoints cover all layers with >= 1 required per layer."""

    def test_checkpoints_cover_all_layers(self, scenario):
        layers = {cp["layer"] for cp in scenario["checkpoints"]}
        expected = set(range(1, scenario["expected_depth"] + 1))
        assert layers == expected, f"Expected layers {expected} but got {layers}"

    def test_each_layer_has_at_least_one_required(self, scenario):
        for layer in range(1, scenario["expected_depth"] + 1):
            layer_cps = [cp for cp in scenario["checkpoints"] if cp["layer"] == layer]
            required = [cp for cp in layer_cps if cp.get("required", False)]
            assert len(required) >= 1, f"Layer {layer} has no required checkpoints"

    def test_checkpoint_items_have_required_fields(self, scenario):
        for cp in scenario["checkpoints"]:
            assert "layer" in cp
            assert "text" in cp
            assert "required" in cp


class TestExpectedMatches:
    """Validate expected_matches have valid direction."""

    def test_matches_have_valid_direction(self, scenario):
        for match in scenario["expected_matches"]:
            assert (
                "direction" in match
            ), f"Match for {match.get('ticker')} missing direction"
            assert match["direction"] in (
                "long",
                "short",
            ), f"Direction must be 'long' or 'short', got {match['direction']}"


class TestExpectedSkills:
    """Validate expected_skills cover all layers."""

    def test_skills_have_all_layers(self, scenario):
        expected = {f"L{i}" for i in range(1, scenario["expected_depth"] + 1)}
        assert set(scenario["expected_skills"].keys()) == expected


# ---------------------------------------------------------------------------
# Iran-escalation-specific assertions
# ---------------------------------------------------------------------------


class TestIranScenarioIdentity:
    """Iran scenario identity and specific values."""

    def test_id(self):
        assert IRAN["id"] == "iran-escalation"

    def test_name(self):
        assert IRAN["name"] == "Iran Escalation — Oil & Gold"

    def test_expected_depth(self):
        assert IRAN["expected_depth"] == 3


class TestIranValuePool:
    """Iran scenario specific tickers and prices."""

    def test_instrument_tickers(self):
        tickers = {inst["ticker"] for inst in IRAN["value_pool"]}
        assert tickers == {"USO", "XLE", "GLD", "QQQ"}

    def test_uso_price(self):
        uso = next(i for i in IRAN["value_pool"] if i["ticker"] == "USO")
        assert uso["price"] == 72.50

    def test_xle_price(self):
        xle = next(i for i in IRAN["value_pool"] if i["ticker"] == "XLE")
        assert xle["price"] == 88.30

    def test_gld_price(self):
        gld = next(i for i in IRAN["value_pool"] if i["ticker"] == "GLD")
        assert gld["price"] == 215.40

    def test_qqq_price(self):
        qqq = next(i for i in IRAN["value_pool"] if i["ticker"] == "QQQ")
        assert qqq["price"] == 485.20


class TestIranCheckpoints:
    """Iran scenario checkpoint text assertions."""

    def test_layer1_military_strike(self):
        layer1_required = [
            cp["text"]
            for cp in IRAN["checkpoints"]
            if cp["layer"] == 1 and cp.get("required", False)
        ]
        assert any(
            "military strike" in t.lower() or "attack on iran" in t.lower()
            for t in layer1_required
        ), "Layer 1 missing military strike checkpoint"

    def test_layer1_political_timing(self):
        layer1_required = [
            cp["text"]
            for cp in IRAN["checkpoints"]
            if cp["layer"] == 1 and cp.get("required", False)
        ]
        assert any(
            "political" in t.lower() for t in layer1_required
        ), "Layer 1 missing political timing checkpoint"

    def test_layer2_oil_price(self):
        layer2_required = [
            cp["text"]
            for cp in IRAN["checkpoints"]
            if cp["layer"] == 2 and cp.get("required", False)
        ]
        assert any(
            "oil" in t.lower() for t in layer2_required
        ), "Layer 2 missing oil price checkpoint"

    def test_layer2_iran_hormuz(self):
        layer2_required = [
            cp["text"]
            for cp in IRAN["checkpoints"]
            if cp["layer"] == 2 and cp.get("required", False)
        ]
        assert any(
            "iran" in t.lower() or "hormuz" in t.lower() or "exporter" in t.lower()
            for t in layer2_required
        ), "Layer 2 missing Iran/Hormuz checkpoint"

    def test_layer3_inflation(self):
        layer3_required = [
            cp["text"]
            for cp in IRAN["checkpoints"]
            if cp["layer"] == 3 and cp.get("required", False)
        ]
        assert any(
            "inflation" in t.lower() for t in layer3_required
        ), "Layer 3 missing inflation checkpoint"

    def test_layer3_fed_rates(self):
        layer3_required = [
            cp["text"]
            for cp in IRAN["checkpoints"]
            if cp["layer"] == 3 and cp.get("required", False)
        ]
        assert any(
            "interest rate" in t.lower() or "fed" in t.lower() for t in layer3_required
        ), "Layer 3 missing interest rates/Fed checkpoint"

    def test_layer3_gold(self):
        layer3_required = [
            cp["text"]
            for cp in IRAN["checkpoints"]
            if cp["layer"] == 3 and cp.get("required", False)
        ]
        assert any(
            "gold" in t.lower() or "gld" in t.lower() for t in layer3_required
        ), "Layer 3 missing gold checkpoint"


class TestIranExpectedMatches:
    """Iran scenario specific match assertions."""

    def test_uso_long_at_layer2(self):
        uso_match = next(
            (m for m in IRAN["expected_matches"] if m["ticker"] == "USO"), None
        )
        assert uso_match is not None, "USO not in expected_matches"
        assert uso_match["direction"] == "long"
        assert uso_match["layer"] == 2

    def test_gld_short_at_layer3(self):
        gld_match = next(
            (m for m in IRAN["expected_matches"] if m["ticker"] == "GLD"), None
        )
        assert gld_match is not None, "GLD not in expected_matches"
        assert gld_match["direction"] == "short"
        assert gld_match["layer"] == 3


class TestIranExpectedSkills:
    """Iran scenario specific skill assertions."""

    def test_l1_has_geopolitical_risk(self):
        assert "geopolitical_risk" in IRAN["expected_skills"]["L1"]

    def test_l2_has_supply_chain_and_geopolitical_risk(self):
        l2 = IRAN["expected_skills"]["L2"]
        assert "supply_chain" in l2
        assert "geopolitical_risk" in l2

    def test_l3_has_macro_economics(self):
        assert "macro_economics" in IRAN["expected_skills"]["L3"]
