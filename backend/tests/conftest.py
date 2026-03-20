import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def mock_mongodb():
    """Prevent real MongoDB connection during tests."""
    with patch("src.database.mongodb.mongodb") as mock:
        mock.connect = AsyncMock()
        mock.close = AsyncMock()
        yield mock
