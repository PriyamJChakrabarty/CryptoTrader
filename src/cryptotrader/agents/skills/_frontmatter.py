"""YAML frontmatter parsing and validation utilities.

Supports parsing three formats: SKILL.md / pattern_record.md / case_record.md.
On parse failure, raises CorruptFrontmatterError with path and line number.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class CorruptFrontmatterError(ValueError):
    """YAML frontmatter parse failure or validation failure."""

    def __init__(self, msg: str, path: Path | None = None, line: int | None = None) -> None:
        detail = msg
        if path:
            detail = f"{path}: {msg}"
        if line is not None:
            detail = f"{detail} (line {line})"
        super().__init__(detail)
        self.path = path
        self.line = line


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def parse_frontmatter(text: str, path: Path | None = None) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and body from markdown file content.

    Returns:
        (frontmatter_dict, body_str)

    Raises:
        CorruptFrontmatterError: frontmatter is missing or YAML parsing failed
    """
    import yaml

    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise CorruptFrontmatterError("缺少 YAML frontmatter（需以 '---' 开头）", path=path, line=1)

    yaml_str = m.group(1)
    body = m.group(2)

    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        line = None
        if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
            line = exc.problem_mark.line + 2  # +1 for '---' line, +1 for 1-indexed
        raise CorruptFrontmatterError(f"YAML 解析失败: {exc}", path=path, line=line) from exc

    if not isinstance(data, dict):
        raise CorruptFrontmatterError("frontmatter 必须是 YAML mapping", path=path, line=1)

    return data, body


def validate_skill_frontmatter(data: dict[str, Any], path: Path | None = None) -> None:
    """Validate required fields of SKILL.md frontmatter.

    Required: name, description, scope
    """
    required = ["name", "description", "scope"]
    for field in required:
        if not data.get(field):
            raise CorruptFrontmatterError(f"SKILL.md frontmatter 缺少必填字段: '{field}'", path=path)

    name = data["name"]
    if not re.match(r"^[a-z][a-z0-9-]*$", str(name)):
        raise CorruptFrontmatterError(f"SKILL.md name 格式不合规（必须 kebab-case）: '{name}'", path=path)

    scope = data["scope"]
    if scope != "shared" and not re.match(r"^agent:(tech|chain|news|macro)$", str(scope)):
        raise CorruptFrontmatterError(
            f"SKILL.md scope 格式不合规: '{scope}'（应为 'shared' 或 'agent:<id>'）", path=path
        )


def validate_pattern_frontmatter(data: dict[str, Any], path: Path | None = None) -> None:
    """Validate required fields of pattern_record.md frontmatter."""
    required = ["name", "agent", "maturity"]
    for field in required:
        if not data.get(field):
            raise CorruptFrontmatterError(f"pattern frontmatter 缺少必填字段: '{field}'", path=path)


def validate_case_frontmatter(data: dict[str, Any], path: Path | None = None) -> None:
    """Validate required fields of case_record.md frontmatter."""
    required = ["cycle_id", "pair", "verdict_action"]
    for field in required:
        if not data.get(field):
            raise CorruptFrontmatterError(f"case frontmatter 缺少必填字段: '{field}'", path=path)


def render_frontmatter(data: dict[str, Any]) -> str:
    """Render a dict as a YAML frontmatter block (including --- delimiters)."""
    import yaml

    yaml_str = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n"
