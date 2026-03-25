"""Fed Rate Decision scenario-specific assertions.

Generic structural tests run via parameterized ``scenario`` fixture in
``test_scenario.py``.  This file only contains assertions unique to the
fed-rate-decision scenario (specific tickers, checkpoint text, match
directions, and skills).
"""

from tests.benchmark.scenarios.fed_rate_decision import SCENARIO as FED


class TestFedScenarioIdentity:
    """Fed scenario identity and specific values."""

    def test_id(self):
        assert FED["id"] == "fed-rate-decision"

    def test_name(self):
        assert FED["name"] == "Fed Rate Decision — Rates & Housing"

    def test_expected_depth(self):
        assert FED["expected_depth"] == 3


class TestFedValuePool:
    """Fed scenario specific tickers."""

    def test_instrument_tickers(self):
        tickers = {inst["ticker"] for inst in FED["value_pool"]}
        assert tickers == {"TLT", "VNQ", "KRE", "XLU"}


class TestFedCheckpoints:
    """Fed scenario checkpoint text assertions."""

    def test_layer1_has_fed_hold_checkpoint(self):
        layer1_required = [
            cp["text"]
            for cp in FED["checkpoints"]
            if cp["layer"] == 1 and cp.get("required", False)
        ]
        assert any(
            "fed" in t.lower() or "rate" in t.lower() for t in layer1_required
        ), "Layer 1 missing Fed rate hold checkpoint"

    def test_layer2_has_yield_curve_checkpoint(self):
        layer2_required = [
            cp["text"]
            for cp in FED["checkpoints"]
            if cp["layer"] == 2 and cp.get("required", False)
        ]
        assert any(
            "yield" in t.lower() or "mortgage" in t.lower() for t in layer2_required
        ), "Layer 2 missing yield curve / mortgage checkpoint"

    def test_layer3_has_reit_or_bank_checkpoint(self):
        layer3_required = [
            cp["text"]
            for cp in FED["checkpoints"]
            if cp["layer"] == 3 and cp.get("required", False)
        ]
        assert any(
            "reit" in t.lower() or "bank" in t.lower() for t in layer3_required
        ), "Layer 3 missing REIT or bank checkpoint"


class TestFedExpectedMatches:
    """Fed scenario specific match assertions."""

    def test_tlt_short_at_layer2(self):
        tlt = next(
            (m for m in FED["expected_matches"] if m["ticker"] == "TLT"), None
        )
        assert tlt is not None, "TLT not in expected_matches"
        assert tlt["direction"] == "short"
        assert tlt["layer"] == 2

    def test_vnq_long_at_layer3(self):
        vnq = next(
            (m for m in FED["expected_matches"] if m["ticker"] == "VNQ"), None
        )
        assert vnq is not None, "VNQ not in expected_matches"
        assert vnq["direction"] == "long"
        assert vnq["layer"] == 3

    def test_kre_long_at_layer3(self):
        kre = next(
            (m for m in FED["expected_matches"] if m["ticker"] == "KRE"), None
        )
        assert kre is not None, "KRE not in expected_matches"
        assert kre["direction"] == "long"
        assert kre["layer"] == 3


class TestFedExpectedSkills:
    """Fed scenario specific skill assertions."""

    def test_l1_has_macro_economics(self):
        assert "macro_economics" in FED["expected_skills"]["L1"]

    def test_l2_has_macro_and_sector_rotation(self):
        l2 = FED["expected_skills"]["L2"]
        assert "macro_economics" in l2
        assert "sector_rotation" in l2

    def test_l3_has_sector_rotation(self):
        assert "sector_rotation" in FED["expected_skills"]["L3"]
