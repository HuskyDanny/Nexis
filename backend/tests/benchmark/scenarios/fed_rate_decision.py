"""
Fed Rate Decision benchmark scenario.

Causal chain:
  Fed holds rates at 5.5% + strong jobs data + sticky inflation
  → yield curve steepens (long-term rates rise)
  → housing affordability worsens (mortgage rates stay elevated)
  → homebuilder revenue declines (buyer demand drops)
  → regional bank net interest margins improve (higher lending rates)
  → REIT valuations compress (higher discount rates, refinancing costs)
  → consumer spending shifts from durables to services

Expected trades: TLT short (L1), XHB short (L2), KRE long (L2)
"""

SCENARIO: dict = {
    "id": "fed-rate-decision",
    "name": "Fed Rate Decision — Rates & Housing",
    "description": (
        "Fed holds rates + strong jobs + sticky inflation → yield curve steepens "
        "→ housing weakens → banks benefit → REITs decline"
    ),
    # -------------------------------------------------------------------------
    # News inputs
    # -------------------------------------------------------------------------
    "news_pool": [
        {
            "id": "fed-news-1",
            "title": "Federal Reserve holds rates steady at 5.5% for seventh consecutive meeting",
            "summary": (
                "The Federal Open Market Committee voted unanimously to maintain the "
                "federal funds rate at 5.25-5.50%, citing persistent inflationary "
                "pressures and a resilient labor market. Chair Powell emphasized that "
                "the committee needs to see more evidence of sustained disinflation "
                "before considering rate cuts, pushing back against market expectations "
                "of near-term easing."
            ),
            "url": "https://example.com/news/fed-holds-rates-march-2026",
            "source": "Reuters",
            "tickers": [],
            "sectors": ["Monetary Policy", "Economy", "Federal Reserve"],
        },
        {
            "id": "fed-news-2",
            "title": "US jobs report beats expectations — 275K added, unemployment at 3.7%",
            "summary": (
                "The US economy added 275,000 non-farm payroll jobs in the latest "
                "report, significantly exceeding the consensus forecast of 195,000. "
                "The unemployment rate held steady at 3.7%, while average hourly "
                "earnings rose 0.4% month-over-month. The strong labor market data "
                "reinforces the Fed's higher-for-longer rate stance."
            ),
            "url": "https://example.com/news/us-jobs-report-march-2026",
            "source": "Bloomberg",
            "tickers": [],
            "sectors": ["Employment", "Economy", "Labor Market"],
        },
        {
            "id": "fed-news-3",
            "title": "Inflation remains sticky at 3.2%, above Fed's 2% target",
            "summary": (
                "The Consumer Price Index rose 3.2% year-over-year, with core CPI "
                "at 3.0%, both above the Federal Reserve's 2% target. Services "
                "inflation remains particularly elevated, driven by shelter costs "
                "and insurance premiums. Economists warn that the last mile of "
                "disinflation may prove the most difficult."
            ),
            "url": "https://example.com/news/cpi-inflation-sticky-march-2026",
            "source": "CNBC",
            "tickers": [],
            "sectors": ["Inflation", "Economy", "Consumer Prices"],
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
            "price": 88.50,
            "pe_ratio": None,
            "market_cap": 45_000_000_000,
            "price_change_pct": -1.2,
            "score": 65,
            "discount_pct": 8.3,
        },
        {
            "ticker": "XHB",
            "name": "SPDR S&P Homebuilders ETF",
            "sector": "Real Estate / Construction",
            "price": 78.20,
            "pe_ratio": 10.8,
            "market_cap": 1_500_000_000,
            "price_change_pct": -2.1,
            "score": 58,
            "discount_pct": 12.5,
        },
        {
            "ticker": "KRE",
            "name": "SPDR S&P Regional Banking ETF",
            "sector": "Financial Services",
            "price": 52.40,
            "pe_ratio": 9.2,
            "market_cap": 3_200_000_000,
            "price_change_pct": 1.8,
            "score": 71,
            "discount_pct": -6.4,
        },
        {
            "ticker": "VNQ",
            "name": "Vanguard Real Estate ETF",
            "sector": "Real Estate / REITs",
            "price": 82.10,
            "pe_ratio": 35.6,
            "market_cap": 32_000_000_000,
            "price_change_pct": -0.9,
            "score": 48,
            "discount_pct": 5.7,
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
        # Layer 1 — monetary policy impact
        {
            "layer": 1,
            "text": "rates staying elevated / prolonged tight monetary policy",
            "required": True,
        },
        {
            "layer": 1,
            "text": "bond yields rise / yield curve steepens",
            "required": True,
        },
        # Layer 2 — sector-specific consequences
        {
            "layer": 2,
            "text": "housing market weakens from mortgage rate pressure",
            "required": True,
        },
        {
            "layer": 2,
            "text": "bank profitability improves from higher lending margins",
            "required": True,
        },
        {
            "layer": 2,
            "text": "credit tightening reduces consumer borrowing",
            "required": False,  # bonus
        },
        # Layer 3 — second-order macro effects
        {
            "layer": 3,
            "text": "REIT valuations decline from higher discount rates",
            "required": True,
        },
        {
            "layer": 3,
            "text": "consumer spending rotation from durables to services",
            "required": False,  # bonus
        },
        {
            "layer": 3,
            "text": "small business lending contraction",
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
            "layer": 1,
            "rationale": (
                "Prolonged high rates push long-term yields up, "
                "driving bond prices (and TLT) down."
            ),
        },
        {
            "ticker": "XHB",
            "direction": "short",
            "layer": 2,
            "rationale": (
                "Elevated mortgage rates reduce home-buying demand, "
                "pressuring homebuilder revenue and margins."
            ),
        },
        {
            "ticker": "KRE",
            "direction": "long",
            "layer": 2,
            "rationale": (
                "Higher-for-longer rates expand net interest margins "
                "for regional banks with variable-rate lending."
            ),
        },
    ],
    # -------------------------------------------------------------------------
    # Expected skills invoked per layer
    # -------------------------------------------------------------------------
    "expected_skills": {
        "L1": ["macro_economics"],
        "L2": ["sector_rotation", "consumer_behavior"],
        "L3": ["macro_economics", "company_fundamentals"],
    },
}
