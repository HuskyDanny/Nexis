"""Incremental JSON parser for LLM-streamed thinker output.

Consumes token chunks, emits events as node objects become complete.
Handles markdown fences and partial JSON gracefully.
"""

import re
from typing import Any

from json_repair import repair_json

from src.core.logger import get_logger

log = get_logger("stream_parser")

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?", re.MULTILINE)
_FENCE_END_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    text = _FENCE_RE.sub("", text)
    text = _FENCE_END_RE.sub("", text)
    return text


class IncrementalEffectsParser:
    """Feed LLM chunks, get back structured events.

    Events emitted:
    - {"type": "node_start", "data": {"index": int}}
    - {"type": "node_text", "data": {"index": int, "field": str, "delta": str}}
    - {"type": "node_complete", "data": {"index": int, ...full effect dict}}
    """

    def __init__(self):
        self._buffer = ""
        self._completed_count = 0
        self._last_content_len: dict[int, dict[str, int]] = {}

    def feed(self, chunk: str) -> list[dict[str, Any]]:
        """Feed a chunk of LLM output. Returns list of events."""
        self._buffer += chunk
        clean = _strip_fences(self._buffer)
        events: list[dict[str, Any]] = []

        effects = self._extract_effects(clean)
        if effects is None:
            partial_events = self._emit_partial_deltas(clean)
            events.extend(partial_events)
            return events

        for i, effect in enumerate(effects):
            if i < self._completed_count:
                continue
            # Only emit node_start if partial deltas haven't already done so
            if i not in self._last_content_len:
                events.append({"type": "node_start", "data": {"index": i}})
            # Emit only remaining deltas (avoid duplicating already-streamed text)
            for field_name in ("content", "reasoning"):
                val = effect.get(field_name, "")
                if not val:
                    continue
                prev_len = self._last_content_len.get(i, {}).get(field_name, 0)
                if len(val) > prev_len:
                    delta = val[prev_len:]
                    events.append(
                        {
                            "type": "node_text",
                            "data": {
                                "index": i,
                                "field": field_name,
                                "delta": delta,
                            },
                        }
                    )
            events.append({"type": "node_complete", "data": {"index": i, **effect}})
            self._completed_count = i + 1

        return events

    def _extract_effects(self, text: str) -> list[dict] | None:
        """Try to parse complete effects from the buffer."""
        try:
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict) and "effects" in repaired:
                effects = repaired["effects"]
                if isinstance(effects, list):
                    complete = [
                        e
                        for e in effects
                        if isinstance(e, dict) and "content" in e and "confidence" in e
                    ]
                    if len(complete) > self._completed_count:
                        return complete
        except Exception:
            log.debug(
                "JSON repair failed during extract_effects (expected for partial chunks)"
            )
        return None

    def _emit_partial_deltas(self, text: str) -> list[dict[str, Any]]:
        """Try to extract partial text deltas from incomplete JSON."""
        events: list[dict[str, Any]] = []
        try:
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict) and "effects" in repaired:
                effects = repaired.get("effects", [])
                if not isinstance(effects, list):
                    return events
                for i, effect in enumerate(effects):
                    if not isinstance(effect, dict):
                        continue
                    if i < self._completed_count:
                        continue
                    if i not in self._last_content_len:
                        self._last_content_len[i] = {}
                        events.append({"type": "node_start", "data": {"index": i}})
                    for field_name in ("content", "reasoning"):
                        val = effect.get(field_name, "")
                        if not val:
                            continue
                        prev_len = self._last_content_len[i].get(field_name, 0)
                        if len(val) > prev_len:
                            delta = val[prev_len:]
                            events.append(
                                {
                                    "type": "node_text",
                                    "data": {
                                        "index": i,
                                        "field": field_name,
                                        "delta": delta,
                                    },
                                }
                            )
                            self._last_content_len[i][field_name] = len(val)
        except Exception:
            log.debug(
                "JSON repair failed during emit_partial_deltas (expected for partial chunks)"
            )
        return events
