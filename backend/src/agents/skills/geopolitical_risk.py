SKILL = {
    "name": "geopolitical_risk",
    "description": "Assess geopolitical events and their financial market transmission",
    "content": """You are analyzing a geopolitical development. Follow this framework strictly.

## Step 1: Classify the Event Type
- **Armed conflict:** War, military escalation, proxy conflicts — assess duration probability and geographic containment
- **Sanctions / trade restrictions:** Financial sanctions, export controls, tariffs — identify targeted flows and workaround potential
- **Trade tensions:** Bilateral disputes, bloc formation, decoupling moves — assess escalation trajectory
- **Alliance shifts:** Treaty changes, new pacts, bloc realignment — evaluate credibility and enforcement capacity
- **Regime change:** Elections, coups, policy pivots — assess institutional continuity and policy reversal risk

## Step 2: Map Supply Route and Commodity Impact
Geopolitical events hit markets primarily through physical flow disruption:
- **Energy chokepoints:** Strait of Hormuz (20% global oil), Malacca Strait (25% global trade), Suez Canal, Panama Canal
- **Commodity concentration:** Which commodities depend on affected regions? (e.g., Russia — palladium, wheat; Taiwan — semiconductors; Chile — copper)
- **Substitution feasibility:** Can supply be rerouted or replaced? At what cost and timeline?

## Step 3: Trace Financial Transmission
- **Risk premium repricing:** VIX spike, credit spreads widen, safe-haven flows (USD, CHF, gold, treasuries)
- **Capital flight patterns:** Money exits perceived-risk geographies → flows to perceived-safe ones. Track FX moves as a proxy.
- **Commodity price shock:** Direct supply disruption → price spike → cost-push inflation → central bank response constrained
- **Sanctions financial plumbing:** SWIFT disconnection, asset freezes, correspondent banking cutoff — who is exposed as counterparty?

## Step 4: Assess Escalation vs. De-escalation Probability
- What are each side's incentives? Is there an off-ramp?
- Historical analogues: How did similar events resolve? (duration, market recovery timeline)
- Red lines: What triggers further escalation? What signals de-escalation?

## Step 5: Second-Order Geopolitical Effects
- **Alliance realignment:** Does this push neutral parties to pick sides? (e.g., trade war → bloc formation)
- **Domestic political spillover:** Does the event change election odds or policy priorities in major economies?
- **Precedent effects:** Does this embolden similar actions elsewhere? (e.g., invasion precedent → Taiwan risk repricing)
- **Refugee and humanitarian costs:** Fiscal burden on neighboring countries, political instability spillover

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
