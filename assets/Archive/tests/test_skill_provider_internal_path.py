from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cryptotrader._compat import UTC

REPO_ROOT = Path(__file__).parent.parent
INTERNAL_SKILLS_DIR = REPO_ROOT / "agent_skills" / "_internal"


def _write_skill(
    skills_dir: Path,
    name: str,
    scope: str = "shared",
    regime_tags: list[str] | None = None,
    importance: float = 0.5,
    confidence: float = 0.5,
    access_count: int = 0,
) -> Path:
    path = skills_dir / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    regime_str = str(regime_tags or [])
    la = datetime.now(UTC).isoformat()
    content = f"""---
name: {name}
description: Test skill - internal path migration verification (spec 022).
scope: {scope}
version: "1.0"
manually_edited: false
regime_tags: {regime_str}
triggers_keywords: []
importance: {importance}
confidence: {confidence}
access_count: {access_count}
last_accessed_at: "{la}"
---

Body content for {name}.
"""
    path.write_text(content, encoding="utf-8")
    return path


class TestInternalPathStructure:
    def test_internal_dir_exists(self):
        assert INTERNAL_SKILLS_DIR.exists(), "agent_skills/_internal/ 目录不存在"

    def test_five_skill_dirs_under_internal(self):
        expected = [
            "tech-analysis",
            "chain-analysis",
            "news-analysis",
            "macro-analysis",
            "trading-knowledge",
        ]
        for name in expected:
            d = INTERNAL_SKILLS_DIR / name
            assert d.is_dir(), f"agent_skills/_internal/{name}/ 不存在"

    def test_each_internal_skill_has_skill_md(self):
        for skill_dir in INTERNAL_SKILLS_DIR.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                assert (skill_dir / "SKILL.md").exists(), f"agent_skills/_internal/{skill_dir.name}/SKILL.md 缺失"

    def test_old_top_level_dirs_no_longer_exist(self):
        old_dirs = [
            "tech-analysis",
            "chain-analysis",
            "news-analysis",
            "macro-analysis",
            "trading-knowledge",
        ]
        top_level = REPO_ROOT / "agent_skills"
        for name in old_dirs:
            old_path = top_level / name
            assert not old_path.exists(), f"旧路径 agent_skills/{name}/ 仍存在，应已迁移到 _internal/"


class TestEvolvingSkillProviderFromInternalPath:
    def test_default_skill_root_is_internal(self):
        from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

        provider = EvolvingSkillProvider()
        assert "_internal" in str(provider._skill_root), (
            f"默认 skill_root 未更新到 _internal/，当前值: {provider._skill_root}"
        )

    def test_loads_four_agent_skills_from_internal(self):
        from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

        provider = EvolvingSkillProvider(skill_root=INTERNAL_SKILLS_DIR)
        for agent_id in ("tech", "chain", "news", "macro"):
            result = provider.get_available_skills(f"{agent_id}_agent", {})
            assert len(result) >= 1, f"agent={agent_id} 未从 _internal/ 加载到任何 skill"

    def test_get_skill_by_name_from_internal(self, tmp_path):
        from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

        skills_dir = tmp_path / "_internal"
        _write_skill(skills_dir, "tech-analysis", scope="agent:tech")
        provider = EvolvingSkillProvider(skill_root=skills_dir)
        skill = provider.get_skill_by_name("tech-analysis")
        assert skill is not None
        assert skill.name == "tech-analysis"

    def test_scope_filter_works_in_internal(self, tmp_path):
        from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

        skills_dir = tmp_path / "_internal"
        _write_skill(skills_dir, "tech-only", scope="agent:tech")
        _write_skill(skills_dir, "shared-skill", scope="shared")
        provider = EvolvingSkillProvider(skill_root=skills_dir)

        tech_result = provider.get_available_skills("tech", {})
        chain_result = provider.get_available_skills("chain", {})

        tech_names = [s.name for s in tech_result]
        chain_names = [s.name for s in chain_result]

        assert "tech-only" in tech_names
        assert "shared-skill" in tech_names
        assert "tech-only" not in chain_names
        assert "shared-skill" in chain_names

    def test_access_count_written_back_in_internal(self, tmp_path):
        import json

        from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

        skills_dir = tmp_path / "_internal"
        skill_path = _write_skill(skills_dir, "shared-skill", scope="shared", access_count=3)
        provider = EvolvingSkillProvider(skill_root=skills_dir)
        provider.get_available_skills("tech", {})
        # access state persisted in sidecar, not SKILL.md.
        # sidecar starts at 0 when absent (frontmatter access_count is ignored at
        # runtime — sidecar is the single source of truth), so first access → 1.
        sidecar = skill_path.parent / ".access_state.json"
        assert sidecar.exists(), ".access_state.json sidecar 未生成"
        state = json.loads(sidecar.read_text(encoding="utf-8"))
        assert state["access_count"] == 1, f"期望 access_count=1（首次访问），实际={state['access_count']}"

    def test_empty_internal_dir_returns_empty(self, tmp_path):
        from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

        skills_dir = tmp_path / "_internal"
        skills_dir.mkdir()
        provider = EvolvingSkillProvider(skill_root=skills_dir)
        result = provider.get_available_skills("tech", {})
        assert result == []

    def test_nonexistent_internal_path_returns_empty(self):
        from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

        provider = EvolvingSkillProvider(skill_root=Path("/nonexistent/_internal"))
        result = provider.get_available_skills("tech", {})
        assert result == []
