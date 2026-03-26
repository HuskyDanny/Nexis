import pytest
from src.services.stream_parser import IncrementalEffectsParser


class TestIncrementalEffectsParser:
    def test_single_complete_effect(self):
        parser = IncrementalEffectsParser()
        chunk = '{"effects": [{"content": "Fed pause", "reasoning": "dovish", "confidence": 80, "parent_ids": ["s1"], "sector": "macro", "fetched_news_ids": [], "information_gaps": []}]}'
        events = parser.feed(chunk)
        starts = [e for e in events if e["type"] == "node_start"]
        completes = [e for e in events if e["type"] == "node_complete"]
        assert len(starts) == 1
        assert len(completes) == 1
        assert completes[0]["data"]["confidence"] == 80

    def test_streamed_chunks(self):
        parser = IncrementalEffectsParser()
        chunks = [
            '{"effects": [{"content": "Rate',
            ' cut impact", "reasoning": "Fed',
            ' signals easing", "confidence": 75,',
            ' "parent_ids": ["s1"], "sector":',
            ' "macro", "fetched_news_ids": [],',
            ' "information_gaps": []}]}',
        ]
        all_events = []
        for c in chunks:
            all_events.extend(parser.feed(c))
        completes = [e for e in all_events if e["type"] == "node_complete"]
        assert len(completes) == 1

    def test_multiple_effects(self):
        parser = IncrementalEffectsParser()
        chunk = '{"effects": [{"content": "A", "reasoning": "r1", "confidence": 70, "parent_ids": ["s1"], "sector": "tech", "fetched_news_ids": [], "information_gaps": []}, {"content": "B", "reasoning": "r2", "confidence": 60, "parent_ids": ["s2"], "sector": "energy", "fetched_news_ids": [], "information_gaps": []}]}'
        events = parser.feed(chunk)
        completes = [e for e in events if e["type"] == "node_complete"]
        assert len(completes) == 2

    def test_markdown_fence_stripped(self):
        parser = IncrementalEffectsParser()
        chunk = '```json\n{"effects": [{"content": "X", "reasoning": "Y", "confidence": 50, "parent_ids": ["s1"], "sector": "fin", "fetched_news_ids": [], "information_gaps": []}]}\n```'
        events = parser.feed(chunk)
        completes = [e for e in events if e["type"] == "node_complete"]
        assert len(completes) == 1

    def test_text_deltas_emitted(self):
        parser = IncrementalEffectsParser()
        chunks = [
            '{"effects": [{"content": "Fed ',
            "rate pause signals dovish ",
            'pivot", "reasoning": "The hold',
            ' despite pressure", "confidence": 78,',
            ' "parent_ids": ["s1"], "sector": "macro",',
            ' "fetched_news_ids": [], "information_gaps": []}]}',
        ]
        all_events = []
        for c in chunks:
            all_events.extend(parser.feed(c))
        text_events = [e for e in all_events if e["type"] == "node_text"]
        assert len(text_events) > 0
        content_deltas = [
            e["data"]["delta"]
            for e in text_events
            if e["data"].get("field") == "content"
        ]
        assert "Fed " in "".join(content_deltas) or "rate" in "".join(content_deltas)

    def test_empty_effects(self):
        parser = IncrementalEffectsParser()
        events = parser.feed('{"effects": []}')
        assert len([e for e in events if e["type"] == "node_complete"]) == 0

    def test_malformed_prose_input(self):
        parser = IncrementalEffectsParser()
        events = parser.feed(
            "I think the main effects would be inflation and trade disruption."
        )
        assert len([e for e in events if e["type"] == "node_complete"]) == 0

    def test_partial_json_then_complete(self):
        parser = IncrementalEffectsParser()
        events1 = parser.feed('{"effects": [{"content": "partial')
        assert len([e for e in events1 if e["type"] == "node_complete"]) == 0
        events2 = parser.feed(
            '", "reasoning": "r", "confidence": 60, "parent_ids": ["s1"], "sector": "x", "fetched_news_ids": [], "information_gaps": []}]}'
        )
        assert len([e for e in events2 if e["type"] == "node_complete"]) == 1
