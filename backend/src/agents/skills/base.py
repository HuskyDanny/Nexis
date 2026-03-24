"""The load_skill CrewAI tool — agents call this to load skill content into their context."""

from crewai.tools import tool

from src.agents.skills import (
    get_skill,
    list_skills,
    get_all_descriptions,
    get_descriptions_for,
)


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


def build_system_prompt(allowed_skills: list[str] | None = None) -> str:
    """Build the system message with skill descriptions for agent initialization.

    Args:
        allowed_skills: If provided, only include descriptions for these skill names.
                        If None, include all available skills.
    """
    descriptions = (
        get_descriptions_for(allowed_skills)
        if allowed_skills is not None
        else get_all_descriptions()
    )
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


def build_system_prompt_with_skills(allowed_skills: list[str] | None = None) -> str:
    """Build system message with full skill content pre-loaded.

    Unlike ``build_system_prompt`` which tells the agent to use a tool to load
    skills, this embeds the full skill frameworks directly into the prompt.
    More reliable with models that don't support tool calling well.
    """
    skill_names = allowed_skills or list_skills()
    skill_blocks: list[str] = []
    for name in skill_names:
        skill = get_skill(name)
        if skill:
            skill_blocks.append(
                f"### {skill['name']}: {skill['description']}\n{skill['content']}"
            )

    skills_text = "\n\n".join(skill_blocks) if skill_blocks else "(no skills loaded)"

    return f"""You are a senior financial analyst at a top-tier investment firm.
Your job is to analyze news events and reason about their market impact
through multiple layers of cause-and-effect thinking.

ANALYTICAL PRINCIPLE — MACRO FIRST:
Always start from the broadest scope (geopolitical, macroeconomic) and work
downward to sector-specific and company-specific implications. Never jump
directly to company conclusions without tracing the transmission mechanism.

ANALYTICAL FRAMEWORKS:
Apply the following skill frameworks in your reasoning:

{skills_text}

IMPORTANT:
- Apply the relevant skill frameworks above in your analysis
- If an event spans multiple domains, combine insights from multiple frameworks
- Always return ONLY valid JSON as specified in the task — no prose, no tool calls"""
