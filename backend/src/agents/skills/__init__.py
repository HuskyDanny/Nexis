"""Skill auto-discovery registry.

Scans all .py files in this directory for a SKILL dict.
Drop a new file → it's automatically available. No registration needed.
"""

import importlib
import pkgutil
from pathlib import Path

from src.core.logger import get_logger

log = get_logger("skills")

_skills: dict[str, dict] = {}
_scanned = False


def _scan_skills():
    """Import every module in skills/, collect SKILL dicts."""
    global _scanned
    if _scanned:
        return
    skills_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(skills_dir)]):
        if module_info.name.startswith("_") or module_info.name == "base":
            continue
        try:
            mod = importlib.import_module(f".{module_info.name}", package=__name__)
            if hasattr(mod, "SKILL"):
                skill = mod.SKILL
                _skills[skill["name"]] = skill
        except Exception as e:
            log.warning("Failed to load skill module %s: %s", module_info.name, e)
    _scanned = True


def get_all_descriptions() -> str:
    """Lightweight descriptions for system message injection."""
    _scan_skills()
    return "\n".join(f"- {s['name']}: {s['description']}" for s in _skills.values())


def get_descriptions_for(skill_names: list[str]) -> str:
    """Lightweight descriptions filtered to the given skill names."""
    _scan_skills()
    return "\n".join(
        f"- {s['name']}: {s['description']}"
        for s in _skills.values()
        if s["name"] in skill_names
    )


def get_skill(name: str) -> dict | None:
    """Get full skill dict by name."""
    _scan_skills()
    return _skills.get(name)


def list_skills() -> list[str]:
    """List all available skill names."""
    _scan_skills()
    return list(_skills.keys())


def get_skill_count() -> int:
    _scan_skills()
    return len(_skills)
