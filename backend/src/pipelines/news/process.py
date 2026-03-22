import hashlib
from datetime import datetime, timezone
from src.models.pool_common import ProcessResult


class HybridSimilarityProcess:
    def __init__(self, title_threshold: float = 0.6, entity_threshold: float = 0.5):
        self.title_threshold = title_threshold
        self.entity_threshold = entity_threshold

    async def process(self, raw: dict, existing: list[dict]) -> ProcessResult:
        raw_tokens = self._tokenize(raw.get("title", ""))
        raw_tickers = set(raw.get("tickers", []))
        raw_ents = set(raw.get("named_entities", []))
        best_id, best_score = None, 0.0

        for e in existing:
            title_sim = self._jaccard(
                raw_tokens, self._tokenize(e.get("canonical_title", ""))
            )
            ticker_sim = self._jaccard(raw_tickers, set(e.get("tickers", [])))
            ent_sim = self._jaccard(raw_ents, set(e.get("named_entities", [])))
            combined = 0.4 * title_sim + 0.3 * ticker_sim + 0.3 * ent_sim
            if combined > best_score:
                best_score, best_id = combined, e.get("id")

        if best_id and (
            best_score >= self.title_threshold or best_score >= self.entity_threshold
        ):
            return ProcessResult(
                action="merge", entity_id=best_id, merged_from=self._gen_id(raw)
            )
        return ProcessResult(action="insert", entity_id=self._gen_id(raw))

    def _tokenize(self, text: str) -> set[str]:
        return set(text.lower().split())

    def _jaccard(self, a: set, b: set) -> float:
        if not a and not b:
            return 0.0
        union = a | b
        return len(a & b) / len(union) if union else 0.0

    def _gen_id(self, raw: dict) -> str:
        title = raw.get("title", "")
        market = raw.get("market", "US")
        date = raw.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        return hashlib.sha256(f"{market}:{title}:{date}".encode()).hexdigest()[:16]
