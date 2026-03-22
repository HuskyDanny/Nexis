SKILL = {
    "name": "consumer_behavior",
    "description": "Analyze consumer spending patterns, demand shifts, and sentiment signals",
    "content": """You are analyzing a consumer behavior development. Follow this framework strictly.

## Step 1: Classify the Demand Signal
Identify what is driving the consumer shift:
- **Income effect:** Real income rising/falling changes total spending capacity. Wage growth minus inflation = real purchasing power.
- **Substitution effect:** Relative price changes cause consumers to switch between goods. Rising beef prices → chicken demand up.
- **Wealth effect:** Asset price changes (housing, stocks) alter spending confidence. Housing wealth is the strongest driver — homeowners spend more when values rise.
- **Credit conditions:** Tightening credit standards or rising rates reduce borrowing-funded consumption. Watch consumer credit growth and delinquency rates.
- **Sentiment shift:** Consumer confidence can lead or lag actual spending — distinguish between survey noise and actionable signal.

## Step 2: Assess Demand Elasticity
Not all consumer spending responds equally to shocks:
- **Inelastic demand (essentials):** Food, utilities, healthcare, basic telecom — spending is sticky, volumes barely change. Companies here have pricing power but limited upside.
- **Elastic demand (discretionary):** Travel, dining, luxury goods, entertainment — first to be cut in downturns, first to recover in upswings. High beta to consumer sentiment.
- **Durable vs. non-durable:** Durables (cars, appliances) are deferrable — demand is lumpy and rate-sensitive. Non-durables (groceries, personal care) are steady.

## Step 3: Consumer Confidence Transmission
How confidence translates to market impact:
- **Confidence rising:** Willingness to take on debt increases → durable goods purchases → housing activity → retail spending broadens
- **Confidence falling:** Precautionary saving rises → discretionary cuts → trade-down behavior (premium → value brands) → experiential spending cut before goods
- **Leading indicators:** University of Michigan / Conference Board surveys, credit card spending data, retail foot traffic, job openings rate

## Step 4: Demographic and Structural Trends
Look beyond the cycle for structural consumer shifts:
- **Generational spending patterns:** Millennials/Gen-Z prioritize experiences, digital, sustainability. Boomers drive healthcare, wealth management, downsizing.
- **Urbanization/remote work:** Shifts spending from urban commercial to suburban residential, from transit to home office, from restaurants to grocery delivery.
- **Digital adoption:** E-commerce penetration, digital payments, subscription models — secular growth overlaid on cyclical consumer spending.
- **Health and wellness:** Structural growth in fitness, organic/clean food, mental health services — resilient across cycles.

## Step 5: Trade-Down and Trade-Up Patterns
Consumer shifts within categories reveal economic stress or confidence:
- **Trade-down signals:** Private label share gains, fast food outperforming casual dining, discount retail gaining share — indicates stressed consumer
- **Trade-up signals:** Premium brand outperformance, luxury resilience, experience spending growth — indicates confident consumer

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
