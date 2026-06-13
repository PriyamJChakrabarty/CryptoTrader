def test_get_metrics_collector_returns_singleton():
    from cryptotrader.metrics import get_metrics_collector

    a = get_metrics_collector()
    b = get_metrics_collector()
    assert a is b


def test_inc_llm_calls():
    from prometheus_client import REGISTRY

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    before = _sample_value(REGISTRY, "ct_llm_calls_total", {"model": "gpt-4o", "node": "agents"})
    mc.inc_llm_calls(model="gpt-4o", node="agents")
    after = _sample_value(REGISTRY, "ct_llm_calls_total", {"model": "gpt-4o", "node": "agents"})
    assert after == (before or 0) + 1


def test_inc_debate_skipped():
    from prometheus_client import REGISTRY

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    before = _sample_value(REGISTRY, "ct_debate_skipped_total", {})
    mc.inc_debate_skipped()
    after = _sample_value(REGISTRY, "ct_debate_skipped_total", {})
    assert after == (before or 0) + 1


def test_inc_verdict():
    from prometheus_client import REGISTRY

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    before = _sample_value(REGISTRY, "ct_verdict_total", {"action": "buy"})
    mc.inc_verdict(action="buy")
    after = _sample_value(REGISTRY, "ct_verdict_total", {"action": "buy"})
    assert after == (before or 0) + 1


def test_inc_risk_rejected():
    from prometheus_client import REGISTRY

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    before = _sample_value(REGISTRY, "ct_risk_rejected_total", {"check_name": "volatility"})
    mc.inc_risk_rejected(check_name="volatility")
    after = _sample_value(REGISTRY, "ct_risk_rejected_total", {"check_name": "volatility"})
    assert after == (before or 0) + 1


def test_inc_trade_executed():
    from prometheus_client import REGISTRY

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    before = _sample_value(REGISTRY, "ct_trade_executed_total", {"engine": "paper", "side": "buy"})
    mc.inc_trade_executed(engine="paper", side="buy")
    after = _sample_value(REGISTRY, "ct_trade_executed_total", {"engine": "paper", "side": "buy"})
    assert after == (before or 0) + 1


def test_observe_execution_latency():
    from prometheus_client import REGISTRY

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    before_count = _sample_count(REGISTRY, "ct_execution_latency_ms", {"engine": "paper"})
    mc.observe_execution_latency(engine="paper", ms=42.5)
    after_count = _sample_count(REGISTRY, "ct_execution_latency_ms", {"engine": "paper"})
    assert after_count == (before_count or 0) + 1


def test_observe_pipeline_duration():
    from prometheus_client import REGISTRY

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    before_count = _sample_count(REGISTRY, "ct_pipeline_duration_ms", {})
    mc.observe_pipeline_duration(ms=1234.0)
    after_count = _sample_count(REGISTRY, "ct_pipeline_duration_ms", {})
    assert after_count == (before_count or 0) + 1


def test_generate_latest_contains_metric_names():
    from prometheus_client import generate_latest

    from cryptotrader.metrics import get_metrics_collector

    mc = get_metrics_collector()
    # Ensure each metric is invoked at least once so it appears in the output
    mc.inc_llm_calls(model="test", node="test")
    mc.inc_debate_skipped()
    mc.inc_verdict(action="hold")
    mc.inc_risk_rejected(check_name="drawdown")
    mc.inc_trade_executed(engine="live", side="sell")
    mc.observe_execution_latency(engine="live", ms=10.0)
    mc.observe_pipeline_duration(ms=500.0)

    output = generate_latest().decode("utf-8")
    assert "ct_llm_calls_total" in output
    assert "ct_debate_skipped_total" in output
    assert "ct_verdict_total" in output
    assert "ct_risk_rejected_total" in output
    assert "ct_trade_executed_total" in output
    assert "ct_execution_latency_ms" in output
    assert "ct_pipeline_duration_ms" in output


def test_prometheus_metrics_endpoint_returns_200():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200


def test_prometheus_metrics_endpoint_content_type():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    r = client.get("/metrics")
    assert "text/plain" in r.headers["content-type"]


def test_prometheus_metrics_endpoint_contains_ct_metrics():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    r = client.get("/metrics")
    body = r.text
    # Should contain at least one ct_ metric
    assert "ct_" in body


def _sample_value(registry, metric_name: str, labels: dict) -> float | None:
    """Read a Counter/Gauge sample value from the Prometheus registry.

    prometheus_client's m.name is the base name without the _total suffix;
    a Counter's sample name is {base}_total, while a Gauge's sample name equals
    the base name. The metric_name parameter is the full name (e.g.
    ct_llm_calls_total), and this function derives the base name automatically.
    """
    base_name = metric_name.removesuffix("_total")
    for m in registry.collect():
        if m.name == base_name:
            for sample in m.samples:
                if (sample.name == f"{base_name}_total" or sample.name == base_name) and _labels_match(
                    sample.labels, labels
                ):
                    return sample.value
    return None


def _sample_count(registry, metric_name: str, labels: dict) -> float | None:
    """Read a Histogram _count sample value from the Prometheus registry."""
    base_name = metric_name.removesuffix("_total")
    for m in registry.collect():
        if m.name == base_name:
            for sample in m.samples:
                if sample.name == f"{base_name}_count" and _labels_match(sample.labels, labels):
                    return sample.value
    return None


def _labels_match(sample_labels: dict, expected: dict) -> bool:
    """Check whether sample_labels contains all key-value pairs from expected."""
    return all(sample_labels.get(k) == v for k, v in expected.items())
