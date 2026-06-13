"""SKILL.md loader — parse + in-process LRU cache (mtime invalidation).

FR-019a: scans agent_skills/*/SKILL.md, filters by frontmatter scope;
          in-process LRU cache (max 32 entries), compares disk mtime on each
          access and reloads if it differs.
FR-004b: does not hardcode a skill name -> agent mapping; discovers dynamically
          via frontmatter scope.
FR-024: on load failure -> logger.warning + skip, does not block the cycle.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cryptotrader.agents.skills._constants import DEFAULT_AGENT_SKILLS_DIR
from cryptotrader.agents.skills._frontmatter import (
    CorruptFrontmatterError,
    parse_frontmatter,
    validate_skill_frontmatter,
)
from cryptotrader.agents.skills.schema import Skill

logger = logging.getLogger(__name__)

# ── In-process LRU cache (max 32 SKILL.md parse results) ──
# key: str(path) -> (mtime: float, Skill)
_skill_cache: dict[str, tuple[float, Skill]] = {}
_CACHE_MAX = 32


def _clear_cache() -> None:
    """Clear the LRU cache (mainly used for testing)."""
    _skill_cache.clear()


def parse_skill_md(path: Path) -> Skill | None:
    """Parse a single SKILL.md file and return a Skill object.

    On failure, logger.warning + returns None (FR-024).
    Uses an in-process mtime cache (FR-019a).
    """
    try:
        current_mtime = path.stat().st_mtime
    except OSError:
        logger.warning("Skill file not found: %s", path)
        return None

    cache_key = str(path)
    cached = _skill_cache.get(cache_key)
    if cached is not None:
        cached_mtime, cached_skill = cached
        if cached_mtime == current_mtime:
            return cached_skill

    try:
        content = path.read_text(encoding="utf-8")
        data, body = parse_frontmatter(content, path=path)
        validate_skill_frontmatter(data, path=path)

        skill = Skill(
            name=str(data["name"]),
            description=str(data["description"]),
            scope=str(data["scope"]),
            body=body,
            file_path=path,
            manually_edited=bool(data.get("manually_edited", False)),
            version=str(data.get("version", "1.0")),
            mtime=current_mtime,
        )

        # Write to cache (LRU: evict oldest entry when over the limit)
        if len(_skill_cache) >= _CACHE_MAX:
            oldest_key = next(iter(_skill_cache))
            del _skill_cache[oldest_key]
        _skill_cache[cache_key] = (current_mtime, skill)
        return skill

    except CorruptFrontmatterError as exc:
        logger.warning("Skill frontmatter corrupt: %s — %s", path, exc)
        return None
    except Exception as exc:
        logger.warning("Failed to load skill %s: %s", path, exc)
        return None


def discover_skills_for_agent(
    agent_id: str,
    skill_dir: Path | None = None,
) -> list[Skill]:
    """Dynamically discover and load all skills matching agent_id.

    FR-004b: discovers via the agent_skills/*/SKILL.md frontmatter scope
             field instead of hardcoding a skill->agent mapping.
    FR-019: match condition: scope == "shared" or scope == "agent:<agent_id>".
    FR-019a: mtime invalidation cache; adding/removing/modifying skill files
             is automatically reflected on the next cycle.
    FR-024: a single SKILL.md load failure is skipped + warned, does not
             block the cycle.
    """
    base = skill_dir or DEFAULT_AGENT_SKILLS_DIR
    if not base.exists():
        logger.warning("agent_skills directory not found: %s", base)
        return []

    result: list[Skill] = []
    for skill_dir_entry in sorted(base.iterdir()):
        if not skill_dir_entry.is_dir() or skill_dir_entry.name.startswith("."):
            continue
        skill_md = skill_dir_entry / "SKILL.md"
        if not skill_md.exists():
            continue
        skill = parse_skill_md(skill_md)
        if skill is None:
            continue  # parse_skill_md already warned

        # Filter by scope
        if skill.is_shared or (skill.scope == f"agent:{agent_id}"):
            result.append(skill)

    return result
