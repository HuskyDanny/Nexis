### E2E Verification Checklist

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)

Each verification runs against a live dev stack (`docker compose up`). Commands use `httpie` or `curl`. MongoDB assertions use `mongosh`.

---

- [ ] **V1: Session cache round-trip**

Start a session, verify Redis is populated, verify GET reads from cache.

```bash
# Start session
http POST http://localhost:8000/api/thinking date=2026-03-22 market=US

# Capture session_id from response
SESSION_ID=<from response>

# Check Redis keys exist
docker compose exec redis redis-cli KEYS "session:${SESSION_ID}:*"
```

Expected output:
```
1) "session:<id>:meta"
2) "session:<id>:nodes"
3) "session:<id>:edges"
```

```bash
# GET session — should read from Redis (check backend logs for "cache hit")
http GET http://localhost:8000/api/thinking/${SESSION_ID}
```

Expected: 200 response with session data. Backend log shows `cache hit` not `MongoDB load`.

---

- [ ] **V2: CAS prevents duplicate step**

Two concurrent POST /step — one succeeds (200), one gets 409.

```bash
# Start a session first
SESSION_ID=$(http POST http://localhost:8000/api/thinking date=2026-03-22 market=US | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Fire two concurrent steps
curl -s -o /tmp/step1.json -w "%{http_code}" -X POST http://localhost:8000/api/thinking/${SESSION_ID}/step &
curl -s -o /tmp/step2.json -w "%{http_code}" -X POST http://localhost:8000/api/thinking/${SESSION_ID}/step &
wait
```

Expected: one returns `200`, the other returns `409`. Check:
```bash
cat /tmp/step1.json
cat /tmp/step2.json
```

Exactly one response has `"status": "paused"`, the other has `"detail"` containing `"Cannot step"`.

---

- [ ] **V3: Cold to hot reload**

Expire Redis keys, then GET session — should lazy-load from MongoDB back to Redis.

```bash
# After V1, expire all session keys
docker compose exec redis redis-cli KEYS "session:${SESSION_ID}:*" | while read key; do
  docker compose exec redis redis-cli DEL "$key"
done

# Verify keys gone
docker compose exec redis redis-cli KEYS "session:${SESSION_ID}:*"
# Expected: (empty array)

# GET session — triggers lazy-load
http GET http://localhost:8000/api/thinking/${SESSION_ID}
# Expected: 200 with full session data

# Verify Redis re-populated
docker compose exec redis redis-cli KEYS "session:${SESSION_ID}:*"
```

Expected: keys exist again after GET. Backend log shows `cache miss, loading from MongoDB`.

---

- [ ] **V4: Pipeline insert and merge**

Seed test data, run news pipeline, verify insert + merge behavior.

```bash
# Seed 2 existing news entities
docker compose exec mongodb mongosh --eval '
  db = db.getSiblingDB("financial_agent_v2");
  db.news_entities.insertMany([
    {
      id: "entity-aaa",
      canonical_title: "Fed raises interest rates",
      sources: [{url: "https://a.com", publisher: "A", fetched_at: "2026-03-22T00:00:00Z"}],
      score: 70,
      score_factors: {freshness: 0.8, quality: 0.7, impact: 0.6},
      status: "active",
      market: "US",
      first_seen_at: "2026-03-22T00:00:00Z",
      last_seen_at: "2026-03-22T00:00:00Z"
    },
    {
      id: "entity-bbb",
      canonical_title: "Oil prices surge",
      sources: [{url: "https://b.com", publisher: "B", fetched_at: "2026-03-22T00:00:00Z"}],
      score: 60,
      score_factors: {freshness: 0.7, quality: 0.6, impact: 0.5},
      status: "active",
      market: "US",
      first_seen_at: "2026-03-22T00:00:00Z",
      last_seen_at: "2026-03-22T00:00:00Z"
    }
  ]);
  print("Seeded 2 entities");
'

# Run news pipeline (via test script or management endpoint)
docker compose exec backend python -c "
import asyncio
from src.cron.scheduler import run_news_pipeline
asyncio.run(run_news_pipeline())
"

# Verify: check entity counts and source arrays
docker compose exec mongodb mongosh --eval '
  db = db.getSiblingDB("financial_agent_v2");
  const count = db.news_entities.countDocuments({market: "US"});
  print("Entity count: " + count);
  db.news_entities.find({market: "US"}).forEach(e => {
    print(e.id + " sources=" + e.sources.length + " score=" + e.score);
  });
'
```

Expected: duplicate entity has `sources.length >= 2` (merged). New entities inserted. All scores computed.

---

- [ ] **V5: Decay re-scoring**

Old entity score decreases after pipeline re-run due to freshness decay.

```bash
# Record current score
docker compose exec mongodb mongosh --eval '
  db = db.getSiblingDB("financial_agent_v2");
  const e = db.news_entities.findOne({id: "entity-aaa"});
  print("Before: score=" + e.score + " freshness=" + e.score_factors.freshness);
'

# Wait or manually set first_seen_at to 48 hours ago
docker compose exec mongodb mongosh --eval '
  db = db.getSiblingDB("financial_agent_v2");
  const old = new Date(Date.now() - 48*60*60*1000).toISOString();
  db.news_entities.updateOne({id: "entity-aaa"}, {$set: {first_seen_at: old, last_seen_at: old}});
  print("Set entity-aaa to 48h old");
'

# Run pipeline again (rescore pass will update scores)
docker compose exec backend python -c "
import asyncio
from src.cron.scheduler import run_news_pipeline
asyncio.run(run_news_pipeline())
"

# Check score decreased
docker compose exec mongodb mongosh --eval '
  db = db.getSiblingDB("financial_agent_v2");
  const e = db.news_entities.findOne({id: "entity-aaa"});
  print("After: score=" + e.score + " freshness=" + e.score_factors.freshness);
'
```

Expected: score decreased. Freshness factor is lower than before.

---

- [ ] **V6: Stale filtering**

Score below threshold = stale. Excluded from default GET, included with `?include_stale=true`.

```bash
# Set entity-bbb score below threshold manually
docker compose exec mongodb mongosh --eval '
  db = db.getSiblingDB("financial_agent_v2");
  db.news_entities.updateOne({id: "entity-bbb"}, {$set: {score: 5, status: "stale"}});
  print("Set entity-bbb to stale");
'

# Default GET — stale excluded
http GET http://localhost:8000/api/pools/2026-03-22?market=US
```

Expected: response `news_entities` does NOT contain `entity-bbb`.

```bash
# With include_stale=true — stale included
http GET "http://localhost:8000/api/pools/2026-03-22?market=US&include_stale=true"
```

Expected: response `news_entities` contains `entity-bbb` with `status: "stale"`.

---

- [ ] **V7: Strategy swap**

Replace fetch strategy with a mock, run pipeline — output shape unchanged.

```bash
# Create a test script that swaps the fetch strategy
docker compose exec backend python -c "
import asyncio
from src.pipelines.base import PoolPipeline, ThresholdRetain
from src.pipelines.news.process import HybridSimilarityProcess
from src.pipelines.news.score import NewsDecayScore
from src.database.mongodb import mongodb
from src.core.config import settings


class MockNewsFetch:
    async def fetch(self, market):
        return [
            {'title': 'Mock Breaking News', 'url': 'https://mock.com/1',
             'publisher': 'MockPress', 'published_at': '2026-03-22T12:00:00Z'},
        ]


async def main():
    await mongodb.connect(settings.mongodb_url)
    pipeline = PoolPipeline(
        fetch=MockNewsFetch(),
        process=HybridSimilarityProcess(lexical_weight=0.4, threshold=0.75),
        score=NewsDecayScore(base_half_life_hours=24),
        retain=ThresholdRetain(min_score=30),
    )
    col = mongodb.get_collection('news_entities')
    result = await pipeline.run('US', col)
    print(f'inserted={result.inserted} merged={result.merged} rescored={result.rescored}')
    assert result.inserted >= 0
    assert result.merged >= 0
    print('Strategy swap: PASS')
    await mongodb.close()


asyncio.run(main())
"
```

Expected: prints counts and `Strategy swap: PASS`. No errors about missing methods.

---

- [ ] **V8: Error resilience — Redis down**

Stop Redis, verify API still works via MongoDB fallback.

```bash
# Stop Redis container
docker compose stop redis

# Start a session — should still work (Redis failure is non-fatal)
http POST http://localhost:8000/api/thinking date=2026-03-22 market=US
```

Expected: 200 response. Backend log shows `Redis connection failed (non-fatal)` or `Redis write failed, continuing`.

```bash
# GET pools — should work from MongoDB
http GET http://localhost:8000/api/pools/2026-03-22?market=US
```

Expected: 200 response with data from MongoDB.

```bash
# Restart Redis
docker compose start redis
```

Expected: subsequent requests use Redis cache again. No manual intervention needed.
