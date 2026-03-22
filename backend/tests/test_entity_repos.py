from unittest.mock import AsyncMock, MagicMock
import pytest
from src.database.repositories.news_entity_repo import NewsEntityRepo
from src.database.repositories.value_entity_repo import ValueEntityRepo


# --- Fixtures ---


@pytest.fixture
def news_collection():
    col = MagicMock()
    col.replace_one = AsyncMock()
    col.find_one = AsyncMock()
    return col


@pytest.fixture
def value_collection():
    col = MagicMock()
    col.replace_one = AsyncMock()
    col.find_one = AsyncMock()
    return col


@pytest.fixture
def news_repo(news_collection):
    return NewsEntityRepo(news_collection)


@pytest.fixture
def value_repo(value_collection):
    return ValueEntityRepo(value_collection)


# --- NewsEntityRepo ---


async def test_news_upsert(news_repo, news_collection):
    entity = {"id": "n1", "canonical_title": "Test", "status": "active", "market": "US"}
    await news_repo.upsert(entity)
    news_collection.replace_one.assert_awaited_once_with(
        {"id": "n1"}, entity, upsert=True
    )


async def test_news_get_by_id(news_repo, news_collection):
    doc = {"id": "n1", "canonical_title": "Test"}
    news_collection.find_one.return_value = doc
    result = await news_repo.get_by_id("n1")
    assert result == doc
    news_collection.find_one.assert_awaited_once_with({"id": "n1"}, {"_id": 0})


async def test_news_get_by_id_not_found(news_repo, news_collection):
    news_collection.find_one.return_value = None
    result = await news_repo.get_by_id("missing")
    assert result is None


async def test_news_get_active(news_repo, news_collection):
    docs = [{"id": "n1", "status": "active", "market": "US"}]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    news_collection.find.return_value = mock_cursor

    result = await news_repo.get_active("US")
    assert result == docs
    news_collection.find.assert_called_once_with(
        {"status": "active", "market": "US"}, {"_id": 0}
    )


async def test_news_get_all_active_only(news_repo, news_collection):
    docs = [{"id": "n1", "status": "active", "market": "US"}]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    news_collection.find.return_value = mock_cursor

    result = await news_repo.get_all("US", include_stale=False)
    assert result == docs
    news_collection.find.assert_called_once_with(
        {"status": "active", "market": "US"}, {"_id": 0}
    )


async def test_news_get_all_with_stale(news_repo, news_collection):
    docs = [
        {"id": "n1", "status": "active", "market": "US"},
        {"id": "n2", "status": "stale", "market": "US"},
    ]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    news_collection.find.return_value = mock_cursor

    result = await news_repo.get_all("US", include_stale=True)
    assert result == docs
    news_collection.find.assert_called_once_with(
        {"status": {"$in": ["active", "stale"]}, "market": "US"}, {"_id": 0}
    )


# --- ValueEntityRepo ---


async def test_value_upsert(value_repo, value_collection):
    entity = {"id": "v1", "ticker": "AAPL", "status": "active", "market": "US"}
    await value_repo.upsert(entity)
    value_collection.replace_one.assert_awaited_once_with(
        {"id": "v1"}, entity, upsert=True
    )


async def test_value_get_by_id(value_repo, value_collection):
    doc = {"id": "v1", "ticker": "AAPL"}
    value_collection.find_one.return_value = doc
    result = await value_repo.get_by_id("v1")
    assert result == doc
    value_collection.find_one.assert_awaited_once_with({"id": "v1"}, {"_id": 0})


async def test_value_get_by_id_not_found(value_repo, value_collection):
    value_collection.find_one.return_value = None
    result = await value_repo.get_by_id("missing")
    assert result is None


async def test_value_get_active(value_repo, value_collection):
    docs = [{"id": "v1", "ticker": "AAPL", "status": "active", "market": "US"}]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    value_collection.find.return_value = mock_cursor

    result = await value_repo.get_active("US")
    assert result == docs
    value_collection.find.assert_called_once_with(
        {"status": "active", "market": "US"}, {"_id": 0}
    )
