"""Tests for RAG search quality metrics."""

import pytest
from tests.benchmark.rag.metrics import ndcg_at_k, recall_at_k, mrr


class TestNDCG:
    def test_perfect_ranking(self):
        retrieved = ["a", "b", "c", "d", "e"]
        relevant = {"a", "b", "c"}
        assert ndcg_at_k(retrieved, relevant, k=5) == pytest.approx(1.0)

    def test_inverse_ranking(self):
        retrieved = ["x", "y", "a", "b", "c"]
        relevant = {"a", "b", "c"}
        score = ndcg_at_k(retrieved, relevant, k=5)
        assert 0.0 < score < 1.0

    def test_no_relevant_results(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        assert ndcg_at_k(retrieved, relevant, k=3) == 0.0

    def test_empty_retrieved(self):
        assert ndcg_at_k([], {"a"}, k=5) == 0.0

    def test_k_limits_evaluation(self):
        retrieved = ["x", "a", "b", "c"]
        relevant = {"a", "b", "c"}
        score_k2 = ndcg_at_k(retrieved, relevant, k=2)
        score_k4 = ndcg_at_k(retrieved, relevant, k=4)
        assert score_k4 > score_k2


class TestRecall:
    def test_all_found(self):
        retrieved = ["a", "b", "c", "d"]
        relevant = {"a", "b"}
        assert recall_at_k(retrieved, relevant, k=4) == 1.0

    def test_none_found(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        assert recall_at_k(retrieved, relevant, k=3) == 0.0

    def test_partial(self):
        retrieved = ["a", "x", "y"]
        relevant = {"a", "b"}
        assert recall_at_k(retrieved, relevant, k=3) == 0.5

    def test_empty_relevant(self):
        assert recall_at_k(["a"], set(), k=1) == 1.0

    def test_k_limits(self):
        retrieved = ["x", "a"]
        relevant = {"a"}
        assert recall_at_k(retrieved, relevant, k=1) == 0.0
        assert recall_at_k(retrieved, relevant, k=2) == 1.0


class TestMRR:
    def test_first_position(self):
        assert mrr([["a", "b"]], [{"a"}]) == 1.0

    def test_second_position(self):
        assert mrr([["x", "a"]], [{"a"}]) == 0.5

    def test_not_found(self):
        assert mrr([["x", "y"]], [{"a"}]) == 0.0

    def test_multiple_queries(self):
        queries_results = [["a", "b"], ["x", "b"]]
        queries_relevant = [{"a"}, {"b"}]
        assert mrr(queries_results, queries_relevant) == pytest.approx(0.75)
