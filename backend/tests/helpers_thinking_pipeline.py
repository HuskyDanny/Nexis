"""Shared mock data factories for thinking pipeline tests."""


def seed_nodes():
    """Layer-0 seed nodes (news items selected by user)."""
    return [
        {
            "id": "seed-1",
            "layer": 0,
            "type": "news",
            "content": "Fed raises rates 75bps",
            "reasoning": "",
            "confidence": 100,
            "sources": [],
            "parents": [],
            "selected": True,
            "metadata": {"sector": "macro"},
        },
        {
            "id": "seed-2",
            "layer": 0,
            "type": "news",
            "content": "China tariffs expanded",
            "reasoning": "",
            "confidence": 100,
            "sources": [],
            "parents": [],
            "selected": True,
            "metadata": {"sector": "trade"},
        },
    ]


def news_pool():
    return [
        {
            "id": "np-1",
            "title": "OPEC cuts production",
            "summary": "OPEC announces cuts",
        },
        {"id": "np-2", "title": "EU inflation data", "summary": "EU CPI rises"},
    ]


def value_pool():
    return [
        {"ticker": "XOM", "sector": "energy", "discount_pct": 15, "summary": "Exxon"},
        {"ticker": "AAPL", "sector": "tech", "discount_pct": 8, "summary": "Apple"},
    ]


def thinker_result_layer1():
    """What run_thinker returns for layer 1."""
    effect_nodes = [
        {
            "id": "eff-1",
            "layer": 1,
            "type": "effect",
            "content": "Housing slows",
            "reasoning": "Rate hike -> mortgage spike",
            "confidence": 80,
            "sources": [],
            "parents": ["seed-1"],
            "selected": True,
            "metadata": {"sector": "real_estate"},
        },
    ]
    fetch_nodes = [
        {
            "id": "fetch-1",
            "layer": 1,
            "type": "fetch",
            "content": "Related: OPEC cuts",
            "reasoning": "Fetched for context",
            "confidence": 100,
            "sources": [],
            "parents": ["seed-1"],
            "selected": True,
            "metadata": {},
        },
    ]
    effect_edges = [{"source": "seed-1", "target": "eff-1", "relationship": "causes"}]
    fetch_edges = [
        {"source": "seed-1", "target": "fetch-1", "relationship": "fetched_for"}
    ]
    return effect_nodes, fetch_nodes, effect_edges, fetch_edges


def thinker_result_layer2():
    """What run_thinker returns for layer 2."""
    effect_nodes = [
        {
            "id": "eff-2",
            "layer": 2,
            "type": "effect",
            "content": "Construction jobs decline",
            "reasoning": "Housing slows -> fewer jobs",
            "confidence": 60,
            "sources": [],
            "parents": ["eff-1"],
            "selected": True,
            "metadata": {"sector": "employment"},
        },
    ]
    fetch_nodes = []
    effect_edges = [{"source": "eff-1", "target": "eff-2", "relationship": "compounds"}]
    fetch_edges = []
    return effect_nodes, fetch_nodes, effect_edges, fetch_edges


def matcher_result_layer1():
    """What run_matcher returns for layer 1 effects."""
    opp_nodes = [
        {
            "id": "opp-1",
            "layer": 1,
            "type": "opportunity",
            "content": "XOM — 72% conviction",
            "reasoning": "Energy sector benefits",
            "confidence": 72,
            "sources": [],
            "parents": ["eff-1"],
            "selected": True,
            "metadata": {"ticker": "XOM", "convergence_score": 72},
        },
    ]
    match_edges = [{"source": "eff-1", "target": "opp-1", "relationship": "matches"}]
    return opp_nodes, match_edges


def matcher_result_layer2():
    return [], []


def controller_continue():
    return {
        "continue": True,
        "reasoning": "More to explore",
        "summary": "Chain continues",
    }


def controller_stop():
    return {
        "continue": False,
        "reasoning": "Diminishing returns",
        "summary": "Chain done",
    }
