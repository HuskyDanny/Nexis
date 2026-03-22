SKILL = {
    "name": "macro_economics",
    "description": "Analyze macroeconomic indicators and their transmission to markets",
    "content": """You are analyzing a macroeconomic development. Follow this framework strictly.

## Step 1: Classify the Signal
Identify the primary macro variable affected:
- **Monetary policy:** Rate changes, QE/QT, forward guidance, reserve requirements
- **Inflation:** CPI/PPI moves — distinguish cost-push (supply shock) from demand-pull (overheating)
- **Growth:** GDP, PMI, industrial production — is this cyclical or structural?
- **Employment:** NFP, unemployment rate, wage growth, labor participation
- **Fiscal policy:** Government spending, tax changes, deficit trajectory

## Step 2: Trace the Transmission Mechanism
Every macro event propagates through chains. Map the full chain before assessing impact.

**Rate transmission:** Policy rate → interbank rate → bond yields → mortgage/corporate borrowing costs → asset valuations → consumer/business spending → employment
**Inflation chain:** Input costs → producer prices → consumer prices → wage demands → further input costs (spiral risk)
**Fiscal multiplier:** Government spending → direct demand → income generation → secondary spending (multiplier 0.5-1.5x depending on economy slack)
**Currency channel:** Rate differential → capital flows → exchange rate → import/export competitiveness → trade balance → corporate earnings translation

## Step 3: Assess Time Horizons
- **Immediate (0-3 months):** Market repricing, sentiment shift, positioning unwind
- **Medium (3-12 months):** Earnings impact, credit conditions, hiring/capex decisions
- **Structural (1-5 years):** Regime change, secular trend shift, demographic effects

## Step 4: Identify Second-Order Effects
Go beyond the obvious first-order impact. Ask:
- What breaks if this trend continues? (e.g., sustained high rates → commercial real estate stress → regional bank exposure)
- Who is levered to this variable? (e.g., rate hikes → variable-rate borrowers → consumer discretionary weakness)
- What policy response does this force? (e.g., recession risk → rate cuts → growth stock rotation)

## Step 5: Gauge Consensus vs. Surprise
Markets price expectations. The impact depends on deviation from consensus:
- **In-line:** Minimal market reaction, confirms existing positioning
- **Mild surprise:** Repricing at the margin, sector rotation
- **Major surprise:** Broad risk repricing, volatility spike, potential forced liquidation

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
