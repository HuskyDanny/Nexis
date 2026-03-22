SKILL = {
    "name": "technical_momentum",
    "description": "Analyze price action, trends, and momentum for timing and confirmation",
    "content": """You are analyzing technical and momentum signals. Follow this framework strictly.

## Step 1: Identify the Primary Trend
Establish the dominant trend across timeframes before any detail analysis:
- **Weekly/monthly (structural):** 200-day moving average direction, multi-year trendlines — defines the secular backdrop
- **Daily (tactical):** 50-day MA direction, intermediate swing highs/lows — defines the tradeable trend
- **Intraday (noise):** Only relevant for entry/exit timing, not for analytical conclusions
- **Trend alignment:** Strongest signals occur when all timeframes agree. Conflicting timeframes = chop, lower confidence.

## Step 2: Map Key Support and Resistance Levels
Levels are where supply/demand concentrates:
- **Prior highs/lows:** Market memory — where buyers/sellers previously stepped in
- **Moving averages:** 50-day (tactical), 100-day (intermediate), 200-day (structural) — act as dynamic support/resistance
- **Volume profile nodes:** High-volume nodes = areas of acceptance (support). Low-volume gaps = areas price moves through quickly.
- **Round numbers:** Psychological levels (e.g., $100, $50) — attract options positioning and stop-loss clusters

## Step 3: Volume Confirmation
Price moves without volume are suspect:
- **Breakout + high volume:** Confirms conviction, likely sustainable
- **Breakout + low volume:** Suspect, higher probability of failure/reversal
- **Decline + high volume:** Capitulation potential — could mark exhaustion if climactic
- **Decline + low volume:** Orderly selling, trend likely continues lower

## Step 4: Momentum and Divergence Signals
Momentum measures the speed of price change and warns of trend exhaustion:
- **RSI (14-period):** Above 70 = overbought (not necessarily bearish in strong trends), below 30 = oversold
- **MACD:** Signal line crossovers for momentum shifts, histogram for acceleration/deceleration
- **Bullish divergence:** Price makes lower low, but RSI/MACD makes higher low — weakening sell pressure, potential reversal
- **Bearish divergence:** Price makes higher high, but RSI/MACD makes lower high — weakening buy pressure, potential top
- **Divergence is a warning, not a signal.** Divergences can persist for extended periods. Require price confirmation (break of support/resistance) before acting.

## Step 5: Multi-Timeframe Synthesis
Combine the above into a coherent read:
- What is the structural trend telling you? (direction bias)
- Where are the key levels? (risk/reward zones)
- Does volume confirm the current move? (conviction check)
- Is momentum supporting or diverging? (continuation vs. exhaustion)

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
