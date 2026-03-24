"""Tests for run_thinker — causal effects agent."""

import json
from unittest.mock import MagicMock, patch

from tests.helpers_thinking_agents import mock_crew_result

_TC = "src.agents.thinking_crew"


class TestRunThinker:
    """Tests for run_thinker — causal effects agent."""

    def test_empty_parents_returns_empty(self):
        from src.agents.thinking_crew import run_thinker

        effects, fetches, eff_edges, fetch_edges = run_thinker(
            parent_nodes=[], chain_summary="", news_pool=[], layer=1
        )
        assert effects == []
        assert fetches == []
        assert eff_edges == []
        assert fetch_edges == []

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_successful_effects(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Valid LLM response produces effect nodes with correct structure."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "Housing construction slows",
                            "reasoning": "Rate hike -> mortgage spike -> demand drops",
                            "confidence": 82,
                            "parent_ids": ["p1"],
                            "sector": "real_estate",
                            "fetched_news_ids": [],
                            "information_gaps": ["Need housing starts data"],
                        }
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "Fed raises rates 75bps",
                "reasoning": "",
                "confidence": 95,
                "metadata": {"sector": "macro"},
            }
        ]
        effects, fetches, eff_edges, fetch_edges = run_thinker(
            parent_nodes=parents,
            chain_summary="Fed raised rates.",
            news_pool=[],
            layer=1,
        )

        assert len(effects) == 1
        node = effects[0]
        assert node["type"] == "effect"
        assert node["layer"] == 1
        assert node["content"] == "Housing construction slows"
        assert node["reasoning"] == "Rate hike -> mortgage spike -> demand drops"
        assert node["confidence"] == 82
        assert node["parents"] == ["p1"]
        assert node["metadata"]["sector"] == "real_estate"
        assert node["metadata"]["information_gaps"] == ["Need housing starts data"]
        assert node["selected"] is True

        assert len(eff_edges) == 1
        assert eff_edges[0]["source"] == "p1"
        assert eff_edges[0]["relationship"] == "causes"  # layer 1

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_deeper_layer_uses_compounds_relationship(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Layer > 1 edges use 'compounds' relationship."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "Consumer spending contracts",
                            "reasoning": "Second order effect",
                            "confidence": 65,
                            "parent_ids": ["e1"],
                            "sector": "consumer",
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
                "id": "e1",
                "content": "Housing slows",
                "reasoning": "",
                "confidence": 82,
                "metadata": {},
            }
        ]
        effects, fetches, eff_edges, fetch_edges = run_thinker(
            parent_nodes=parents, chain_summary="", news_pool=[], layer=2
        )

        assert eff_edges[0]["relationship"] == "compounds"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_fetched_news_creates_fetch_nodes(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """When LLM references news from pool, fetch nodes are created."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "Oil prices spike",
                            "reasoning": "Supply disruption",
                            "confidence": 75,
                            "parent_ids": ["p1"],
                            "sector": "energy",
                            "fetched_news_ids": ["news-42"],
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
                "content": "Geopolitical tension",
                "reasoning": "",
                "confidence": 90,
                "metadata": {},
            }
        ]
        news_pool = [
            {
                "id": "news-42",
                "title": "OPEC cuts production",
                "summary": "OPEC announces cuts",
                "url": "https://example.com/42",
            },
            {"id": "news-99", "title": "Unrelated news", "summary": "Not relevant"},
        ]
        effects, fetches, eff_edges, fetch_edges = run_thinker(
            parent_nodes=parents, chain_summary="", news_pool=news_pool, layer=1
        )

        assert len(effects) == 1
        assert len(fetches) == 1
        assert fetches[0]["type"] == "fetch"
        assert "OPEC" in fetches[0]["content"]
        assert len(fetch_edges) == 1
        assert fetch_edges[0]["relationship"] == "fetched_for"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_invalid_parent_ids_defaults_to_first_parent(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """If LLM returns parent_ids not in the input, default to first parent."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "Some effect",
                            "reasoning": "Because",
                            "confidence": 50,
                            "parent_ids": ["nonexistent_id"],
                            "sector": "general",
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
                "content": "Test",
                "reasoning": "",
                "confidence": 80,
                "metadata": {},
            }
        ]
        effects, _, eff_edges, _ = run_thinker(
            parent_nodes=parents, chain_summary="", news_pool=[], layer=1
        )

        assert effects[0]["parents"] == ["p1"]
        assert eff_edges[0]["source"] == "p1"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.get_main_llm")
    def test_error_returns_empty(self, mock_get_llm, mock_crew_cls):
        """On LLM/JSON error, returns empty tuples without crashing."""
        mock_get_llm.side_effect = ValueError("no key")

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "test",
                "reasoning": "",
                "confidence": 80,
                "metadata": {},
            }
        ]
        effects, fetches, eff_edges, fetch_edges = run_thinker(
            parent_nodes=parents, chain_summary="", news_pool=[], layer=1
        )
        assert effects == []
        assert fetches == []
        assert eff_edges == []
        assert fetch_edges == []

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_markdown_code_block_parsing(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """LLM response wrapped in markdown code blocks is parsed correctly."""
        mock_get_llm.return_value = MagicMock()
        wrapped = (
            '```json\n{"effects": [{"content": "Effect X", "reasoning": "R", '
            '"confidence": 60, "parent_ids": ["p1"], "sector": "tech", '
            '"fetched_news_ids": [], "information_gaps": []}]}\n```'
        )
        mock_crew_cls.return_value = mock_crew_result(wrapped)

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "test",
                "reasoning": "",
                "confidence": 80,
                "metadata": {},
            }
        ]
        effects, _, _, _ = run_thinker(
            parent_nodes=parents, chain_summary="", news_pool=[], layer=1
        )
        assert len(effects) == 1
        assert effects[0]["content"] == "Effect X"

    @patch(f"{_TC}.Crew")
    @patch(f"{_TC}.Task")
    @patch(f"{_TC}.Agent")
    @patch(f"{_TC}.get_main_llm")
    def test_confidence_is_top_level_field(
        self, mock_get_llm, mock_agent_cls, mock_task_cls, mock_crew_cls
    ):
        """Confidence must be a top-level field on effect nodes."""
        mock_get_llm.return_value = MagicMock()
        mock_crew_cls.return_value = mock_crew_result(
            json.dumps(
                {
                    "effects": [
                        {
                            "content": "Effect",
                            "reasoning": "R",
                            "confidence": 77,
                            "parent_ids": ["p1"],
                            "sector": "tech",
                            "fetched_news_ids": [],
                            "information_gaps": ["gap1"],
                        }
                    ]
                }
            )
        )

        from src.agents.thinking_crew import run_thinker

        parents = [
            {
                "id": "p1",
                "content": "t",
                "reasoning": "",
                "confidence": 90,
                "metadata": {},
            }
        ]
        effects, _, _, _ = run_thinker(
            parent_nodes=parents, chain_summary="", news_pool=[], layer=1
        )

        node = effects[0]
        assert "confidence" in node
        assert node["confidence"] == 77
        assert "information_gaps" in node["metadata"]
