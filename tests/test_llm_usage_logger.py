from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from cryptotrader.agents.base import acompletion_with_fallback, log_llm_usage
from cryptotrader.models import DataSnapshot, MacroData, MarketData, NewsSentiment, OnchainData


def _make_ai_message(
    content: str = "ok",
    input_tokens: int = 10,
    output_tokens: int = 20,
    model_name: str = "gpt-4o-mini",
) -> AIMessage:
    return AIMessage(
        content=content,
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        response_metadata={"model_name": model_name},
    )


def _make_snapshot(pair: str = "BTC/USDT") -> DataSnapshot:
    return DataSnapshot(
        timestamp=None,
        pair=pair,
        market=MarketData(
            pair=pair,
            ohlcv=None,
            ticker={"last": 50000, "baseVolume": 1000},
            funding_rate=0.0001,
            orderbook_imbalance=0.5,
            volatility=0.02,
        ),
        onchain=OnchainData(),
        news=NewsSentiment(),
        macro=MacroData(),
    )


def test_log_llm_usage_uses_structlog_event():
    msg = _make_ai_message(input_tokens=100, output_tokens=200, model_name="gpt-4o-mini")
    logged_events: list[dict] = []

    with patch("cryptotrader.agents.base._structlog") as mock_log:
        mock_log.info = MagicMock(side_effect=lambda event, **kw: logged_events.append({"event": event, **kw}))
        log_llm_usage(msg, caller="my_node")

    assert len(logged_events) == 1
    ev = logged_events[0]
    assert ev["event"] == "llm_usage"
    assert ev["input_tokens"] == 100
    assert ev["output_tokens"] == 200
    assert ev["model_name"] == "gpt-4o-mini"
    assert ev["caller"] == "my_node"


def test_log_llm_usage_missing_usage_metadata_does_not_raise():
    msg = AIMessage(content="ok")
    logged_events: list[dict] = []

    with patch("cryptotrader.agents.base._structlog") as mock_log:
        mock_log.info = MagicMock(side_effect=lambda event, **kw: logged_events.append({"event": event, **kw}))
        log_llm_usage(msg, caller="test")

    assert logged_events == []


def test_log_llm_usage_missing_model_name_uses_unknown():
    logged_events: list[dict] = []

    with patch("cryptotrader.agents.base._structlog") as mock_log:
        mock_log.info = MagicMock(side_effect=lambda event, **kw: logged_events.append({"event": event, **kw}))
        msg = AIMessage(
            content="ok",
            usage_metadata={"input_tokens": 5, "output_tokens": 10, "total_tokens": 15},
        )
        log_llm_usage(msg, caller="test")

    assert len(logged_events) == 1
    assert logged_events[0]["model_name"] == "unknown"


def test_log_llm_usage_non_ai_message_does_not_raise():
    logged_events: list[dict] = []

    with patch("cryptotrader.agents.base._structlog") as mock_log:
        mock_log.info = MagicMock(side_effect=lambda event, **kw: logged_events.append({"event": event, **kw}))
        log_llm_usage("plain string", caller="test")
        log_llm_usage(None, caller="test")
        log_llm_usage(42, caller="test")

    assert logged_events == []


def test_log_llm_usage_total_tokens():
    logged_events: list[dict] = []

    with patch("cryptotrader.agents.base._structlog") as mock_log:
        mock_log.info = MagicMock(side_effect=lambda event, **kw: logged_events.append({"event": event, **kw}))
        msg = _make_ai_message(input_tokens=30, output_tokens=70)
        log_llm_usage(msg, caller="test")

    assert len(logged_events) == 1
    assert logged_events[0]["total_tokens"] == 100


def test_log_llm_usage_caller_field():
    logged_events: list[dict] = []

    with patch("cryptotrader.agents.base._structlog") as mock_log:
        mock_log.info = MagicMock(side_effect=lambda event, **kw: logged_events.append({"event": event, **kw}))
        msg = _make_ai_message()
        log_llm_usage(msg, caller="tech_agent")

    assert len(logged_events) == 1
    assert logged_events[0]["caller"] == "tech_agent"


async def test_base_agent_analyze_logs_llm_usage():
    from unittest.mock import MagicMock

    from langchain_core.messages import HumanMessage, SystemMessage

    from cryptotrader.agents.base import BaseAgent

    fake_pb = MagicMock()
    fake_pb.build.return_value = (
        SystemMessage(content="You are a test agent."),
        HumanMessage(content="Analyze BTC/USDT"),
    )
    agent = BaseAgent(
        agent_id="test_agent",
        prompt_builder=fake_pb,
        model="gpt-4o-mini",
    )
    snapshot = _make_snapshot()
    response_msg = _make_ai_message(
        content='{"direction":"neutral","confidence":0.5,"data_sufficiency":"medium","reasoning":"test","key_factors":[],"risk_flags":[]}',
        input_tokens=50,
        output_tokens=80,
        model_name="gpt-4o-mini",
    )

    usage_logged: list[dict] = []

    def capture_log_llm_usage(msg, *, caller):
        usage_logged.append({"msg": msg, "caller": caller})

    with (
        patch("cryptotrader.agents.base.create_llm") as mock_create_llm,
        patch("cryptotrader.agents.base.log_llm_usage", side_effect=capture_log_llm_usage),
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=response_msg)
        mock_create_llm.return_value = mock_llm

        await agent.analyze(snapshot)

    assert len(usage_logged) == 1
    assert usage_logged[0]["caller"] == "test_agent"
    assert usage_logged[0]["msg"] == response_msg


async def test_acompletion_with_fallback_logs_llm_usage():
    response_msg = _make_ai_message(
        content="hello",
        input_tokens=20,
        output_tokens=5,
        model_name="gpt-4o-mini",
    )

    usage_logged: list[dict] = []

    def capture_log_llm_usage(msg, *, caller):
        usage_logged.append({"msg": msg, "caller": caller})

    with (
        patch("cryptotrader.agents.base.create_llm") as mock_create_llm,
        patch("cryptotrader.agents.base.log_llm_usage", side_effect=capture_log_llm_usage),
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=response_msg)
        mock_create_llm.return_value = mock_llm

        result = await acompletion_with_fallback(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )

    assert result == response_msg
    assert len(usage_logged) == 1
    assert usage_logged[0]["msg"] == response_msg
    assert usage_logged[0]["caller"] == "acompletion_with_fallback"
