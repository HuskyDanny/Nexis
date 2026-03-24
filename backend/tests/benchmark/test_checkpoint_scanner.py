"""Tests for Pass 1 checkpoint scanner — keyword fast-path + LLM fallback."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.benchmark.scoring.checkpoint_scanner import (
    extract_key_terms,
    check_direction,
    check_checkpoint_keyword,
    scan_matches,
    scan_skills,
    run_pass1,
)
from tests.benchmark.models import (
    AgentTrace,
    ControllerOutput,
    LayerTrace,
    BenchmarkTrace,
    Pass1Report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trace(layers_data: list[dict]) -> BenchmarkTrace:
    """Build a minimal BenchmarkTrace from a list of layer dicts."""
    layer_traces = []
    for i, ld in enumerate(layers_data, start=1):
        ctrl = ControllerOutput(continue_=False, reasoning="done", summary="done")
        agents = [
            AgentTrace(
                agent=f"agent_{i}",
                input_summary="input",
                output_raw="output",
                skills_loaded=ld.get("skills", []),
            )
        ]
        layer_traces.append(
            LayerTrace(
                layer=i,
                agents=agents,
                nodes_produced=ld.get("nodes", []),
                edges_produced=[],
                chain_summary="",
                controller_output=ctrl,
            )
        )
    return BenchmarkTrace(
        scenario_id="test-scenario",
        run_id="test-run",
        timestamp="2026-03-23T00:00:00Z",
        model="test-model",
        total_layers=len(layers_data),
        layers=layer_traces,
        news_pool=[],
        value_pool=[],
        total_tokens=100,
        total_latency_ms=500.0,
    )


# ---------------------------------------------------------------------------
# TestExtractKeyTerms
# ---------------------------------------------------------------------------


class TestExtractKeyTerms:
    def test_extracts_meaningful_terms(self):
        terms = extract_key_terms("oil price increase")
        assert "oil" in terms
        assert "price" in terms
        assert "increase" in terms

    def test_removes_stopwords(self):
        terms = extract_key_terms("the oil price is rising due to supply")
        assert "the" not in terms
        assert "is" not in terms
        assert "due" not in terms
        assert "to" not in terms
        assert "oil" in terms
        assert "price" in terms
        assert "supply" in terms

    def test_removes_single_char_words(self):
        terms = extract_key_terms("a b c oil")
        assert "a" not in terms
        assert "b" not in terms
        assert "c" not in terms
        assert "oil" in terms

    def test_handles_slash_alternatives(self):
        # "military strike / attack" → both terms present
        terms = extract_key_terms("military strike / attack on Iran")
        assert "military" in terms
        assert "strike" in terms
        assert "attack" in terms

    def test_handles_em_dash(self):
        terms = extract_key_terms("political timing — domestic pressure")
        assert "political" in terms
        assert "timing" in terms
        assert "domestic" in terms
        assert "pressure" in terms

    def test_lowercase_output(self):
        terms = extract_key_terms("Oil Price INCREASE")
        assert all(t == t.lower() for t in terms)

    def test_empty_string_returns_empty(self):
        assert extract_key_terms("") == []

    def test_only_stopwords_returns_empty(self):
        assert extract_key_terms("the is a an") == []


# ---------------------------------------------------------------------------
# TestCheckDirection
# ---------------------------------------------------------------------------


class TestCheckDirection:
    def test_matching_direction_returns_true(self):
        # concept says "increase", node_text says "increase"
        result = check_direction("oil price increase", "oil prices increase sharply")
        assert result is True

    def test_opposite_direction_returns_false(self):
        # concept says "increase", node_text says "decrease"
        result = check_direction(
            "oil price increase", "oil prices decrease significantly"
        )
        assert result is False

    def test_no_direction_words_returns_none(self):
        # Neither concept nor node has direction terms
        result = check_direction("oil supply disruption", "hormuz chokepoint blocked")
        assert result is None

    def test_rise_fall_antonym(self):
        result = check_direction("rates rise", "interest rates fall due to cuts")
        assert result is False

    def test_bull_bear_antonym(self):
        result = check_direction("bull market forming", "bear market collapse imminent")
        assert result is False

    def test_same_direction_in_both(self):
        # Use "fall" (exact token in _DIRECTION_WORDS), node has no antonym of "fall"
        result = check_direction("gold fall expected", "gold decline sharply ahead")
        # "fall" is in concept; "rise" (antonym) is NOT in node → returns True
        assert result is True

    def test_long_short_antonym(self):
        result = check_direction("long USO position", "short USO position recommended")
        assert result is False

    def test_multi_directional_returns_none(self):
        # Both "increase" and "decrease" present → ambiguous, defer to LLM
        assert (
            check_direction(
                "inflation increase from oil costs",
                "inflation increase pushes costs up while rates decrease",
            )
            is None
        )

    def test_negated_direction_returns_none(self):
        # "not" stripped as stopword → both "increase" and "decrease" present
        assert (
            check_direction(
                "oil price increase",
                "oil prices decrease, not increase in this scenario",
            )
            is None
        )


# ---------------------------------------------------------------------------
# TestCheckCheckpointKeyword
# ---------------------------------------------------------------------------


class TestCheckCheckpointKeyword:
    def _node(self, node_id: str, content: str, reasoning: str = "") -> dict:
        return {"id": node_id, "content": content, "reasoning": reasoning}

    def test_hit_on_term_overlap(self):
        checkpoint = {
            "layer": 1,
            "text": "military strike attack Iran",
            "required": True,
        }
        nodes = [
            self._node(
                "n1",
                "A military strike on Iranian nuclear facilities is now considered likely.",
                "Iran attack probability high given naval deployment.",
            )
        ]
        result = check_checkpoint_keyword(checkpoint, 1, nodes)
        assert result.hit is True
        assert result.method == "keyword"
        assert result.matched_node_id == "n1"

    def test_miss_on_no_overlap(self):
        checkpoint = {
            "layer": 2,
            "text": "inflation rise consumer prices",
            "required": True,
        }
        nodes = [
            self._node(
                "n1", "Gold prices fall due to strong dollar.", "USD strengthens."
            ),
        ]
        result = check_checkpoint_keyword(checkpoint, 2, nodes)
        assert result.hit is False
        assert result.method == "keyword"
        assert result.matched_node_id is None

    def test_falls_through_on_wrong_direction(self):
        # concept says "increase", node has "decrease" (opposite) — should NOT match
        checkpoint = {
            "layer": 2,
            "text": "oil price increase supply disruption",
            "required": True,
        }
        nodes = [
            self._node(
                "n1",
                "oil price decrease as supply recovers disruption eases",
                "supply disruption resolved oil decrease",
            )
        ]
        # The node has high term overlap BUT wrong direction → should be miss
        result = check_checkpoint_keyword(checkpoint, 2, nodes)
        assert result.hit is False

    def test_direction_correct_set_on_hit(self):
        checkpoint = {"layer": 2, "text": "oil price increase", "required": True}
        # Use exact tokens matching concept terms ("oil", "price", "increase")
        nodes = [
            self._node(
                "n1", "oil price increase due to supply shock", "price rise further"
            )
        ]
        result = check_checkpoint_keyword(checkpoint, 2, nodes)
        assert result.hit is True
        assert result.direction_correct is True

    def test_multiple_nodes_first_hit_wins(self):
        checkpoint = {
            "layer": 1,
            "text": "military strike Iran attack",
            "required": True,
        }
        nodes = [
            self._node("n_miss", "Gold rally on safe haven demand.", "USD weakens."),
            self._node(
                "n_hit", "Military strike on Iran attack facilities confirmed.", ""
            ),
        ]
        result = check_checkpoint_keyword(checkpoint, 1, nodes)
        assert result.hit is True
        assert result.matched_node_id == "n_hit"

    def test_custom_threshold(self):
        # Very low threshold: a single shared term should be enough
        checkpoint = {"layer": 1, "text": "military action", "required": True}
        nodes = [self._node("n1", "military operations ongoing in the region", "")]
        result = check_checkpoint_keyword(checkpoint, 1, nodes, threshold=0.3)
        assert result.hit is True


# ---------------------------------------------------------------------------
# TestScanMatches
# ---------------------------------------------------------------------------


class TestScanMatches:
    def _opp_node(
        self,
        ticker: str,
        layer: int,
        sentiment_score: int,
        node_id: str | None = None,
    ) -> dict:
        return {
            "id": node_id or f"{ticker}_L{layer}",
            "type": "opportunity",
            "content": f"{ticker} opportunity",
            "metadata": {
                "ticker": ticker,
                "layer": layer,
                "sentiment_score": sentiment_score,
            },
        }

    def test_finds_correct_match_uso_long(self):
        expected_matches = [{"ticker": "USO", "direction": "long", "layer": 2}]
        opportunity_nodes = [self._opp_node("USO", 2, 75)]  # >= 50 → long
        results = scan_matches(expected_matches, opportunity_nodes)
        assert len(results) == 1
        r = results[0]
        assert r.ticker == "USO"
        assert r.found is True
        assert r.actual_direction == "long"
        assert r.correct is True

    def test_detects_wrong_direction(self):
        # GLD expected short, but sentiment_score=80 → inferred as long
        expected_matches = [{"ticker": "GLD", "direction": "short", "layer": 3}]
        opportunity_nodes = [self._opp_node("GLD", 3, 80)]
        results = scan_matches(expected_matches, opportunity_nodes)
        assert len(results) == 1
        r = results[0]
        assert r.ticker == "GLD"
        assert r.found is True
        assert r.actual_direction == "long"
        assert r.correct is False

    def test_missing_match(self):
        expected_matches = [{"ticker": "USO", "direction": "long", "layer": 2}]
        opportunity_nodes = []  # no nodes produced
        results = scan_matches(expected_matches, opportunity_nodes)
        assert len(results) == 1
        r = results[0]
        assert r.ticker == "USO"
        assert r.found is False
        assert r.actual_direction is None
        assert r.correct is False

    def test_correct_short_direction(self):
        # sentiment_score=30 → short, expected short → correct
        expected_matches = [{"ticker": "GLD", "direction": "short", "layer": 3}]
        opportunity_nodes = [self._opp_node("GLD", 3, 30)]
        results = scan_matches(expected_matches, opportunity_nodes)
        assert results[0].correct is True
        assert results[0].actual_direction == "short"

    def test_multiple_expected_matches(self):
        expected_matches = [
            {"ticker": "USO", "direction": "long", "layer": 2},
            {"ticker": "GLD", "direction": "short", "layer": 3},
        ]
        opportunity_nodes = [
            self._opp_node("USO", 2, 75),  # long → correct
            self._opp_node("GLD", 3, 25),  # short → correct
        ]
        results = scan_matches(expected_matches, opportunity_nodes)
        assert len(results) == 2
        assert all(r.correct for r in results)


# ---------------------------------------------------------------------------
# TestScanSkills
# ---------------------------------------------------------------------------


class TestScanSkills:
    def test_subset_check_passes_with_extra_skills(self):
        expected = {1: ["geopolitical_risk"]}
        actual = {1: ["geopolitical_risk", "supply_chain", "extra_skill"]}
        results = scan_skills(expected, actual)
        assert len(results) == 1
        assert results[0].all_loaded is True
        assert results[0].layer == 1

    def test_missing_skill_fails(self):
        expected = {2: ["supply_chain", "geopolitical_risk"]}
        actual = {2: ["supply_chain"]}  # missing geopolitical_risk
        results = scan_skills(expected, actual)
        assert len(results) == 1
        assert results[0].all_loaded is False

    def test_exact_match_passes(self):
        expected = {1: ["geopolitical_risk"], 2: ["supply_chain", "geopolitical_risk"]}
        actual = {1: ["geopolitical_risk"], 2: ["supply_chain", "geopolitical_risk"]}
        results = scan_skills(expected, actual)
        assert all(r.all_loaded for r in results)

    def test_empty_expected_for_layer_always_passes(self):
        expected = {1: []}
        actual = {1: ["some_skill"]}
        results = scan_skills(expected, actual)
        assert results[0].all_loaded is True

    def test_layer_not_in_actual_fails(self):
        expected = {3: ["macro_economics"]}
        actual = {}  # layer 3 not present
        results = scan_skills(expected, actual)
        assert results[0].all_loaded is False

    def test_multiple_layers_mixed(self):
        expected = {1: ["geo"], 2: ["supply"], 3: ["macro"]}
        actual = {1: ["geo", "extra"], 2: [], 3: ["macro"]}
        results = scan_skills(expected, actual)
        by_layer = {r.layer: r for r in results}
        assert by_layer[1].all_loaded is True
        assert by_layer[2].all_loaded is False
        assert by_layer[3].all_loaded is True


# ---------------------------------------------------------------------------
# TestRunPass1
# ---------------------------------------------------------------------------


class TestRunPass1:
    """Integration-level smoke tests for run_pass1 orchestrator."""

    def _scenario(self) -> dict:
        return {
            "checkpoints": [
                {"layer": 1, "text": "military strike Iran attack", "required": True},
                {
                    "layer": 2,
                    "text": "oil price increase supply disruption",
                    "required": True,
                },
            ],
            "expected_matches": [
                {"ticker": "USO", "direction": "long", "layer": 2},
            ],
            "expected_skills": {
                "L1": ["geopolitical_risk"],
                "L2": ["supply_chain"],
            },
        }

    def _trace_hit(self) -> BenchmarkTrace:
        return _make_trace(
            [
                {
                    "nodes": [
                        {
                            "id": "n1_1",
                            "content": "Military strike on Iran confirmed attack imminent",
                            "reasoning": "naval deployment signals Iran strike",
                        }
                    ],
                    "skills": ["geopolitical_risk"],
                },
                {
                    "nodes": [
                        {
                            "id": "n2_1",
                            "content": "Oil price increase due to supply disruption Hormuz",
                            "reasoning": "supply disruption causes oil price to rise",
                        },
                        {
                            "id": "n2_opp",
                            "type": "opportunity",
                            "content": "USO long opportunity",
                            "metadata": {
                                "ticker": "USO",
                                "layer": 2,
                                "sentiment_score": 75,
                            },
                            "reasoning": "",
                        },
                    ],
                    "skills": ["supply_chain"],
                },
            ]
        )

    @pytest.mark.asyncio
    async def test_run_pass1_returns_pass1_report(self):
        report = await run_pass1(self._scenario(), self._trace_hit())
        assert isinstance(report, Pass1Report)

    @pytest.mark.asyncio
    async def test_run_pass1_checkpoint_hit_rate(self):
        report = await run_pass1(self._scenario(), self._trace_hit())
        # Both required checkpoints should hit
        assert report.checkpoint_hit_rate > 0.0
        assert 0.0 <= report.checkpoint_hit_rate <= 1.0

    @pytest.mark.asyncio
    async def test_run_pass1_match_accuracy(self):
        report = await run_pass1(self._scenario(), self._trace_hit())
        assert 0.0 <= report.match_accuracy <= 1.0

    @pytest.mark.asyncio
    async def test_run_pass1_skill_compliance(self):
        report = await run_pass1(self._scenario(), self._trace_hit())
        assert 0.0 <= report.skill_compliance <= 1.0

    @pytest.mark.asyncio
    async def test_run_pass1_metrics_populated(self):
        report = await run_pass1(self._scenario(), self._trace_hit())
        assert report.total_tokens >= 0
        assert report.total_latency_ms >= 0.0
        assert report.tokens_per_layer >= 0.0
        assert report.latency_per_layer >= 0.0
