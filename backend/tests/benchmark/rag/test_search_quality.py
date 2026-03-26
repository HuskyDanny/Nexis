"""RAG search quality benchmarks against golden set.

Run: pytest tests/benchmark/rag/test_search_quality.py -v -m benchmark
"""

import pytest
from statistics import mean

from tests.benchmark.rag.metrics import ndcg_at_k, recall_at_k, mrr
from tests.benchmark.rag.golden_set import GOLDEN_QUERIES

# Baseline with FakeEmbedding (hash-based): NDCG≈0.61, Recall=1.0, MRR≈0.57
# Targets will increase when switching to real semantic embeddings
NDCG_TARGET = 0.5
RECALL_TARGET = 0.9
MRR_TARGET = 0.5


@pytest.mark.benchmark
class TestSearchQualityTargets:
    async def test_ndcg_at_20(self, search_service):
        scores = []
        for gq in GOLDEN_QUERIES:
            results = await search_service.search(
                query=gq["query"],
                current_session_id="benchmark",
            )
            retrieved_ids = [r["id"] for r in results]
            scores.append(ndcg_at_k(retrieved_ids, gq["relevant"], k=20))

        avg_ndcg = mean(scores)
        print(f"\nNDCG@20: {avg_ndcg:.3f} (target: {NDCG_TARGET})")
        for gq, s in zip(GOLDEN_QUERIES, scores):
            print(f"  {gq['description']}: {s:.3f}")
        assert avg_ndcg >= NDCG_TARGET, f"NDCG@20 = {avg_ndcg:.3f} < {NDCG_TARGET}"

    async def test_recall_at_20(self, search_service):
        scores = []
        for gq in GOLDEN_QUERIES:
            results = await search_service.search(
                query=gq["query"],
                current_session_id="benchmark",
            )
            retrieved_ids = [r["id"] for r in results]
            scores.append(recall_at_k(retrieved_ids, gq["relevant"], k=20))

        avg_recall = mean(scores)
        print(f"\nRecall@20: {avg_recall:.3f} (target: {RECALL_TARGET})")
        for gq, s in zip(GOLDEN_QUERIES, scores):
            print(f"  {gq['description']}: {s:.3f}")
        assert (
            avg_recall >= RECALL_TARGET
        ), f"Recall@20 = {avg_recall:.3f} < {RECALL_TARGET}"

    async def test_mrr(self, search_service):
        queries_results = []
        queries_relevant = []
        for gq in GOLDEN_QUERIES:
            results = await search_service.search(
                query=gq["query"],
                current_session_id="benchmark",
            )
            queries_results.append([r["id"] for r in results])
            queries_relevant.append(gq["relevant"])

        avg_mrr = mrr(queries_results, queries_relevant)
        print(f"\nMRR: {avg_mrr:.3f} (target: {MRR_TARGET})")
        assert avg_mrr >= MRR_TARGET, f"MRR = {avg_mrr:.3f} < {MRR_TARGET}"


@pytest.mark.benchmark
class TestHybridVsSingle:
    async def test_hybrid_search_returns_results(self, search_service):
        for gq in GOLDEN_QUERIES:
            results = await search_service.search(
                query=gq["query"],
                current_session_id="benchmark",
            )
            assert len(results) > 0, f"No results for: {gq['query']}"


@pytest.mark.benchmark
class TestDecayInSearch:
    async def test_newer_nodes_favored(self, search_service):
        results = await search_service.search(
            query="oil energy trade impact",
            current_session_id="benchmark",
            node_type=["effect"],
            sector="energy",
        )
        if len(results) >= 2:
            ids = [r["id"] for r in results]
            if "eff_005" in ids and "eff_006" in ids:
                assert ids.index("eff_005") < ids.index(
                    "eff_006"
                ), "Newer node (eff_005) should rank above older (eff_006) after decay"
