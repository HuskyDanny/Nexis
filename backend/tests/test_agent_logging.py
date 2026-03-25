"""Tests for structured agent-level logging in thinking_crew.py.

Covers:
- Structured INFO log per agent call (timing, skills, parsed output, prompt size)
- DEBUG log of raw LLM response before parsing
- CrewAI verbose toggle based on LOG_LEVEL
"""

import json
import logging
from unittest.mock import MagicMock, patch

from tests.helpers_thinking_agents import mock_crew_result

_TC = "src.agents.thinking_crew"
_LOGGER = "nexis.agents"


class TestThinkerLogging:
    """Structured logging for run_thinker."""

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_thinker_info_log_contains_structured_fields(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls, caplog
    ):
        """run_thinker emits a structured INFO log with agent name, layer,
        skills count, latency, parsed count, and prompt size."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "Housing slows",
                            "reasoning": "Rate hike",
                            "confidence": 80,
                            "parent_ids": ["p1"],
                            "sector": "real_estate",
                            "fetched_news_ids": [],
                            "information_gaps": [],
                        }
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "Fed raises rates",
                "reasoning": "",
                "confidence": 95,
                "metadata": {"sector": "macro"},
            }
        ]

        with caplog.at_level(logging.INFO, logger=_LOGGER):
            run_thinker(parent_nodes=parents, chain_summary="", news_pool=[], layer=1)

        # Find the structured THINKER log line
        thinker_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.INFO and "THINKER" in r.message
        ]
        assert (
            len(thinker_logs) >= 1
        ), f"Expected THINKER INFO log, got: {[r.message for r in caplog.records]}"

        msg = thinker_logs[0].message
        assert "L1" in msg, "Should contain layer number"
        assert "skills=" in msg, "Should contain skills count"
        assert "s" in msg, "Should contain latency in seconds"
        assert "parsed=" in msg, "Should contain parsed results count"
        assert "prompt=" in msg, "Should contain prompt size"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_thinker_debug_log_contains_raw_response(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls, caplog
    ):
        """run_thinker emits a DEBUG log with raw LLM response before parsing."""
        mock_get_llm.return_value = MagicMock()
        raw_response = json.dumps(
            {
                "effects": [
                    {
                        "content": "X",
                        "reasoning": "Y",
                        "confidence": 70,
                        "parent_ids": ["p1"],
                        "sector": "tech",
                        "fetched_news_ids": [],
                        "information_gaps": [],
                    }
                ]
            }
        )
        mock_crew_cls.return_value = mock_crew_result(raw_response)

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "Test",
                "reasoning": "",
                "confidence": 90,
                "metadata": {},
            }
        ]

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            run_thinker(parent_nodes=parents, chain_summary="", news_pool=[], layer=1)

        debug_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.DEBUG and "raw" in r.message.lower()
        ]
        assert (
            len(debug_logs) >= 1
        ), f"Expected DEBUG raw response log, got: {[r.message for r in caplog.records]}"
        assert (
            "effects" in debug_logs[0].message
        ), "Raw response should contain LLM output"


class TestMatcherLogging:
    """Structured logging for run_matcher."""

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_matcher_info_log_contains_structured_fields(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls, caplog
    ):
        """run_matcher emits a structured INFO log with agent name, latency,
        parsed count, and prompt size."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "matches": [
                        {
                            "ticker": "AAPL",
                            "effect_id": "e1",
                            "sentiment_score": 75.0,
                            "agreement_score": 80.0,
                            "reasoning": "Tech benefits",
                        }
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_matcher

        effects = [
            {
                "id": "e1",
                "content": "Tech rally",
                "reasoning": "R",
                "confidence": 80,
                "layer": 1,
            }
        ]
        value_pool = [
            {
                "ticker": "AAPL",
                "sector": "tech",
                "discount_pct": 15,
                "summary": "Apple Inc",
            }
        ]

        with caplog.at_level(logging.INFO, logger=_LOGGER):
            run_matcher(effects=effects, value_pool=value_pool)

        matcher_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.INFO and "MATCHER" in r.message
        ]
        assert (
            len(matcher_logs) >= 1
        ), f"Expected MATCHER INFO log, got: {[r.message for r in caplog.records]}"

        msg = matcher_logs[0].message
        assert "skills=" in msg, "Should contain skills count"
        assert "s" in msg, "Should contain latency"
        assert "parsed=" in msg, "Should contain parsed count"
        assert "prompt=" in msg, "Should contain prompt size"


class TestControllerLogging:
    """Structured logging for run_controller."""

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_controller_info_log_contains_structured_fields(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls, caplog
    ):
        """run_controller emits a structured INFO log when LLM is invoked."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "continue": True,
                    "reasoning": "More to explore",
                    "summary": "Chain continues",
                }
            )
        )

        from src.agents.thinking_crew import run_controller

        effects = [{"id": "e1", "content": "Effect", "confidence": 80}]

        with caplog.at_level(logging.INFO, logger=_LOGGER):
            run_controller(
                chain_summary="Test chain",
                effects=effects,
                matches=[],
                layer=1,
                max_depth=3,
            )

        ctrl_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.INFO and "CONTROLLER" in r.message
        ]
        assert (
            len(ctrl_logs) >= 1
        ), f"Expected CONTROLLER INFO log, got: {[r.message for r in caplog.records]}"

        msg = ctrl_logs[0].message
        assert "L1" in msg, "Should contain layer number"
        assert "s" in msg, "Should contain latency"
        assert "continue=" in msg, "Should contain continue decision"

    def test_controller_deterministic_stop_no_llm_log(self, caplog):
        """Deterministic stops (empty effects, max depth) should NOT emit agent log."""
        from src.agents.thinking_crew import run_controller

        with caplog.at_level(logging.INFO, logger=_LOGGER):
            run_controller(
                chain_summary="", effects=[], matches=[], layer=1, max_depth=3
            )

        ctrl_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.INFO and "CONTROLLER" in r.message
        ]
        assert len(ctrl_logs) == 0, "Deterministic stop should not log agent call"


class TestCrewVerboseToggle:
    """CrewAI verbose flag toggles based on LOG_LEVEL."""

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_crew_verbose_false_at_info_level(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Crew() and Agent() are created with verbose=False when LOG_LEVEL is INFO."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "X",
                            "reasoning": "Y",
                            "confidence": 70,
                            "parent_ids": ["p1"],
                            "sector": "tech",
                            "fetched_news_ids": [],
                            "information_gaps": [],
                        }
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "T",
                "reasoning": "",
                "confidence": 90,
                "metadata": {},
            }
        ]

        with patch.dict("os.environ", {"LOG_LEVEL": "INFO"}):
            run_thinker(parent_nodes=parents, chain_summary="", news_pool=[], layer=1)

        # Check Crew was called with verbose=False
        crew_call = mock_crew_cls.call_args
        assert crew_call.kwargs.get("verbose") is False or (
            len(crew_call.args) > 2 and crew_call.args[2] is False
        ), f"Crew should be verbose=False at INFO level, got: {crew_call}"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_crew_verbose_true_at_debug_level(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Crew() and Agent() are created with verbose=True when LOG_LEVEL is DEBUG."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "X",
                            "reasoning": "Y",
                            "confidence": 70,
                            "parent_ids": ["p1"],
                            "sector": "tech",
                            "fetched_news_ids": [],
                            "information_gaps": [],
                        }
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "T",
                "reasoning": "",
                "confidence": 90,
                "metadata": {},
            }
        ]

        with patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"}):
            run_thinker(parent_nodes=parents, chain_summary="", news_pool=[], layer=1)

        # Check Crew was called with verbose=True
        crew_call = mock_crew_cls.call_args
        assert (
            crew_call.kwargs.get("verbose") is True
        ), f"Crew should be verbose=True at DEBUG level, got: {crew_call}"
