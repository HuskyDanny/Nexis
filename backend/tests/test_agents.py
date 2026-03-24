"""Tests for the agents module — LLM config and convergence score.

Old tests for rank_and_select_news, think_effects, match_opportunities have been
replaced by test_thinking_agents.py, test_thinking_matcher.py, test_thinking_controller.py.
"""

import pytest


# ---------------------------------------------------------------------------
# LLM config tests
# ---------------------------------------------------------------------------


class TestLLMConfig:
    def test_is_llm_available_false_when_no_key(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.llm_config.settings",
            type("S", (), {"siliconflow_api_key": ""})(),
        )
        from src.agents.llm_config import is_llm_available

        assert is_llm_available() is False

    def test_is_llm_available_true_when_key_set(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.llm_config.settings",
            type("S", (), {"siliconflow_api_key": "test-key"})(),
        )
        from src.agents.llm_config import is_llm_available

        assert is_llm_available() is True

    def test_get_api_key_raises_without_env(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.llm_config.settings",
            type("S", (), {"siliconflow_api_key": ""})(),
        )
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
