"""SiliconFlow embedding provider."""

from __future__ import annotations

import httpx

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger("rag.embedding")


class SiliconFlowEmbedding:
    def __init__(self, model: str = "BAAI/bge-m3"):
        self.model = model
        self.url = "https://api.siliconflow.cn/v1/embeddings"
        self.api_key = settings.siliconflow_api_key

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts, "encoding_format": "float"},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            return [e["embedding"] for e in embeddings]
