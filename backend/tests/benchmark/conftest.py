"""Pytest configuration for benchmark tests."""

from __future__ import annotations

import pytest


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
