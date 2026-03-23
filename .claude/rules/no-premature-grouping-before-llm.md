# No Premature Grouping or Matching Before LLM Reasoning

## The Trap
Pre-grouping inputs by sector/category before sending to the LLM, or matching outputs by sector text overlap. Both lose cross-sector compounding signals. "China tariffs" (trade) + "AI chip demand" (tech) compound into one effect on NVIDIA — sector grouping splits them. "Fed rate pause" causes a fintech stock to recover — not same sector.

## The Solution
1. **Effects:** Let the LLM see ALL selected nodes together and infer what effects emerge. No pre-grouping.
2. **Matching:** Let the LLM reason causally: "this effect will cause this stock to recover because..." Not sector text matching.
3. Heuristic grouping is acceptable only as mock/placeholder logic, clearly marked for replacement.

## Context
- **When this applies:** Any pipeline step that feeds inputs to LLM reasoning or matches outputs to entities
- **Related files:** `backend/src/api/thinking.py` (step + match endpoints), pipeline strategies
- **Discovered:** 2026-03-22, user corrected: "if you do the heuristic before analysis, you might hurt the information mass"
