"""
Iran Escalation benchmark scenario.

Causal chain:
  US Navy near Iran + domestic political pressure
  → military strike on Iran
  → oil price spike (Strait of Hormuz supply disruption)
  → inflation rise
  → Fed constrained, cannot cut rates
  → USD strengthens
  → gold falls relative to strong USD

Expected trades: USO long (L2), GLD short (L3)
"""

SCENARIO: dict = {
    "id": "iran-escalation",
    "name": "Iran Escalation — Oil & Gold",
    "description": (
        "US Navy near Iran + domestic political pressure → military strike "
        "→ oil spike → inflation → gold down"
    ),
    # -------------------------------------------------------------------------
    # News inputs
    # -------------------------------------------------------------------------
    "news_pool": [
        {
            "id": "iran-news-1",
            "title": "US Navy deploys carrier group near Iranian coast",
            "summary": (
                "The USS Eisenhower carrier strike group has been redirected to the "
                "Persian Gulf in a show of force amid rising tensions with Iran. "
                "The deployment marks the largest US naval presence in the region in "
                "over a decade, signaling a potential escalation of military posture."
            ),
            "url": "https://example.com/news/uss-eisenhower-persian-gulf",
            "source": "Reuters",
            "tickers": [],
            "sectors": ["Defense", "Energy", "Geopolitics"],
        },
        {
            "id": "iran-news-2",
            "title": "Domestic political pressure mounts amid massacre fallout",
            "summary": (
                "Presidential approval ratings have dropped to a record low following "
                "public outcry over recent regional incidents, with opposition leaders "
                "demanding decisive military action. "
                "Polling data shows a majority of voters now support a stronger response, "
                "creating significant political incentive for the administration to act."
            ),
            "url": "https://example.com/news/political-pressure-iran-response",
            "source": "Politico",
            "tickers": [],
            "sectors": ["Politics", "Geopolitics"],
        },
        {
            "id": "iran-news-3",
            "title": "Analysts warn of strategic timing for military action against Iran",
            "summary": (
                "A convergence of factors — forward-deployed naval assets, waning "
                "diplomatic options, and a narrow weather window — is creating a "
                "strategic opportunity for a US military strike on Iranian facilities. "
                "Defense analysts note that the combination of military readiness and "
                "domestic political pressure has not been this aligned in years."
            ),
            "url": "https://example.com/news/iran-strike-window-analysts",
            "source": "Foreign Policy",
            "tickers": [],
            "sectors": ["Defense", "Geopolitics", "Energy"],
        },
    ],
    # -------------------------------------------------------------------------
    # Market instruments
    # -------------------------------------------------------------------------
    "value_pool": [
        {
            "ticker": "USO",
            "name": "United States Oil Fund",
            "sector": "Energy",
            "price": 72.50,
            "pe_ratio": None,
            "market_cap": 1_800_000_000,
            "price_change_pct": 0.8,
            "score": 72,
            "discount_pct": -5.2,
        },
        {
            "ticker": "XLE",
            "name": "Energy Select Sector SPDR",
            "sector": "Energy",
            "price": 88.30,
            "pe_ratio": 12.4,
            "market_cap": 38_000_000_000,
            "price_change_pct": 1.1,
            "score": 68,
            "discount_pct": -3.8,
        },
        {
            "ticker": "GLD",
            "name": "SPDR Gold Shares",
            "sector": "Precious Metals",
            "price": 215.40,
            "pe_ratio": None,
            "market_cap": 56_000_000_000,
            "price_change_pct": -0.3,
            "score": 55,
            "discount_pct": 2.1,
        },
        {
            "ticker": "QQQ",
            "name": "Invesco QQQ Trust",
            "sector": "Technology",
            "price": 485.20,
            "pe_ratio": 32.1,
            "market_cap": 220_000_000_000,
            "price_change_pct": -0.6,
            "score": 61,
            "discount_pct": 4.5,
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
        # Layer 1 — geopolitical trigger
        {
            "layer": 1,
            "text": "military strike / attack on Iran",
            "required": True,
        },
        {
            "layer": 1,
            "text": (
                "political timing — domestic pressure creates window "
                "for military action"
            ),
            "required": True,
        },
        # Layer 2 — energy market impact
        {
            "layer": 2,
            "text": "oil price increase due to supply disruption",
            "required": True,
        },
        {
            "layer": 2,
            "text": ("Iran as major oil exporter or Strait of Hormuz chokepoint"),
            "required": True,
        },
        {
            "layer": 2,
            "text": "supply disruption risk to global energy markets",
            "required": False,  # bonus
        },
        # Layer 3 — macro / monetary consequences
        {
            "layer": 3,
            "text": "inflation increase from oil and transportation costs",
            "required": True,
        },
        {
            "layer": 3,
            "text": ("interest rates cannot decrease / Fed constrained by inflation"),
            "required": True,
        },
        {
            "layer": 3,
            "text": "USD strengthens from tight monetary policy",
            "required": False,  # bonus
        },
        {
            "layer": 3,
            "text": "gold falls relative to strong USD",
            "required": True,
        },
    ],
    # -------------------------------------------------------------------------
    # Expected instrument matches
    # -------------------------------------------------------------------------
    "expected_matches": [
        {
            "ticker": "USO",
            "direction": "long",
            "layer": 2,
            "rationale": "Oil supply disruption from Hormuz closure drives USO price up.",
        },
        {
            "ticker": "GLD",
            "direction": "short",
            "layer": 3,
            "rationale": (
                "Strong USD from Fed rate constraints suppresses gold prices."
            ),
        },
    ],
    # -------------------------------------------------------------------------
    # Expected skills invoked per layer
    # -------------------------------------------------------------------------
    "expected_skills": {
        "L1": ["geopolitical_risk"],
        "L2": ["supply_chain", "geopolitical_risk"],
        "L3": ["macro_economics"],
    },
}
