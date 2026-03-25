"""Tests for thinking_service.py — pipeline orchestrator.

Tests run_layer() and run_pipeline() with mocked agent functions.
No real LLM calls — all three agents (thinker, matcher, controller) are mocked.
"""

import asyncio
from unittest.mock import patch


from tests.helpers_thinking_pipeline import (
    controller_continue,
    controller_stop,
    matcher_result_layer1,
    matcher_result_layer2,
    news_pool,
    seed_nodes,
    thinker_result_layer1,
    thinker_result_layer2,
    value_pool,
)

_SVC = "src.services.thinking_service"


class TestRunLayer:
    """Tests for run_layer — one layer of think + match + control."""

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_calls_agents_in_sequence(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.return_value = thinker_result_layer1()
        mock_matcher.return_value = matcher_result_layer1()
        mock_ctrl.return_value = controller_continue()

        from src.services.thinking_service import run_layer

        result = await run_layer(
            chain_summary="",
            parent_nodes=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            layer=1,
            max_depth=5,
        )
        mock_thinker.assert_called_once()
        mock_matcher.assert_called_once()
        mock_ctrl.assert_called_once()
        assert len(result.effect_nodes) == 1
        assert len(result.fetch_nodes) == 1
        assert len(result.opportunity_nodes) == 1
        assert len(result.all_edges) == 3
        assert result.controller_decision["continue"] is True

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_thinker_fails_returns_empty_stop(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.side_effect = asyncio.TimeoutError("thinker timed out")

        from src.services.thinking_service import run_layer

        result = await run_layer(
            chain_summary="",
            parent_nodes=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            layer=1,
            max_depth=5,
        )
        assert result.effect_nodes == []
        assert result.controller_decision["continue"] is False
        mock_matcher.assert_not_called()
        mock_ctrl.assert_not_called()

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_matcher_fails_continues_without_matches(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.return_value = thinker_result_layer1()
        mock_matcher.side_effect = asyncio.TimeoutError("matcher timed out")
        mock_ctrl.return_value = controller_continue()

        from src.services.thinking_service import run_layer

        result = await run_layer(
            chain_summary="",
            parent_nodes=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            layer=1,
            max_depth=5,
        )
        assert len(result.effect_nodes) == 1
        assert result.opportunity_nodes == []
        assert len(result.all_edges) == 2
        assert result.controller_decision["continue"] is True

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_controller_fails_default_logic(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.return_value = thinker_result_layer1()
        mock_matcher.return_value = matcher_result_layer1()
        mock_ctrl.side_effect = asyncio.TimeoutError("controller timed out")

        from src.services.thinking_service import run_layer

        r1 = await run_layer(
            chain_summary="",
            parent_nodes=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            layer=1,
            max_depth=5,
        )
        assert r1.controller_decision["continue"] is True  # layer 1 < 3

        mock_thinker.return_value = thinker_result_layer1()
        mock_matcher.return_value = matcher_result_layer1()
        mock_ctrl.side_effect = asyncio.TimeoutError("controller timed out")

        r3 = await run_layer(
            chain_summary="",
            parent_nodes=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            layer=3,
            max_depth=5,
        )
        assert r3.controller_decision["continue"] is False  # layer 3 >= 3

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_thinker_returns_empty_effects_stops(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.return_value = ([], [], [], [], 0)

        from src.services.thinking_service import run_layer

        result = await run_layer(
            chain_summary="",
            parent_nodes=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            layer=1,
            max_depth=5,
        )
        assert result.effect_nodes == []
        assert result.controller_decision["continue"] is False
        mock_matcher.assert_not_called()
        mock_ctrl.assert_not_called()


class TestRunPipeline:
    """Tests for run_pipeline — full loop until Controller stops or max_depth."""

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_runs_two_layers_then_stops(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.side_effect = [thinker_result_layer1(), thinker_result_layer2()]
        mock_matcher.side_effect = [matcher_result_layer1(), matcher_result_layer2()]
        mock_ctrl.side_effect = [controller_continue(), controller_stop()]

        from src.services.thinking_service import run_pipeline

        layers = []

        async def on_done(n, r):
            layers.append((n, r))

        await run_pipeline(
            session_id="s1",
            seeds=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            max_depth=5,
            on_layer_complete=on_done,
        )
        assert len(layers) == 2
        assert layers[0][0] == 1
        assert layers[1][0] == 2

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_stops_at_max_depth(self, mock_thinker, mock_matcher, mock_ctrl):
        mock_thinker.return_value = thinker_result_layer1()
        mock_matcher.return_value = matcher_result_layer1()
        mock_ctrl.return_value = controller_continue()

        from src.services.thinking_service import run_pipeline

        layers = []

        async def on_done(n, r):
            layers.append((n, r))

        await run_pipeline(
            session_id="s1",
            seeds=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            max_depth=1,
            on_layer_complete=on_done,
        )
        assert len(layers) == 1

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_dag_acyclicity(self, mock_thinker, mock_matcher, mock_ctrl):
        mock_thinker.side_effect = [thinker_result_layer1(), thinker_result_layer2()]
        mock_matcher.side_effect = [matcher_result_layer1(), matcher_result_layer2()]
        mock_ctrl.side_effect = [controller_continue(), controller_stop()]

        from src.services.thinking_service import run_pipeline

        all_nodes = list(seed_nodes())
        all_edges = []

        async def on_done(n, r):
            all_nodes.extend(r.effect_nodes + r.fetch_nodes + r.opportunity_nodes)
            all_edges.extend(r.all_edges)

        await run_pipeline(
            session_id="s1",
            seeds=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            max_depth=5,
            on_layer_complete=on_done,
        )
        node_layers = {n["id"]: n["layer"] for n in all_nodes}
        for edge in all_edges:
            sl = node_layers.get(edge["source"])
            tl = node_layers.get(edge["target"])
            assert sl is not None, f"Source {edge['source']} missing"
            assert tl is not None, f"Target {edge['target']} missing"
            assert (
                sl <= tl
            ), f"{edge['source']}(L{sl})->{edge['target']}(L{tl}) violates DAG"

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_chain_summary_passed_between_layers(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.side_effect = [thinker_result_layer1(), thinker_result_layer2()]
        mock_matcher.side_effect = [matcher_result_layer1(), matcher_result_layer2()]
        mock_ctrl.side_effect = [
            ({"continue": True, "reasoning": "More", "summary": "Layer 1 summary"}, 20),
            controller_stop(),
        ]

        from src.services.thinking_service import run_pipeline

        async def noop(n, r):
            pass

        await run_pipeline(
            session_id="s1",
            seeds=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            max_depth=5,
            on_layer_complete=noop,
        )
        assert mock_thinker.call_count == 2
        args, kwargs = mock_thinker.call_args_list[1]
        summary = kwargs.get("chain_summary", args[0] if args else "")
        assert "Layer 1 summary" in summary


class TestDegradedMode:
    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_thinker_fails_pipeline_stops(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.side_effect = Exception("LLM unavailable")

        from src.services.thinking_service import run_pipeline

        layers = []

        async def on_done(n, r):
            layers.append((n, r))

        await run_pipeline(
            session_id="s1",
            seeds=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            max_depth=5,
            on_layer_complete=on_done,
        )
        assert len(layers) == 1
        assert layers[0][1].effect_nodes == []
        assert layers[0][1].controller_decision["continue"] is False

    @patch(f"{_SVC}.run_controller")
    @patch(f"{_SVC}.run_matcher")
    @patch(f"{_SVC}.run_thinker")
    async def test_thinker_fails_mid_pipeline(
        self, mock_thinker, mock_matcher, mock_ctrl
    ):
        mock_thinker.side_effect = [thinker_result_layer1(), Exception("LLM down")]
        mock_matcher.return_value = matcher_result_layer1()
        mock_ctrl.return_value = controller_continue()

        from src.services.thinking_service import run_pipeline

        layers = []

        async def on_done(n, r):
            layers.append((n, r))

        await run_pipeline(
            session_id="s1",
            seeds=seed_nodes(),
            news_pool=news_pool(),
            value_pool=value_pool(),
            max_depth=5,
            on_layer_complete=on_done,
        )
        assert len(layers) == 2
        assert len(layers[0][1].effect_nodes) == 1
        assert layers[1][1].effect_nodes == []
        assert layers[1][1].controller_decision["continue"] is False


class TestNoMockFallback:
    def test_no_mock_think_effects(self):
        import src.services.thinking_service as svc

        assert not hasattr(svc, "_mock_think_effects")

    def test_no_mock_match(self):
        import src.services.thinking_service as svc

        assert not hasattr(svc, "_mock_match")

    def test_no_use_real_agents(self):
        import src.services.thinking_service as svc

        assert not hasattr(svc, "_use_real_agents")

    def test_no_mock_references_in_source(self):
        import src.services.thinking_service as svc

        source = open(svc.__file__).read()
        assert "_mock_" not in source, "Module still contains mock references"
