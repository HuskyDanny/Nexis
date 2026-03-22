import pytest
from src.pipelines.value.process import TickerUpsertProcess


class TestTickerUpsertProcess:
    def setup_method(self):
        self.proc = TickerUpsertProcess()

    @pytest.mark.asyncio
    async def test_insert_new_ticker(self):
        result = await self.proc.process(
            {"ticker": "AAPL", "market": "US", "price": 150.0, "name": "Apple"}, []
        )
        assert result.action == "insert"
        assert result.entity_id == "AAPL:US"
        assert result.merged_from is None

    @pytest.mark.asyncio
    async def test_merge_existing_ticker(self):
        existing = [
            {
                "id": "AAPL:US",
                "ticker": "AAPL",
                "market": "US",
                "price": 150.0,
                "pe_ratio": 27.0,
                "name": "Apple Inc",
            }
        ]
        result = await self.proc.process(
            {"ticker": "AAPL", "market": "US", "price": 155.0, "pe_ratio": 28.5},
            existing,
        )
        assert result.action == "merge"
        assert result.entity_id == "AAPL:US"

    @pytest.mark.asyncio
    async def test_entity_id_format(self):
        result = await self.proc.process(
            {"ticker": "BABA", "market": "CN", "price": 80.0}, []
        )
        assert result.entity_id == "BABA:CN"

    @pytest.mark.asyncio
    async def test_no_match_gives_insert(self):
        existing = [
            {
                "id": "MSFT:US",
                "ticker": "MSFT",
                "market": "US",
                "price": 390.0,
                "sector": "Technology",
            }
        ]
        # Different ticker — should insert, not merge
        result = await self.proc.process(
            {"ticker": "GOOG", "market": "US", "price": 170.0}, existing
        )
        assert result.action == "insert"
        assert result.entity_id == "GOOG:US"
