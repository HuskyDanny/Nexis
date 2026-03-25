"""Tests for reasoning truncation in Thinker context preparation.

Ensures that parent nodes from older layers get truncated reasoning
to prevent context window overflow at deeper layers, while nodes
from the immediately preceding layer keep full reasoning.
"""

import json


from src.agents.thinking_helpers import prepare_parent_nodes as _prepare_parent_nodes

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LONG_REASONING = "A" * 500  # Well over any truncation limit
SHORT_REASONING = "Short chain"


def _node(node_id: str, layer: int, reasoning: str = "") -> dict:
    return {
        "id": node_id,
        "layer": layer,
        "type": "effect",
        "content": f"Effect at layer {layer}",
        "reasoning": reasoning,
        "confidence": 80,
        "metadata": {"sector": "macro"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPrepareParentNodes:
    """Unit tests for _prepare_parent_nodes context truncation."""

    def test_layer1_no_truncation(self):
        """At layer 1, parent nodes (layer 0) are the immediate prior — no truncation."""
        nodes = [_node("seed-1", 0, LONG_REASONING)]
        result = _prepare_parent_nodes(nodes, current_layer=1)
        assert result[0]["reasoning"] == LONG_REASONING

    def test_layer2_keeps_layer1_full(self):
        """At layer 2, layer-1 nodes are immediate prior — keep full reasoning."""
        nodes = [_node("eff-1", 1, LONG_REASONING)]
        result = _prepare_parent_nodes(nodes, current_layer=2)
        assert result[0]["reasoning"] == LONG_REASONING

    def test_layer2_truncates_layer0(self):
        """At layer 2, layer-0 nodes are >1 layer back — truncate reasoning."""
        nodes = [_node("seed-1", 0, LONG_REASONING)]
        result = _prepare_parent_nodes(nodes, current_layer=2)
        assert len(result[0]["reasoning"]) < len(LONG_REASONING)
        # Should end with ellipsis to indicate truncation
        assert result[0]["reasoning"].endswith("…")

    def test_layer3_truncates_layer0_and_layer1(self):
        """At layer 3, only layer-2 nodes keep full reasoning."""
        nodes = [
            _node("seed-1", 0, LONG_REASONING),
            _node("eff-1", 1, LONG_REASONING),
            _node("eff-2", 2, LONG_REASONING),
        ]
        result = _prepare_parent_nodes(nodes, current_layer=3)
        # Layer 0 and 1: truncated
        assert len(result[0]["reasoning"]) < len(LONG_REASONING)
        assert len(result[1]["reasoning"]) < len(LONG_REASONING)
        # Layer 2: full (immediate prior)
        assert result[2]["reasoning"] == LONG_REASONING

    def test_short_reasoning_not_truncated(self):
        """Reasoning shorter than the limit is never truncated, even for old layers."""
        nodes = [_node("seed-1", 0, SHORT_REASONING)]
        result = _prepare_parent_nodes(nodes, current_layer=3)
        assert result[0]["reasoning"] == SHORT_REASONING

    def test_preserves_all_fields(self):
        """Truncation only affects reasoning — all other fields stay intact."""
        nodes = [_node("seed-1", 0, LONG_REASONING)]
        result = _prepare_parent_nodes(nodes, current_layer=2)
        assert result[0]["id"] == "seed-1"
        assert result[0]["content"] == "Effect at layer 0"
        assert result[0]["confidence"] == 80
        assert result[0]["metadata"] == {"sector": "macro"}

    def test_nodes_without_layer_field_not_truncated(self):
        """Nodes missing 'layer' key default to no truncation (safe fallback)."""
        node = {
            "id": "x",
            "content": "test",
            "reasoning": LONG_REASONING,
            "confidence": 50,
            "metadata": {},
        }
        result = _prepare_parent_nodes([node], current_layer=3)
        assert result[0]["reasoning"] == LONG_REASONING

    def test_result_is_json_serializable(self):
        """Output must be JSON-serializable for the LLM prompt."""
        nodes = [_node("seed-1", 0, LONG_REASONING), _node("eff-1", 1, LONG_REASONING)]
        result = _prepare_parent_nodes(nodes, current_layer=2)
        serialized = json.dumps(result, ensure_ascii=False)
        assert isinstance(serialized, str)
