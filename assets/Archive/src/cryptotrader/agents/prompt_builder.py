"""Agent prompt externalization — PromptBuilder + Provider protocol + TokenBudgetEnforcer.

This module implements spec 017: it externalizes the ROLE system prompts of the
4 analysis agents from Python source code into config/agents/<name>.md
(YAML frontmatter + Markdown body), assembled at runtime by PromptBuilder.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml
from langchain_core.messages import HumanMessage, SystemMessage

from cryptotrader.learning.evolution.skill_provider import (  # noqa: F401
    EvolvingSkillProvider as DefaultSkillProvider,
)

logger = logging.getLogger(__name__)

# ── Token estimation (CJK-aware) ───────────────────────────────


def _estimate_tokens(text: str) -> int:
    """CJK-aware token estimation: ASCII/4 + CJK/1.5 (error < 10% vs tiktoken)."""
    ascii_chars = 0
    cjk_chars = 0
    for ch in text:
        cp = ord(ch)
        # CJK Unified Ideographs ranges
        if (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0xF900 <= cp <= 0xFAFF):
            cjk_chars += 1
        else:
            ascii_chars += 1
    return int(ascii_chars / 4) + int(cjk_chars / 1.5) + 1


# ── ConfigValidationError ───────────────────────────────────────────────────────


class ConfigValidationError(Exception):
    """Raised when startup-time config validation fails; includes the failed file path and reason."""

    def __init__(self, file_path: Path, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Config 校验失败 [{file_path}]: {reason}")


# ── AgentConfig dataclass ───────────────────────────────────────────────────────

# Core required sections (runtime prompt keeps only skill + snapshot + output_schema + user_tail)
_REQUIRED_SECTIONS = frozenset({"system_prompt", "user_tail", "available_skills", "output_schema"})

# Default slot allocation; live_steering / snapshot / portfolio / agent_analyses are dynamically injected
_DEFAULT_SYSTEM_SLOT = ["system_prompt", "available_skills", "output_schema"]
_DEFAULT_USER_SLOT = ["live_steering", "snapshot", "portfolio", "agent_analyses", "user_tail"]


@dataclass
class AgentConfig:
    """In-memory representation of a single agent's config, parsed by ConfigLoader from config/agents/<agent_id>.md."""

    agent_id: str
    description: str
    sections: list[str]
    budget: int
    priority: dict[str, int]
    body_sections: dict[str, str]
    slot_overrides: dict[str, list[str]] = field(default_factory=dict)

    @property
    def system_slot(self) -> list[str]:
        """Return the list of section names that should go into SystemMessage."""
        return self.slot_overrides.get("system", _DEFAULT_SYSTEM_SLOT)

    @property
    def user_slot(self) -> list[str]:
        """Return the list of section names that should go into HumanMessage."""
        return self.slot_overrides.get("user_tail", _DEFAULT_USER_SLOT)


# ── ConfigLoader ────────────────────────────────────────────────────────────────


class ConfigLoader:
    """Loads and validates AgentConfig from config/agents/<agent_id>.md.

    Satisfies 9 validation rules (see contracts/agent-config-schema.md).
    """

    @staticmethod
    def load(path: Path) -> AgentConfig:
        """Load and validate the agent config file; raises ConfigValidationError on failure."""
        # Rule 1: file is readable
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigValidationError(path, f"无法读取 config 文件: {e}") from e

        # Split frontmatter / body
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not m:
            raise ConfigValidationError(path, "无法找到 YAML frontmatter（缺少 --- 分隔符）")
        fm_text, body_text = m.group(1), m.group(2)

        # Rule 2: YAML is parseable
        try:
            fm = yaml.safe_load(fm_text)
        except yaml.YAMLError as e:
            raise ConfigValidationError(path, f"YAML 解析失败: {e}") from e

        if not isinstance(fm, dict):
            raise ConfigValidationError(path, "YAML frontmatter 应为 dict 类型")

        # Rule 3: all required fields present
        for required_field in ("agent_id", "description", "sections", "budget", "priority"):
            if required_field not in fm:
                raise ConfigValidationError(path, f"缺少必填字段: {required_field!r}")

        agent_id: str = fm["agent_id"]
        description: str = fm["description"]
        sections: list[str] = fm["sections"]
        budget: int = fm["budget"]
        priority: dict[str, int] = fm["priority"]
        slot_overrides: dict[str, list[str]] = fm.get("slot_overrides", {}) or {}

        # Rule 4: agent_id matches the filename
        expected_name = path.stem
        if agent_id != expected_name:
            raise ConfigValidationError(path, f"agent_id ({agent_id!r}) 与文件名 ({expected_name!r}) 不匹配")

        # Rule 5: budget > 0
        if not isinstance(budget, int) or budget <= 0:
            raise ConfigValidationError(path, f"budget 必须 > 0，当前值: {budget!r}")

        # Rule 6: sections contains the 5 core required items
        missing_required = _REQUIRED_SECTIONS - set(sections)
        if missing_required:
            raise ConfigValidationError(path, f"sections 缺少必需项: {sorted(missing_required)}")

        # Parse body sections
        body_sections = ConfigLoader._parse_body_sections(body_text)

        # Rule 7: sections in body correspond 1:1 with declared sections
        for sec_name in sections:
            if sec_name not in body_sections:
                raise ConfigValidationError(path, f"section {sec_name!r} 在 body 中未找到")

        # Rule 8: every key in priority must be in sections (dynamic sections excepted)
        _dynamic_sections = {"snapshot", "portfolio", "agent_analyses", "live_steering"}
        for pkey in priority:
            if pkey not in sections and pkey not in _dynamic_sections:
                raise ConfigValidationError(path, f"priority 引用了未声明的 section: {pkey!r}")

        # Rule 9: slot_overrides validation
        if slot_overrides:
            all_slot_sections: list[str] = []
            for slot_name, slot_secs in slot_overrides.items():
                for sec in slot_secs:
                    if sec not in sections and sec not in _dynamic_sections:
                        raise ConfigValidationError(
                            path, f"slot_overrides[{slot_name!r}] 引用了未声明的 section: {sec!r}"
                        )
                all_slot_sections.extend(slot_secs)
            # Check for overlap between system / user_tail
            sys_secs = set(slot_overrides.get("system", []))
            usr_secs = set(slot_overrides.get("user_tail", []))
            overlap = sys_secs & usr_secs
            if overlap:
                raise ConfigValidationError(path, f"slot_overrides system 与 user_tail 有交集: {sorted(overlap)}")

        return AgentConfig(
            agent_id=agent_id,
            description=description,
            sections=list(sections),
            budget=budget,
            priority=dict(priority),
            body_sections=body_sections,
            slot_overrides=slot_overrides,
        )

    @staticmethod
    def _parse_body_sections(body_text: str) -> dict[str, str]:
        """Split a Markdown body into a dict keyed by '## section_name' headings."""
        sections: dict[str, str] = {}
        current_name: str | None = None
        current_lines: list[str] = []
        for line in body_text.splitlines():
            if line.startswith("## "):
                if current_name is not None:
                    sections[current_name] = "\n".join(current_lines).strip()
                current_name = line[3:].strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_name is not None:
            sections[current_name] = "\n".join(current_lines).strip()
        return sections


# ── Skill dataclass ─────────────────────────────────────────────────────────────


@dataclass
class Skill:
    """Data carrier for a single skill (reuses the spec 014 schema)."""

    skill_id: str
    description: str
    tags: list[str]
    steps: list[str]
    body: str = ""
    name: str = ""  # FR-Y30: skill display name; falls back to skill_id when missing


# ── SkillProvider Protocol ──────────────────────────────────────────────────────


class SkillProvider(Protocol):
    """Skill data source protocol interface; implemented by EvolvingSkillProvider."""

    def get_available_skills(
        self,
        agent_id: str,
        snapshot: dict,
        k: int = 5,
    ) -> list[Skill]:
        """Return a ranked list of skills, length <= k; returns [] when empty."""
        ...


# ── EnforceResult + TokenBudgetEnforcer ────────────────────────────────────────


@dataclass
class EnforceResult:
    """Dataclass output by TokenBudgetEnforcer (spec 017 FR-X12)."""

    final_sections: dict[str, str]
    dropped_sections: list[str]
    degraded_sections: list[str]
    prompt_size_pre: int
    prompt_size_post: int
    budget: int


_PROTECTED_SECTIONS = frozenset({"system_prompt", "output_schema"})


class TokenBudgetEnforcer:
    """Drops/degrades sections by priority to fit within the token budget (spec 017 FR-X11).

    Higher priority numbers are dropped first; system_prompt / output_schema are
    always retained.
    """

    def enforce(
        self,
        sections: dict[str, str],
        budget: int,
        priority: dict[str, int],
        protected: frozenset[str] = _PROTECTED_SECTIONS,
    ) -> EnforceResult:
        """Run the token budget check and drop/degrade flow, returning an EnforceResult."""
        # Deep-copy sections to avoid mutating the passed-in dict
        working = dict(sections)
        prompt_size_pre = sum(_estimate_tokens(v) for v in working.values())

        dropped: list[str] = []
        degraded: list[str] = []

        if prompt_size_pre <= budget:
            return EnforceResult(
                final_sections=working,
                dropped_sections=dropped,
                degraded_sections=degraded,
                prompt_size_pre=prompt_size_pre,
                prompt_size_post=prompt_size_pre,
                budget=budget,
            )

        # In descending priority order (highest number dropped first), skip protected
        sorted_keys = sorted(
            working.keys(),
            key=lambda k: priority.get(k, 999),
            reverse=True,
        )
        for name in sorted_keys:
            if name in protected:
                continue
            if sum(_estimate_tokens(v) for v in working.values()) <= budget:
                break
            working.pop(name)
            dropped.append(name)

        # Still over budget -> truncate available_skills
        if sum(_estimate_tokens(v) for v in working.values()) > budget:
            for name in ["available_skills"]:
                if name in working:
                    target_chars = int(budget * 0.3 * 4)
                    if len(working[name]) > target_chars:
                        working[name] = working[name][:target_chars] + "\n...(截断)"
                        degraded.append(name)

        prompt_size_post = sum(_estimate_tokens(v) for v in working.values())
        return EnforceResult(
            final_sections=working,
            dropped_sections=dropped,
            degraded_sections=degraded,
            prompt_size_pre=prompt_size_pre,
            prompt_size_post=prompt_size_post,
            budget=budget,
        )


# ── PromptBuilder ───────────────────────────────────────────────────────────────


class PromptBuilder:
    """Runtime prompt assembler; each agent holds its own instance (spec 017 FR-X5/X6).

    Loads and validates config/agents/<agent_id>.md at construction time;
    build() is the sole public method, returning (SystemMessage, HumanMessage)
    for the LLM call.
    """

    def __init__(
        self,
        agent_id: str,
        config_dir: Path,
        skill_provider: SkillProvider,
        model: str = "",
    ) -> None:
        self._agent_id = agent_id
        self._skill_provider = skill_provider
        self._model = model
        self._enforcer = TokenBudgetEnforcer()

        config_path = config_dir / f"{agent_id}.md"
        self.config: AgentConfig = ConfigLoader.load(config_path)

    def build(
        self,
        snapshot: dict,
        portfolio: dict,
        agent_analyses: dict | None = None,
        steering: str = "",
    ) -> tuple[SystemMessage, HumanMessage]:
        """Assemble LLM messages — the sole public entry point.

        Args:
            steering: Real-time user steering text (from frontend chat -> Redis queue).
                When non-empty, it is injected as the live_steering section; when
                empty, this section does not appear in the prompt.
        """
        t0 = time.monotonic()

        # 1. Get skills
        try:
            skills = self._skill_provider.get_available_skills(self._agent_id, snapshot)
        except Exception:
            logger.warning("SkillProvider 异常，降级为空列表", exc_info=True)
            skills = []

        available_skills_text = self._render_skills(skills)

        # 2. Dynamic rendering
        snapshot_text = self._render_snapshot(snapshot)
        portfolio_text = self._render_portfolio(portfolio)
        agent_analyses_text = self._render_agent_analyses(agent_analyses)

        # 3. Assemble sections
        sections: dict[str, str] = {}
        for sec_name, sec_body in self.config.body_sections.items():
            sections[sec_name] = sec_body
        sections["available_skills"] = available_skills_text
        sections["snapshot"] = snapshot_text
        sections["portfolio"] = portfolio_text
        if agent_analyses_text:
            sections["agent_analyses"] = agent_analyses_text
        if steering:
            sections["live_steering"] = f"[用户实时引导]\n{steering}"

        # 4. Token budget
        result = self._enforcer.enforce(sections, self.config.budget, self.config.priority)

        # 5. Assemble messages
        sys_msg, usr_msg = self._assemble_messages(result.final_sections)

        duration_ms = (time.monotonic() - t0) * 1000
        self._emit_telemetry(result, duration_ms)

        return sys_msg, usr_msg

    def _render_skills(self, skills: list[Skill]) -> str:
        """Render list[Skill] into the full body (FR-Y29, verbatim body, matching the spec 014 loader format)."""
        if not skills:
            return "暂无可用技能"
        parts = []
        for sk in skills:
            display_name = sk.name or sk.skill_id
            parts.append(f"\n\n---\n## Skill: {display_name}\n\n{sk.body}")
        return "".join(parts)

    def _render_snapshot(self, snapshot: dict) -> str:
        """Render the snapshot dict into the crypto-domain format (FR-Y14)."""
        from cryptotrader.agents.snapshot_renderer import render_crypto_snapshot

        return render_crypto_snapshot(snapshot)

    def _render_portfolio(self, portfolio: dict) -> str:
        """Render the portfolio dict into text; uses a placeholder when missing."""
        if not portfolio:
            return "<missing>"
        lines = []
        for k, v in portfolio.items():
            val = v if v is not None else "<missing>"
            lines.append(f"{k}: {val}")
        return "\n".join(lines)

    def _render_agent_analyses(self, agent_analyses: dict | None) -> str:
        """Render other agents' analysis results into text (verdict-style only)."""
        if not agent_analyses:
            return ""
        lines = []
        for agent_id, analysis in agent_analyses.items():
            if isinstance(analysis, dict):
                direction = analysis.get("direction", "?")
                confidence = analysis.get("confidence", "?")
                reasoning = analysis.get("reasoning", "")
                lines.append(f"- {agent_id}: {direction} (confidence={confidence}) — {reasoning}")
            else:
                lines.append(f"- {agent_id}: {analysis}")
        return "\n".join(lines)

    def _assemble_messages(self, final_sections: dict[str, str]) -> tuple[SystemMessage, HumanMessage]:
        """Assemble SystemMessage + HumanMessage per slot_overrides or the default allocation."""
        sys_parts = []
        for sec in self.config.system_slot:
            if final_sections.get(sec):
                sys_parts.append(final_sections[sec])

        usr_parts = []
        for sec in self.config.user_slot:
            if final_sections.get(sec):
                usr_parts.append(final_sections[sec])

        sys_content = "\n\n".join(sys_parts)
        usr_content = "\n\n".join(usr_parts)

        return SystemMessage(content=sys_content), HumanMessage(content=usr_content)

    def _emit_telemetry(
        self,
        result: EnforceResult,
        duration_ms: float,
    ) -> None:
        """Write telemetry fields to the current active OpenTelemetry span or to structured log."""
        attrs = {
            "prompt.builder.agent_id": self._agent_id,
            "prompt.builder.sections_included": list(result.final_sections.keys()),
            "prompt.builder.dropped_sections": result.dropped_sections,
            "prompt.builder.degraded_sections": result.degraded_sections,
            "prompt.builder.prompt_size_pre": result.prompt_size_pre,
            "prompt.builder.prompt_size_post": result.prompt_size_post,
            "prompt.builder.budget": result.budget,
            "prompt.builder.duration_ms": round(duration_ms, 2),
        }

        # Attempt to attach to the OpenTelemetry active span (spec 010 infrastructure)
        span_attached = False
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span is not None and span.is_recording():
                for key, val in attrs.items():
                    if isinstance(val, list):
                        span.set_attribute(key, str(val))
                    else:
                        span.set_attribute(key, val)
                span_attached = True
        except Exception:
            pass  # opentelemetry not installed or no active span -> fallback to log

        if not span_attached:
            logger.info(
                "prompt_builder_telemetry agent_id=%s sections_included=%s "
                "dropped=%s degraded=%s size_pre=%d size_post=%d budget=%d duration_ms=%.2f",
                self._agent_id,
                result.final_sections.keys(),
                result.dropped_sections,
                result.degraded_sections,
                result.prompt_size_pre,
                result.prompt_size_post,
                result.budget,
                duration_ms,
            )
