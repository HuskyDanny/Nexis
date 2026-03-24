### Task 4: Checkpoint Scanner (Pass 1)

**Files:**
- Create: `backend/tests/benchmark/scoring/__init__.py`
- Create: `backend/tests/benchmark/scoring/checkpoint_scanner.py`
- Test: `backend/tests/benchmark/test_checkpoint_scanner.py`

**Reference:** `backend/src/models/thinking.py` — ThinkingNode has `content` and `reasoning` fields

- [ ] **Step 1: Write failing tests for checkpoint scanner**

```python
# backend/tests/benchmark/test_checkpoint_scanner.py
import pytest
from tests.benchmark.scoring.checkpoint_scanner import (
    extract_key_terms, check_direction, check_checkpoint_keyword,
    scan_matches, scan_skills,
)
from tests.benchmark.models import CheckpointResult, MatchResult, SkillResult


class TestExtractKeyTerms:
    def test_extracts_meaningful_terms(self):
        terms = extract_key_terms("oil price increase due to supply disruption")
        assert "oil" in terms and "increase" in terms and "disruption" in terms
        assert "due" not in terms and "to" not in terms

    def test_handles_slash_alternatives(self):
        terms = extract_key_terms("military strike / attack on Iran")
        assert "military" in terms and "strike" in terms and "attack" in terms


class TestCheckDirection:
    def test_correct_direction(self):
        assert check_direction("oil price increase", "oil prices expected to increase") is True

    def test_wrong_direction(self):
        assert check_direction("oil price increase", "oil prices expected to decrease") is False

    def test_no_direction_words(self):
        assert check_direction("Iran oil exporter", "Iran exports oil") is None


class TestCheckCheckpointKeyword:
    def test_hits_when_terms_overlap(self):
        node = {"id": "n1", "content": "Oil prices increase sharply",
                "reasoning": "Iran supply disruption through Strait of Hormuz"}
        result = check_checkpoint_keyword(
            {"concept": "oil price increase due to supply disruption", "required": True},
            layer=2, layer_nodes=[node])
        assert result.hit is True and result.method == "keyword"

    def test_misses_when_no_overlap(self):
        node = {"id": "n1", "content": "Tech stocks rally", "reasoning": "AI demand"}
        result = check_checkpoint_keyword(
            {"concept": "oil price increase", "required": True}, layer=2, layer_nodes=[node])
        assert result.hit is False

    def test_falls_through_on_wrong_direction(self):
        node = {"id": "n1", "content": "Oil prices expected to decrease",
                "reasoning": "Supply surplus from new production"}
        result = check_checkpoint_keyword(
            {"concept": "oil price increase due to supply disruption", "required": True},
            layer=2, layer_nodes=[node])
        assert result.hit is False  # Wrong direction → falls through


class TestScanMatches:
    def test_finds_correct_match(self):
        opp = [{"id": "opp-1", "type": "opportunity", "layer": 2,
                "content": "USO", "metadata": {"ticker": "USO", "sentiment_score": 80}}]
        results = scan_matches([{"ticker": "USO", "direction": "long", "layer": 2, "required": True}], opp)
        assert results[0].found and results[0].correct and results[0].actual_direction == "long"

    def test_detects_wrong_direction(self):
        opp = [{"id": "opp-1", "type": "opportunity", "layer": 3,
                "content": "GLD", "metadata": {"ticker": "GLD", "sentiment_score": 80}}]
        results = scan_matches([{"ticker": "GLD", "direction": "short", "layer": 3, "required": True}], opp)
        assert results[0].found and not results[0].correct

    def test_missing_match(self):
        results = scan_matches([{"ticker": "USO", "direction": "long", "layer": 2, "required": True}], [])
        assert not results[0].found


class TestScanSkills:
    def test_subset_check_passes(self):
        results = scan_skills({1: ["geopolitical_risk"]}, {1: ["geopolitical_risk", "sector_rotation"]})
        assert results[0].all_loaded is True

    def test_missing_skill_fails(self):
        results = scan_skills({1: ["geopolitical_risk", "supply_chain"]}, {1: ["geopolitical_risk"]})
        assert results[0].all_loaded is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/benchmark/test_checkpoint_scanner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement checkpoint scanner**

Create `backend/tests/benchmark/scoring/__init__.py` (empty).

Create `backend/tests/benchmark/scoring/checkpoint_scanner.py` with:
- `_STOPWORDS`: frozenset of common English stopwords
- `_ANTONYMS`: bidirectional dict from antonym pairs (increase/decrease, rise/fall, up/down, long/short, strengthen/weaken, grow/shrink, expand/contract, gain/lose, higher/lower, bull/bear, rally/decline)
- `extract_key_terms(concept: str) -> list[str]`: lowercase, replace `/` and `—` with spaces, split, filter stopwords
- `check_direction(concept: str, node_text: str) -> bool | None`: check if direction terms in concept match/conflict with node_text using antonym dict
- `check_checkpoint_keyword(checkpoint, layer, layer_nodes, threshold=0.7) -> CheckpointResult`: keyword overlap matching. Falls through (returns miss) if direction is explicitly wrong.
- `check_checkpoint_llm(checkpoint, layer, layer_nodes, judge_model) -> CheckpointResult`: async LLM fallback. Feeds layer text + concept to judge, returns structured verdict.
- `scan_matches(expected, opportunity_nodes) -> list[MatchResult]`: match by ticker + layer, infer direction from `sentiment_score >= 50 → long`
- `scan_skills(expected, actual) -> list[SkillResult]`: subset check per layer
- `run_pass1(scenario, trace, judge_model=None) -> Pass1Report`: full Pass 1 orchestrator

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/benchmark/test_checkpoint_scanner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/scoring/ backend/tests/benchmark/test_checkpoint_scanner.py
git commit -m "feat(benchmark): add Pass 1 checkpoint scanner with keyword + LLM fallback"
```
