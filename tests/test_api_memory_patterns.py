"""Tests for GET /api/memory/patterns endpoint — spec 024 SC-P3.

5 cases:
  (a) total >= 3 (spec 021 already produced 3 patterns on disk)
  (b) ?agent=tech filter returns only tech patterns
  (c) ?maturity=observed filter
  (d) ?limit=2 truncates results
  (e) ?agent=news empty dir returns items=[] total=0 (no 500)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_MODE", "disabled")
os.environ.setdefault("API_KEY", "test-key-024")

# ── Pattern MD template ────────────────────────────────────────────────────────

_PATTERN_TEMPLATE = """\
---
name: {name}
agent: {agent}
description: "Auto-distilled pattern: {name} (from {n} cases)"
regime_tags: {regime_tags}
maturity: {maturity}
pnl_track:
  pnls: {pnls}
source_cycles: {source_cycles}
created: "2026-05-11T03:00:00Z"
version: 1
manually_edited: false
---

# {name}

Auto-distilled from {n} cases.
"""


def _write_pattern(
    memory_root: Path,
    agent: str,
    name: str,
    maturity: str = "observed",
    regime_tags: list[str] | None = None,
    pnls: list[float] | None = None,
    n: int = 6,
) -> Path:
    """Write a PatternRecord file to memory_root/<agent>/patterns/<name>.md."""
    patterns_dir = memory_root / agent / "patterns"
    patterns_dir.mkdir(parents=True, exist_ok=True)
    path = patterns_dir / f"{name}.md"
    path.write_text(
        _PATTERN_TEMPLATE.format(
            name=name,
            agent=agent,
            maturity=maturity,
            regime_tags=str(regime_tags or ["high_vol"]),
            pnls=str(pnls or [12.5, -3.2, 8.0]),
            source_cycles=str([f"cycle-{i}" for i in range(min(n, 5))]),
            n=n,
        ),
        encoding="utf-8",
    )
    return path


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def memory_root(tmp_path: Path) -> Path:
    """Create a temp memory dir with 3 patterns (simulating spec 021 output).

    tech:  volume-spike-rsi-overbought (observed)
    chain: on-chain-whale-accumulation (probationary)
    macro: high-funding-fade           (observed)
    """
    _write_pattern(tmp_path, "tech", "volume-spike-rsi-overbought", maturity="observed")
    _write_pattern(tmp_path, "chain", "on-chain-whale-accumulation", maturity="probationary")
    _write_pattern(tmp_path, "macro", "high-funding-fade", maturity="observed")
    return tmp_path


@pytest.fixture
def client(memory_root: Path) -> TestClient:
    """TestClient with the memory router's _MEMORY_ROOT pointed at memory_root."""
    from unittest.mock import patch

    import api.routes.memory as mem_module
    from api.main import app

    original = mem_module._MEMORY_ROOT
    mem_module._MEMORY_ROOT = memory_root

    with patch("api.routes.memory._MEMORY_ROOT", memory_root):
        yield TestClient(app, raise_server_exceptions=False)

    mem_module._MEMORY_ROOT = original


# ── (a) total >= 3 ────────────────────────────────────────────────────────────


class TestPatternsTotal:
    def test_total_gte_3(self, client: TestClient, memory_root: Path) -> None:
        """(a) spec 021 already produced >= 3 patterns -> total >= 3."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

    def test_response_schema_fields(self, client: TestClient, memory_root: Path) -> None:
        """Response contains all PatternRecordResponse fields."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns")

        assert resp.status_code == 200
        item = resp.json()["items"][0]
        for field in ("name", "agent", "description", "maturity", "regime_tags", "pnl_track", "source_cycles", "body"):
            assert field in item, f"缺少字段: {field}"


# ── (b) ?agent=tech filter ─────────────────────────────────────────────────────


class TestAgentFilter:
    def test_agent_tech_filter(self, client: TestClient, memory_root: Path) -> None:
        """(b) ?agent=tech returns only tech patterns."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?agent=tech")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["agent"] == "tech"

    def test_invalid_agent_returns_400(self, client: TestClient, memory_root: Path) -> None:
        """Invalid agent param returns 400."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?agent=invalid")

        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_query"


# ── (c) ?maturity=observed filter ─────────────────────────────────────────────


class TestMaturityFilter:
    def test_maturity_observed_filter(self, client: TestClient, memory_root: Path) -> None:
        """(c) ?maturity=observed filter returns only maturity=observed patterns."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?maturity=observed")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["maturity"] == "observed"

    def test_maturity_probationary_filter(self, client: TestClient, memory_root: Path) -> None:
        """maturity=probationary returns only probationary patterns."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?maturity=probationary")

        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["maturity"] == "probationary"

    def test_invalid_maturity_returns_400(self, client: TestClient, memory_root: Path) -> None:
        """Invalid maturity param returns 400."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?maturity=unknown_state")

        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_query"


# ── (d) ?limit=2 truncation ────────────────────────────────────────────────────


class TestLimitParam:
    def test_limit_truncates_results(self, client: TestClient, memory_root: Path) -> None:
        """(d) ?limit=2 truncates items to 2; total returns the pre-truncation count (>= 3)."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?limit=2")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 3

    def test_limit_0_returns_empty(self, client: TestClient, memory_root: Path) -> None:
        """?limit=0 returns items=[]; total still reflects the full match count (not zeroed by limit=0)."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?limit=0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] >= 3


# ── (e) ?agent=news empty dir returns items=[] total=0 (no 500) ───────────────


class TestEmptyDir:
    def test_empty_agent_dir_returns_empty(self, client: TestClient, memory_root: Path) -> None:
        """(e) ?agent=news -- news patterns dir does not exist -> items=[], total=0, no 500."""
        from unittest.mock import patch

        with patch("api.routes.memory._MEMORY_ROOT", memory_root):
            resp = client.get("/api/memory/patterns?agent=news")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_no_memory_root_returns_empty(self, tmp_path: Path) -> None:
        """memory_root completely empty (no subdirs) -> items=[], total=0, no 500."""
        from unittest.mock import patch

        import api.routes.memory as mem_module
        from api.main import app

        empty_root = tmp_path / "nonexistent_memory"

        original = mem_module._MEMORY_ROOT
        mem_module._MEMORY_ROOT = empty_root

        with patch("api.routes.memory._MEMORY_ROOT", empty_root):
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.get("/api/memory/patterns")

        mem_module._MEMORY_ROOT = original

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
