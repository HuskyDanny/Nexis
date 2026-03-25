"""Tests for structured agent-level logging in thinking_crew.py.

Verifies that:
1. Each agent call emits a structured INFO log line with timing and results
2. DEBUG level enables CrewAI verbose mode and logs raw LLM responses
3. _is_debug() reads LOG_LEVEL env var directly (not cached logger level)
"""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

from src.agents.thinking_crew import run_thinker, run_matcher, run_controller

_TC = "src.agents.thinking_crew"


def _mock_crew_result(raw: str = '{"effects": []}') -> MagicMock:
    result = MagicMock()
    result.raw = raw
    token_usage = MagicMock()
    token_usage.total_tokens = 0
    result.token_usage = token_usage
    return result


def _parent_nodes(n: int = 1) -> list[dict]:
    return [
        {
            "id": f"node-{i}",
            "layer": 0,
            "type": "news",
            "content": f"Test event {i}",
            "reasoning": "",
            "confidence": 100,
            "sources": [],
            "parents": [],
            "selected": True,
            "metadata": {"sector": "tech"},
        }
        for i in range(n)
    ]


def _effects(n: int = 2) -> list[dict]:
    return [
        {
            "id": f"eff-{i}",
            "content": f"Effect {i}",
            "reasoning": "test",
            "confidence": 70,
            "layer": 1,
        }
        for i in range(n)
    ]


def _value_pool() -> list[dict]:
    return [
        {"ticker": "AAPL", "sector": "tech", "discount_pct": 15, "summary": "Apple"}
    ]


class TestThinkerLogging:
    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    @patch(f"{_TC}.FetchNewsTool")
    @patch(f"{_TC}.build_system_prompt_with_skills", return_value="system")
    def test_logs_structured_info(
        self, _bld, _fetch, _llm, _agent, _task, mock_crew_cls, caplog
    ):
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result(
            '{"effects": [{"content": "test", "reasoning": "r", "confidence": 80, '
            '"parent_ids": ["node-0"], "sector": "tech", "fetched_news_ids": [], '
            '"information_gaps": []}]}'
        )
        mock_crew_cls.return_value = mock_crew

        with caplog.at_level(logging.INFO, logger="nexis.agents"):
            run_thinker(
                parent_nodes=_parent_nodes(),
                chain_summary="",
                news_pool=[],
                layer=1,
            )

        # Match the structured format from the spec:
        # THINKER L1 | skills=N | Xs | parsed=N effects, N fetch | prompt=N chars
        thinker_logs = [
            r for r in caplog.records if "THINKER" in r.message and "L1" in r.message
        ]
        assert (
            len(thinker_logs) >= 1
        ), f"Expected THINKER structured log, got: {[r.message for r in caplog.records]}"
        msg = thinker_logs[0].message
        assert "skills=" in msg
        assert "parsed=" in msg
        assert "prompt=" in msg


class TestMatcherLogging:
    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    @patch(f"{_TC}.FetchNewsTool")
    @patch(f"{_TC}.build_system_prompt_with_skills", return_value="system")
    def test_logs_structured_info(
        self, _bld, _fetch, _llm, _agent, _task, mock_crew_cls, caplog
    ):
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result('{"matches": []}')
        mock_crew_cls.return_value = mock_crew

        with caplog.at_level(logging.INFO, logger="nexis.agents"):
            run_matcher(effects=_effects(), value_pool=_value_pool())

        matcher_logs = [r for r in caplog.records if "MATCHER" in r.message]
        assert (
            len(matcher_logs) >= 1
        ), f"Expected MATCHER log, got: {[r.message for r in caplog.records]}"
        msg = matcher_logs[0].message
        assert "skills=" in msg
        assert "parsed=" in msg


class TestControllerLogging:
    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_logs_structured_info(self, _llm, _agent, _task, mock_crew_cls, caplog):
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result(
            '{"continue": true, "reasoning": "More to explore", "summary": "Chain"}'
        )
        mock_crew_cls.return_value = mock_crew

        with caplog.at_level(logging.INFO, logger="nexis.agents"):
            run_controller(
                chain_summary="test",
                effects=_effects(),
                matches=[],
                layer=1,
                max_depth=3,
            )

        ctrl_logs = [r for r in caplog.records if "CONTROLLER" in r.message]
        assert (
            len(ctrl_logs) >= 1
        ), f"Expected CONTROLLER log, got: {[r.message for r in caplog.records]}"
        msg = ctrl_logs[0].message
        assert "L1" in msg
        assert "continue=" in msg


class TestDebugVerboseToggle:
    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    @patch(f"{_TC}.FetchNewsTool")
    @patch(f"{_TC}.build_system_prompt_with_skills", return_value="system")
    def test_verbose_false_at_info(
        self, _bld, _fetch, _llm, _agent, _task, mock_crew_cls
    ):
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result('{"effects": []}')
        mock_crew_cls.return_value = mock_crew

        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}):
            run_thinker(
                parent_nodes=_parent_nodes(),
                chain_summary="",
                news_pool=[],
                layer=1,
            )

        kwargs = mock_crew_cls.call_args[1]
        assert kwargs.get("verbose") is False, f"Expected verbose=False, got {kwargs}"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    @patch(f"{_TC}.FetchNewsTool")
    @patch(f"{_TC}.build_system_prompt_with_skills", return_value="system")
    def test_verbose_true_at_debug(
        self, _bld, _fetch, _llm, _agent, _task, mock_crew_cls
    ):
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result('{"effects": []}')
        mock_crew_cls.return_value = mock_crew

        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            run_thinker(
                parent_nodes=_parent_nodes(),
                chain_summary="",
                news_pool=[],
                layer=1,
            )

        kwargs = mock_crew_cls.call_args[1]
        assert kwargs.get("verbose") is True, f"Expected verbose=True, got {kwargs}"


class TestDebugRawResponseLogging:
    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    @patch(f"{_TC}.FetchNewsTool")
    @patch(f"{_TC}.build_system_prompt_with_skills", return_value="system")
    def test_raw_response_logged_at_debug(
        self, _bld, _fetch, _llm, _agent, _task, mock_crew_cls, caplog
    ):
        raw_json = (
            '{"effects": [{"content": "test", "reasoning": "r", "confidence": 80}]}'
        )
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result(raw_json)
        mock_crew_cls.return_value = mock_crew

        # _is_debug() reads LOG_LEVEL env directly; caplog.at_level captures output
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            with caplog.at_level(logging.DEBUG, logger="nexis.agents"):
                run_thinker(
                    parent_nodes=_parent_nodes(),
                    chain_summary="",
                    news_pool=[],
                    layer=1,
                )

        debug_logs = [r for r in caplog.records if r.levelno == logging.DEBUG]
        raw_logs = [
            r
            for r in debug_logs
            if "raw" in r.message.lower() or raw_json[:30] in r.message
        ]
        assert (
            len(raw_logs) >= 1
        ), f"Expected raw response in DEBUG logs, got: {[r.message for r in debug_logs]}"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    @patch(f"{_TC}.FetchNewsTool")
    @patch(f"{_TC}.build_system_prompt_with_skills", return_value="system")
    def test_matcher_raw_response_logged_at_debug(
        self, _bld, _fetch, _llm, _agent, _task, mock_crew_cls, caplog
    ):
        raw_json = '{"matches": [{"ticker": "AAPL", "effect_id": "eff-0", "sentiment_score": 80, "agreement_score": 70, "reasoning": "test"}]}'
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result(raw_json)
        mock_crew_cls.return_value = mock_crew

        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            with caplog.at_level(logging.DEBUG, logger="nexis.agents"):
                run_matcher(effects=_effects(), value_pool=_value_pool())

        debug_logs = [r for r in caplog.records if r.levelno == logging.DEBUG]
        raw_logs = [
            r for r in debug_logs if "MATCHER" in r.message and "raw" in r.message.lower()
        ]
        assert (
            len(raw_logs) >= 1
        ), f"Expected MATCHER raw response in DEBUG logs, got: {[r.message for r in debug_logs]}"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_controller_raw_response_logged_at_debug(
        self, _llm, _agent, _task, mock_crew_cls, caplog
    ):
        raw_json = '{"continue": true, "reasoning": "More to explore", "summary": "Chain"}'
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = _mock_crew_result(raw_json)
        mock_crew_cls.return_value = mock_crew

        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            with caplog.at_level(logging.DEBUG, logger="nexis.agents"):
                run_controller(
                    chain_summary="test",
                    effects=_effects(),
                    matches=[],
                    layer=1,
                    max_depth=3,
                )

        debug_logs = [r for r in caplog.records if r.levelno == logging.DEBUG]
        raw_logs = [
            r for r in debug_logs if "CONTROLLER" in r.message and "raw" in r.message.lower()
        ]
        assert (
            len(raw_logs) >= 1
        ), f"Expected CONTROLLER raw response in DEBUG logs, got: {[r.message for r in debug_logs]}"
