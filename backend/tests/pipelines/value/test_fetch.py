import pytest
from src.pipelines.value.fetch import YahooFinanceFetch


class TestYahooFinanceFetch:
    @pytest.mark.asyncio
    async def test_fetch_returns_list(self):
        assert isinstance(await YahooFinanceFetch().fetch("US"), list)

    @pytest.mark.asyncio
    async def test_fetch_returns_empty(self):
        assert len(await YahooFinanceFetch().fetch("CN")) == 0
