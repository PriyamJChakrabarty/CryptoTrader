"""Project-level constants — Agent Skills submodule."""

from pathlib import Path

VALID_AGENT_IDS: frozenset[str] = frozenset({"tech", "chain", "news", "macro"})

DEFAULT_AGENT_SKILLS_DIR = Path("agent_skills/_internal")

# initial 5 skill directory names (used by ensure_skill_dirs)
_INITIAL_SKILL_DIRS = [
    "tech-analysis",
    "chain-analysis",
    "news-analysis",
    "macro-analysis",
    "trading-knowledge",
]
