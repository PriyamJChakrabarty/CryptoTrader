# CryptoTrader AI

[Simplified Chinese](README.md) | **English**

AI-powered crypto trading system using LangGraph multi-agent debate.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-2279%20collected-brightgreen.svg)]()

## Overview

4 specialized AI agents (Technical, On-chain, News, Macro) independently analyze market data, then debate through cross-challenge rounds to reach consensus. A hard-coded risk gate (11 rule-based checks, no LLM) enforces position limits, loss limits, and circuit breakers. Every decision is recorded in a Git-like Decision Journal for auditability.

Each agent runs a domain-specific **pre-signal checklist** (inspired by Devin's think-before-act pattern) to reduce overconfidence and hallucination before outputting signals.

### Key Features

- **Multi-agent debate** - 4 agents analyze independently, then cross-challenge each other over 2-3 rounds; the debate gate skips debate on consensus or confusion for progressive filtering
- **Three graph modes** - Full debate pipeline with debate gate, lite (backtest), and bull/bear adversarial with judge
- **11-check risk gate** - Pure rules, no LLM: position limits, CVaR, correlation, circuit breakers
- **Decision journal** - Git-like immutable commit chain stored in PostgreSQL `decision_commits`
- **Config-driven prompts** - Each agent's `system_prompt` / `output_schema` / `token_budget` lives in `config/agents/<name>.md`; `PromptBuilder` assembles them at runtime
- **EvolvingSkillProvider** (spec 019) - Two-stage retrieval (`scope` + `regime_tags` filter -> `idf` + `importance` + `recency` score) picks top-k skills from `agent_skills/_internal/<id>/SKILL.md` into the prompt
- **Trilogy evolution system** (spec 016 -> 020c) - 8 specs delivering PromptBuilder + Memory Evolution (5-signal Maturity FSM) + Skill Evolution + Pareto frontier + Git Lineage + Evolution Daemon (daily Pareto + Regime + Skill proposal loop)
- **Agent-Native Skill Protocol** (spec 022) - External `SKILL.md` interface: `agent_skills/_external/{cryptotrader,verdict-feed,market-intel,evolution-insights,execution-replay}/` lets foreign agents integrate via a single `Read /skill/cryptotrader` message; `/api/events/heartbeat` provides a pull-mode event feed; `/api/memory/patterns` exposes trilogy outputs
- **Mandatory numeric SL/TP** - Verdict must output `stop_loss` + `take_profit` as plain numbers; missing / direction-inverted / too-tight / R:R < 1.5 -> action forced to `hold`
- **Backtesting engine** - Historical simulation with realistic cost modeling and no look-ahead bias
- **Live trading ready** - OKX perp adapter via ccxt with retry, precision, configurable leverage (`set_leverage` idempotent retry + `long_short_mode` dual-side application), and server-side OCO protection
- **APScheduler automation + watchdog** - 4-hour trading cycles; scheduler watchdog inspects `last_successful_cycle_at` every 5 minutes and force-reschedules when staleness exceeds `1.5x interval` to defeat the `IntervalTrigger` silent-miss bug
- **61+ data sources** - Unified SQLite store across 7 categories with rate limiting per source
- **Prompt cache observability** - `apply_cache_control()` in production; OTel span attrs `llm.cache.{read,creation,hit_rate}`; Prometheus `llm_cache_hit_rate_24h_avg` gauge plus 3 spec 022 heartbeat / external-skill gauges
- **Close exempt from risk + cooldown fallback** - `close` bypasses the risk gate ("risk reduction must not be blocked"); during OKX venue cooldown `_build_close_order` falls back to `position_context` (DB-backed) instead of silently dropping
- **Live steering** - User real-time instructions flow through a Redis queue into the `live_steering` section, consumed once per cycle with no feedback loop

## Architecture

```text
Data Collection -> Regime Tagging -> 4 Agents (fan-out, parallel)
  -> Debate Gate -> [skip] -> Enrich Context -> Verdict
                -> [debate] -> 2 Debate Rounds (parallel per round)
  -> Verdict -> Risk Gate (11 checks) -> Execute / Reject -> Journal
                                        |
                                        v
                              Portfolio Write-back -> Snapshot
```

**Three graph variants:**
- `build_trading_graph()` - Full pipeline with debate gate (skip on consensus/confusion), 2 debate rounds, AI verdict with downgrade
- `build_lite_graph()` - Skips debate, used for backtesting
- `build_debate_graph()` - Bull/bear adversarial debate with judge (TradingAgents-style)

### How Agents Work

| Agent | Type | Data | Role |
|-------|------|------|------|
| TechAgent | BaseAgent | OHLCV + pure-pandas indicators (RSI, MACD, SMA, BBands, ATR, OBV) | Technical pattern recognition |
| ChainAgent | ToolAgent | OI, funding rate, exchange netflow, whale transfers, DeFi TVL | On-chain signal detection |
| NewsAgent | ToolAgent | RSS headlines + keyword sentiment + CoinGecko social buzz | News and sentiment analysis |
| MacroAgent | BaseAgent | Fed rate, DXY, BTC dominance, Fear and Greed, ETF flows, VIX | Macro regime assessment |

- **BaseAgent**: Single LLM call with structured JSON output
- **ToolAgent**: LangChain agent with a tool-calling loop for real-time data queries (falls back to a single call in backtest mode to avoid forward-looking bias)

Every agent's system prompt includes a **5-point pre-signal checklist**: contradiction check, evidence grounding, confidence sanity, base-rate awareness, and recency-trap avoidance. Confidence is calibrated on a 0-1 scale with `data_sufficiency="low"` capping output at 0.3.

### How Debate Works

1. **Round 1**: All 4 agents analyze independently in parallel
2. **Debate Gate**: Evaluates divergence; skips debate if agents already show consensus or confusion, otherwise proceeds to debate
3. **Round 2-3**: Each agent sees all others' analyses and must justify holding or revising its position with specific data points
4. **Convergence check**: Divergence score (population standard deviation of `confidence * direction`) is tracked per round; the process stops when relative change is below 10% or max rounds are reached
5. **Verdict**: A single LLM at temperature 0.1 sees all agent outputs, position context (FLAT/LONG/SHORT, entry price, unrealized PnL), price trend, and risk constraints -> outputs `{action, confidence, position_scale, reasoning, thesis, stop_loss, take_profit}`

### Prompt and Skill System

- **Directory layout** (spec 022 reorganization):
  - `agent_skills/_internal/{tech,chain,news,macro,trading-knowledge}/SKILL.md` - internal capabilities injected into agent prompts
  - `agent_skills/_external/{cryptotrader,verdict-feed,market-intel,evolution-insights,execution-replay}/SKILL.md` - external `SKILL.md` protocol for foreign agents and coding assistants
- **Skill retrieval**: `EvolvingSkillProvider` loads `agent_skills/_internal/<id>/SKILL.md`, filters by `scope` + `regime_tags`, scores by `idf + importance + recency`, and injects top-5 into each agent prompt's `available_skills` section; `access_count` / `last_accessed_at` persist to a gitignored sidecar
- **Skill content**: Human-maintained, git-tracked Markdown containing role + reasoning approach + checklists only; no historical case dumps, no directional predictions, no numeric thresholds
- **Regime tagging**: `tag_regime()` classifies the snapshot into discrete labels (`high_funding`, `high_vol`, `trending_up`, `extreme_fear`, etc.) used for skill retrieval filtering
- **SL/TP hard reject**: Verdict `stop_loss` + `take_profit` must be plain numbers and pass four checks: present / direction-correct / stop-distance >= `max(1.5 * ATR, 1.0% of entry)` / R:R >= 1.5. Failure forces `action=hold`
- **Live steering**: Frontend chat writes real-time instructions to a Redis queue; the next cycle drains and injects them into `live_steering` with a single-cycle lifetime
- **Agent-native integration** (spec 022): External agents register with one prompt - `Read http://host:8003/skill/cryptotrader and register` -> auto-pull bootstrap `SKILL.md` -> route to child skills -> call `/api/memory/patterns`, `/api/events/heartbeat`, `/api/verdicts/recent`, and related endpoints

## Quickstart

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Groq API key

### Installation

```bash
# Clone and install
git clone https://github.com/your-org/cryptotrader-ai.git
cd cryptotrader-ai
uv sync

# Configure the LLM endpoint
cp config/default.toml config/local.toml
# Edit config/local.toml and set [llm] api_key and base_url
# Groq base_url: https://api.groq.com/openai/v1
```

Use Groq by putting your Groq API key into `[llm].api_key` and setting `[llm].base_url = "https://api.groq.com/openai/v1"` in `config/local.toml`.

### First Run

```bash
# Run one analysis cycle (paper trading) - perp linear contracts recommended
# Spot accounts cannot short without inventory
arena run --pair BTC/USDT:USDT --mode paper

# Choose graph variant
arena run --pair BTC/USDT:USDT --graph full   # debate gate + 2 debate rounds
arena run --pair BTC/USDT:USDT --graph lite   # skip debate (backtest)
arena run --pair BTC/USDT:USDT --graph debate # bull/bear adversarial + judge

# View the decision journal
arena journal log --limit 10
arena journal show <hash>
```

### Backtesting

```bash
# Basic backtest with AI agents
arena backtest --pair BTC/USDT --start 2024-01-01 --end 2024-06-01 --interval 4h

# Fast backtest with SMA crossover (no LLM calls)
arena backtest --pair BTC/USDT --start 2024-01-01 --end 2024-06-01 --no-llm

# Sync historical data first for richer backtests
arena sync
```

The backtest engine features:
- **No look-ahead bias**: Signal on `bar[i]`, execution at `bar[i+1]` open
- **Realistic costs**: Configurable slippage (5 bps) + fees (10 bps)
- **Dynamic position sizing**: 35% at high confidence, 12% medium, 6% low
- **Rich data**: ETF flows, OI, long/short ratio, DeFi TVL, VIX, S&P 500, stablecoin supply, hashrate
- **Metrics**: Total return, Sharpe ratio (365d annualized), max drawdown, win rate, equity curve

### Scheduler

```bash
# Start periodic trading cycles (requires scheduler.enabled=true in config)
arena scheduler start

# Check portfolio status
arena scheduler status
```

APScheduler-based with `IntervalTrigger` (default 4 hours, aligned with OKX perp 4h candles + funding cadence) for trading cycles and `CronTrigger` for daily portfolio summaries.

**Scheduler watchdog** (post-spec-022 fix, commit `57eb884`): `AsyncIOScheduler.next_fire_time` can occasionally get stuck in the past, causing silent cycle misses. The watchdog checks `last_successful_cycle_at` every 5 minutes; if it exceeds `1.5 * interval_minutes`, the `trading_cycle` job is force-rescheduled via `modify_job`.

### Dashboard and API

```bash
# Web frontend (React + Vite)
arena web --port 5173

# FastAPI server
arena serve --port 8003
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `arena run --pair BTC/USDT --mode paper` | Single analysis + execution cycle |
| `arena run --pair BTC/USDT --graph full\|lite\|debate` | Choose graph variant |
| `arena backtest --pair BTC/USDT --start DATE --end DATE` | Historical backtest |
| `arena sync` | Sync all historical data to the SQLite store |
| `arena serve --port 8003` | Start the FastAPI server |
| `arena web` | Launch the React web frontend |
| `arena scheduler start` | Start the periodic scheduler |
| `arena scheduler status` | Show portfolio and positions |
| `arena journal log --limit 10` | Recent decisions |
| `arena journal show <hash>` | Decision detail |
| `arena migrate` | Create PostgreSQL tables |
| `arena risk reset-breaker` | Reset the circuit breaker |
| `arena live-check --exchange okx` | Pre-flight check for live trading |

## Data Sources

### Market and On-chain

Real-time data from 5 providers with graceful degradation (works even without most optional API keys):

| Provider | Data | Cost | Key Required |
|----------|------|------|-------------|
| Binance | Futures OI, funding rate, liquidations, long/short ratio | Free | No |
| DefiLlama | DeFi TVL, 7d change, stablecoin supply | Free | No |
| CoinGlass | Open interest, liquidations | Free tier (1000/month) | Yes |
| CryptoQuant | Exchange netflow | Free tier (daily) | Yes |
| Whale Alert | Large transfers | Free tier (10/minute) | Yes |

### News and Sentiment

| Source | Data | Cost |
|--------|------|------|
| CoinDesk, CoinTelegraph, Decrypt | Headlines via RSS | Free |
| CoinGecko Community API | Social buzz (Twitter followers, Reddit subscribers, sentiment votes) | Free |

### Macro

| Source | Data | Cost |
|--------|------|------|
| FRED | Fed funds rate, DXY, VIX, S&P 500 | Free (key required) |
| CoinGecko | BTC dominance | Free |
| Alternative.me | Fear and Greed Index | Free |
| SoSoValue | BTC/ETH ETF daily flows, net assets | Free (key required) |

### Unified Data Store

All data is cached in `~/.cryptotrader/market_data.db` (SQLite, WAL mode):

- 61+ data sources across 7 categories (macro, on-chain, derivatives, DeFi, sentiment, ETF, stablecoin)
- Per-source rate limiting (5 minutes to 1 hour TTL depending on source)
- Forward-fill for trading-day data (FRED, ETF) to handle weekends and holidays
- `arena sync` bulk-fetches all historical data for backtesting

## Configuration

### Config Files

```text
config/
|-- default.toml            # Main config (mode, models, risk, scheduler, providers)
|-- local.toml              # Local overrides (API keys, gitignored)
`-- exchanges.toml.example  # Exchange credential template
```

Config loads `default.toml` first, then deep-merges `local.toml`. The result is cached after first load.

### Key Config Sections

```toml
[llm]
api_key = ""           # Groq API key
base_url = ""          # API endpoint (for example "https://api.groq.com/openai/v1")

[models]               # Per-role model selection (must be available in your LLM gateway)
analysis = "deepseek-v4-flash"
debate = "deepseek-v4-flash"
verdict = "gpt-5.5"
tech_agent = "deepseek-v4-flash"
chain_agent = "deepseek-v4-flash"
news_agent = "deepseek-v4-flash"
macro_agent = "deepseek-v4-flash"
fallback = "deepseek-v4-flash"
# Empty model name -> resolves to `models.analysis` then `models.fallback`

[debate]
max_rounds = 3
convergence_threshold = 0.1
skip_debate = true
consensus_skip_threshold = 0.5
confusion_skip_threshold = 0.05
confusion_max_dispersion = 0.2

[risk]
max_stop_loss_pct = 0.05

# Defaults (multi-pair diversified):
[risk.position]
max_single_pct = 0.10
max_total_exposure_pct = 0.50
max_margin_used_pct = 0.40

# BTC-only concentrated production overrides (config/local.toml, post-spec-022):
# [risk.position]
# max_single_pct = 0.80
# max_total_exposure_pct = 4.00       # 5x leverage * 80% single -> total notional cap
# max_margin_used_pct = 0.90
# max_same_direction_positions = 1    # BTC is the sole pair

[risk.loss]
max_daily_loss_pct = 0.03
max_drawdown_pct = 0.10

[scheduler]
enabled = false
pairs = ["BTC/USDT:USDT"]    # BTC-only concentrated strategy; perp linear contract
interval_minutes = 240       # 4h cadence, aligned with OKX perp 4h candles + 8h funding
exchange_id = "okx"          # production uses OKX perp
daily_summary_hour = 0       # UTC hour (0-23)

[exchanges.okx]              # set in config/local.toml (gitignored)
api_key = "..."
secret = "..."
passphrase = "..."
sandbox = true               # demo trading environment
leverage = 5                 # BTC 5x
margin_mode = "isolated"     # OKX: "isolated" | "cross"
```

### Environment Variables

```bash
# -- API authentication (REQUIRED for production) --
# Default: AUTH_MODE=enabled - API_KEY MUST be set or the process fails to start.
# Use AUTH_MODE=disabled only for local dev (logs WARNING per request).
AUTH_MODE=enabled
API_KEY=$(openssl rand -hex 32)

# -- On-chain providers (optional but recommended) --
# When unset, providers return None; the chain_agent prompt is told which
# data sources are unavailable so it lowers data_sufficiency accordingly.
COINGLASS_API_KEY=your_key
CRYPTOQUANT_API_KEY=your_key
WHALE_ALERT_API_KEY=your_key
FRED_API_KEY=your_key

# -- Infrastructure (read by config when CRYPTOTRADER_INFRASTRUCTURE__* prefix is used) --
CRYPTOTRADER_INFRASTRUCTURE__DATABASE_URL=postgresql+asyncpg://...
CRYPTOTRADER_INFRASTRUCTURE__REDIS_URL=redis://localhost:6379

# -- Frontend (production builds reject VITE_API_KEY at build time) --
# Use only in dev .env.local for one-time hydration into useSettingsStore.
VITE_API_BASE_URL=http://localhost:8003
# VITE_API_KEY= (dev only; production users enter the key in Settings UI)
```

Groq setup: set the Groq key in `[llm].api_key` and use `https://api.groq.com/openai/v1` as `[llm].base_url`.

## Risk Gate

11 rule-based checks (no LLM), all configurable in `config/default.toml` under `[risk]`:

| Check | What it does | Default |
|-------|--------------|---------|
| Max Position Size | Cap a single position as % of the portfolio | 10% |
| Total Exposure | Limit total open exposure | 50% |
| Daily Loss Limit | Trigger circuit breaker on daily loss threshold | 3% |
| Max Drawdown | Reject trades during deep drawdowns | 10% |
| CVaR (99%) | Conditional Value-at-Risk from recent returns | 5% |
| Correlation | Block correlated positions (14 hardcoded groups) | - |
| Cooldown | Minimum time between trades on the same pair | 60 min |
| Post-Loss Cooldown | Extra cooldown after a losing trade | 120 min |
| Volatility | Reject during extreme volatility or flash crashes | - |
| Funding Rate | Block when funding rate signals crowded positioning | - |
| Rate Limit | Cap trades per hour/day | - |
| Exchange Health | Check API latency before execution | - |

The `close` action (closing existing positions) is **exempt from all risk checks** because reducing exposure should never be blocked.

## Notifications

Webhook notifications for 6 event types (configure in `config/default.toml`):

| Event | Trigger |
|-------|---------|
| `trade` | Successful order fill |
| `rejection` | Risk gate rejects a trade |
| `circuit_breaker` | Daily loss limit triggers the circuit breaker |
| `daily_summary` | Scheduler emits a daily portfolio summary |
| `reconcile_mismatch` | Position reconciliation detects a mismatch |
| `portfolio_stale` | Portfolio data becomes stale or unavailable |

## API and Authentication

FastAPI auto-generates OpenAPI: start `arena serve --port 8003` and visit `http://localhost:8003/docs` for Swagger UI or `/redoc` for ReDoc. The external protocol entry point is `GET /skill/<name>` (public, no auth) with 5 child skills: `cryptotrader`, `verdict-feed`, `market-intel`, `evolution-insights`, and `execution-replay`.

**Authentication**: Default `AUTH_MODE=enabled` requires the `API_KEY` environment variable; missing key fails startup. `AUTH_MODE=disabled` bypasses auth and logs a WARNING per request (dev only). All comparisons use `secrets.compare_digest` for timing-safe checks.

**Rate limit**: 60 requests/minute/IP, Redis-backed when configured for multi-process safety, with an in-memory fallback for single-process dev.

**CORS**: Explicit `allow_methods` / `allow_headers` allowlist (no wildcards) because `allow_credentials=true`.

## Execution Layer

### Paper Trading

- Default mode, no real money at risk
- Configurable initial balance (default `$10,000`)
- Slippage model: `base + amount * price * 1e-8`
- Thread-safe via `asyncio.Lock`

### Live Trading

Production-hardened `LiveExchange` wrapping ccxt:

- **Retry**: Exponential backoff (3 attempts), fatal errors excluded (auth, permissions, insufficient funds)
- **Balance pre-check**: Verifies sufficient funds before every order
- **Precision**: Applies exchange-specific `amount_to_precision()` / `price_to_precision()`
- **Minimum order**: Checks exchange market limits
- **Timeout**: Polls every 2 seconds for up to 30 seconds, then auto-cancels stale orders
- **Pre-flight**: `arena live-check` validates credentials, API latency, Redis, and database

```bash
# Verify live trading readiness
arena live-check --exchange okx
```

## Docker Deployment

```bash
# Start full stack (PostgreSQL 16 + Redis 7 + API + Web + Scheduler + Caddy)
docker compose up -d

# Services (docker-compose.yml):
#   postgres   - Decision journal + portfolio persistence
#   redis      - Risk state + cooldowns + circuit breaker
#   api        - FastAPI on :8003 (embedded scheduler + watchdog)
#   web        - React frontend on :5173
#   scheduler  - Standalone scheduler process (mutually exclusive with api; pick one)
#   caddy      - Reverse proxy + TLS
```

The Dockerfile uses a multi-stage build with a non-root user. Health checks poll `/health` every 30 seconds.

## Project Structure

```text
src/cryptotrader/
|-- models.py                 # All data models (DataSnapshot, AgentAnalysis, TradeVerdict, Order, etc.)
|-- config.py                 # TOML config loading + dataclass validation
|-- graph.py                  # LangGraph orchestration (3 graph variants)
|-- state.py                  # ArenaState TypedDict + build_initial_state() factory
|-- scheduler.py              # APScheduler-based periodic trading cycles + daily summary
|-- notifications.py          # Webhook notifications (6 event types)
|-- db.py                     # Shared async DB session factory
|-- data/
|   |-- store.py              # Unified SQLite store (61+ sources, rate limiting)
|   |-- snapshot.py           # SnapshotAggregator (data collection entry point)
|   |-- market.py             # ccxt OHLCV + ticker + funding rate + volatility
|   |-- onchain.py            # Aggregates 5 providers (parallel fetch)
|   |-- news.py               # RSS + keyword sentiment + CoinGecko social buzz
|   |-- macro.py              # FRED + CoinGecko + Fear and Greed + SoSoValue ETF
|   |-- sync.py               # Bulk historical sync (arena sync)
|   `-- providers/            # Binance, DefiLlama, CoinGlass, CryptoQuant, WhaleAlert, SoSoValue
|-- agents/
|   |-- base.py               # BaseAgent + ToolAgent + create_llm() factory
|   |-- tech.py               # TechAgent (uses pure pandas/numpy indicators)
|   |-- chain.py              # ChainAgent (ToolAgent with on-chain tools)
|   |-- news.py               # NewsAgent (ToolAgent with news tools)
|   |-- macro.py              # MacroAgent (macro regime analysis)
|   `-- data_tools.py         # LangChain @tool definitions (6 chain + 3 news)
|-- debate/
|   |-- challenge.py          # Cross-challenge prompt construction
|   |-- convergence.py        # Divergence score + convergence detection
|   |-- verdict.py            # AI verdict (LLM) + rules verdict (backtest)
|   `-- researchers.py        # Bull/bear adversarial debate with judge
|-- nodes/
|   |-- agents.py             # 4-agent fan-out
|   |-- data.py               # Data collection + PnL update + trend context
|   |-- debate.py             # Debate rounds + convergence routing
|   |-- verdict.py            # Verdict + risk check
|   |-- execution.py          # Order placement + stop loss + position update
|   `-- journal.py            # Decision logging
|-- risk/
|   |-- gate.py               # RiskGate (11 sequential checks)
|   `-- state.py              # RedisStateManager (with in-memory fallback)
|-- execution/
|   |-- simulator.py          # PaperExchange (paper trading)
|   |-- exchange.py           # LiveExchange (ccxt, production-hardened)
|   |-- order.py              # OrderManager (state machine)
|   `-- reconcile.py          # Position reconciliation
|-- portfolio/
|   `-- manager.py            # PortfolioManager (DB + in-memory)
|-- journal/
|   |-- store.py              # JournalStore (PostgreSQL + in-memory fallback)
|   `-- commit.py             # DecisionCommit + immutable hash-chained schema
|-- learning/
|   |-- regime.py             # tag_regime (market regime labels)
|   `-- evolution/
|       |-- skill_provider.py # EvolvingSkillProvider (scope + regime + idf retrieval)
|       `-- idf.py            # IDF scoring + keyword extraction
`-- backtest/
    |-- engine.py             # BacktestEngine (LLM + SMA modes)
    |-- session.py            # Backtest session storage (commits, results)
    |-- cache.py              # OHLCV SQLite cache
    |-- historical_data.py    # FnG, funding rate, FRED, futures volume
    `-- result.py             # BacktestResult metrics

src/cli/main.py               # Typer CLI (arena command)
src/api/                      # FastAPI server (auth, rate limiting, middleware)
web/                          # React 19 + Vite 8 frontend (dashboard, decisions, backtest, risk, metrics)
agent_skills/
|-- _internal/                # Capabilities injected into agent prompts (spec 019/022)
|   |-- tech-analysis/SKILL.md
|   |-- chain-analysis/SKILL.md
|   |-- news-analysis/SKILL.md
|   |-- macro-analysis/SKILL.md
|   `-- trading-knowledge/SKILL.md
`-- _external/                # External SKILL.md protocol (spec 022)
    |-- cryptotrader/SKILL.md
    |-- verdict-feed/SKILL.md
    |-- market-intel/SKILL.md
    |-- evolution-insights/SKILL.md
    `-- execution-replay/SKILL.md
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Package Manager | uv + Hatchling |
| LLM Orchestration | LangChain 1.2+ / LangGraph 1.0+ |
| LLM Provider | Groq |
| Exchange | ccxt (OKX perp primary) |
| Data Processing | pandas + numpy (pure-Python indicators in `agents/_indicators.py`) |
| Scheduling | APScheduler 3.x |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async |
| Cache / State | Redis 7 |
| Local Storage | SQLite (market data store + LLM response cache) |
| API Server | FastAPI + Uvicorn |
| Dashboard | React 19 + Vite 8 + TypeScript 5.9 |
| CLI | Typer + Rich |

## Development

```bash
make install          # uv pip install -e ".[dev]"
make test             # uv run pytest tests/ -v (2279 tests)
make lint             # ruff check src/ tests/
make format           # ruff format src/ tests/
make scheduler        # arena scheduler start
make pre-commit-run   # Run all pre-commit hooks

# Run a single test
uv run pytest tests/test_risk_gate.py -v
uv run pytest tests/test_risk_gate.py::test_max_position -v

# Docker infrastructure
docker compose up -d  # PostgreSQL 16 + Redis 7
arena migrate         # Create database tables
arena sync            # Sync historical data
```

### Code Quality

- **Zero lint errors**: `ruff check src/ tests/` must pass with zero errors
- **No `noqa` comments**: Refactor instead of suppressing (C901 threshold = 10)
- **2279 tests collected** as the spec 022 baseline; 9 pre-existing failures are unrelated to the current spec
- **Async tests**: `asyncio_mode = "auto"` - no `@pytest.mark.asyncio` needed
- **Use `uv run pytest`** with the Python 3.12 virtual environment, not bare `pytest`

## Author

Name: Priyam Jyoti Chakrabarty

Institute: Indian Institute of Information Technology Allahabad, Prayagraj, India

## License

MIT
