"""The load_skill CrewAI tool — agents call this to load skill content into their context."""

from crewai.tools import tool

from src.agents.skills import get_skill, list_skills, get_all_descriptions


@tool("Load Skill")
def load_skill(skill_name: str) -> str:
    """Load an analytical skill for deeper domain expertise.
    Call this before analyzing a topic that matches a skill.
    The skill provides a detailed analytical framework and methodology."""
    skill = get_skill(skill_name)
    if not skill:
        available = ", ".join(list_skills())
        return f"Skill '{skill_name}' not found. Available skills: {available}"
    return skill["content"]


def build_system_prompt() -> str:
    """Build the system message with skill descriptions for agent initialization."""
    descriptions = get_all_descriptions()
    return f"""You are a senior financial analyst at a top-tier investment firm.
Your job is to analyze news events and reason about their market impact
through multiple layers of cause-and-effect thinking.

ANALYTICAL PRINCIPLE — MACRO FIRST:
Always start from the broadest scope (geopolitical, macroeconomic) and work
downward to sector-specific and company-specific implications. Never jump
directly to company conclusions without tracing the transmission mechanism.

SKILL SYSTEM:
You have access to analytical skills that provide deep domain expertise.
Before reasoning about a topic, use the Load Skill tool to load the relevant
skill(s). You may load multiple skills per analysis.

Available skills:
{descriptions}

IMPORTANT:
- Load skills BEFORE reasoning, not after
- You may load 1-3 skills per analysis depending on the topic
- If a news event spans multiple domains (e.g., Fed rate + housing), load multiple skills
- After loading skills, follow their analytical frameworks in your reasoning"""
