"""
Fed Rate Decision benchmark scenario.

Causal chain:
  Fed holds rates steady amid cooling inflation + strong labor market
  → yield curve steepens (long rates rise, short rates anchored)
  → housing market softens (mortgage rates stay elevated)
  → REITs recover (rate stability = predictable cash flows)
  → regional bank earnings improve (net interest margin expands)

Expected trades: TLT short (L2), VNQ long (L3), KRE long (L3)
"""

SCENARIO: dict = {
    "id": "fed-rate-decision",
    "name": "Fed Rate Decision — Rates & Housing",
    "description": (
        "Fed holds rates amid cooling inflation → yield curve steepens "
        "→ housing softens → REITs recover → bank margins improve"
    ),
    # -------------------------------------------------------------------------
    # News inputs
    # -------------------------------------------------------------------------
    "news_pool": [
        {
            "id": "fed-news-1",
            "title": "Federal Reserve holds rates steady at 5.25-5.50% range",
            "summary": (
                "The Federal Open Market Committee voted unanimously to maintain "
                "the federal funds rate at 5.25-5.50%, citing continued progress "
                "on inflation but noting the labor market remains resilient. "
                "Chair Powell emphasized the committee needs more confidence that "
                "inflation is moving sustainably toward 2% before cutting rates."
            ),
            "url": "https://example.com/news/fed-holds-rates-steady",
            "source": "CNBC",
            "tickers": [],
            "sectors": ["Macro", "Monetary Policy", "Banking"],
        },
        {
            "id": "fed-news-2",
            "title": "CPI data shows inflation cooling to 2.9% year-over-year",
            "summary": (
                "The Consumer Price Index rose 2.9% in the latest reading, down "
                "from 3.1% the prior month, signaling continued disinflation. "
                "Core CPI excluding food and energy came in at 3.2%, still above "
                "the Fed's 2% target but trending in the right direction. "
                "Markets now price in the first rate cut no earlier than Q4."
            ),
            "url": "https://example.com/news/cpi-cooling-inflation",
            "source": "Bloomberg",
            "tickers": [],
            "sectors": ["Macro", "Economy", "Monetary Policy"],
        },
        {
            "id": "fed-news-3",
            "title": "Jobs report beats expectations with 275K new positions",
            "summary": (
                "The US economy added 275,000 jobs in the latest monthly report, "
                "well above the 200,000 consensus estimate. Unemployment held at "
                "3.7% while wage growth moderated to 3.9% annualized. "
                "The strong labor data reduces urgency for the Fed to cut rates "
                "and reinforces the higher-for-longer interest rate narrative."
            ),
            "url": "https://example.com/news/jobs-report-beats-expectations",
            "source": "Reuters",
            "tickers": [],
            "sectors": ["Macro", "Economy", "Labor"],
        },
    ],
    # -------------------------------------------------------------------------
    # Market instruments
    # -------------------------------------------------------------------------
    "value_pool": [
        {
            "ticker": "TLT",
            "name": "iShares 20+ Year Treasury Bond ETF",
            "sector": "Fixed Income",
            "price": 92.40,
            "pe_ratio": None,
            "market_cap": 50_000_000_000,
            "price_change_pct": -0.8,
            "score": 45,
            "discount_pct": 8.2,
        },
        {
            "ticker": "VNQ",
            "name": "Vanguard Real Estate ETF",
            "sector": "Real Estate",
            "price": 82.10,
            "pe_ratio": 35.2,
            "market_cap": 32_000_000_000,
            "price_change_pct": 0.4,
            "score": 62,
            "discount_pct": 12.5,
        },
        {
            "ticker": "KRE",
            "name": "SPDR S&P Regional Banking ETF",
            "sector": "Banking",
            "price": 48.60,
            "pe_ratio": 10.8,
            "market_cap": 3_500_000_000,
            "price_change_pct": 1.2,
            "score": 71,
            "discount_pct": 18.3,
        },
        {
            "ticker": "XLU",
            "name": "Utilities Select Sector SPDR",
            "sector": "Utilities",
            "price": 67.80,
            "pe_ratio": 18.5,
            "market_cap": 16_000_000_000,
            "price_change_pct": -0.2,
            "score": 58,
            "discount_pct": 5.1,
        },
    ],
    # -------------------------------------------------------------------------
    # Reasoning depth target
    # -------------------------------------------------------------------------
    "expected_depth": 3,
    # -------------------------------------------------------------------------
    # Checkpoints per causal layer
    # -------------------------------------------------------------------------
    "checkpoints": [
        # Layer 1 — monetary policy trigger
        {
            "layer": 1,
            "text": "Fed holds rates / no rate cut decision",
            "required": True,
        },
        {
            "layer": 1,
            "text": (
                "inflation cooling but not yet at 2% target — "
                "justifies patience on cuts"
            ),
            "required": True,
        },
        {
            "layer": 1,
            "text": "strong labor market reduces urgency to cut",
            "required": False,  # bonus
        },
        # Layer 2 — bond and housing market impact
        {
            "layer": 2,
            "text": "yield curve steepens / long-term rates rise",
            "required": True,
        },
        {
            "layer": 2,
            "text": "mortgage rates stay elevated from higher-for-longer policy",
            "required": True,
        },
        {
            "layer": 2,
            "text": "housing market demand weakens or cools",
            "required": False,  # bonus
        },
        # Layer 3 — sector rotation consequences
        {
            "layer": 3,
            "text": "REITs benefit from rate stability / predictable financing costs",
            "required": True,
        },
        {
            "layer": 3,
            "text": (
                "bank net interest margins improve / regional bank earnings benefit"
            ),
            "required": True,
        },
        {
            "layer": 3,
            "text": "utilities underperform as yield-seeking capital rotates out",
            "required": False,  # bonus
        },
    ],
    # -------------------------------------------------------------------------
    # Expected instrument matches
    # -------------------------------------------------------------------------
    "expected_matches": [
        {
            "ticker": "TLT",
            "direction": "short",
            "layer": 2,
            "rationale": (
                "Higher-for-longer rates push long-term bond prices down as "
                "the yield curve steepens."
            ),
        },
        {
            "ticker": "VNQ",
            "direction": "long",
            "layer": 3,
            "rationale": (
                "Rate stability gives REITs predictable financing costs, "
                "supporting valuations at current discount levels."
            ),
        },
        {
            "ticker": "KRE",
            "direction": "long",
            "layer": 3,
            "rationale": (
                "Steeper yield curve expands net interest margins for "
                "regional banks, boosting earnings."
            ),
        },
    ],
    # -------------------------------------------------------------------------
    # Expected skills invoked per layer
    # -------------------------------------------------------------------------
    "expected_skills": {
        "L1": ["macro_economics"],
        "L2": ["macro_economics", "sector_rotation"],
        "L3": ["sector_rotation"],
    },
}
