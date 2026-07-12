"""NodeLogger decorator tests -- verify node_entry/node_exit event recording and metadata preservation."""

from __future__ import annotations

import asyncio
import typing

import pytest
import structlog


@pytest.mark.asyncio
async def test_node_logger_records_entry_event():
    """@node_logger() records a node_entry event at the entry of a node function."""
    events: list[dict] = []

    def capture_processor(logger, method_name, event_dict):
        events.append(dict(event_dict))
        raise structlog.DropEvent

    structlog.configure(processors=[capture_processor])

    from cryptotrader.tracing import node_logger

    @node_logger()
    async def dummy_node(state: dict) -> dict:
        return {}

    await dummy_node({"metadata": {}, "data": {}})

    entry_events = [e for e in events if e.get("event") == "node_entry"]
    assert len(entry_events) >= 1, "应当记录至少一个 node_entry 事件"
    assert "node" in entry_events[0], "node_entry 事件应含 node 字段"


@pytest.mark.asyncio
async def test_node_logger_records_exit_event():
    """@node_logger() records a node_exit event at the exit of a node function, including duration_ms."""
    events: list[dict] = []

    def capture_processor(logger, method_name, event_dict):
        events.append(dict(event_dict))
        raise structlog.DropEvent

    structlog.configure(processors=[capture_processor])

    from cryptotrader.tracing import node_logger

    @node_logger()
    async def dummy_node(state: dict) -> dict:
        return {}

    await dummy_node({"metadata": {}, "data": {}})

    exit_events = [e for e in events if e.get("event") == "node_exit"]
    assert len(exit_events) >= 1, "应当记录至少一个 node_exit 事件"
    assert "duration_ms" in exit_events[0], "node_exit 事件应含 duration_ms 字段"
    assert exit_events[0]["duration_ms"] >= 0, "duration_ms 应为非负数"


@pytest.mark.asyncio
async def test_node_logger_node_name_in_events():
    """The node field in node_entry and node_exit events matches the function name."""
    events: list[dict] = []

    def capture_processor(logger, method_name, event_dict):
        events.append(dict(event_dict))
        raise structlog.DropEvent

    structlog.configure(processors=[capture_processor])

    from cryptotrader.tracing import node_logger

    @node_logger()
    async def collect_snapshot(state: dict) -> dict:
        return {}

    await collect_snapshot({"metadata": {}, "data": {}})

    node_names = {e.get("node") for e in events if e.get("event") in ("node_entry", "node_exit")}
    assert "collect_snapshot" in node_names, "node 字段应为函数名 collect_snapshot"


@pytest.mark.asyncio
async def test_node_logger_trace_id_from_state():
    """When state['metadata']['trace_id'] exists, the event's trace_id should match it."""
    events: list[dict] = []

    def capture_processor(logger, method_name, event_dict):
        events.append(dict(event_dict))
        raise structlog.DropEvent

    structlog.configure(processors=[capture_processor])
    structlog.contextvars.clear_contextvars()

    from cryptotrader.tracing import node_logger

    @node_logger()
    async def dummy_node(state: dict) -> dict:
        return {}

    state = {"metadata": {"trace_id": "test-trace-abc"}, "data": {}}
    await dummy_node(state)

    entry_events = [e for e in events if e.get("event") == "node_entry"]
    assert len(entry_events) >= 1
    assert entry_events[0].get("trace_id") == "test-trace-abc", "trace_id 应从 state metadata 中获取"


@pytest.mark.asyncio
async def test_node_logger_trace_id_from_structlog_context():
    """When state has no trace_id but structlog context does, use the context value."""
    events: list[dict] = []

    def capture_processor(logger, method_name, event_dict):
        events.append(dict(event_dict))
        raise structlog.DropEvent

    structlog.configure(processors=[capture_processor])
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id="ctx-trace-xyz")

    from cryptotrader.tracing import node_logger

    @node_logger()
    async def dummy_node(state: dict) -> dict:
        return {}

    state = {"metadata": {}, "data": {}}
    await dummy_node(state)

    entry_events = [e for e in events if e.get("event") == "node_entry"]
    assert len(entry_events) >= 1
    assert entry_events[0].get("trace_id") == "ctx-trace-xyz", "trace_id 应从 structlog context 获取"


def test_node_logger_preserves_function_name():
    """@node_logger() preserves the original function's __name__ via functools.wraps."""
    from cryptotrader.tracing import node_logger

    @node_logger()
    async def my_node_function(state: dict) -> dict:
        return {}

    assert my_node_function.__name__ == "my_node_function", "__name__ 应与原函数一致"


def test_node_logger_preserves_qualname():
    """@node_logger() preserves the original function's __qualname__."""
    from cryptotrader.tracing import node_logger

    @node_logger()
    async def my_node_function(state: dict) -> dict:
        return {}

    assert "my_node_function" in my_node_function.__qualname__, "__qualname__ 应包含原函数名"


def test_node_logger_preserves_annotations():
    """@node_logger() preserves the original function's __annotations__, so get_type_hints() resolves correctly."""
    from cryptotrader.tracing import node_logger

    @node_logger()
    async def typed_node(state: dict) -> dict:
        return {}

    hints = typing.get_type_hints(typed_node)
    assert "return" in hints, "get_type_hints() 应能解析返回类型注解"
    assert "state" in hints, "get_type_hints() 应能解析参数类型注解"


def test_node_logger_preserves_docstring():
    """@node_logger() preserves the original function's __doc__."""
    from cryptotrader.tracing import node_logger

    @node_logger()
    async def documented_node(state: dict) -> dict:
        """This is the docstring."""
        return {}

    assert documented_node.__doc__ == "This is the docstring.", "__doc__ 应与原函数一致"


@pytest.mark.asyncio
async def test_node_logger_passes_through_return_value():
    """@node_logger() does not change the node function's return value."""

    def drop_processor(logger, method_name, event_dict):
        raise structlog.DropEvent

    structlog.configure(processors=[drop_processor])

    from cryptotrader.tracing import node_logger

    expected = {"data": {"key": "value"}}

    @node_logger()
    async def returning_node(state: dict) -> dict:
        return expected

    result = await returning_node({"metadata": {}, "data": {}})
    assert result == expected, "装饰后返回值应与原函数一致"


@pytest.mark.asyncio
async def test_node_logger_propagates_exception():
    """When a node function raises, @node_logger() propagates the exception to the caller."""

    def drop_processor(logger, method_name, event_dict):
        raise structlog.DropEvent

    structlog.configure(processors=[drop_processor])

    from cryptotrader.tracing import node_logger

    @node_logger()
    async def failing_node(state: dict) -> dict:
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        await failing_node({"metadata": {}, "data": {}})


@pytest.mark.asyncio
async def test_node_logger_duration_ms_uses_monotonic():
    """duration_ms should be based on time.monotonic(), and its value should be >= 0."""
    events: list[dict] = []

    def capture_processor(logger, method_name, event_dict):
        events.append(dict(event_dict))
        raise structlog.DropEvent

    structlog.configure(processors=[capture_processor])

    from cryptotrader.tracing import node_logger

    @node_logger()
    async def slow_node(state: dict) -> dict:
        await asyncio.sleep(0.01)
        return {}

    await slow_node({"metadata": {}, "data": {}})

    exit_events = [e for e in events if e.get("event") == "node_exit"]
    assert len(exit_events) >= 1
    duration = exit_events[0]["duration_ms"]
    assert duration >= 10, f"sleep(0.01) 后 duration_ms 应 >= 10, 实际 {duration}"


def test_public_nodes_are_decorated():
    """All public node functions under nodes/ should have @node_logger() applied.

    Verified via the __wrapped__ attribute, confirming functools.wraps was applied correctly.
    """
    from cryptotrader.nodes.agents import (
        chain_analyze,
        macro_analyze,
        news_analyze,
        tech_analyze,
    )
    from cryptotrader.nodes.data import (
        collect_snapshot,
        enrich_verdict_context,
        tag_regime_node,
        update_past_pnl,
    )
    from cryptotrader.nodes.debate import (
        bull_bear_debate,
        check_stability,
        debate_gate,
        debate_round,
        judge_verdict,
    )
    from cryptotrader.nodes.execution import check_stop_loss, place_order
    from cryptotrader.nodes.journal import journal_rejection, journal_trade
    from cryptotrader.nodes.verdict import make_verdict, risk_check

    public_nodes = [
        collect_snapshot,
        update_past_pnl,
        tag_regime_node,
        enrich_verdict_context,
        tech_analyze,
        chain_analyze,
        news_analyze,
        macro_analyze,
        debate_round,
        debate_gate,
        check_stability,
        bull_bear_debate,
        judge_verdict,
        make_verdict,
        risk_check,
        check_stop_loss,
        place_order,
        journal_trade,
        journal_rejection,
    ]

    for fn in public_nodes:
        assert hasattr(fn, "__wrapped__"), f"{fn.__name__} 应已应用 @node_logger() 装饰器 (__wrapped__ 属性缺失)"
