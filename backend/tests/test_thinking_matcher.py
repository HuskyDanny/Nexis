"""Tests for run_matcher — value opportunity matching agent."""

import json
from unittest.mock import MagicMock, patch

from tests.helpers_thinking_agents import mock_crew_result

_TC = "src.agents.thinking_crew"


class TestRunMatcher:
    """Tests for run_matcher — value opportunity matching agent."""

    def test_empty_inputs_returns_empty(self):
        from src.agents.thinking_crew import run_matcher

        nodes, edges, tokens = run_matcher(effects=[], value_pool=[])
        assert nodes == []
        assert edges == []
        assert tokens == 0

    def test_empty_effects_returns_empty(self):
        from src.agents.thinking_crew import run_matcher

        nodes, edges, tokens = run_matcher(effects=[], value_pool=[{"ticker": "AAPL"}])
        assert nodes == []
        assert edges == []
        assert tokens == 0

    def test_empty_value_pool_returns_empty(self):
        from src.agents.thinking_crew import run_matcher

        nodes, edges, tokens = run_matcher(
            effects=[
                {
                    "id": "e1",
                    "layer": 1,
                    "content": "X",
                    "reasoning": "",
                    "confidence": 80,
                    "metadata": {},
                }
            ],
            value_pool=[],
        )
        assert nodes == []
        assert edges == []
        assert tokens == 0

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_successful_matching(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Valid LLM response produces opportunity nodes with correct structure."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "matches": [
                        {
                            "ticker": "XOM",
                            "effect_id": "e1",
                            "sentiment_score": 75,
                            "agreement_score": 80,
                            "reasoning": "Energy sector benefits.",
                        }
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_matcher

        effects = [
            {
                "id": "e1",
                "layer": 2,
                "content": "Oil prices spike",
                "reasoning": "Supply disruption",
                "confidence": 75,
                "metadata": {"sector": "energy"},
            },
        ]
        values = [
            {
                "ticker": "XOM",
                "sector": "energy",
                "discount_pct": 22,
                "summary": "Exxon Mobil",
            }
        ]

        nodes, edges, _tokens = run_matcher(effects=effects, value_pool=values)

        assert len(nodes) == 1
        node = nodes[0]
        assert node["type"] == "opportunity"
        assert node["layer"] == 2  # Same layer as parent effect, NOT +1
        assert "XOM" in node["content"]
        assert node["parents"] == ["e1"]
        assert node["selected"] is True

        # Convergence: 75*0.3 + 22*0.3 + 80*0.4 = 22.5 + 6.6 + 32.0 = 61.1
        assert node["metadata"]["convergence_score"] == 61.1
        assert node["metadata"]["sentiment_score"] == 75
        assert node["metadata"]["agreement_score"] == 80

        assert len(edges) == 1
        assert edges[0]["relationship"] == "matches"
        assert edges[0]["source"] == "e1"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_no_seen_tickers_dedup(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Multiple matches for the same ticker from different effects are ALL kept."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "matches": [
                        {
                            "ticker": "AAPL",
                            "effect_id": "e1",
                            "sentiment_score": 80,
                            "agreement_score": 70,
                            "reasoning": "Path A",
                        },
                        {
                            "ticker": "AAPL",
                            "effect_id": "e2",
                            "sentiment_score": 90,
                            "agreement_score": 85,
                            "reasoning": "Path B",
                        },
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_matcher

        effects = [
            {
                "id": "e1",
                "layer": 1,
                "content": "Effect 1",
                "reasoning": "",
                "confidence": 80,
                "metadata": {},
            },
            {
                "id": "e2",
                "layer": 1,
                "content": "Effect 2",
                "reasoning": "",
                "confidence": 70,
                "metadata": {},
            },
        ]
        values = [{"ticker": "AAPL", "sector": "tech", "discount_pct": 15}]

        nodes, edges, _tokens = run_matcher(effects=effects, value_pool=values)

        # Both matches kept — no dedup!
        assert len(nodes) == 2
        assert len(edges) == 2

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_invalid_effect_id_skipped(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Matches referencing nonexistent effect IDs are skipped."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "matches": [
                        {
                            "ticker": "AAPL",
                            "effect_id": "nonexistent",
                            "sentiment_score": 80,
                            "agreement_score": 70,
                            "reasoning": "R",
                        },
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_matcher

        effects = [
            {
                "id": "e1",
                "layer": 1,
                "content": "Effect 1",
                "reasoning": "",
                "confidence": 80,
                "metadata": {},
            }
        ]
        values = [{"ticker": "AAPL", "sector": "tech", "discount_pct": 15}]

        nodes, edges, _tokens = run_matcher(effects=effects, value_pool=values)
        assert len(nodes) == 0

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.get_main_llm")
    def test_error_returns_empty(self, mock_get_llm, mock_crew_cls):
        """On error, returns empty without crashing."""
        mock_get_llm.side_effect = ValueError("no key")

        from src.agents.thinking_crew import run_matcher

        effects = [
            {
                "id": "e1",
                "layer": 1,
                "content": "X",
                "reasoning": "",
                "confidence": 80,
                "metadata": {},
            }
        ]
        values = [{"ticker": "AAPL", "sector": "tech", "discount_pct": 15}]

        nodes, edges, tokens = run_matcher(effects=effects, value_pool=values)
        assert nodes == []
        assert edges == []
        assert tokens == 0
