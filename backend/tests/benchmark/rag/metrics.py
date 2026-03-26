"""Search quality metrics for RAG benchmarking."""

import math


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    if not relevant:
        return 1.0
    retrieved = retrieved[:k]
    if not retrieved:
        return 0.0
    dcg = sum(
        1.0 / math.log2(i + 2)
        for i, doc_id in enumerate(retrieved)
        if doc_id in relevant
    )
    ideal_k = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_k))
    return dcg / idcg if idcg > 0 else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items found in the top k results."""
    if not relevant:
        return 1.0
    retrieved_set = set(retrieved[:k])
    found = retrieved_set & relevant
    return len(found) / len(relevant)


def mrr(
    queries_retrieved: list[list[str]],
    queries_relevant: list[set[str]],
) -> float:
    """Mean Reciprocal Rank across multiple queries."""
    if not queries_retrieved:
        return 0.0
    total = 0.0
    for retrieved, relevant in zip(queries_retrieved, queries_relevant):
        for rank, doc_id in enumerate(retrieved, start=1):
            if doc_id in relevant:
                total += 1.0 / rank
                break
    return total / len(queries_retrieved)
