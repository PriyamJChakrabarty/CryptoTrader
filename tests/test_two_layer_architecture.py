from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


class TestGitignore:
    def test_gitignore_contains_agent_memory(self):
        gitignore = REPO_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore 文件不存在"
        content = gitignore.read_text(encoding="utf-8")
        assert "agent_memory/" in content, ".gitignore 必须包含 agent_memory/ 条目"


class TestAgentSkillsDirectory:
    def test_initial_five_skill_dirs_exist(self):
        skills_dir = REPO_ROOT / "agent_skills" / "_internal"
        expected = [
            "tech-analysis",
            "chain-analysis",
            "news-analysis",
            "macro-analysis",
            "trading-knowledge",
        ]
        assert skills_dir.exists(), "agent_skills/_internal/ 目录不存在"
        for name in expected:
            assert (skills_dir / name).is_dir(), f"agent_skills/_internal/{name}/ 目录不存在"

    def test_each_skill_dir_has_skill_md(self):
        skills_dir = REPO_ROOT / "agent_skills" / "_internal"
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                skill_md = skill_dir / "SKILL.md"
                assert skill_md.exists(), f"_internal/{skill_dir.name}/SKILL.md 不存在"

    def test_skill_md_frontmatter_compliant(self):
        from cryptotrader.agents.skills._frontmatter import parse_frontmatter, validate_skill_frontmatter

        skills_dir = REPO_ROOT / "agent_skills" / "_internal"
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            content = skill_md.read_text(encoding="utf-8")
            data, _ = parse_frontmatter(content, path=skill_md)
            validate_skill_frontmatter(data, path=skill_md)
            assert data["name"], f"_internal/{skill_dir.name}/SKILL.md 缺少 name 字段"
            assert data["description"], f"_internal/{skill_dir.name}/SKILL.md 缺少 description 字段"
            assert data["scope"], f"_internal/{skill_dir.name}/SKILL.md 缺少 scope 字段"

    def test_agent_skills_tracked_by_git(self):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "agent_skills/"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        # exit code 1 = not ignored (we expect agent_skills/ to NOT be gitignored)
        assert result.returncode != 0, "agent_skills/ 不应该被 .gitignore 排除"

    def test_agent_memory_not_tracked_by_git(self):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "agent_memory/"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        # exit code 0 = IS ignored (we expect agent_memory/ to be ignored)
        assert result.returncode == 0, "agent_memory/ 应该被 .gitignore 排除"
