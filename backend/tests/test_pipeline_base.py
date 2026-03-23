from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.pipelines.base import PoolPipeline, ThresholdRetain
from src.models.pool_common import ProcessResult, ScoreResult


@pytest.fixture
def mock_fetch():
    s = AsyncMock()
    s.fetch.return_value = [{"title": "New headline", "source": "https://ex.com"}]
    return s


@pytest.fixture
def mock_process():
    s = AsyncMock()
    s.process.return_value = ProcessResult(action="insert", entity_id="hash_new")
    return s


@pytest.fixture
def mock_score():
    s = MagicMock()
    s.score.return_value = ScoreResult(score=0.8, factors={"freshness": 0.9})
    return s


@pytest.fixture
def mock_retain():
    s = MagicMock()
    s.should_retain.return_value = True
    return s


@pytest.fixture
def mock_repo():
    r = AsyncMock()
    r.get_all.return_value = []
    return r


@pytest.fixture
def pipeline(mock_fetch, mock_process, mock_score, mock_retain, mock_repo):
    return PoolPipeline(
        fetch=mock_fetch,
        process=mock_process,
        score=mock_score,
        retain=mock_retain,
        repo=mock_repo,
        market="US",
    )


async def test_inserts_new_entity(pipeline, mock_repo):
    result = await pipeline.run()
    assert result.inserted == 1 and result.merged == 0
    assert mock_repo.upsert.await_count >= 1


async def test_merges_existing(pipeline, mock_repo, mock_process):
    mock_process.process.return_value = ProcessResult(
        action="merge", entity_id="h_old", merged_from="h_raw"
    )
    result = await pipeline.run()
    assert result.merged == 1 and result.inserted == 0


async def test_rescores_existing(
    mock_fetch, mock_process, mock_score, mock_retain, mock_repo
):
    now = datetime.now(timezone.utc).isoformat()
    mock_repo.get_all.return_value = [
        {
            "id": "e1",
            "status": "active",
            "score": 0.9,
            "score_factors": {},
            "last_seen_at": now,
        },
        {
            "id": "e2",
            "status": "active",
            "score": 0.5,
            "score_factors": {},
            "last_seen_at": (
                datetime.now(timezone.utc) - timedelta(days=5)
            ).isoformat(),
        },
    ]
    mock_fetch.fetch.return_value = []
    mock_score.score.return_value = ScoreResult(score=0.4, factors={"freshness": 0.4})
    mock_retain.should_retain.side_effect = [True, False]
    p = PoolPipeline(
        fetch=mock_fetch,
        process=mock_process,
        score=mock_score,
        retain=mock_retain,
        repo=mock_repo,
        market="US",
    )
    result = await p.run()
    assert result.rescored == 2 and result.removed == 1


async def test_stales_below_threshold(
    mock_fetch, mock_process, mock_score, mock_retain, mock_repo
):
    mock_repo.get_all.return_value = [
        {
            "id": "s1",
            "status": "active",
            "score": 0.1,
            "score_factors": {},
            "last_seen_at": (
                datetime.now(timezone.utc) - timedelta(days=30)
            ).isoformat(),
        }
    ]
    mock_fetch.fetch.return_value = []
    mock_score.score.return_value = ScoreResult(score=0.05, factors={"freshness": 0.05})
    mock_retain.should_retain.return_value = False
    p = PoolPipeline(
        fetch=mock_fetch,
        process=mock_process,
        score=mock_score,
        retain=mock_retain,
        repo=mock_repo,
        market="US",
    )
    result = await p.run()
    assert result.removed == 1
    stale = [
        c for c in mock_repo.upsert.call_args_list if c[0][0].get("status") == "stale"
    ]
    assert len(stale) == 1


# --- ThresholdRetain ---
def test_keeps_above_min():
    r = ThresholdRetain(min_score=0.3)
    assert r.should_retain(
        {"score": 0.5, "last_seen_at": datetime.now(timezone.utc).isoformat()}
    )


def test_removes_below_min():
    r = ThresholdRetain(min_score=0.3)
    assert not r.should_retain(
        {"score": 0.1, "last_seen_at": datetime.now(timezone.utc).isoformat()}
    )


def test_removes_old():
    r = ThresholdRetain(min_score=0.1, max_age_days=7)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert not r.should_retain({"score": 0.5, "last_seen_at": old})


def test_keeps_recent():
    r = ThresholdRetain(min_score=0.1, max_age_days=7)
    assert r.should_retain(
        {"score": 0.5, "last_seen_at": datetime.now(timezone.utc).isoformat()}
    )


def test_no_max_age_keeps_old():
    r = ThresholdRetain(min_score=0.1)
    old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    assert r.should_retain({"score": 0.5, "last_seen_at": old})


def test_missing_last_seen_not_retainable():
    r = ThresholdRetain(min_score=0.1, max_age_days=7)
    assert not r.should_retain({"score": 0.5})
    assert not r.should_retain({"score": 0.5, "last_seen_at": ""})
    assert not r.should_retain({"score": 0.5, "last_seen_at": None})
