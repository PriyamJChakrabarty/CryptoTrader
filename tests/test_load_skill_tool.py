"""Tests for US4: load_skill tool I/O (FR-021 / FR-022 / FR-023 / FR-025).

TDD: starts FAIL, turns GREEN after agents/skills/tool.py is implemented.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _write_skill(skills_dir: Path, name: str, scope: str = "shared") -> Path:
    path = skills_dir / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""---
name: {name}
description: Test skill description that is at least 30 chars.
scope: {scope}
version: "1.0"
manually_edited: false
---

Body content for skill {name}.
"""
    path.write_text(content, encoding="utf-8")
    return path


class TestLoadSkillFunction:
    def test_skill_exists_returns_body(self, tmp_path):
        """When the skill exists, return a dict containing the body (FR-022)."""
        from cryptotrader.agents.skills.tool import load_skill

        skills_dir = tmp_path / "agent_skills"
        _write_skill(skills_dir, "trading-knowledge")

        result = load_skill("trading-knowledge", skill_dir=skills_dir)
        assert isinstance(result, dict)
        assert result.get("name") == "trading-knowledge"
        assert "Body content for skill trading-knowledge" in result.get("body", "")

    def test_skill_not_found_returns_error(self, tmp_path):
        """A nonexistent skill returns a skill_not_found error (FR-025 + load_skill.contract.md)."""
        from cryptotrader.agents.skills.tool import load_skill

        skills_dir = tmp_path / "agent_skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        result = load_skill("nonexistent", skill_dir=skills_dir)
        assert result.get("error") == "skill_not_found"
        assert result.get("name") == "nonexistent"

    def test_corrupt_file_returns_error(self, tmp_path):
        """When frontmatter is corrupt, return a corrupt_file error."""
        from cryptotrader.agents.skills.tool import load_skill

        skills_dir = tmp_path / "agent_skills"
        bad = skills_dir / "bad-skill" / "SKILL.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("no frontmatter here at all", encoding="utf-8")

        result = load_skill("bad-skill", skill_dir=skills_dir)
        assert result.get("error") in ("corrupt_file", "skill_not_found"), (
            f"损坏文件应返回 corrupt_file 或 skill_not_found，实际: {result}"
        )

    def test_rate_limit_per_cycle_on_11th_call(self, tmp_path):
        """The 11th call with the same trace_id should return rate_limit_per_cycle (FR-025)."""
        from cryptotrader.agents.skills.tool import _reset_call_counter, load_skill

        skills_dir = tmp_path / "agent_skills"
        _write_skill(skills_dir, "trading-knowledge")

        trace_id = "test-trace-001"
        _reset_call_counter(trace_id)

        # The first 10 calls should succeed
        for i in range(10):
            result = load_skill("trading-knowledge", skill_dir=skills_dir, trace_id=trace_id)
            assert result.get("error") != "rate_limit_per_cycle", f"第 {i + 1} 次不应限流"

        # The 11th call should be rate-limited
        result = load_skill("trading-knowledge", skill_dir=skills_dir, trace_id=trace_id)
        assert result.get("error") == "rate_limit_per_cycle", "第 11 次应返回 rate_limit_per_cycle"


class TestLoadSkillToolProviderInjection:
    def test_provider_path_returns_skill_body(self):
        """When provider is non-None, go through provider.get_skill_by_name(name)."""
        from unittest.mock import MagicMock

        from cryptotrader.agents.skills.tool import _make_load_skill_tool

        mock_skill = MagicMock()
        mock_skill.body = "Provider skill body content"
        mock_provider = MagicMock()
        mock_provider.get_skill_by_name.return_value = mock_skill

        tool = _make_load_skill_tool(provider=mock_provider)
        assert tool is not None
        result = tool.invoke({"name": "tech-analysis"})
        assert result == "Provider skill body content"
        mock_provider.get_skill_by_name.assert_called_once_with("tech-analysis")

    def test_provider_returns_none_gives_error_message(self):
        """When provider.get_skill_by_name returns None, return an error string."""
        from unittest.mock import MagicMock

        from cryptotrader.agents.skills.tool import _make_load_skill_tool

        mock_provider = MagicMock()
        mock_provider.get_skill_by_name.return_value = None

        tool = _make_load_skill_tool(provider=mock_provider)
        assert tool is not None
        result = tool.invoke({"name": "missing-skill"})
        assert "Error" in result
        assert "missing-skill" in result

    def test_provider_exception_gives_error_message(self):
        """When provider.get_skill_by_name raises, return an error string."""
        from unittest.mock import MagicMock

        from cryptotrader.agents.skills.tool import _make_load_skill_tool

        mock_provider = MagicMock()
        mock_provider.get_skill_by_name.side_effect = RuntimeError("db gone")

        tool = _make_load_skill_tool(provider=mock_provider)
        assert tool is not None
        result = tool.invoke({"name": "tech-analysis"})
        assert "Error" in result

    def test_provider_none_fallback_to_file_not_found(self, tmp_path):
        """When provider=None, fall back to the spec 014 file-read path."""
        from cryptotrader.agents.skills.tool import _make_load_skill_tool

        skills_dir = tmp_path / "agent_skills"
        skills_dir.mkdir()
        tool = _make_load_skill_tool(provider=None, skill_dir=skills_dir)
        assert tool is not None
        result = tool.invoke({"name": "nonexistent"})
        assert "Error" in result
        assert "nonexistent" in result
