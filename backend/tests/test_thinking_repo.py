from unittest.mock import AsyncMock, MagicMock
import pytest
from src.database.repositories.thinking_repo import ThinkingRepo


@pytest.fixture
def mock_collection():
    col = AsyncMock()
    return col


@pytest.fixture
def repo(mock_collection):
    return ThinkingRepo(mock_collection)


async def test_create_returns_session_id(repo, mock_collection):
    session = {"id": "abc123", "date": "2026-03-20", "status": "idle"}
    mock_collection.insert_one.return_value = MagicMock(inserted_id="mongo_id")
    result = await repo.create(session)
    assert result == "abc123"
    mock_collection.insert_one.assert_awaited_once_with(session)


async def test_get_returns_document(repo, mock_collection):
    doc = {"id": "abc123", "date": "2026-03-20"}
    mock_collection.find_one.return_value = doc
    result = await repo.get("abc123")
    assert result == doc
    mock_collection.find_one.assert_awaited_once_with({"id": "abc123"}, {"_id": 0})


async def test_get_returns_none_when_not_found(repo, mock_collection):
    mock_collection.find_one.return_value = None
    result = await repo.get("nonexistent")
    assert result is None


async def test_update_returns_true_on_match(repo, mock_collection):
    mock_collection.update_one.return_value = MagicMock(matched_count=1)
    result = await repo.update("abc123", {"status": "thinking"})
    assert result is True
    mock_collection.update_one.assert_awaited_once_with(
        {"id": "abc123"}, {"$set": {"status": "thinking"}}
    )


async def test_update_returns_false_when_not_found(repo, mock_collection):
    mock_collection.update_one.return_value = MagicMock(matched_count=0)
    result = await repo.update("missing", {"status": "error"})
    assert result is False


async def test_add_nodes_pushes_and_returns_count(repo, mock_collection):
    nodes = [
        {"id": "n1", "type": "news", "content": "a"},
        {"id": "n2", "type": "effect", "content": "b"},
    ]
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    result = await repo.add_nodes("abc123", nodes)
    assert result == 2
    mock_collection.update_one.assert_awaited_once_with(
        {"id": "abc123"}, {"$push": {"nodes": {"$each": nodes}}}
    )


async def test_add_edges_pushes_and_returns_count(repo, mock_collection):
    edges = [{"source": "n1", "target": "n2", "relationship": "causes"}]
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    result = await repo.add_edges("abc123", edges)
    assert result == 1
    mock_collection.update_one.assert_awaited_once_with(
        {"id": "abc123"}, {"$push": {"edges": {"$each": edges}}}
    )


async def test_update_node_selection_returns_true(repo, mock_collection):
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    result = await repo.update_node_selection("abc123", "n1", False)
    assert result is True
    mock_collection.update_one.assert_awaited_once_with(
        {"id": "abc123", "nodes.id": "n1"},
        {"$set": {"nodes.$.selected": False}},
    )


async def test_update_node_selection_returns_false_when_not_found(
    repo, mock_collection
):
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    result = await repo.update_node_selection("abc123", "missing", True)
    assert result is False
