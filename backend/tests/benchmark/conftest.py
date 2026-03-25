"""Pytest configuration for benchmark tests."""

from __future__ import annotations

import pytest


# Registry of all scenario modules — add new scenarios here.
SCENARIO_REGISTRY = {
    "iran-escalation": "tests.benchmark.scenarios.iran_escalation",
    "fed-rate-decision": "tests.benchmark.scenarios.fed_rate_decision",
}


def _load_scenario(module_path: str) -> dict:
    """Import a scenario module and return its SCENARIO dict."""
    import importlib

    mod = importlib.import_module(module_path)
    return mod.SCENARIO


def pytest_addoption(parser):
    parser.addoption(
        "--mode",
        default="replay",
        choices=["live", "replay"],
        help="Benchmark execution mode",
    )
    parser.addoption("--judge", default="claude-sonnet-4-6", help="Judge model name")
    parser.addoption(
        "--runs", default=1, type=int, help="Number of benchmark runs for aggregation"
    )
    parser.addoption(
        "--bench-trace", default=None, help="Path to trace JSON file for replay mode"
    )
    parser.addoption(
        "--scenario",
        default="all",
        help="Scenario ID to test (e.g. iran-escalation, fed-rate-decision, or all)",
    )


def pytest_generate_tests(metafunc):
    """Parameterize tests that use the 'scenario' fixture."""
    if "scenario" not in metafunc.fixturenames:
        return
    selected = metafunc.config.getoption("--scenario")
    if selected == "all":
        ids = list(SCENARIO_REGISTRY.keys())
    else:
        ids = [s.strip() for s in selected.split(",")]
        for sid in ids:
            if sid not in SCENARIO_REGISTRY:
                raise pytest.UsageError(
                    f"Unknown scenario '{sid}'. Available: {list(SCENARIO_REGISTRY.keys())}"
                )
    scenarios = [_load_scenario(SCENARIO_REGISTRY[sid]) for sid in ids]
    metafunc.parametrize("scenario", scenarios, ids=ids)


@pytest.fixture
def benchmark_mode(request):
    return request.config.getoption("--mode")


@pytest.fixture
def judge_model_name(request):
    return request.config.getoption("--judge")


@pytest.fixture
def judge_model(request):
    from tests.benchmark.scoring.judge_models import create_judge_model

    name = request.config.getoption("--judge")
    return create_judge_model(name)


@pytest.fixture
def num_runs(request):
    return request.config.getoption("--runs")


@pytest.fixture
def trace_path(request):
    return request.config.getoption("--bench-trace")
