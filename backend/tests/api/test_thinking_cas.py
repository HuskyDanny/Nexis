import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_step_uses_find_one_and_update_cas():
    mock_col = AsyncMock()
    mock_col.find_one_and_update.return_value = {
        "id": "abc123",
        "status": "thinking",
        "version": 2,
        "current_layer": 0,
        "max_depth": 3,
        "nodes": [],
        "edges": [],
        "news_pool": [],
        "value_pool": [],
    }
    with patch("src.api.thinking.mongodb") as mock_db:
        mock_db.get_collection.return_value = mock_col
        from src.api.thinking import think_step

        await think_step("abc123")
        mock_col.find_one_and_update.assert_called_once()
        call_args = mock_col.find_one_and_update.call_args
        filter_arg = call_args[0][0] if call_args[0] else call_args[1].get("filter", {})
        assert "status" in filter_arg


@pytest.mark.asyncio
async def test_step_returns_409_on_cas_failure():
    mock_col = AsyncMock()
    mock_col.find_one_and_update.return_value = None
    mock_col.find_one.return_value = {"id": "abc123", "status": "thinking"}
    with patch("src.api.thinking.mongodb") as mock_db:
        mock_db.get_collection.return_value = mock_col
        from fastapi import HTTPException
        from src.api.thinking import think_step

        with pytest.raises(HTTPException) as exc_info:
            await think_step("abc123")
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_step_returns_404_when_session_missing():
    mock_col = AsyncMock()
    mock_col.find_one_and_update.return_value = None
    mock_col.find_one.return_value = None
    with patch("src.api.thinking.mongodb") as mock_db:
        mock_db.get_collection.return_value = mock_col
        from fastapi import HTTPException
        from src.api.thinking import think_step

        with pytest.raises(HTTPException) as exc_info:
            await think_step("missing123")
        assert exc_info.value.status_code == 404
