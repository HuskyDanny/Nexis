"""Tiered quota for news pool — guarantees macro news representation."""

import math


def apply_tiered_quota(
    items: list[dict],
    macro_ratio: float = 0.4,
    macro_scope_threshold: int = 4,
) -> list[dict]:
    if not items:
        return []

    macro_ratio = max(0.0, min(1.0, macro_ratio))

    macro = [n for n in items if n.get("scope", 0) >= macro_scope_threshold]
    other = [n for n in items if n.get("scope", 0) < macro_scope_threshold]

    macro.sort(key=lambda x: x.get("score", 0), reverse=True)
    other.sort(key=lambda x: x.get("score", 0), reverse=True)

    total = len(items)
    macro_slots = min(math.ceil(total * macro_ratio), len(macro))
    other_slots = total - macro_slots

    return macro[:macro_slots] + other[:other_slots] + macro[macro_slots:]
