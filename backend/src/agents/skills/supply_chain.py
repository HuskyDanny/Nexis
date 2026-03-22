SKILL = {
    "name": "supply_chain",
    "description": "Analyze supply chain disruptions, logistics bottlenecks, and inventory dynamics",
    "content": """You are analyzing a supply chain development. Follow this framework strictly.

## Step 1: Identify the Disruption Type
- **Chokepoint disruption:** Physical bottleneck at a critical transit point — Suez Canal, Strait of Malacca, Panama Canal, major ports (Shanghai, Rotterdam, LA/Long Beach). Impact is immediate and broad.
- **Production disruption:** Factory shutdown, natural disaster, energy crisis in a manufacturing hub — impact depends on concentration and substitutability.
- **Logistics disruption:** Shipping capacity constraints, container shortages, trucking/rail bottlenecks, port congestion — raises transit costs and delivery times.
- **Trade policy disruption:** Tariffs, export controls, sanctions, local content requirements — reshapes trade flows structurally.
- **Inventory cycle:** Bullwhip amplification, destocking, restocking — cyclical and often self-correcting but can amplify commodity swings.

## Step 2: Map Commodity and Input Dependency
Trace what depends on the disrupted source:
- **Single-source dependency:** Which inputs come predominantly from the affected region? (e.g., Taiwan — advanced semiconductors; China — rare earths, active pharma ingredients; Russia — palladium, enriched uranium)
- **Substitution options:** Can alternative suppliers fill the gap? At what cost premium and lead time?
- **Downstream propagation:** Which finished goods depend on the disrupted input? Trace the full bill-of-materials chain from raw material to end product.

## Step 3: Assess the Bullwhip Effect
Small demand signals amplify as they move upstream:
- **Demand signal → Retailer overorders → Distributor overorders more → Manufacturer scales up excessively → Commodity price spike**
- **Then demand softens → Excess inventory at every level → Destocking cascade → Commodity price crash**
- **Key question:** Where are we in the cycle? Early disruption (prices rising, shortage fear) or late cycle (inventory glut building, demand normalizing)?

## Step 4: Just-in-Time vs. Just-in-Case Shift
Assess the structural vs. cyclical response:
- **JIT (lean inventory):** Cost-efficient but fragile. Works in stable environments. Breaks under disruption.
- **JIC (buffer inventory):** Higher carrying cost but resilient. Companies shift to JIC after disruptions — raises demand for warehousing, inventory management, working capital.
- **Nearshoring/reshoring:** Companies moving production closer to end markets — benefits domestic manufacturing, industrial automation, logistics providers. Cost-inflationary but risk-reducing.
- **Dual-sourcing:** Qualifying backup suppliers in different geographies — increases procurement complexity and cost but reduces single-point-of-failure risk.

## Step 5: Price and Margin Transmission
Supply chain disruption flows through the P&L:
- **Input cost increase:** Raw material and logistics costs rise → gross margin compression for companies without pricing power
- **Pass-through ability:** Companies with strong brands or inelastic demand pass costs to consumers (inflationary). Commodity businesses and low-margin retailers absorb costs (margin destruction).
- **Inventory valuation:** Companies holding inventory before the disruption benefit from FIFO gains. Companies needing to procure at new prices face immediate cost inflation.
- **Lead time extension:** Longer lead times → higher safety stock requirements → working capital tied up → cash flow pressure

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
