"""Layer cache utilities for Thinking DAG parent-set memoization."""

import hashlib
import json


def parent_set_hash(selected_parent_ids: list[str]) -> str:
    """Compute a deterministic hash for a set of parent IDs.

    Sorts IDs so order doesn't matter. Returns 16 hex chars.
    """
    key = json.dumps(sorted(selected_parent_ids), separators=(",", ":"))
    return hashlib.sha256(key.encode()).hexdigest()[:16]
