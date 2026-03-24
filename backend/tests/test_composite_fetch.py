import pytest
from src.pipelines.news.fetch import CompositeFetch


class FakeFetcher:
    def __init__(self, items: list[dict]):
        self._items = items

    async def fetch(self, market=None) -> list[dict]:
        return self._items


class FailingFetcher:
    async def fetch(self, market=None) -> list[dict]:
        raise RuntimeError("API down")


@pytest.mark.asyncio
async def test_composite_fetch_merges_results():
    f1 = FakeFetcher([{"id": "a"}])
    f2 = FakeFetcher([{"id": "b"}])
    cf = CompositeFetch([f1, f2])
    result = await cf.fetch()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_composite_fetch_survives_failure():
    f1 = FakeFetcher([{"id": "a"}])
    f2 = FailingFetcher()
    cf = CompositeFetch([f1, f2])
    result = await cf.fetch()
    assert len(result) == 1
    assert result[0]["id"] == "a"
