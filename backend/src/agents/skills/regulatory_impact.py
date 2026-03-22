SKILL = {
    "name": "regulatory_impact",
    "description": "Assess regulatory and policy changes on markets, sectors, and companies",
    "content": """You are analyzing a regulatory or policy change. Follow this framework strictly.

## Step 1: Classify the Regulatory Action
- **New regulation:** Novel rules imposing new obligations — highest uncertainty, widest impact
- **Enforcement action:** Existing rules applied to a specific company/sector — precedent-setting potential
- **Deregulation:** Removal of rules, reduced oversight — often sector-wide positive but may increase systemic risk
- **Antitrust action:** Merger blocking, breakup threats, market dominance challenges — company-specific with sector read-through
- **Standards/requirements:** Safety, environmental, reporting — compliance cost with long implementation timelines

## Step 2: Assess Compliance Cost and Burden
Regulation creates direct costs. Estimate the magnitude:
- **One-time costs:** System changes, legal compliance, restructuring — front-loaded impact on earnings
- **Ongoing costs:** Reporting, monitoring, staffing, licensing — permanent margin compression
- **Proportional burden:** Large companies absorb compliance costs more easily than small ones. Regulation often acts as a moat for incumbents by raising barriers to entry.
- **Timeline:** Proposed → comment period → final rule → implementation deadline. Markets react at each stage.

## Step 3: Market Structure Changes
Regulation reshapes competitive dynamics:
- **Barrier to entry:** Higher compliance costs = fewer new entrants = incumbent advantage
- **Market access:** Licensing requirements, geographic restrictions, data localization — who is excluded?
- **Product scope:** What can be sold, to whom, under what conditions? Product restrictions narrow addressable market.
- **Business model viability:** Some regulations make entire business models uneconomic (e.g., data privacy rules vs. ad-targeting models)

## Step 4: Precedent and Contagion Analysis
No regulation exists in isolation:
- **Precedent effect:** Does this ruling set precedent for other companies/sectors? (e.g., one antitrust action → sector-wide de-rating)
- **Jurisdictional spread:** Does regulation in one country trigger similar moves elsewhere? (e.g., EU GDPR → global privacy regulation wave)
- **Political momentum:** Is this a one-off or part of a regulatory cycle? (e.g., post-crisis tightening, election-year populism)
- **Legal challenge probability:** Will this survive court challenges? Regulatory uncertainty persists until legal resolution.

## Step 5: Winner/Loser Asymmetry
Regulation rarely affects all players equally:
- **Compliance-ready incumbents:** Already meet the standard — competitors face cost, they don't
- **Alternative beneficiaries:** If one product is restricted, what substitutes gain share?
- **Compliance technology providers:** Companies selling regulatory solutions benefit from complexity

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
