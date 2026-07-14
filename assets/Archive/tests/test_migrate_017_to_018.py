from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from migrate_017_to_018 import (  # noqa: E402
    _case_needs_migration,
    _pattern_needs_migration,
    _split_frontmatter,
    migrate_case,
    migrate_pattern,
    run_migration,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "memory_old_format"


def _copy_fixture_to_tmp(tmp_path: Path) -> Path:
    """Copy the fixture directory to tmp_path and return the new path (test isolation)."""
    dest = tmp_path / "memory_old_format"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    result = _split_frontmatter(content)
    assert result is not None, f"frontmatter 解析失败: {path}"
    return result[0]


def _read_body(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    result = _split_frontmatter(content)
    assert result is not None
    return result[1]


def test_case_migration_adds_three_sections(tmp_path: Path):
    """T008(a): after migration, an old case contains Trade Execution / Causal Chain / IVE Classification."""
    root = _copy_fixture_to_tmp(tmp_path)
    case_path = root / "cases" / "old_case_001.md"

    migrated = migrate_case(case_path, dry_run=False)
    assert migrated is True

    body = _read_body(case_path)
    assert "## Trade Execution" in body
    assert "## Causal Chain" in body
    assert "## IVE Classification" in body


def test_pattern_migration_adds_five_fields(tmp_path: Path):
    """T008(b): after migration, an old pattern contains 5 new fields."""
    root = _copy_fixture_to_tmp(tmp_path)
    pattern_path = root / "tech" / "patterns" / "breakout_continuation.md"

    migrated = migrate_pattern(pattern_path, dry_run=False)
    assert migrated is True

    fm = _read_frontmatter(pattern_path)
    assert "importance" in fm
    assert "access_count" in fm
    assert "last_accessed_at" in fm
    assert "last_modified_at" in fm
    assert "fundamental_failure_streak" in fm

    assert fm["importance"] == 0.5
    assert fm["access_count"] == 0
    assert fm["fundamental_failure_streak"] == 0


def test_migration_idempotent(tmp_path: Path):
    """T008(c): re-running the migration script does not corrupt data (idempotency)."""
    root = _copy_fixture_to_tmp(tmp_path)

    # First migration
    stats1 = run_migration(root, dry_run=False)
    assert stats1["cases_migrated"] > 0
    assert stats1["patterns_migrated"] > 0

    # Read content after migration
    case_path = root / "cases" / "old_case_001.md"
    content_after_1 = case_path.read_text(encoding="utf-8")

    # Second migration
    stats2 = run_migration(root, dry_run=False)
    assert stats2["cases_migrated"] == 0  # all skipped
    assert stats2["cases_skipped"] >= 1
    assert stats2["patterns_migrated"] == 0
    assert stats2["patterns_skipped"] >= 1

    # Content unchanged
    content_after_2 = case_path.read_text(encoding="utf-8")
    assert content_after_1 == content_after_2


def test_dry_run_does_not_modify_files(tmp_path: Path):
    """T008(d): dry_run=True does not modify any files."""
    root = _copy_fixture_to_tmp(tmp_path)

    case_path = root / "cases" / "old_case_001.md"
    original_content = case_path.read_text(encoding="utf-8")

    stats = run_migration(root, dry_run=True)
    assert stats["cases_migrated"] > 0  # dry-run returns the count "to be migrated"

    # File unmodified
    assert case_path.read_text(encoding="utf-8") == original_content


def test_corrupted_frontmatter_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """T008(e): when frontmatter is corrupted, skip the file and warn."""
    bad_case = tmp_path / "bad_case.md"
    bad_case.write_text("not a valid frontmatter\n\nbody here", encoding="utf-8")

    with caplog.at_level("WARNING"):
        result = migrate_case(bad_case, dry_run=False)

    assert result is False
    assert any(
        "frontmatter 损坏" in r.message or "无法找到" in r.message or "损坏" in r.message for r in caplog.records
    )


def test_backup_suggestion_printed(tmp_path: Path, capsys: pytest.CaptureFixture):
    """T008(f): a backup suggestion is printed when migration starts."""
    # Calling main directly is complicated by path arguments; instead check main's output
    # via subprocess, testing --dry-run mode
    import subprocess

    root = _copy_fixture_to_tmp(tmp_path)
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / "migrate_017_to_018.py"), "--dry-run", "--memory-root", str(root)],
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    assert "backup" in combined.lower() or "备份" in combined


def test_already_migrated_case_skipped(tmp_path: Path):
    """T008(g): a case that already has a Trade Execution section is not migrated again."""
    case_path = tmp_path / "already_migrated.md"
    case_path.write_text(
        "---\ncycle_id: abc\ntimestamp: '2026-01-01T00:00:00+00:00'\npair: BTC/USDT\n---\n"
        "## Agent Analyses\nContent\n\n## Trade Execution\n- entry_price: 50000\n",
        encoding="utf-8",
    )

    result = migrate_case(case_path, dry_run=False)
    assert result is False  # skipped, not modified


def test_already_migrated_pattern_skipped(tmp_path: Path):
    """T008(h): a pattern that already has the importance field is not migrated again."""
    pattern_path = tmp_path / "already_migrated_pattern.md"
    pattern_path.write_text(
        "---\nname: test\nagent: tech\ndescription: desc\nmaturity: active\n"
        "importance: 0.8\naccess_count: 5\nlast_accessed_at: '2026-01-01T00:00:00+00:00'\n"
        "last_modified_at: '2026-01-01T00:00:00+00:00'\nfundamental_failure_streak: 0\n---\n"
        "## Rule\nBody content",
        encoding="utf-8",
    )

    result = migrate_pattern(pattern_path, dry_run=False)
    assert result is False  # skipped


def test_run_migration_stats(tmp_path: Path):
    """Overall migration stats are correct (1 case + 2 patterns)."""
    root = _copy_fixture_to_tmp(tmp_path)
    stats = run_migration(root, dry_run=False)

    assert stats["cases_migrated"] == 1
    assert stats["cases_failed"] == 0
    assert stats["patterns_migrated"] == 2
    assert stats["patterns_failed"] == 0


def test_case_needs_migration_flag():
    """Migration is needed when the body lacks the new sections, otherwise not."""
    assert _case_needs_migration("## Agent Analyses\nContent") is True
    assert _case_needs_migration("## Trade Execution\n- entry_price: null") is False


def test_pattern_needs_migration_flag():
    """Migration is needed when fm lacks importance, otherwise not."""
    assert _pattern_needs_migration({"name": "x", "maturity": "active"}) is True
    assert _pattern_needs_migration({"name": "x", "importance": 0.5}) is False
