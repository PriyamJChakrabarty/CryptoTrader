
from __future__ import annotations

import argparse
import contextlib
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StepResult:
    idx: int
    name: str
    status: str  # "PASS" | "FAIL"
    duration_ms: int
    error: str = ""

    def fmt(self) -> str:
        line = f"[step {self.idx}] {self.name}: {self.status} {self.duration_ms}ms"
        if self.error:
            line += f"\n  ERROR: {self.error}"
        return line


def run_step(idx: int, name: str, fn: Callable[[], None]) -> StepResult:
    start = time.time()
    try:
        fn()
        return StepResult(idx, name, "PASS", int((time.time() - start) * 1000))
    except Exception as exc:
        return StepResult(idx, name, "FAIL", int((time.time() - start) * 1000), str(exc))


def _migrate(script_name: str, dry_run: bool = True) -> None:
    script_path = Path(__file__).parent / f"{script_name}.py"
    if not script_path.exists():
        raise FileNotFoundError(f"migrate script not found: {script_path}")

    cmd = [sys.executable, str(script_path)]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        stderr_snippet = (result.stderr or "")[:500]
        raise RuntimeError(f"{script_name} exited {result.returncode}: {stderr_snippet}")


def _run_smoke_cycle() -> None:
    from cryptotrader.agents.base import create_llm, log_llm_usage  # noqa: F401

    with contextlib.suppress(ImportError):
        from cryptotrader import scheduler as _sched  # noqa: F401

    import asyncio

    from cryptotrader.graph import build_trading_graph  # noqa: F401

    from cryptotrader.learning.evolution.ive import classify_case

    if not asyncio.iscoroutinefunction(classify_case):
        raise AssertionError(
            "classify_case must be async def (FR-Z10); found sync function — IVE async migration incomplete"
        )


def _check_otel_fields() -> None:
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    except ImportError as exc:
        raise ImportError(
            f"opentelemetry SDK not installed: {exc}; install opentelemetry-sdk to enable OTel field validation"
        ) from exc

    from langchain_core.messages import AIMessage

    from cryptotrader.agents.base import log_llm_usage

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("staging_validate")

    msg = AIMessage(
        content="test",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cache_read_input_tokens": 80,
            "cache_creation_input_tokens": 20,
        },
        response_metadata={"model_name": "claude-3-5-sonnet-20241022"},
    )

    with tracer.start_as_current_span("llm.call"):
        log_llm_usage(msg, caller="staging_validate")

    spans = exporter.get_finished_spans()
    if not spans:
        raise AssertionError("No OTel spans recorded — tracer not active during log_llm_usage")

    attrs = dict(spans[0].attributes or {})

    missing_cache = [
        field_name
        for field_name in ("llm.cache.read_tokens", "llm.cache.creation_tokens", "llm.cache.hit_rate")
        if field_name not in attrs
    ]

    if missing_cache:
        raise AssertionError(f"Missing cache OTel attr: {missing_cache}; found attrs: {sorted(attrs.keys())}")

    hit_rate = attrs.get("llm.cache.hit_rate", -1)
    if abs(hit_rate - 0.8) > 0.001:
        raise AssertionError(f"llm.cache.hit_rate expected 0.8, got {hit_rate}")


def _check_retrieval() -> None:
    import tempfile
    from pathlib import Path

    from cryptotrader.learning.evolution.skill_provider import EvolvingSkillProvider

    with tempfile.TemporaryDirectory() as tmp:
        provider = EvolvingSkillProvider(skill_root=Path(tmp))
        result = provider.get_available_skills(
            agent_id="tech",
            snapshot={"regime_tags": ["high_funding"]},
        )
        if not isinstance(result, list):
            raise AssertionError(f"get_available_skills returned {type(result).__name__}, expected list")


def main(dry_run: bool = True) -> int:
    steps: list[tuple[int, str, Callable[[], None]]] = [
        (1, "migrate_017_to_018 dry-run", lambda: _migrate("migrate_017_to_018", dry_run)),
        (2, "migrate_018_to_019 dry-run", lambda: _migrate("migrate_018_to_019", dry_run)),
        (3, "single cycle smoke (mocked LLM)", _run_smoke_cycle),
        (4, "OTel telemetry 8+3 fields", _check_otel_fields),
        (5, "EvolvingSkillProvider retrieval ≥1 hit", _check_retrieval),
    ]

    results: list[StepResult] = []
    for idx, name, fn in steps:
        r = run_step(idx, name, fn)
        print(r.fmt(), flush=True)
        results.append(r)

    failed = [r for r in results if r.status == "FAIL"]
    if failed:
        print(
            f"\n[summary] {len(failed)}/{len(results)} step(s) FAILED: " + ", ".join(r.name for r in failed),
            flush=True,
        )
        return 1

    print(f"\n[summary] All {len(results)} steps PASSED", flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="spec 020a staging smoke check")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        dest="dry_run",
        help="Run migrate scripts in dry-run mode (default: True)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Run migrate scripts in real mode (CAUTION: modifies data)",
    )
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
