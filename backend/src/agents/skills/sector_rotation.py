SKILL = {
    "name": "sector_rotation",
    "description": "Determine which sectors benefit or suffer from macro regime shifts",
    "content": """You are analyzing sector rotation implications of a macro or market shift. Follow this framework strictly.

## Step 1: Identify the Macro Regime
Classify the current or transitioning regime:
- **Early expansion:** Rates falling, growth recovering, credit easing → cyclicals and small-caps lead
- **Mid expansion:** Steady growth, moderate inflation, earnings broadening → tech, industrials, consumer discretionary
- **Late expansion:** Overheating, rising inflation, tightening begins → energy, materials, financials
- **Contraction:** Growth slowing, risk-off, flight to quality → utilities, healthcare, consumer staples, treasuries

## Step 2: Assess Rate Sensitivity
Interest rate changes create asymmetric sector impacts:
- **Rate-sensitive beneficiaries (rates up):** Banks and financials (wider net interest margins), insurance (higher investment returns)
- **Rate-sensitive losers (rates up):** Real estate / REITs (higher cap rates, lower valuations), utilities (bond proxy repricing), growth/tech (longer duration, DCF compression)
- **Rate-sensitive beneficiaries (rates down):** Growth/tech (multiple expansion), REITs, homebuilders, leveraged companies

## Step 3: Apply Growth vs. Value Rotation Logic
- **Growth outperforms when:** Rates are low/falling, liquidity abundant, earnings scarce (growth premium rises)
- **Value outperforms when:** Rates rising, inflation up, earnings broadening (growth premium compresses)
- **Quality matters most when:** Late cycle, credit stress, recession risk (flight to balance sheet strength)

## Step 4: Map Defensive vs. Cyclical Positioning
- **Cyclical sectors:** Industrials, materials, consumer discretionary, financials, tech — earnings amplify GDP swings
- **Defensive sectors:** Utilities, healthcare, consumer staples, telecom — earnings resist GDP swings
- **Transition signal:** Watch credit spreads, yield curve, PMI direction — leading indicators of regime shift

## Step 5: Cross-Sector Correlation Thinking
No sector moves in isolation. Trace the chain:
- Oil price spike → energy wins → airlines/transport lose → consumer discretionary pressured → defensive rotation
- Dollar strength → US domestic revenue companies benefit → multinationals face translation headwinds → EM exporters pressured
- Tech regulation → mega-cap tech re-rates → capital rotates to mid-cap software or non-US tech

## Step 6: Identify Sector-Specific Catalysts
Beyond macro: what sector-level events are upcoming?
- Earnings season positioning, regulatory rulings, patent cliffs, capacity additions, M&A cycles

Required output format:
- Primary effect: [one sentence]
- Transmission: [mechanism chain: A → B → C]
- Scope: [1-5] — [justification]
- Impact: [1-5] — [justification]
- Winners: [sectors/companies that benefit]
- Losers: [sectors/companies that suffer]
- Confidence: [high/medium/low] — [why]
- Time horizon: [immediate/medium/structural]""",
}
