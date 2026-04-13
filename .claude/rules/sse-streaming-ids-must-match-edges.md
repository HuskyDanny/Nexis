# SSE Streaming Node IDs Must Match Edge Source/Target IDs

## The Trap
Backend `run_layer_streaming` creates nodes via SSE with `uuid4().hex[:12]` IDs, but `_build_thinker_output` generates independent UUIDs for the same effects. Edges reference the batch IDs which don't exist in the frontend — edges silently fail to render with zero error messages.

## The Solution
After `_build_thinker_output`, remap batch IDs to streaming IDs using `index_to_id` (both iterate effects_raw in order):
```python
batch_to_stream = {}
for idx, node in enumerate(effect_nodes):
    stream_id = index_to_id.get(idx)
    if stream_id:
        batch_to_stream[node["id"]] = stream_id
        node["id"] = stream_id
for edge in effect_edges:
    edge["source"] = batch_to_stream.get(edge["source"], edge["source"])
    edge["target"] = batch_to_stream.get(edge["target"], edge["target"])
```

## Context
- **When this applies:** Any SSE streaming path that also generates edges from a batch parse of the same LLM output
- **Related files:** `backend/src/services/thinking_service.py` (run_layer_streaming)
- **Discovered:** 2026-04-09, edges were invisible in the thinking graph for the entire streaming path
