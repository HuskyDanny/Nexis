"""Value processing — ticker-based upsert."""

from src.models.pool_common import ProcessResult


class TickerUpsertProcess:
    """Upsert by ticker:market composite key.

    Merge: raw fields overwrite existing; unset fields are preserved.
    Insert: creates a new entity with id = ticker:market.
    """

    async def process(self, raw: dict, existing: list[dict]) -> ProcessResult:
        ticker = raw.get("ticker", "")
        market = raw.get("market", "US")
        entity_id = f"{ticker}:{market}"
        match = next((e for e in existing if e.get("id") == entity_id), None)

        if match:
            return ProcessResult(action="merge", entity_id=entity_id)

        return ProcessResult(action="insert", entity_id=entity_id)
