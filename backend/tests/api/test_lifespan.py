import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_lifespan_connects_redis():
    mock_col = MagicMock()
    mock_col.update_many = AsyncMock(return_value=MagicMock(modified_count=0))

    with patch("src.main.mongodb") as mock_mongo, patch(
        "src.main.redis_client"
    ) as mock_redis:
        mock_mongo.connect = AsyncMock()
        mock_mongo.close = AsyncMock()
        mock_mongo.get_collection = MagicMock(return_value=mock_col)
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()
        from src.main import lifespan, app

        async with lifespan(app):
            mock_mongo.connect.assert_called_once()
            mock_redis.connect.assert_called_once()
        mock_mongo.close.assert_called_once()
        mock_redis.close.assert_called_once()
