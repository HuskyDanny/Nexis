"""Tests for the agents module — LLM config and thinking crew functions."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Patch target prefix for thinking_crew module
_TC = "src.agents.thinking_crew"

# Shared decorator to mock all CrewAI classes + LLM factory so no real
# Pydantic validation or LLM calls happen.
_PATCH_CREWAI = lambda llm_fn: (  # noqa: E731
    patch(f"{_TC}.Crew"),
    patch(f"{_TC}.Task"),
    patch(f"{_TC}.Agent"),
    patch(f"{_TC}.{llm_fn}"),
)


def _mock_crew_result(raw_json: str):
    """Build a mock Crew whose kickoff() returns a result with the given raw JSON."""
    mock_result = MagicMock()
    mock_result.raw = raw_json
    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = mock_result
    return mock_crew


# ---------------------------------------------------------------------------
# LLM config tests
# ---------------------------------------------------------------------------


class TestLLMConfig:
    def test_is_llm_available_false_when_no_key(self, monkeypatch):
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        from src.agents.llm_config import is_llm_available

        assert is_llm_available() is False

    def test_is_llm_available_true_when_key_set(self, monkeypatch):
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key-123")
        from src.agents.llm_config import is_llm_available

        assert is_llm_available() is True

    def test_get_api_key_raises_without_env(self, monkeypatch):
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        from src.agents.llm_config import _get_api_key

        with pytest.raises(ValueError, match="SILICONFLOW_API_KEY"):
            _get_api_key()


# ---------------------------------------------------------------------------
# Convergence score tests
# ---------------------------------------------------------------------------


class TestConvergenceScore:
    def test_basic_calculation(self):
        from src.agents.thinking_crew import convergence_score

        # sentiment*0.3 + discount*0.3 + agreement*0.4
        # 70*0.3 + 60*0.3 + 80*0.4 = 21 + 18 + 32 = 71.0
        assert convergence_score(70.0, 60.0, 80.0) == 71.0

    def test_capped_at_100(self):
        from src.agents.thinking_crew import convergence_score

        # 200*0.3 + 200*0.3 + 200*0.4 = 60 + 60 + 80 = 200 -> capped at 100
        assert convergence_score(200.0, 200.0, 200.0) == 100.0

    def test_zero_inputs(self):
        from src.agents.thinking_crew import convergence_score

        assert convergence_score(0.0, 0.0, 0.0) == 0.0

    def test_rounding(self):
        from src.agents.thinking_crew import convergence_score

        # 33*0.3 + 33*0.3 + 33*0.4 = 9.9 + 9.9 + 13.2 = 33.0
        assert convergence_score(33.0, 33.0, 33.0) == 33.0

    def test_uneven_weights(self):
        from src.agents.thinking_crew import convergence_score

        # 100*0.3 + 0*0.3 + 0*0.4 = 30.0
        assert convergence_score(100.0, 0.0, 0.0) == 30.0
        # 0*0.3 + 100*0.3 + 0*0.4 = 30.0
        assert convergence_score(0.0, 100.0, 0.0) == 30.0
        # 0*0.3 + 0*0.3 + 100*0.4 = 40.0
        assert convergence_score(0.0, 0.0, 100.0) == 40.0


# ---------------------------------------------------------------------------
# rank_and_select_news tests
# ---------------------------------------------------------------------------


class TestRankAndSelectNews:
    def test_empty_pool_returns_empty(self):
        from src.agents.thinking_crew import rank_and_select_news

        assert rank_and_select_news([]) == []

    @patch(f"{_TC}.get_small_llm")
    @patch(f"{_TC}.Crew")
    def test_fallback_on_llm_error(self, mock_crew_cls, mock_get_llm):
        """When the LLM/Crew raises, we fall back to returning all news."""
        mock_get_llm.side_effect = ValueError("no key")

        from src.agents.thinking_crew import rank_and_select_news

        news = [
            {"id": "n1", "title": "News 1"},
            {"id": "n2", "title": "News 2"},
        ]
        result = rank_and_select_news(news)
        assert len(result) == 2
        assert result[0]["id"] == "n1"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_small_llm")
    def test_successful_ranking(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """When LLM returns valid ranking, news is sorted by impact."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = _mock_crew_result(
            '[{"id": "n2", "impact_score": 90}, {"id": "n1", "impact_score": 30}]'
        )

        from src.agents.thinking_crew import rank_and_select_news

        news = [
            {"id": "n1", "title": "Minor update"},
            {"id": "n2", "title": "Major crash"},
        ]
        result = rank_and_select_news(news)
        assert result[0]["id"] == "n2"  # higher impact first
        assert result[1]["id"] == "n1"


# ---------------------------------------------------------------------------
# think_effects tests
# ---------------------------------------------------------------------------


class TestThinkEffects:
    def test_empty_parents_returns_empty(self):
        from src.agents.thinking_crew import think_effects

        nodes, edges = think_effects([], [], layer=1)
        assert nodes == []
        assert edges == []

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.get_main_llm")
    def test_error_returns_empty(self, mock_get_llm, mock_crew_cls):
        mock_get_llm.side_effect = ValueError("no key")

        from src.agents.thinking_crew import think_effects

        parents = [{"id": "p1", "content": "test", "type": "news", "metadata": {}}]
        nodes, edges = think_effects(parents, [], layer=1)
        assert nodes == []
        assert edges == []

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_successful_effects(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = _mock_crew_result(
            '{"effects": [{"content": "Tech selloff", "reasoning": "Rate hike impact", '
            '"parent_ids": ["p1"], "sector": "tech", "fetched_news_ids": []}]}'
        )

        from src.agents.thinking_crew import think_effects

        parents = [
            {"id": "p1", "content": "Fed raises rates", "type": "news", "metadata": {}}
        ]
        nodes, edges = think_effects(parents, [], layer=1)
        assert len(nodes) == 1
        assert nodes[0]["type"] == "effect"
        assert nodes[0]["layer"] == 1
        assert nodes[0]["content"] == "Tech selloff"
        assert nodes[0]["parents"] == ["p1"]
        assert nodes[0]["selected"] is True
        assert len(edges) == 1
        assert edges[0]["source"] == "p1"
        assert edges[0]["relationship"] == "causes"


# ---------------------------------------------------------------------------
# match_opportunities tests
# ---------------------------------------------------------------------------


class TestMatchOpportunities:
    def test_empty_inputs_returns_empty(self):
        from src.agents.thinking_crew import match_opportunities

        nodes, edges = match_opportunities([], [])
        assert nodes == []
        assert edges == []

    def test_empty_effects_returns_empty(self):
        from src.agents.thinking_crew import match_opportunities

        nodes, edges = match_opportunities([], [{"ticker": "AAPL"}])
        assert nodes == []
        assert edges == []

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_successful_matching(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = _mock_crew_result(
            '{"matches": [{"ticker": "AAPL", "effect_id": "e1", '
            '"sentiment_score": 80, "agreement_score": 70, '
            '"reasoning": "Apple benefits from tech boom"}]}'
        )

        from src.agents.thinking_crew import match_opportunities

        effects = [
            {
                "id": "e1",
                "layer": 2,
                "content": "Tech sector rally",
                "reasoning": "",
                "metadata": {},
            }
        ]
        values = [{"ticker": "AAPL", "sector": "tech", "discount_pct": 15}]
        nodes, edges = match_opportunities(effects, values)

        assert len(nodes) == 1
        assert nodes[0]["type"] == "opportunity"
        assert nodes[0]["layer"] == 3  # effect layer + 1
        assert "AAPL" in nodes[0]["content"]
        assert nodes[0]["parents"] == ["e1"]

        # Verify convergence score is deterministic: 80*0.3 + 15*0.3 + 70*0.4 = 24+4.5+28 = 56.5
        assert nodes[0]["metadata"]["convergence_score"] == 56.5

        assert len(edges) == 1
        assert edges[0]["relationship"] == "matches"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_deduplicates_tickers(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Only one opportunity per ticker even if LLM returns duplicates."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = _mock_crew_result(
            '{"matches": ['
            '{"ticker": "AAPL", "effect_id": "e1", "sentiment_score": 80, "agreement_score": 70, "reasoning": "r1"},'
            '{"ticker": "AAPL", "effect_id": "e2", "sentiment_score": 90, "agreement_score": 90, "reasoning": "r2"}'
            "]}"
        )

        from src.agents.thinking_crew import match_opportunities

        effects = [
            {
                "id": "e1",
                "layer": 2,
                "content": "Effect 1",
                "reasoning": "",
                "metadata": {},
            },
            {
                "id": "e2",
                "layer": 2,
                "content": "Effect 2",
                "reasoning": "",
                "metadata": {},
            },
        ]
        values = [{"ticker": "AAPL", "sector": "tech", "discount_pct": 15}]
        nodes, edges = match_opportunities(effects, values)

        assert len(nodes) == 1  # deduplicated
