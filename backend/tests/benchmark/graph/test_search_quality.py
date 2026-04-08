"""Graph search quality benchmarks against golden set.

Run: pytest tests/benchmark/graph/test_search_quality.py -v -m benchmark

FakeGraphStore uses substring matching — these tests verify the search
pipeline plumbing. Real search quality should be benchmarked against
actual Graphiti/Neo4j with semantic similarity + graph structure.
"""

import pytest
from statistics import mean

from tests.benchmark.graph.metrics import ndcg_at_k, recall_at_k, mrr
from tests.benchmark.graph.golden_set import GOLDEN_QUERIES

# FakeGraphStore with substring matching achieves near-perfect scores.
# Targets are set high to catch pipeline regressions.
NDCG_TARGET = 0.9
RECALL_TARGET = 0.9
MRR_TARGET = 0.9


def _extract_entity_ids(results: list[dict]) -> list[str]:
    """Extract entity IDs from graph search results.

    GraphStore.search() returns [{"edges": [...], "nodes": [...]}].
    """
    if not results:
        return []
    return [n["id"] for n in results[0].get("nodes", [])]


@pytest.mark.benchmark
class TestGraphSearchQualityTargets:
    async def test_ndcg_at_20(self, graph_store):
        scores = []
        for gq in GOLDEN_QUERIES:
            results = await graph_store.search(query=gq["query"])
            retrieved_ids = _extract_entity_ids(results)
            scores.append(ndcg_at_k(retrieved_ids, gq["relevant"], k=20))

        avg_ndcg = mean(scores)
        print(f"\nNDCG@20: {avg_ndcg:.3f} (target: {NDCG_TARGET})")
        for gq, s in zip(GOLDEN_QUERIES, scores):
            print(f"  {gq['description']}: {s:.3f}")
        assert avg_ndcg >= NDCG_TARGET, f"NDCG@20 = {avg_ndcg:.3f} < {NDCG_TARGET}"

    async def test_recall_at_20(self, graph_store):
        scores = []
        for gq in GOLDEN_QUERIES:
            results = await graph_store.search(query=gq["query"])
            retrieved_ids = _extract_entity_ids(results)
            scores.append(recall_at_k(retrieved_ids, gq["relevant"], k=20))

        avg_recall = mean(scores)
        print(f"\nRecall@20: {avg_recall:.3f} (target: {RECALL_TARGET})")
        for gq, s in zip(GOLDEN_QUERIES, scores):
            print(f"  {gq['description']}: {s:.3f}")
        assert (
            avg_recall >= RECALL_TARGET
        ), f"Recall@20 = {avg_recall:.3f} < {RECALL_TARGET}"

    async def test_mrr(self, graph_store):
        queries_results = []
        queries_relevant = []
        for gq in GOLDEN_QUERIES:
            results = await graph_store.search(query=gq["query"])
            queries_results.append(_extract_entity_ids(results))
            queries_relevant.append(gq["relevant"])

        avg_mrr = mrr(queries_results, queries_relevant)
        print(f"\nMRR: {avg_mrr:.3f} (target: {MRR_TARGET})")
        assert avg_mrr >= MRR_TARGET, f"MRR = {avg_mrr:.3f} < {MRR_TARGET}"


@pytest.mark.benchmark
class TestGraphSearchReturnsResults:
    async def test_search_returns_results_for_all_queries(self, graph_store):
        """Every golden query should return at least one result."""
        for gq in GOLDEN_QUERIES:
            results = await graph_store.search(query=gq["query"])
            entity_ids = _extract_entity_ids(results)
            assert len(entity_ids) > 0, f"No results for: {gq['query']}"

    async def test_search_returns_nodes_and_edges(self, graph_store):
        """Search result format should include both nodes and edges."""
        results = await graph_store.search(query="fed rate")
        assert len(results) == 1
        assert "nodes" in results[0]
        assert "edges" in results[0]
