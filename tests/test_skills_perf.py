from __future__ import annotations

import time
from pathlib import Path


def _write_skill(tmp_path: Path, name: str = "perf-test", scope: str = "shared") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\nname: {name}\ndescription: perf test skill\nscope: {scope}\n---\n\n## Body\nContent here.\n"
    )
    return skill_file


def test_parse_skill_md_cache_hit_is_fast(tmp_path):
    from cryptotrader.agents.skills.loader import _clear_cache, parse_skill_md

    _clear_cache()
    skill_file = _write_skill(tmp_path)

    parse_skill_md(skill_file)

    start = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        parse_skill_md(skill_file)
    elapsed_ms = (time.perf_counter() - start) * 1000

    avg_ms = elapsed_ms / iterations
    assert avg_ms < 1.0, f"平均缓存命中耗时 {avg_ms:.3f}ms 超过 1ms 阈值"


def test_discover_skills_for_agent_is_fast(tmp_path):
    from cryptotrader.agents.skills.loader import _clear_cache, discover_skills_for_agent

    _clear_cache()

    agents = ["tech", "chain", "news", "macro"]
    for agent_id in agents:
        _write_skill(tmp_path, f"{agent_id}-analysis", scope=f"agent:{agent_id}")
    _write_skill(tmp_path, "trading-knowledge", scope="shared")

    discover_skills_for_agent("tech", skill_dir=tmp_path)

    start = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        discover_skills_for_agent("tech", skill_dir=tmp_path)
    elapsed_ms = (time.perf_counter() - start) * 1000

    avg_ms = elapsed_ms / iterations
    assert avg_ms < 10.0, f"平均 discover 耗时 {avg_ms:.3f}ms 超过 10ms 阈值"


def test_rate_limit_check_overhead_is_negligible():
    from cryptotrader.agents.skills.tool import _reset_call_counter

    _reset_call_counter("perf-trace-id")

    start = time.perf_counter()
    iterations = 1000
    for i in range(iterations):
        _reset_call_counter(f"perf-trace-{i}")
    elapsed_ms = (time.perf_counter() - start) * 1000

    avg_ms = elapsed_ms / iterations
    assert avg_ms < 0.1, f"平均 rate-limit 重置耗时 {avg_ms:.4f}ms 超过 0.1ms 阈值"


def test_get_available_skills_is_fast(tmp_path):
    from cryptotrader.agents.prompt_builder import DefaultSkillProvider
    from cryptotrader.agents.skills.loader import _clear_cache

    _clear_cache()
    _write_skill(tmp_path, "tech-analysis", scope="agent:tech")
    _write_skill(tmp_path, "trading-knowledge", scope="shared")

    provider = DefaultSkillProvider(skills_root=tmp_path)
    provider.get_available_skills("tech", snapshot={})

    start = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        provider.get_available_skills("tech", snapshot={})
    elapsed_ms = (time.perf_counter() - start) * 1000

    avg_ms = elapsed_ms / iterations
    assert avg_ms < 5.0, f"平均 get_available_skills 耗时 {avg_ms:.3f}ms 超过 5ms 阈值"
