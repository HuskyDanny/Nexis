"""Scenario-specific assertions for Iran Escalation."""

from tests.benchmark.scenarios.iran_escalation import SCENARIO


class TestIranScenarioIdentity:
    def test_id(self):
        assert SCENARIO["id"] == "iran-escalation"

    def test_name(self):
        assert SCENARIO["name"] == "Iran Escalation — Oil & Gold"

    def test_expected_depth(self):
        assert SCENARIO["expected_depth"] == 3


class TestIranValuePool:
    def test_has_four_instruments(self):
        assert len(SCENARIO["value_pool"]) == 4

    def test_instrument_tickers(self):
        tickers = {inst["ticker"] for inst in SCENARIO["value_pool"]}
        assert tickers == {"USO", "XLE", "GLD", "QQQ"}

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


class TestIranCheckpoints:
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


class TestIranExpectedMatches:
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


class TestIranExpectedSkills:
    def test_l1_has_geopolitical_risk(self):
        assert "geopolitical_risk" in SCENARIO["expected_skills"]["L1"]

    def test_l2_has_supply_chain_and_geopolitical_risk(self):
        l2 = SCENARIO["expected_skills"]["L2"]
        assert "supply_chain" in l2
        assert "geopolitical_risk" in l2

    def test_l3_has_macro_economics(self):
        assert "macro_economics" in SCENARIO["expected_skills"]["L3"]
