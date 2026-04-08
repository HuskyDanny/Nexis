"""BM25 sparse encoding via fastembed.

DEPRECATED: Graph services handle sparse encoding internally via Graphiti.
Kept for backwards compatibility with existing tests. Do not use in new code.
"""

from __future__ import annotations

from src.core.logger import get_logger
from fastembed import SparseTextEmbedding

log = get_logger("rag.sparse")


class FastEmbedBM25:
    def __init__(self, model_name: str = "Qdrant/bm25"):
        self._model = SparseTextEmbedding(model_name=model_name)

    def encode(self, text: str) -> tuple[list[int], list[float]]:
        if not text.strip():
            return [], []
        results = list(self._model.embed([text]))
        if not results:
            return [], []
        sparse = results[0]
        return sparse.indices.tolist(), sparse.values.tolist()
