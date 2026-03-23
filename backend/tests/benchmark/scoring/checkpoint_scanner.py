"""Pass 1 checkpoint scanner — keyword fast-path + LLM fallback."""

from __future__ import annotations

import re
from typing import Optional

from tests.benchmark.models import (
    BenchmarkTrace,
    CheckpointResult,
    MatchResult,
    Pass1Report,
    SkillResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "and",
        "but",
        "or",
        "not",
        "no",
        "due",
        "that",
        "this",
        "it",
    }
)

# Each pair is bidirectional: either word is the antonym of the other.
_ANTONYM_PAIRS: list[tuple[str, str]] = [
    ("increase", "decrease"),
    ("rise", "fall"),
    ("up", "down"),
    ("long", "short"),
    ("strengthen", "weaken"),
    ("grow", "shrink"),
    ("expand", "contract"),
    ("gain", "lose"),
    ("higher", "lower"),
    ("positive", "negative"),
    ("bull", "bear"),
    ("rally", "decline"),
]

# Build bidirectional lookup: word → its antonym
_ANTONYMS: dict[str, str] = {}
for _a, _b in _ANTONYM_PAIRS:
    _ANTONYMS[_a] = _b
    _ANTONYMS[_b] = _a

# All direction-related words (both sides of every pair)
_DIRECTION_WORDS: frozenset[str] = frozenset(_ANTONYMS.keys())


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def extract_key_terms(concept: str) -> list[str]:
    """Lowercase, normalise punctuation, split, strip stopwords and single-char words."""
    text = concept.lower()
    # Replace slash and em-dash with space so alternatives become separate tokens
    text = text.replace("/", " ").replace("—", " ")
    tokens = text.split()
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def check_direction(concept: str, node_text: str) -> bool | None:
    """Check whether direction terms in concept and node_text agree.

    Returns:
        True   — concept has a direction term AND node has the same (or compatible) direction.
        False  — node explicitly uses the antonym of the concept's direction term.
        None   — no direction terms found in concept (can't determine directionality).
    """
    concept_terms = set(extract_key_terms(concept))
    node_terms = set(extract_key_terms(node_text))

    # Find direction words present in the concept
    concept_dirs = concept_terms & _DIRECTION_WORDS
    if not concept_dirs:
        return None

    for cdir in concept_dirs:
        antonym = _ANTONYMS.get(cdir)
        if antonym and antonym in node_terms:
            # Explicit contradiction found
            return False

    # No contradiction found — direction is consistent (or absent in node, which is fine)
    return True


# ---------------------------------------------------------------------------
# Checkpoint evaluation
# ---------------------------------------------------------------------------


def check_checkpoint_keyword(
    checkpoint: dict,
    layer: int,
    layer_nodes: list[dict],
    threshold: float = 0.7,
) -> CheckpointResult:
    """Keyword fast-path: evaluate a single checkpoint against layer nodes.

    For each node, concatenates ``content`` + ``reasoning`` and computes
    term-overlap ratio against the checkpoint concept.  If overlap >= threshold
    AND direction is not explicitly wrong, the checkpoint is a hit.
    """
    concept: str = checkpoint.get("text", checkpoint.get("concept", ""))
    required: bool = checkpoint.get("required", True)
    concept_terms = set(extract_key_terms(concept))

    if not concept_terms:
        # Nothing to match against — immediate miss
        return CheckpointResult(
            layer=layer,
            concept=concept,
            required=required,
            hit=False,
            method="keyword",
            matched_node_id=None,
            direction_correct=None,
            evidence="No key terms extracted from concept.",
        )

    for node in layer_nodes:
        node_text = f"{node.get('content', '')} {node.get('reasoning', '')}"
        node_terms = set(extract_key_terms(node_text))

        if not node_terms:
            continue

        overlap = len(concept_terms & node_terms) / len(concept_terms)

        if overlap < threshold:
            continue

        # Check direction
        direction_result = check_direction(concept, node_text)
        if direction_result is False:
            # Explicit antonym found — fall through to next node
            continue

        # Hit
        return CheckpointResult(
            layer=layer,
            concept=concept,
            required=required,
            hit=True,
            method="keyword",
            matched_node_id=node.get("id"),
            direction_correct=direction_result,  # True or None
            evidence=(
                f"Term overlap {overlap:.0%} >= {threshold:.0%} "
                f"with node '{node.get('id')}'."
            ),
        )

    # No node matched
    return CheckpointResult(
        layer=layer,
        concept=concept,
        required=required,
        hit=False,
        method="keyword",
        matched_node_id=None,
        direction_correct=None,
        evidence=f"No node reached {threshold:.0%} term overlap threshold.",
    )


async def check_checkpoint_llm(
    checkpoint: dict,
    layer: int,
    layer_nodes: list[dict],
    judge_model=None,
) -> CheckpointResult:
    """LLM fallback: ask the judge model whether the concept is present in the layer.

    If ``judge_model`` is None the function returns a miss with a diagnostic note.
    """
    concept: str = checkpoint.get("text", checkpoint.get("concept", ""))
    required: bool = checkpoint.get("required", True)

    if judge_model is None:
        return CheckpointResult(
            layer=layer,
            concept=concept,
            required=required,
            hit=False,
            method="llm",
            matched_node_id=None,
            direction_correct=None,
            evidence="LLM fallback skipped: no judge_model provided.",
        )

    # Build a compact representation of the layer text
    layer_text_parts = []
    for node in layer_nodes:
        node_id = node.get("id", "?")
        content = node.get("content", "")
        reasoning = node.get("reasoning", "")
        layer_text_parts.append(f"[{node_id}] {content} {reasoning}".strip())
    layer_text = "\n".join(layer_text_parts)

    prompt = (
        f"You are a financial reasoning evaluator.\n\n"
        f"Concept to verify:\n{concept}\n\n"
        f"Layer {layer} nodes:\n{layer_text}\n\n"
        f"Does the layer capture the concept above? "
        f"Reply with JSON: "
        f'{{"hit": true|false, "node_id": "<id or null>", '
        f'"direction_correct": true|false|null, "evidence": "<brief>"}}'
    )

    try:
        response = await judge_model.agenerate(prompt)
        import json

        data = json.loads(response)
        return CheckpointResult(
            layer=layer,
            concept=concept,
            required=required,
            hit=bool(data.get("hit", False)),
            method="llm",
            matched_node_id=data.get("node_id"),
            direction_correct=data.get("direction_correct"),
            evidence=data.get("evidence", ""),
        )
    except Exception as exc:
        return CheckpointResult(
            layer=layer,
            concept=concept,
            required=required,
            hit=False,
            method="llm",
            matched_node_id=None,
            direction_correct=None,
            evidence=f"LLM fallback error: {exc}",
        )


# ---------------------------------------------------------------------------
# Match scanning
# ---------------------------------------------------------------------------


def scan_matches(
    expected_matches: list[dict],
    opportunity_nodes: list[dict],
) -> list[MatchResult]:
    """Match expected trades against opportunity nodes by ticker + layer.

    Direction is inferred from ``metadata.sentiment_score``:
      >= 50 → "long", < 50 → "short"
    """
    # Index opportunity nodes by (ticker, layer)
    opp_index: dict[tuple[str, int], dict] = {}
    for node in opportunity_nodes:
        meta = node.get("metadata", {})
        ticker = meta.get("ticker")
        node_layer = meta.get("layer")
        if ticker and node_layer is not None:
            opp_index[(ticker, node_layer)] = node

    results: list[MatchResult] = []
    for em in expected_matches:
        ticker = em["ticker"]
        expected_direction = em["direction"]
        expected_layer = em.get("layer")

        key = (ticker, expected_layer)
        node = opp_index.get(key)

        if node is None:
            results.append(
                MatchResult(
                    ticker=ticker,
                    expected_direction=expected_direction,
                    found=False,
                    actual_direction=None,
                    correct=False,
                )
            )
            continue

        score = node.get("metadata", {}).get("sentiment_score", 50)
        actual_direction = "long" if score >= 50 else "short"
        correct = actual_direction == expected_direction

        results.append(
            MatchResult(
                ticker=ticker,
                expected_direction=expected_direction,
                found=True,
                actual_direction=actual_direction,
                correct=correct,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Skill scanning
# ---------------------------------------------------------------------------


def scan_skills(
    expected: dict[int, list[str]],
    actual: dict[int, list[str]],
) -> list[SkillResult]:
    """Verify that every expected skill for each layer is present in actual."""
    results: list[SkillResult] = []
    for layer, expected_skills in expected.items():
        actual_skills = actual.get(layer, [])
        all_loaded = set(expected_skills).issubset(set(actual_skills))
        results.append(
            SkillResult(
                layer=layer,
                expected_skills=expected_skills,
                actual_skills=actual_skills,
                all_loaded=all_loaded,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Pass 1 orchestrator
# ---------------------------------------------------------------------------


def _parse_layer_key(key: str) -> int:
    """Convert 'L1', 'L2', … or integer keys to int."""
    if isinstance(key, int):
        return key
    return int(re.sub(r"[^0-9]", "", str(key)))


async def run_pass1(
    scenario: dict,
    trace: BenchmarkTrace,
    judge_model=None,
) -> Pass1Report:
    """Orchestrate Pass 1 evaluation.

    1. Walk trace layers, run checkpoints (keyword → LLM fallback on miss).
    2. Scan opportunity matches.
    3. Scan skill compliance.
    4. Compute hit rates and return Pass1Report.
    """
    # Build a quick lookup: layer_number → LayerTrace
    layer_map = {lt.layer: lt for lt in trace.layers}

    # ---- Checkpoints ----
    checkpoint_results: list[CheckpointResult] = []
    for cp in scenario.get("checkpoints", []):
        layer_num: int = cp["layer"]
        layer_trace = layer_map.get(layer_num)
        layer_nodes = layer_trace.nodes_produced if layer_trace else []

        kw_result = check_checkpoint_keyword(cp, layer_num, layer_nodes)
        if kw_result.hit:
            checkpoint_results.append(kw_result)
        else:
            # LLM fallback
            llm_result = await check_checkpoint_llm(
                cp, layer_num, layer_nodes, judge_model
            )
            checkpoint_results.append(llm_result)

    required_cps = [r for r in checkpoint_results if r.required]
    all_cps = checkpoint_results

    checkpoint_hit_rate = (
        sum(1 for r in required_cps if r.hit) / len(required_cps)
        if required_cps
        else 0.0
    )
    checkpoint_hit_rate_all = (
        sum(1 for r in all_cps if r.hit) / len(all_cps) if all_cps else 0.0
    )

    # ---- Matches ----
    # Collect all opportunity nodes across all layers
    opportunity_nodes: list[dict] = []
    for lt in trace.layers:
        for node in lt.nodes_produced:
            if node.get("type") == "opportunity" or node.get("metadata", {}).get(
                "ticker"
            ):
                opportunity_nodes.append(node)

    match_results = scan_matches(
        scenario.get("expected_matches", []), opportunity_nodes
    )
    match_accuracy = (
        sum(1 for r in match_results if r.correct) / len(match_results)
        if match_results
        else 0.0
    )

    # ---- Skills ----
    # Build actual skills per layer from agent traces
    actual_skills_by_layer: dict[int, list[str]] = {}
    for lt in trace.layers:
        skills: list[str] = []
        for agent in lt.agents:
            skills.extend(agent.skills_loaded)
        actual_skills_by_layer[lt.layer] = skills

    # Convert expected_skills keys ("L1", "L2", …) to ints
    raw_expected_skills: dict = scenario.get("expected_skills", {})
    expected_skills_by_layer: dict[int, list[str]] = {
        _parse_layer_key(k): v for k, v in raw_expected_skills.items()
    }

    skill_results = scan_skills(expected_skills_by_layer, actual_skills_by_layer)
    skill_compliance = (
        sum(1 for r in skill_results if r.all_loaded) / len(skill_results)
        if skill_results
        else 0.0
    )

    return Pass1Report(
        checkpoints=checkpoint_results,
        checkpoint_hit_rate=checkpoint_hit_rate,
        checkpoint_hit_rate_all=checkpoint_hit_rate_all,
        matches=match_results,
        match_accuracy=match_accuracy,
        skills=skill_results,
        skill_compliance=skill_compliance,
        total_tokens=trace.total_tokens,
        total_latency_ms=trace.total_latency_ms,
        tokens_per_layer=(
            trace.total_tokens / trace.total_layers if trace.total_layers else 0.0
        ),
        latency_per_layer=(
            trace.total_latency_ms / trace.total_layers if trace.total_layers else 0.0
        ),
    )
