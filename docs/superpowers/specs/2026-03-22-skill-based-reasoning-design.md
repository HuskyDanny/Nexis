# Skill-Based Agent Reasoning Design

**Goal:** Replace monolithic hardcoded agent prompts with a dynamic skill system where skills are file-based, auto-discovered, and loaded into agent context on demand — following the Claude Code pattern.

**Architecture:** Skills are Python files with a `SKILL` dict. Descriptions injected into system message (permanent, lightweight). Full content loaded via `load_skill` tool call into conversation context (on demand). Agent decides which skills to load based on the reasoning context.

**Tech Stack:** CrewAI agents + tools, Python dynamic module loading, existing SiliconFlow LLM

---

## 1. Skill Definition

Each skill is a standalone `.py` file in `backend/src/agents/skills/`:

```python
# backend/src/agents/skills/macro_economics.py
SKILL = {
    "name": "macro_economics",
    "description": "GDP, inflation, interest rates, employment, monetary/fiscal policy",
    "content": """
## Macro Economics Analysis Framework
[Full analytical methodology, reasoning templates, output format]
""",
}
```

Three fields only: `name`, `description`, `content`. No registration code needed.

## 2. Auto-Discovery Registry

`backend/src/agents/skills/__init__.py` scans all `.py` files in the skills directory at import time using `pkgutil.iter_modules`. Any file with a `SKILL` dict is registered. Adding a new skill = dropping a new file. No imports, no config, no hardcoded lists.

## 3. Two-Phase Context Injection (Claude Code Pattern)

**Phase 1 — System message (permanent, lightweight):**
Skill descriptions embedded in the agent's system prompt. Always present, low token cost.

```
You are a senior financial analyst. You can load analytical skills
for deeper domain expertise. Use the Load Skill tool when you need
specialized knowledge for your analysis.

Available skills:
- macro_economics: GDP, inflation, interest rates, monetary/fiscal policy
- geopolitical_risk: Wars, sanctions, trade tensions, alliances
- sector_rotation: Which sectors win/lose from macro shifts
[auto-generated from registry]
```

**Phase 2 — Tool result (on demand, in conversation):**
When the agent calls `load_skill("macro_economics")`, the full skill content is returned as a tool result. This appears in the conversation context (not system message), giving the agent deep expertise for that specific reasoning turn.

**Key properties:**
- System message: descriptions only (cheap, permanent)
- Tool result: full content (loaded on demand, conversation history)
- Agent decides what to load (no external router, no pre-filter)
- Multiple skills can be loaded per turn

## 4. The `load_skill` Tool

A CrewAI `@tool` that the agent calls like any other tool:

```python
@tool("Load Skill")
def load_skill(skill_name: str) -> str:
    """Load an analytical skill for deeper domain expertise.
    Call this before analyzing a topic that matches a skill."""
    skill = registry.get_skill(skill_name)
    if not skill:
        return f"Skill '{skill_name}' not found. Available: {registry.list_skills()}"
    return skill["content"]
```

## 5. Integration with Thinking Pipeline

The thinking crew at each layer:
1. Receives parent nodes + Perigon metadata as user context
2. Has skill descriptions in system message (always)
3. Agent reads context, decides which skills are relevant
4. Agent calls `load_skill` for each needed skill (tool calls)
5. Agent reasons with loaded skill expertise
6. Output validated by `after_think` hook

**Lifecycle hooks on each layer:**
- `before_think`: Assemble system message with skill descriptions + parent context
- `think`: Agent runs — loads skills via tool, then reasons
- `after_think`: Validate output structure, ensure scope/impact scored
- `on_error`: Log, mark layer as failed, allow retry

## 6. Initial Skills (8)

| Skill File | Name | What it provides |
|-----------|------|-----------------|
| `macro_economics.py` | macro_economics | Rate transmission, inflation chains, growth outlook |
| `geopolitical_risk.py` | geopolitical_risk | Supply disruption, risk premium, alliance shifts |
| `sector_rotation.py` | sector_rotation | Sector winners/losers from macro shifts |
| `company_fundamentals.py` | company_fundamentals | P/E context, competitive moat, earnings quality |
| `technical_momentum.py` | technical_momentum | Price action, support/resistance, volume signals |
| `regulatory_impact.py` | regulatory_impact | Policy effects, compliance costs, market access |
| `consumer_behavior.py` | consumer_behavior | Spending shifts, demand elasticity, sentiment |
| `supply_chain.py` | supply_chain | Logistics disruption, bottlenecks, trade routes |

## 7. Macro-First Reasoning Quality

Each skill's `content` enforces the macro-first analytical principle:
- Start from the broadest impact
- Trace transmission mechanisms step by step
- Identify second-order effects
- End with specific sector/company implications
- State confidence with reasoning

Output format standardized across skills:
```
Primary effect: [one sentence]
Transmission: [mechanism chain: A → B → C]
Scope: [1-5, with justification]
Impact: [1-5, with justification]
Winners: [sectors/industries]
Losers: [sectors/industries]
Confidence: [high/medium/low] — [why]
```

## 8. File Structure

```
backend/src/agents/skills/
├── __init__.py              # Auto-discovery registry
├── base.py                  # load_skill tool definition
├── macro_economics.py       # SKILL dict
├── geopolitical_risk.py
├── sector_rotation.py
├── company_fundamentals.py
├── technical_momentum.py
├── regulatory_impact.py
├── consumer_behavior.py
└── supply_chain.py
```

## 9. Adding New Skills

To add a new skill, create a file:
```python
# backend/src/agents/skills/currency_fx.py
SKILL = {
    "name": "currency_fx",
    "description": "Foreign exchange, currency strength, cross-border capital flows",
    "content": """...""",
}
```

No other changes needed. Next agent run picks it up automatically.
