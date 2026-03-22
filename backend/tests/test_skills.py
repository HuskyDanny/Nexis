"""Tests for the skill-based reasoning system."""

from src.agents.skills import (
    get_all_descriptions,
    list_skills,
    get_skill,
    get_skill_count,
)
from src.agents.skills.base import build_system_prompt


class TestSkillRegistry:
    def test_discovers_all_skills(self):
        assert get_skill_count() == 8

    def test_list_skills_returns_names(self):
        names = list_skills()
        assert "macro_economics" in names
        assert "geopolitical_risk" in names
        assert "sector_rotation" in names
        assert "company_fundamentals" in names
        assert "technical_momentum" in names
        assert "regulatory_impact" in names
        assert "consumer_behavior" in names
        assert "supply_chain" in names

    def test_get_skill_returns_dict(self):
        skill = get_skill("macro_economics")
        assert skill is not None
        assert "name" in skill
        assert "description" in skill
        assert "content" in skill
        assert skill["name"] == "macro_economics"

    def test_get_skill_content_is_substantial(self):
        skill = get_skill("macro_economics")
        assert len(skill["content"]) > 200  # Not trivially short

    def test_get_nonexistent_skill(self):
        assert get_skill("nonexistent") is None

    def test_descriptions_are_lightweight(self):
        desc = get_all_descriptions()
        assert len(desc) < 2000  # Should be compact
        assert "macro_economics" in desc
        assert "geopolitical_risk" in desc


class TestSystemPrompt:
    def test_build_system_prompt_includes_descriptions(self):
        prompt = build_system_prompt()
        assert "Available skills:" in prompt
        assert "macro_economics" in prompt
        assert "Load Skill" in prompt

    def test_build_system_prompt_macro_first_principle(self):
        prompt = build_system_prompt()
        assert "MACRO FIRST" in prompt

    def test_build_system_prompt_is_reasonable_length(self):
        prompt = build_system_prompt()
        assert 500 < len(prompt) < 5000  # Not too short, not too long


class TestSkillContent:
    def test_each_skill_has_output_format(self):
        """Every skill should guide structured output."""
        for name in list_skills():
            skill = get_skill(name)
            content = skill["content"].lower()
            # Should mention some form of structured output
            assert any(
                kw in content
                for kw in ["output", "format", "return", "report", "assessment"]
            ), f"Skill {name} missing output guidance"

    def test_each_skill_has_substantial_content(self):
        for name in list_skills():
            skill = get_skill(name)
            assert len(skill["content"]) > 100, f"Skill {name} content too short"
