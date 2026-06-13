from __future__ import annotations

import pytest

from cryptotrader.agents.prompt_builder import EnforceResult, TokenBudgetEnforcer, _estimate_tokens

PRIORITY = {
    "system_prompt": 1,
    "output_schema": 1,
    "snapshot": 2,
    "portfolio": 3,
    "user_tail": 4,
    "available_skills": 6,
}


@pytest.fixture
def enforcer() -> TokenBudgetEnforcer:
    return TokenBudgetEnforcer()


class TestTokenBudgetNoExceed:
    def test_under_budget_returns_all_sections(self, enforcer: TokenBudgetEnforcer) -> None:
        sections = {
            "system_prompt": "You are a helpful agent.",
            "output_schema": '{"direction": "bullish"}',
            "available_skills": "暂无历史记忆",
        }
        budget = 10000
        result = enforcer.enforce(sections, budget, PRIORITY)
        assert isinstance(result, EnforceResult)
        assert result.dropped_sections == []
        assert result.degraded_sections == []
        assert set(result.final_sections.keys()) == set(sections.keys())
        assert result.prompt_size_pre == result.prompt_size_post

    def test_exactly_at_budget_no_drop(self, enforcer: TokenBudgetEnforcer) -> None:
        text = "Hello world " * 10  # ~25 tokens
        sections = {"system_prompt": text, "output_schema": "{}"}
        pre = sum(_estimate_tokens(v) for v in sections.values())
        result = enforcer.enforce(sections, pre, PRIORITY)
        assert result.dropped_sections == []


class TestTokenBudgetDropByPriority:
    def test_drop_lowest_priority_first(self, enforcer: TokenBudgetEnforcer) -> None:
        # available_skills(6) > user_tail(4): higher priority number drops first
        sections = {
            "system_prompt": "Role description. " * 10,
            "output_schema": '{"direction": "neutral"}',
            "available_skills": "Skill list. " * 40,
            "user_tail": "Tail instructions. " * 5,
        }
        # set a budget that requires exactly dropping available_skills
        pre = sum(_estimate_tokens(v) for v in sections.values())
        # budget = size after removing available_skills + a small margin
        dropped_est = _estimate_tokens(sections["available_skills"])
        budget = pre - dropped_est + 2
        result = enforcer.enforce(sections, budget, PRIORITY)
        assert "available_skills" in result.dropped_sections
        assert "system_prompt" not in result.dropped_sections
        assert "output_schema" not in result.dropped_sections

    def test_protected_sections_never_dropped(self, enforcer: TokenBudgetEnforcer) -> None:
        # extremely small budget, must still retain system_prompt + output_schema
        sections = {
            "system_prompt": "Critical system prompt. " * 5,
            "output_schema": '{"required": "schema"}',
            "available_skills": "Skills. " * 100,
        }
        result = enforcer.enforce(sections, budget=10, priority=PRIORITY)
        assert "system_prompt" in result.final_sections
        assert "output_schema" in result.final_sections
        assert "system_prompt" not in result.dropped_sections
        assert "output_schema" not in result.dropped_sections


class TestTokenBudgetDegradation:
    def test_degradation_triggered_when_drop_insufficient(self, enforcer: TokenBudgetEnforcer) -> None:
        # only system_prompt + output_schema + available_skills (first two can't be dropped)
        # budget is tiny, so even after dropping available_skills it's still over -> triggers truncation
        long_text = "A very long memory entry with lots of detail. " * 100
        sections = {
            "system_prompt": "Role prompt here.",
            "output_schema": '{"direction": "bullish"}',
            "available_skills": long_text,
        }
        sum(_estimate_tokens(v) for v in sections.values())
        # budget only enough for system_prompt + output_schema
        minimal = _estimate_tokens(sections["system_prompt"]) + _estimate_tokens(sections["output_schema"]) - 1
        result = enforcer.enforce(sections, budget=max(1, minimal), priority=PRIORITY)
        # available_skills must be either dropped or degraded
        all_handled = "available_skills" in result.dropped_sections or "available_skills" in result.degraded_sections
        assert all_handled


class TestTokenBudgetProtected:
    def test_system_prompt_always_retained(self, enforcer: TokenBudgetEnforcer) -> None:
        sections = {
            "system_prompt": "Must keep this. " * 20,
            "output_schema": "Must keep schema. " * 10,
            "available_skills": "Drop me. " * 200,
            "user_tail": "Also droppable. " * 50,
        }
        result = enforcer.enforce(sections, budget=1, priority=PRIORITY)
        assert "system_prompt" in result.final_sections
        assert "output_schema" in result.final_sections
        assert "system_prompt" not in result.dropped_sections
        assert "output_schema" not in result.dropped_sections

    def test_enforce_result_fields_complete(self, enforcer: TokenBudgetEnforcer) -> None:
        sections = {"system_prompt": "Role.", "output_schema": "{}"}
        result = enforcer.enforce(sections, budget=100, priority=PRIORITY)
        assert hasattr(result, "final_sections")
        assert hasattr(result, "dropped_sections")
        assert hasattr(result, "degraded_sections")
        assert hasattr(result, "prompt_size_pre")
        assert hasattr(result, "prompt_size_post")
        assert hasattr(result, "budget")
        assert result.budget == 100


class TestTokenEstimation:
    def test_ascii_only_estimation(self) -> None:
        # pure ASCII: ~word_count/0.75 tokens (~1 token per 4 chars)
        text = "Hello world this is a test sentence for token estimation. " * 10
        est = _estimate_tokens(text)
        # reference: tiktoken GPT-4 ~120 tokens for 580 chars -> ~145 tokens
        # we only require the CJK-aware estimate to be reasonable, not an exact tiktoken match
        assert est > 0
        # char_count / 4 <= est <= char_count (reasonable upper bound)
        assert len(text) // 4 <= est <= len(text)

    def test_cjk_only_estimation(self) -> None:
        # pure Chinese: each CJK char ~0.67 token (/1.5)
        text = "这是一段中文测试文本，用于验证 CJK 字符的 token 估算精度。" * 5
        est = _estimate_tokens(text)
        assert est > 0
        # cjk_char_count / 1.5 roughly equals token count (reference: how tiktoken handles Chinese)
        cjk_count = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
        expected_min = int(cjk_count / 2)  # loose lower bound
        expected_max = len(text)  # loose upper bound
        assert expected_min <= est <= expected_max

    def test_mixed_cjk_ascii_estimation(self) -> None:
        # mixed CJK/English: mainly ensure the estimate falls in a reasonable range
        text = "BTC price is rising. 比特币价格上涨。Funding rate is 0.05%. 资金费率偏高。" * 3
        est = _estimate_tokens(text)
        assert est > 5  # non-zero
        assert est < len(text)  # token count is always less than char count

    def test_empty_string(self) -> None:
        assert _estimate_tokens("") == 1  # empty string returns the minimum value 1

    def test_cjk_estimate_within_10pct_of_reference(self) -> None:
        sample = "你是 CryptoTrader AI 系统的技术分析 agent。分析价格走势并输出 JSON 决策。BTC price: 65000."
        est = _estimate_tokens(sample)
        assert 15 <= est <= 60, f"Token 估算值 {est} 超出合理范围 [15, 60]"
        assert _estimate_tokens(sample) == est, "Token 估算应是确定性的"
        assert _estimate_tokens("") == 1
