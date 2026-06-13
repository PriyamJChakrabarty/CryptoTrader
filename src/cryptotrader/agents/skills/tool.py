"""load_skill tool — dual interface: plain Python function + LangChain BaseTool.

FR-022: dual interface (function + LangChain tool), same implementation.
FR-023: requires only 1 parameter (skill name), resolved by directory.
FR-025: more than 10 calls per cycle for the same trace_id returns rate_limit_per_cycle.
FR-025a: each call increments a counter via metrics_collector.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from cryptotrader.agents.skills._constants import DEFAULT_AGENT_SKILLS_DIR

logger = logging.getLogger(__name__)

# ── rate-limit counter (per trace_id) ──
# thread-safe dict: trace_id -> call_count
_call_counts: dict[str, int] = defaultdict(int)
_call_counts_lock = threading.Lock()
_RATE_LIMIT_PER_CYCLE = 10


def _reset_call_counter(trace_id: str) -> None:
    """Reset the call count for the given trace_id (mainly used for testing)."""
    with _call_counts_lock:
        _call_counts[trace_id] = 0


def _increment_and_check(trace_id: str) -> bool:
    """Increment the call count, returning True if the limit is exceeded."""
    with _call_counts_lock:
        _call_counts[trace_id] += 1
        return _call_counts[trace_id] > _RATE_LIMIT_PER_CYCLE


# ── Core function ──


def load_skill(
    name: str,
    skill_dir: Path | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Load the body content of the specified skill.

    FR-022: plain Python function interface.
    FR-023: resolved via the agent_skills/<name>/SKILL.md directory.
    FR-025: rate-limit (> 10 calls/cycle/trace_id).

    Returns:
        On success: {"name": str, "body": str, "scope": str}
        On failure: {"error": "skill_not_found" | "corrupt_file" | "rate_limit_per_cycle", "name": str}
    """
    # FR-025a: metrics
    _record_metric(name, "attempt")

    # FR-025: rate-limit check
    effective_trace_id = trace_id or "default"
    if _increment_and_check(effective_trace_id):
        logger.warning("load_skill rate limit exceeded for trace_id=%s (skill=%s)", effective_trace_id, name)
        _record_metric(name, "rate_limit")
        return {"error": "rate_limit_per_cycle", "name": name}

    base = skill_dir or DEFAULT_AGENT_SKILLS_DIR
    skill_md = base / name / "SKILL.md"

    if not skill_md.exists():
        logger.warning("load_skill: skill not found: %s", name)
        _record_metric(name, "skill_not_found")
        return {"error": "skill_not_found", "name": name}

    from cryptotrader.agents.skills._frontmatter import (
        CorruptFrontmatterError,
        parse_frontmatter,
        validate_skill_frontmatter,
    )

    try:
        content = skill_md.read_text(encoding="utf-8")
        data, body = parse_frontmatter(content, path=skill_md)
        validate_skill_frontmatter(data, path=skill_md)
        _record_metric(name, "ok")
        return {
            "name": str(data["name"]),
            "body": body,
            "scope": str(data.get("scope", "")),
            "description": str(data.get("description", "")),
        }
    except CorruptFrontmatterError as exc:
        logger.warning("load_skill: corrupt frontmatter for '%s': %s", name, exc)
        _record_metric(name, "corrupt_file")
        return {"error": "corrupt_file", "name": name}
    except Exception as exc:
        logger.warning("load_skill: unexpected error for '%s': %s", name, exc)
        _record_metric(name, "corrupt_file")
        return {"error": "corrupt_file", "name": name}


def _record_metric(name: str, result: str) -> None:
    """FR-025a: record the load_skill call count via metrics_collector."""
    try:
        from cryptotrader.metrics import get_metrics_collector

        mc = get_metrics_collector()
        if hasattr(mc, "inc_counter"):
            mc.inc_counter("load_skill_calls", labels={"name": name, "result": result})
    except Exception:
        pass  # do not block when metrics are unavailable


# ── LangChain BaseTool interface ──


def _make_load_skill_tool(provider: Any | None = None, skill_dir: Path | None = None):
    """Create a LangChain BaseTool instance.

    If provider is non-None -> uses provider.get_skill_by_name(name) (access_count accumulates).
    If provider is None -> falls back to reading the file directly.
    """
    try:
        from langchain_core.tools import tool

        @tool
        def load_skill_tool(name: str) -> str:
            """Load the body content of a named skill.

            Args:
                name: The skill directory name (e.g. 'tech-analysis', 'trading-knowledge')

            Returns:
                The skill body as a string, or an error message.
            """
            # provider path (access_count accumulated via provider)
            if provider is not None:
                try:
                    skill = provider.get_skill_by_name(name)
                    if skill is None:
                        logger.warning("load_skill_tool: provider returned None for skill '%s'", name)
                        return f"Error: skill not found: {name}"
                    return skill.body
                except Exception as exc:
                    logger.warning("load_skill_tool: provider error for '%s': %s", name, exc)
                    return f"Error: provider error for skill {name}"
            # spec 014 fallback: direct file read (no access_count accumulation)
            result = load_skill(name, skill_dir=skill_dir)
            if "error" in result:
                return f"Error: {result['error']} (skill: {name})"
            return result.get("body", "")

        return load_skill_tool
    except ImportError:
        logger.warning("langchain_core not available; load_skill_tool not created")
        return None


# Module-level tool instance (default: provider=None, spec 014 fallback path)
# nodes/agents.py replaces this with provider-injected version at init time (FR-W14).
load_skill_tool = _make_load_skill_tool()
