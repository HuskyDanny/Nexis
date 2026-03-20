# Core Concept

## Two Branches Converge

**Branch 1: News-driven (top-down)**
News event → What sectors/stocks get impacted? → Direction (bullish/bearish) → Endpoint stocks/ETFs

**Branch 2: Value-driven (bottom-up)**
Scan for stocks that were once high, now low → Filter for unique fundamentals (inherent value floor, market position) → Why is it undervalued? → Recovery reasoning

**Convergence**: When a news event impacts a stock that's also flagged as undervalued = high-conviction signal. The mind map makes this visible as converging branches.

## Onion-Layer Depth (Every Node)

All layers are pre-computed. No loading spinners. Just click deeper.

| Layer | Content | Example |
|-------|---------|---------|
| **Surface** | 1-2 sentence summary + direction + confidence | "Fed holds rates → Financial sector bullish (82%)" |
| **Layer 1** | Key reasoning, which tools confirmed | "Lower-for-longer benefits bank margins. Sentiment: 0.72, RSI neutral" |
| **Layer 2** | Tool outputs — charts, indicators, scores | Technical chart, fundamental data table, sentiment breakdown |
| **Layer 3** | Raw sources — articles, price data | Reuters article, WSJ analysis, raw price history |

## Convergence Detection

- **Mechanism**: Ticker matching. If a ticker appears in BOTH news branch (impact endpoint) AND value branch (candidate), it's a convergence.
- **Confidence score**: Weighted composite — news sentiment strength (0.3) + value discount depth (0.3) + tool verification agreement (0.4). Each normalized 0-100.
- **Threshold**: Gold star shown only when confidence ≥ 50.

## Value Scanner Criteria

- **Universe**: S&P 500 + NASDAQ 100 + CSI 300 (configurable)
- **"High-to-low" filter**: Current price ≥ 25% below 52-week high
- **Fundamental filter**: P/E below sector 5yr avg OR P/B < 1.5 OR dividend yield > sector avg + 1%
- **"Unique fundamentals"**: LLM-assessed after quantitative screening
- **Output cap**: Top 15 candidates per run
