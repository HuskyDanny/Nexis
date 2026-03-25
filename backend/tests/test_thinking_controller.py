"""Tests for run_controller — meta-reasoning and termination agent."""

import json
from unittest.mock import MagicMock, patch

from tests.helpers_thinking_agents import mock_crew_result

_TC = "src.agents.thinking_crew"


class TestRunController:
    """Tests for run_controller — meta-reasoning and termination agent."""

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_continue_decision(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Controller returns continue=True with reasoning and summary."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "continue": True,
                    "reasoning": "High confidence effects, worth exploring deeper.",
                    "summary": "Fed hike -> credit tightening (conf 88). Unexplored: housing.",
                }
            )
        )

        from src.agents.thinking_crew import run_controller

        result, tokens = run_controller(
            chain_summary="Fed raised rates.",
            effects=[
                {"content": "Credit tightening", "confidence": 88},
                {"content": "Tech margin pressure", "confidence": 85},
            ],
            matches=[{"ticker": "XOM", "convergence_score": 61.1}],
            layer=1,
            max_depth=5,
        )

        assert result["continue"] is True
        assert "reasoning" in result
        assert "summary" in result
        assert len(result["summary"]) > 0

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_stop_decision(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Controller returns continue=False."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "continue": False,
                    "reasoning": "Low confidence, speculative chains.",
                    "summary": "Final summary of the chain.",
                }
            )
        )

        from src.agents.thinking_crew import run_controller

        result, _tokens = run_controller(
            chain_summary="Previous summary.",
            effects=[{"content": "Weak effect", "confidence": 30}],
            matches=[],
            layer=3,
            max_depth=5,
        )

        assert result["continue"] is False

    def test_max_depth_forces_stop(self):
        """When layer >= max_depth, stop without calling LLM."""
        from src.agents.thinking_crew import run_controller

        result, tokens = run_controller(
            chain_summary="Summary.",
            effects=[{"content": "Effect", "confidence": 90}],
            matches=[],
            layer=5,
            max_depth=5,
        )

        assert result["continue"] is False
        assert (
            "max depth" in result["reasoning"].lower()
            or "maximum" in result["reasoning"].lower()
        )
        assert tokens == 0

    def test_low_avg_confidence_forces_stop(self):
        """When average confidence is below threshold, stop without calling LLM."""
        from src.agents.thinking_crew import run_controller

        result, tokens = run_controller(
            chain_summary="Summary.",
            effects=[
                {"content": "E1", "confidence": 20},
                {"content": "E2", "confidence": 25},
                {"content": "E3", "confidence": 15},
            ],
            matches=[],
            layer=2,
            max_depth=5,
        )

        assert result["continue"] is False
        assert "confidence" in result["reasoning"].lower()
        assert tokens == 0

    def test_no_effects_forces_stop(self):
        """When thinker produced no effects, stop without calling LLM."""
        from src.agents.thinking_crew import run_controller

        result, tokens = run_controller(
            chain_summary="Summary.",
            effects=[],
            matches=[],
            layer=2,
            max_depth=5,
        )

        assert result["continue"] is False
        assert tokens == 0

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.get_main_llm")
    def test_error_returns_stop(self, mock_get_llm, mock_crew_cls):
        """On LLM error, returns stop decision (safe default)."""
        mock_get_llm.side_effect = ValueError("no key")

        from src.agents.thinking_crew import run_controller

        result, tokens = run_controller(
            chain_summary="Summary.",
            effects=[{"content": "Effect", "confidence": 80}],
            matches=[],
            layer=1,
            max_depth=5,
        )

        assert result["continue"] is False
        assert "error" in result["reasoning"].lower()
        assert tokens == 0


class TestParseJsonResponse:
    """Tests for the JSON parsing helper."""

    def test_plain_json(self):
        from src.agents.thinking_crew import _parse_json_response

        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_code_block(self):
        from src.agents.thinking_crew import _parse_json_response

        result = _parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_code_block_without_lang(self):
        from src.agents.thinking_crew import _parse_json_response

        result = _parse_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_invalid_json_returns_none(self):
        from src.agents.thinking_crew import _parse_json_response

        result = _parse_json_response("not json at all")
        assert result is None

    def test_empty_string_returns_none(self):
        from src.agents.thinking_crew import _parse_json_response

        result = _parse_json_response("")
        assert result is None


class TestSkillConstants:
    def test_thinker_skills_defined(self):
        from src.agents.thinking_crew import THINKER_SKILLS

        assert "macro_economics" in THINKER_SKILLS
        assert "geopolitical_risk" in THINKER_SKILLS
        assert "sector_rotation" in THINKER_SKILLS
        assert "regulatory_impact" in THINKER_SKILLS
        assert "supply_chain" in THINKER_SKILLS
        assert "consumer_behavior" in THINKER_SKILLS
        assert len(THINKER_SKILLS) == 6

    def test_matcher_skills_defined(self):
        from src.agents.thinking_crew import MATCHER_SKILLS

        assert "company_fundamentals" in MATCHER_SKILLS
        assert "technical_momentum" in MATCHER_SKILLS
        assert "sector_rotation" in MATCHER_SKILLS
        assert len(MATCHER_SKILLS) == 3
