"""Golden set for graph search quality benchmarking.

SEED_ENTITIES: entities to add to FakeGraphStore.
SEED_EDGES: edges connecting related entities.
GOLDEN_QUERIES: queries with expected relevant entity IDs.

FakeGraphStore uses substring matching (query ⊆ name or summary), so
entity names and summaries are designed to contain searchable terms.
Real Graphiti uses hybrid BM25 + cosine + graph structure.
"""

SEED_ENTITIES = [
    {
        "id": "eff_001",
        "name": "fed rate fintech lending",
        "type": "Effect",
        "summary": (
            "Federal reserve rate pause reduces borrowing costs for fintech "
            "lenders. Historical pattern: 2024 rate pause led to 15% increase "
            "in fintech lending volume."
        ),
    },
    {
        "id": "eff_002",
        "name": "fed rate tech valuations",
        "type": "Effect",
        "summary": (
            "Federal reserve rate cuts boost tech stock valuations. DCF models "
            "discount future cash flows at lower rates, raising present values."
        ),
    },
    {
        "id": "eff_003",
        "name": "tariff semiconductor disruption",
        "type": "Effect",
        "summary": (
            "China retaliatory tariffs disrupt semiconductor supply chain. "
            "TSMC fab utilization dropped 8% during 2025 tariff escalation."
        ),
    },
    {
        "id": "eff_004",
        "name": "nvidia china export control",
        "type": "Effect",
        "summary": (
            "NVIDIA revenue at risk from China AI chip tariff and export "
            "controls. China accounts for 25% of NVIDIA data center revenue."
        ),
    },
    {
        "id": "eff_005",
        "name": "oil demand trade war",
        "type": "Effect",
        "summary": (
            "Oil demand falls as trade war reduces industrial output. "
            "Manufacturing PMI contraction correlates with 5-10% crude "
            "demand drop."
        ),
    },
    {
        "id": "eff_006",
        "name": "renewable energy oil decline",
        "type": "Effect",
        "summary": (
            "Renewable energy stocks benefit from oil price decline. "
            "Cost advantage widens when fossil fuel prices are volatile."
        ),
    },
    {
        "id": "opp_001",
        "name": "nvidia tariff undervalued",
        "type": "Opportunity",
        "summary": (
            "NVIDIA undervalued after tariff-driven sell-off. AI inference "
            "demand intact; tariff impact priced in at 2x actual exposure."
        ),
    },
    {
        "id": "opp_002",
        "name": "pfizer pipeline bounce-back",
        "type": "Opportunity",
        "summary": (
            "Pfizer bounce-back opportunity after pipeline sell-off. RSV "
            "vaccine revenue understated; market overreacted to patent cliff "
            "concerns."
        ),
    },
    {
        "id": "news_001",
        "name": "federal reserve interest rates",
        "type": "News",
        "summary": "Federal Reserve holds interest rates steady at 4.25-4.5%.",
    },
    {
        "id": "news_002",
        "name": "market volatility geopolitical",
        "type": "News",
        "summary": (
            "Market volatility index VIX spikes to 30 on geopolitical " "uncertainty."
        ),
    },
]


SEED_EDGES = [
    {
        "source_name": "federal reserve interest rates",
        "target_name": "fed rate fintech lending",
        "edge_type": "CAUSES",
        "fact": (
            "Fed rate pause leads to reduced borrowing costs for fintech " "lenders."
        ),
    },
    {
        "source_name": "federal reserve interest rates",
        "target_name": "fed rate tech valuations",
        "edge_type": "CAUSES",
        "fact": "Federal reserve rate decisions boost tech stock valuations.",
    },
    {
        "source_name": "tariff semiconductor disruption",
        "target_name": "nvidia china export control",
        "edge_type": "IMPACTS",
        "fact": (
            "Tariff and export controls compound to reduce NVIDIA China " "revenue."
        ),
    },
    {
        "source_name": "nvidia tariff undervalued",
        "target_name": "nvidia china export control",
        "edge_type": "RELATES_TO",
        "fact": "NVIDIA tariff sell-off creates undervaluation opportunity.",
    },
    {
        "source_name": "oil demand trade war",
        "target_name": "renewable energy oil decline",
        "edge_type": "CAUSES",
        "fact": (
            "Oil demand decline from trade war benefits renewable energy " "sector."
        ),
    },
]


GOLDEN_QUERIES = [
    {
        "query": "fed rate",
        "relevant": {"eff_001", "eff_002"},
        "description": "Should find Fed rate effects on tech/fintech",
    },
    {
        "query": "tariff",
        "relevant": {"eff_003", "eff_004"},
        "description": "Should find tariff + semiconductor effects",
    },
    {
        "query": "nvidia",
        "relevant": {"eff_004", "opp_001"},
        "description": "Should find NVIDIA-specific entities (keyword + semantic)",
    },
    {
        "query": "oil demand",
        "relevant": {"eff_005"},
        "description": "Should find oil/energy trade war effects",
    },
    {
        "query": "undervalued",
        "relevant": {"opp_001"},
        "description": "Should find undervalued opportunities",
    },
    {
        "query": "federal reserve",
        "relevant": {"news_001", "eff_001", "eff_002"},
        "description": "Should find Fed news and related effects",
    },
]
