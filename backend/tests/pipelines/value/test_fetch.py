import pytest
from src.pipelines.value.fetch import YahooFinanceFetch


class TestYahooFinanceFetch:
    @pytest.mark.asyncio
    async def test_fetch_returns_list(self):
        result = await YahooFinanceFetch().fetch("US")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_returns_stocks_with_required_fields(self):
        result = await YahooFinanceFetch().fetch("US")
        for stock in result:
            assert "id" in stock
            assert "ticker" in stock
            assert "price" in stock
