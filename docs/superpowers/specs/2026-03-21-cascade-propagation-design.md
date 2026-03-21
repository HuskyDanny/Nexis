# Cascade Propagation with Layer Cache

## Problem

The Thinking DAG uses BFS to cascade-deselect descendants when a node is toggled off. This is correct for AND-semantics (all parents required), but two gaps remain:

1. **Re-selection is manual** — user must re-select each descendant individually, even when the same parent combination was seen before.
2. **Adding a node from the pool** doesn't trigger recalculation of downstream layers that now have a different parent set.

## Core Semantics

**AND-semantics:** A node is valid only when ALL its parents are selected. If any parent is deselected, the node and all its descendants are invalid.

This matches how compound effects are generated — the agent combines ALL selected parents in a layer to produce children. The inference is a function of the full parent set, not individual parents independently.

## Three Operations

### 1. Deselect (deterministic, no agent)

- Toggle node to `selected: false`
- BFS cascade deselect all descendants
- Existing behavior — no change needed
- Cached layer results are NOT invalidated (preserved for potential re-selection)

> **Note:** The current BFS is correct for AND-semantics. The Obsidian spec (`Backend Graph Algorithms.md`) flags it as a "limitation" because it doesn't check multi-parent nodes — but that's only a problem under OR-semantics. If the project ever adopts OR-semantics (or mixed), BFS must be replaced with topological forward propagation.

### 2. Re-select (cache lookup) — NEW CODE PATH

The current toggle endpoint only handles deselect cascading. Re-select currently just flips `selected: true` and returns. This operation adds a fundamentally new code path to the toggle endpoint:

- Toggle node to `selected: true`
- Compute `parent_set_hash` for the next layer: `sha256(sorted(selected_parent_ids))` where `selected_parent_ids` = all currently selected nodes at that layer (including the just-re-selected one)
- **Cache hit:** re-select existing deselected nodes that match the cached result (by node ID). Do NOT replace or append — the nodes already exist in the session's flat `nodes` array with `selected: false`. Flip them back to `selected: true`. Then check next layer recursively (may also cache-hit, giving instant full restore down the chain).
- **Cache miss:** falls through to operation 3 (regeneration)

**Interaction with existing session state:** Cached nodes were originally generated and stored in the session's `nodes` array. Deselection only flips `selected: false` — it doesn't remove them. Cache restore means finding those same nodes by ID and flipping them back to `selected: true`. No array mutation (no append, no replace).

### 3. Add from pool (agent regeneration) — NEW CODE PATH

- User selects a new node from a pool (news pool, value pool) into the active graph
- New parent set → new hash → cache miss
- Remove existing children at layer N+1 from the session's `nodes` and `edges` arrays
- Call agent crew with full selected parent set at layer N
- Insert newly generated nodes and edges into the session
- Store generated nodes + edges in cache keyed by `parent_set_hash`
- Cascade downward: layer N+2 must also be checked (its parent set changed since N+1 was regenerated)

## Cache Structure

Per-session, stored in MongoDB alongside the session document:

```python
# Field on session document
"layer_cache": {
    "<layer_number>": {
        "<parent_set_hash>": {
            "nodes": [...],   # Full node objects for this layer
            "edges": [...]    # Edges connecting parents to these nodes
        }
    }
}
```

### Cache Key

```python
import hashlib, json

def parent_set_hash(selected_parent_ids: list[str]) -> str:
    key = json.dumps(sorted(selected_parent_ids), separators=(",", ":"))
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

- Deterministic: same parent set always produces same hash
- Truncated to 16 hex chars — collision-safe for the expected cardinality (< 1000 unique combos per session)

### Cache Lifecycle

- Created when agent generates children for a layer
- Read on re-selection or re-step with same parent set
- Never explicitly invalidated — stale entries are harmless (different hash = different entry)
- Dropped when session is deleted

## Cascade Direction

Downward only. Changing the selected set at layer N affects:
- Layer N+1 (direct children)
- Layer N+2 (children of children)
- ...continuing to max_depth

Each layer independently computes its parent-set hash and checks cache. This means a change at layer 0 can resolve entirely from cache if all downstream layer combinations have been seen before.

## Affected Files

| File | Change |
|------|--------|
| `backend/src/api/thinking.py` | Toggle endpoint: add re-select code path (cache lookup + restore), add regeneration code path (wipe + agent call + cache write). This is the biggest change — the endpoint goes from deselect-only to handling all three operations. |
| `backend/src/services/thinking_service.py` | Extract layer generation into reusable function callable from both `step` and `toggle`. |
| `backend/src/agents/thinking_crew.py` | Verify `think_effects` signature accepts explicit parent set. May need adjustment if it currently derives parents from session state rather than accepting them as input. |
| `backend/src/models/thinking.py` | Add `layer_cache: dict[str, dict[str, dict]] = Field(default_factory=dict)` to session model. |
| Frontend | **No change.** The frontend already re-fetches the full session after toggle (via SSE or polling). The toggle response shape (`dirty_count`, `status`) is unchanged. Cache is transparent to the client. |

## Edge Cases

1. **Empty parent set** — All parents at a layer deselected. Hash of empty list. Children = none. Cache stores empty result.
2. **Max depth reached** — No children to generate. No cache entry needed.
3. **Concurrent toggles** — Existing optimistic concurrency (version field) prevents races. Cache writes are idempotent (same hash = same result).
4. **Large cache** — Bounded by `2^N` combinations where N = nodes per layer. With typical 3-8 news items, this is manageable. No eviction needed.

## What Does NOT Change

- BFS cascade deselection logic (correct for AND-semantics)
- Agent crew prompting (already receives full parent set)
- Frontend components (cache is backend-only)
- Step endpoint semantics (step still advances to next layer)
