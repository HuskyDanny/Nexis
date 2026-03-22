SKILL = {
    "name": "company_fundamentals",
    "description": "Evaluate company financial health, earnings quality, and competitive positioning",
    "content": """You are analyzing a company's fundamentals. Follow this framework strictly.

## Step 1: Earnings Quality Assessment
Not all earnings are equal. Evaluate the composition:
- **Revenue quality:** Recurring vs. one-time? Organic vs. acquisition-driven? Concentrated vs. diversified customer base?
- **Margin trajectory:** Expanding (operating leverage, pricing power) or compressing (cost inflation, competition)?
- **Cash conversion:** Net income vs. operating cash flow — large divergence signals accrual manipulation, aggressive revenue recognition, or heavy working capital needs
- **Earnings surprises:** Consistent beats suggest sandbagging (positive). Consistent misses suggest structural deterioration.

## Step 2: Valuation in Context
Raw multiples are meaningless without context:
- **P/E ratio:** Compare to sector median, historical range, and growth rate. A P/E of 30 is cheap at 40% growth, expensive at 5%.
- **PEG ratio:** P/E divided by earnings growth rate — below 1.0 suggests undervaluation relative to growth
- **EV/EBITDA:** Better for capital-intensive or high-debt companies. Normalizes for capital structure differences.
- **Price/FCF:** Most reliable for mature companies. Free cash flow is harder to manipulate than earnings.
- **Relative valuation:** Always compare to 3-5 closest peers, not the broad market.

## Step 3: Competitive Moat Analysis
Classify the moat type and assess its durability:
- **Brand moat:** Pricing power from brand loyalty (test: can they raise prices without losing share?)
- **Network effect:** Value increases with users (test: would a competitor with identical product but no users succeed?)
- **Cost advantage:** Structural cost leadership from scale, geography, or technology (test: can competitors replicate the cost structure?)
- **Switching costs:** Customer lock-in through integration, data, or workflow dependency (test: what is the customer's cost to switch?)
- **Regulatory moat:** Licenses, patents, government contracts (test: how long until protection expires or changes?)

## Step 4: Balance Sheet Health
Assess survival and flexibility:
- **Debt/EBITDA:** Below 2x is healthy, 2-4x is manageable, above 4x is stressed
- **Interest coverage:** EBIT/interest expense — below 3x is a warning, below 1.5x is danger
- **Maturity wall:** When does debt come due? Refinancing risk in a high-rate environment?
- **Cash runway:** For unprofitable companies — months of cash at current burn rate
- **Off-balance-sheet:** Operating leases, pension obligations, contingent liabilities

## Step 5: Peer Comparison
Rank the company within its competitive set on: growth rate, margins, valuation, balance sheet strength, and moat durability. Identify where it is best-in-class vs. lagging.

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
