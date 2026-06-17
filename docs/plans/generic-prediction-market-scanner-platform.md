# Nunu — Generic Prediction Market Scanner Platform

## Goal

Build a **Kalshi prediction market scanner platform** with:

1. **Python backend** running the 8-engine pipeline (FastAPI REST + WebSocket)
2. **TypeScript/React web UI** for real-time monitoring and control
3. **Three operating modes:**
   - **Dry-run (default)** — full pipeline runs, candidates generated, simulated fills, no real orders
   - **Read-only** — scan, display, save candidates — never touches the order API
   - **Live trading** — full pipeline + pre-trade validation + real order placement
4. Discovers live-now, ending-today events on Kalshi
5. Groups markets into events and ranks them by real-time orderbook activity
6. Tracks event progress and detects when a user-configurable threshold is crossed (default 65%)
7. Selects the **most-volume market** and **dominant side** (YES/NO) using **executed trade volume** as the primary signal
8. Ships with **7 strategy experiments** (default: **executed-volume-follower**) with a full backtesting framework
9. **Live paper-trading logger** to capture orderbook snapshots and trade decisions forward

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Python Backend (FastAPI)                      │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │   Engine Pipeline │─▶│  Scanner State   │─▶│  REST API      │ │
│  │  (8 engines)      │  │  Manager         │  │  + WebSocket   │ │
│  └────────┬─────────┘  └──────────────────┘  └───────┬────────┘ │
│           │                                            │         │
│  ┌────────▼─────────┐  ┌──────────────────┐           │         │
│  │  Kalshi Adapter   │  │  Trade Executor  │           │         │
│  │  (REST + WS)      │  │  (dry/read/live) │           │         │
│  └──────────────────┘  └──────────────────┘           │         │
└───────────────────────────────────────────────────────┼─────────┘
                                                        │
                                                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                  TypeScript Frontend (React/Vite)                  │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │  Dashboard View   │  │  Event Detail    │  │  Config Panel  │ │
│  │  (live events)    │  │  (markets/ob)    │  │  (thresholds)  │ │
│  └──────────────────┘  └──────────────────┘  └────────────────┘ │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │  Order Candidates │  │  Trade Log       │  │  Mode Switch   │ │
│  │  (review/approve) │  │  (history)       │  │  (dry/read/live)│ │
│  └──────────────────┘  └──────────────────┘  └────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Non-Negotiable Design Rules

1. **No category/keyword allowlists** in discovery — everything is lifecycle-based
2. **Classify markets first**, group into events second
3. **Orderbook data enriches** events but does **not** filter them from discovery
4. **Progress gates** are user-configurable per-run, default 65%
5. **Pre-trade validation** always re-fetches live data — never trade on stale state
6. **Engines are stateless pipelines** — all state lives in the runtime context
7. **All three modes share the same pipeline** — only the final execution step differs
8. **Dry-run is the default** — you always see what *would* happen before it does
9. **Strategy profiles are pluggable** — ship with one, add more as one-file plugins

---

## Generic Data Model (Python)

```python
# ──── Core abstractions ────
# These live in src/core/models.py.

@dataclass
class Market:
    id: str                    # Kalshi: ticker
    event_id: str              # Kalshi: event_ticker
    status: str                # "active" | "closed" | "settled" | ... (Kalshi uses "active" for open markets)
    title: str
    open_time: str             # ISO 8601
    close_time: str
    expected_expiration_time: Optional[str] = None
    latest_expiration_time: Optional[str] = None
    yes_bid: Optional[str] = None
    yes_ask: Optional[str] = None
    no_bid: Optional[str] = None
    no_ask: Optional[str] = None
    volume_24h: Optional[str] = None
    total_volume: Optional[str] = None

@dataclass
class Event:
    id: str
    title: str = ""
    market_ids: list[str] = field(default_factory=list)
    market_count: int = 0
    live_market_count: int = 0

@dataclass
class OrderbookLevel:
    price: float     # In dollars
    size: float      # Quantity at this level

@dataclass
class Orderbook:
    market_id: str
    yes_bids: list[OrderbookLevel] = field(default_factory=list)
    no_bids: list[OrderbookLevel] = field(default_factory=list)

@dataclass
class MarketOrderbookStats:
    market_id: str
    event_id: str
    total_resting_order_quantity: float
    yes_order_quantity: float
    no_order_quantity: float
    depth_level_count: int
    best_yes_bid: Optional[float] = None
    best_no_bid: Optional[float] = None
    volume_24h: float = 0.0
    total_volume: float = 0.0

@dataclass
class OrderCandidate:
    event_id: str
    market_id: str
    side: str                    # "yes" | "no"
    estimated_price: float
    estimated_size: float
    progress_percent: float
    threshold_percent: float
    confidence: str              # "high" | "medium" | "low"
    requires_manual_review: bool = False
    reasons: list[str] = field(default_factory=list)

@dataclass
class ValidatedOrderCandidate(OrderCandidate):
    validation_timestamp: str = ""
    pre_trade_market: Optional[Market] = None
    pre_trade_orderbook: Optional[Orderbook] = None
    pre_trade_stats: Optional[MarketOrderbookStats] = None

# ──── Backtesting data models ────

@dataclass
class HistoricalTrade:
    """A single executed trade on Kalshi."""
    market_ticker: str
    trade_time: datetime
    yes_price: float       # cents
    no_price: float        # cents
    count: int             # contract count
    taker_side: Optional[str]  # "YES" | "NO" | None
    is_block_trade: bool = False

@dataclass
class Candlestick:
    """OHLC candlestick for a market."""
    market_ticker: str
    bucket_start: datetime
    open_yes_price: float
    high_yes_price: float
    low_yes_price: float
    close_yes_price: float
    volume: float = 0.0

@dataclass
class OrderbookSnapshot:
    """Point-in-time orderbook snapshot for backtesting resting-depth strategies."""
    market_ticker: str
    snapshot_time: datetime
    yes_bid_price: float
    yes_bid_quantity: float
    no_bid_price: float
    no_bid_quantity: float
    yes_total_depth: float
    no_total_depth: float
    spread: float

@dataclass
class MarketFeatures:
    """Pre-computed features for one child market at entry time."""
    market_ticker: str
    market_title: str
    result: Optional[str]          # settlement outcome (YES/NO) — for backtesting
    status: str
    total_executed_volume: float
    yes_executed_volume: float
    no_executed_volume: float
    trade_count: int
    yes_price: float
    no_price: float
    yes_best_bid: Optional[float] = None
    no_best_bid: Optional[float] = None
    yes_total_depth: Optional[float] = None
    no_total_depth: Optional[float] = None
    spread: Optional[float] = None
    yes_price_momentum: Optional[float] = None  # price change from reference
    open_interest: Optional[float] = None

@dataclass
class EventFeatures:
    """Pre-computed features for one event at a given threshold."""
    event_ticker: str
    event_title: str
    category: str
    event_progress: float
    threshold: float
    entry_time: datetime
    child_markets: list[MarketFeatures] = field(default_factory=list)

@dataclass
class TradeDecision:
    """Unified output for every strategy experiment."""
    event_ticker: str
    market_ticker: str
    selected_side: str                    # "YES" | "NO"
    trade_decision: str                   # "BUY_YES" | "BUY_NO" | "SKIP"
    skip_reason: Optional[str] = None
    entry_price_cents: Optional[float] = None
    entry_threshold: Optional[float] = None
    event_progress_at_entry: Optional[float] = None
    side_signal_strength: Optional[float] = None
    market_signal_strength: Optional[float] = None
    selected_market_reason: Optional[str] = None
    selected_side_reason: Optional[str] = None
    experiment_id: Optional[str] = None
    estimated_fee_cents: float = 1.0
    max_acceptable_price_cents: float = 85.0
```

---

## Engine Pipeline Architecture

```
                      ┌──────────────────┐
                      │  Kalshi REST API  │
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 1           │  Market Discovery │─── fetch_all_open_markets()
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 2           │ Live Classification│─── classify_same_day_live()
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 3           │  Event Grouping   │─── group_by_event_ticker()
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 4           │ Orderbook Fetch   │─── fetch_orderbooks()
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 5           │ Market Ranking    │─── rank_by_resting_orders()
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 6           │ Progress Gate     │─── check_threshold() + select_side()
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 7           │ Pre-Trade Validate│─── revalidate_candidate()
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
   Engine 8           │ Orchestration     │─── run_pipeline() + dispatch()
                      └──────────────────┘
```

---

## Three Operating Modes

### Mode 1: Dry-Run (default)

```
Pipeline runs fully:
  E1→E2→E3→E4→E5→E6→E7   ✅ all execute
  E8 produces candidates   ✅ output to UI + logs
  Trade Executor           ⛔ simulates placement, logs result
  Real API                 ⛔ never called for orders
```

**Behavior:**
- Order candidates generated and displayed in UI
- Each candidate shows a **simulated fill result** (price, size, timestamp)
- A "Place Order" button exists but is disabled — shows **"DRY RUN" badge**
- All simulated trades logged to dry-run history
- User can toggle into live mode from config panel (with confirmation dialog)

### Mode 2: Read-Only

```
Pipeline runs fully:
  E1→E2→E3→E4→E5→E6   ✅ all execute
  E7 (validation)       ✅ runs but does not place
  E8                    ✅ produces candidates for review only
  Trade Executor        ⛔ not invoked
  Order API             ⛔ never called
```

**Behavior:**
- Same as dry-run but no simulated fills
- Candidates are for **manual review only** — no suggestion of placement
- Pure information display

### Mode 3: Live Trading

```
Pipeline runs fully:
  E1→E2→E3→E4→E5→E6→E7   ✅ all execute with real-time re-fetch
  E8                      ✅ produces validated candidates
  Trade Executor          ✅ invoked with validated candidate
  Kalshi Order API        ✅ called with proper auth
```

**Behavior:**
- Full pipeline with pre-trade validation (Engine 7 re-fetches market + orderbook)
- Order placed via Kalshi API
- Result logged to trade history
- Risk limits enforced (configurable max exposure)
- Requires authentication configured

### Mode State Machine

```
                    ┌──────────┐
                    │  DRY RUN │◀──── default on every startup
                    └────┬─────┘
                         │ toggle (with confirmation dialog)
                    ┌────▼─────┐
                    │ LIVE     │
                    │ TRADING  │
                    └────┬─────┘
                         │
                         ├── on auth failure ──▶ back to DRY RUN
                         ├── on risk limit    ──▶ stays LIVE, blocks order
                         └── on manual stop   ──▶ back to DRY RUN
```

Read-only mode is a separate boot-time choice (e.g. `--mode readonly` flag), not a runtime toggle.

---

## Python Backend Architecture

```
backend/
├── main.py                        # FastAPI app entry point
├── config/
│   ├── __init__.py
│   ├── settings.py                # Pydantic settings (env, YAML)
│   └── defaults.py                # Default thresholds, endpoints
├── core/
│   ├── __init__.py
│   ├── models.py                  # Shared data models/dataclasses
│   ├── interfaces.py              # Abstract provider contract
│   └── scanner_state.py           # Runtime state manager
├── adapters/
│   ├── __init__.py
│   ├── kalshi/
│   │   ├── __init__.py
│   │   ├── adapter.py             # KalshiAdapter implements interfaces
│   │   ├── client.py              # REST API client (httpx)
│   │   ├── websocket.py           # WebSocket client
│   │   └── types.py               # Kalshi-specific type mappers
│   └── registry.py                # Adapter registry
├── engines/
│   ├── __init__.py
│   ├── engine1_discovery.py       # Fetch open markets
│   ├── engine2_classification.py  # Classify same-day live
│   ├── engine3_grouping.py        # Group by event_ticker
│   ├── engine4_orderbook.py       # Fetch orderbooks
│   ├── engine5_ranking.py         # Rank by resting orders
│   ├── engine6_progress_gate.py   # Progress threshold + side selection
│   ├── engine7_validation.py      # Pre-trade validation
│   ├── engine8_orchestrator.py    # Pipeline orchestrator
│   └── live/
├── strategies/
│   ├── __init__.py                # EXPERIMENT_REGISTRY + get_experiment()
│   ├── base.py                    # StrategyExperiment ABC
│   ├── executed_volume_follower.py      # ✅ Primary target
│   ├── executed_volume_fade.py          # ⏸ Untested
│   ├── favorite_side_follower.py        # ⏸ Untested
│   ├── momentum_follower.py             # ⏸ Untested
│   ├── liquidity_filtered_follower.py   # ⏸ Untested
│   ├── resting_depth_follower.py        # ⏸ Untested
│   ├── hybrid_score_follower.py         # ⏸ Untested
│   └── backtesting/
│       ├── __init__.py
│       ├── backtest_engine.py
│       ├── feature_builder.py
│       ├── entry_simulator.py
│       ├── exit_simulator.py
│       └── metrics.py
│       ├── websocket_updater.py   # WS state patching
│       ├── event_reranker.py      # Single-event rerank
│       └── progress_gate_loop.py  # Periodic progress check
├── trading/
│   ├── __init__.py
│   ├── trade_executor.py          # Order placement (all 3 modes)
│   ├── dry_run_simulator.py       # Simulated fills for dry-run
│   ├── position_tracker.py        # Track open positions
│   └── risk_manager.py            # Max exposure, limits
├── api/
│   ├── __init__.py
│   ├── rest.py                    # FastAPI REST routes
│   ├── websocket_handler.py       # WebSocket event broadcasting
│   └── schemas.py                 # Pydantic request/response schemas
└── logging/
    ├── __init__.py
    ├── csv_logger.py              # CSV candidate/trade logging
    └── trade_history.py           # Trade history persistence
```

---

## TypeScript Frontend Architecture

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── App.tsx                    # Root component with router
│   ├── pages/
│   │   ├── Dashboard.tsx          # Live scanner dashboard
│   │   ├── Events.tsx             # All events list
│   │   ├── EventDetail.tsx        # Single event with markets
│   │   ├── Candidates.tsx         # Order candidates review
│   │   ├── Trades.tsx             # Trade history
│   │   └── Settings.tsx           # Configuration panel
│   ├── components/
│   │   ├── Dashboard/
│   │   │   ├── EventCard.tsx      # Single event with top markets
│   │   │   ├── EventList.tsx      # Paginated event list
│   │   │   ├── MarketRow.tsx      # Market within event
│   │   │   └── ScannerStatus.tsx  # Connection status, mode badge
│   │   ├── Orderbook/
│   │   │   ├── OrderbookDepth.tsx # Orderbook visualization
│   │   │   ├── BidAskChart.tsx    # Price level chart
│   │   │   └── SpreadIndicator.tsx# Spread display
│   │   ├── Candidates/
│   │   │   ├── CandidateCard.tsx  # Single candidate with details
│   │   │   ├── CandidateList.tsx  # All candidates
│   │   │   └── CandidateActions.tsx # Review/Approve/Reject
│   │   ├── Trading/
│   │   │   ├── ModeSelector.tsx   # Dry-run / Live toggle
│   │   │   ├── ConfirmDialog.tsx  # Safety confirmation
│   │   │   └── TradeHistory.tsx   # Trade log
│   │   ├── Controls/
│   │   │   ├── ThresholdSlider.tsx # Progress threshold adjust
│   │   │   ├── StrategySelector.tsx# Strategy profile picker
│   │   │   └── RefreshControl.tsx # Auto-refresh toggle
│   │   └── Common/
│   │       ├── Badge.tsx          # Mode badge (DRY/LIVE/READ)
│   │       ├── ProgressBar.tsx    # Event progress bar
│   │       └── SideIndicator.tsx  # YES/NO side indicator
│   ├── hooks/
│   │   ├── useWebSocket.ts       # Real-time data hook
│   │   ├── useScanner.ts         # Scanner state hook
│   │   └── useCandidates.ts      # Candidates hook
│   ├── lib/
│   │   ├── api.ts                # REST API client (fetch)
│   │   ├── types.ts              # Shared TypeScript types
│   │   └── constants.ts          # Frontend constants
│   └── styles/
│       └── globals.css
├── public/
│   └── favicon.svg
└── index.html
```

### Frontend Routes

| Route | Purpose | Shows |
|-------|---------|-------|
| `/` | Dashboard | Live events, top markets, scanner status, mode badge |
| `/events` | All events | Searchable, filterable event list |
| `/events/[id]` | Event detail | Event progress, all markets, orderbook, ranked list |
| `/candidates` | Order candidates | All candidates, filter by status, approve/reject |
| `/trades` | Trade history | Executed trades (real or dry-run) |
| `/settings` | Configuration | Threshold, mode, auth, strategy profile |

---

## Strategy Experiments

### Design: Research-First, Backtest-Verified

The platform ships with **seven strategy experiments** from day one. The default is **Experiment A (executed-volume-follower)** using **executed trade volume** as the primary signal — not resting orderbook quantity.

**Critical correction from earlier logic:** The original "most-bet" approach used resting orderbook quantity as a proxy for "most bet." Resting orders can be market-maker liquidity, spoof-like behavior, stale quotes, or unfilled intent. Executed trade volume is a better signal for actual betting activity.

All experiments are treated as **research hypotheses** until backtested and forward-paper-traded. See `docs/engines/strategy-system.md` for full experiment implementations.

### Experiment Summary

| ID | Experiment | Market Selection | Side Selection | Primary Data |
|----|------------|-----------------|----------------|-------------|
| **A** | Executed-volume follower (default) | Highest executed volume | Side with more executed volume | Historical trades |
| **B** | Executed-volume fade | Highest executed volume | Opposite of dominant side | Historical trades |
| **C** | Favorite-side follower | Highest executed volume | Higher priced side (price > 50 → YES) | Candlesticks |
| **D** | Momentum follower | Largest price move (reference → threshold) | Direction of movement | Candlesticks |
| **E** | Liquidity-filtered follower | Highest executed volume (with liquidity filters) | Side with more executed volume | Trades + filters |
| **F** | Resting-depth follower | Highest total resting depth | Side with more resting depth | Orderbook snapshots |
| **G** | Hybrid score follower | Highest weighted hybrid score | Higher YES/NO hybrid score | All sources |

### Interface

```python
class StrategyExperiment(ABC):
    name: str
    description: str
    config: dict

    @abstractmethod
    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        """Evaluate all child markets and return a trade decision."""
        ...
```

### Config

```yaml
# config/settings.yaml
strategy:
  active_experiment: executed-volume-follower   # switch here
  default_threshold: 0.60

  experiments:
    executed-volume-follower: {}
    executed-volume-fade: {}
    favorite-side-follower: {}
    momentum-follower:
      early_reference_progress: 0.40
    liquidity-filtered-follower:
      min_total_executed_volume: 500
      min_trade_count: 20
      max_spread_cents: 5
      max_entry_price_cents: 85
      min_entry_price_cents: 15
      exclude_block_trades: true
    resting-depth-follower: {}
    hybrid-score-follower: {}

  execution:
    mode: taker           # taker | maker
    hold_to_settlement: true

  risk:
    position_size_dollars: 10
    max_daily_loss_dollars: 100
    max_open_positions: 10
    max_positions_per_event: 1
```

The frontend `StrategySelector` dropdown reads available experiments from the backend `/api/v1/config` endpoint.

See `docs/engines/strategy-system.md` for full experiment profiles and pseudocode.

---

## API Contract

The full backend↔frontend communication contract is defined in [`docs/api-contract.md`](../api-contract.md). This single document contains:

- **Every REST endpoint** with full request/response schemas (Pydantic ↔ TypeScript)
- **Every WebSocket message type** with payload shapes
- **Error contract** — all error codes, HTTP statuses, and response formats
- **Type alignment** — Python dataclass ↔ TypeScript interface for every shared type
- **Frontend API client** — the exact `ScannerAPI` class the frontend implements
- **Rate limiting** — limits, headers, backoff behavior
- **Contract versioning** — how the backend and frontend stay in sync

### REST Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/scanner/status` | Scanner state, mode, connected status |
| POST | `/api/v1/scanner/start` | Start scanner (one-shot or live) |
| POST | `/api/v1/scanner/stop` | Stop scanner |
| GET | `/api/v1/events` | List all same-day live events |
| GET | `/api/v1/events/{id}` | Event detail with ranked markets |
| GET | `/api/v1/events/{id}/orderbook` | Orderbook for a specific market |
| GET | `/api/v1/candidates` | All order candidates |
| GET | `/api/v1/candidates/{id}` | Single candidate detail |
| POST | `/api/v1/candidates/{id}/approve` | Approve candidate for trading |
| POST | `/api/v1/candidates/{id}/reject` | Reject candidate |
| GET | `/api/v1/trades` | Trade history |
| GET | `/api/v1/config` | Current config |
| PUT | `/api/v1/config` | Update config |
| POST | `/api/v1/mode` | Switch mode (dry-run ↔ live) |

> **Full schemas, examples, TypeScript types, and error codes → [`docs/api-contract.md`](../api-contract.md)**

### WebSocket Endpoints Summary

| Path | Channels | Purpose |
|------|----------|---------|
| `/api/v1/ws/scanner` | `scanner:started`, `scanner:mode_changed`, `scanner:status` | Scanner lifecycle |
| `/api/v1/ws/events` | `event:discovered`, `event:updated`, `event:progress_updated`, `event:orderbook_update` | Real-time events |
| `/api/v1/ws/candidates` | `candidate:created`, `candidate:approved`, `candidate:executed` | Candidate flow |
| `/api/v1/ws/trades` | `trade:executed`, `trade:partial`, `trade:dry_run` | Trade execution |

> **Full message envelopes, payload schemas, and examples → [`docs/api-contract.md`](../api-contract.md)**

---

## Implementation Phases

### Phase 1: Python Backend Core (engines + Kalshi adapter)

**Goal:** Working pipeline in Python with CLI output. Dry-run only.

| Step | File | What |
|------|------|------|
| 1.1 | `backend/core/models.py` | All shared dataclasses |
| 1.2 | `backend/core/interfaces.py` | Abstract adapter contract + `StrategyProfile` ABC |
| 1.3 | `backend/adapters/kalshi/client.py` | REST client with cursor pagination |
| 1.4 | `backend/adapters/kalshi/adapter.py` | Implements interfaces |
| 1.5 | `backend/engines/engine1_discovery.py` | `fetch_all_open_markets()` |
| 1.6 | `backend/engines/engine2_classification.py` | `classify_same_day_live()` |
| 1.7 | `backend/engines/engine3_grouping.py` | `group_by_event_ticker()` |
| 1.8 | `backend/engines/engine4_orderbook.py` | `fetch_orderbooks()` |
| 1.9 | `backend/engines/engine5_ranking.py` | `rank_by_resting_orders()` |
| 1.10 | `backend/strategies/__init__.py` | `EXPERIMENT_REGISTRY` + `get_experiment()` factory |
| 1.11 | `backend/strategies/executed_volume_follower.py` | `ExecutedVolumeFollower` (Experiment A) ✅ primary target |
| 1.12 | `backend/strategies/executed_volume_fade.py` | `ExecutedVolumeFade` (Experiment B) ⏸ untested |
| 1.13 | `backend/strategies/favorite_side_follower.py` | `FavoriteSideFollower` (Experiment C) ⏸ untested |
| 1.14 | `backend/strategies/momentum_follower.py` | `MomentumFollower` (Experiment D) ⏸ untested |
| 1.15 | `backend/strategies/liquidity_filtered_follower.py` | `LiquidityFilteredFollower` (Experiment E) ⏸ untested |
| 1.16 | `backend/strategies/resting_depth_follower.py` | `RestingDepthFollower` (Experiment F) ⏸ untested |
| 1.17 | `backend/strategies/hybrid_score_follower.py` | `HybridScoreFollower` (Experiment G) ⏸ untested |
| 1.18 | `backend/engines/engine6_progress_gate.py` | Consumes active experiment from registry |
| 1.19 | `backend/engines/engine7_validation.py` | `pre_trade_validate()` |
| 1.20 | `backend/engines/engine8_orchestrator.py` | Pipeline runner |
| 1.21 | `backend/config/settings.py` | Pydantic settings |

**Test:** CLI run prints events, top markets, candidates in dry-run mode.

### Phase 2: Trading Modes + Dry-Run Simulator

**Goal:** All three modes functional and switchable.

| Step | File | What |
|------|------|------|
| 2.1 | `backend/trading/dry_run_simulator.py` | Fake fill engine |
| 2.2 | `backend/trading/trade_executor.py` | Mode-aware executor |
| 2.3 | `backend/trading/position_tracker.py` | Track positions |
| 2.4 | `backend/trading/risk_manager.py` | Risk limits |
| 2.5 | `backend/adapters/kalshi/adapter.py` | Add `place_order()` |
| 2.6 | `backend/adapters/kalshi/websocket.py` | WebSocket client |

**Test:** CLI can run in all three modes. Dry-run shows simulated fills.

### Phase 3: FastAPI REST + WebSocket Layer

**Goal:** Backend serves data over HTTP/WS for the frontend.

| Step | File | What |
|------|------|------|
| 3.1 | `backend/main.py` | FastAPI app |
| 3.2 | `backend/api/rest.py` | All REST routes |
| 3.3 | `backend/api/websocket_handler.py` | WS broadcasting |
| 3.4 | `backend/api/schemas.py` | Pydantic request/response |

**Test:** `curl http://localhost:8000/api/v1/events` returns JSON data.

### Phase 4: TypeScript Frontend

**Goal:** Web UI consuming backend APIs.

| Step | File | What |
|------|------|------|
| 4.1 | `frontend/` scaffold | Vite + React + Tailwind |
| 4.2 | `frontend/src/lib/api.ts` | API client |
| 4.3 | `frontend/src/lib/types.ts` | Shared types |
| 4.4 | `frontend/src/hooks/useWebSocket.ts` | WS connection |
| 4.5 | `frontend/src/pages/Dashboard.tsx` | Dashboard |
| 4.6 | Various components | EventList, MarketRow, etc. |
| 4.7 | `frontend/src/pages/Candidates.tsx` | Candidates page |
| 4.8 | `frontend/src/pages/Settings.tsx` | Config page |
| 4.9 | Mode selector + ConfirmDialog | Mode switching UI |

**Test:** Full web UI displays live scanner data, candidates, config panel.

### Phase 5: Live Updates + WebSocket Streaming

**Goal:** Real-time dashboard updates.

| Step | File | What |
|------|------|------|
| 5.1 | `backend/engines/live/discovery_poller.py` | Periodic re-discovery |
| 5.2 | `backend/engines/live/orderbook_loader.py` | Batch orderbook |
| 5.3 | `backend/engines/live/websocket_updater.py` | WS state patching |
| 5.4 | `backend/engines/live/event_reranker.py` | Single-event rerank |
| 5.5 | `backend/engines/live/progress_gate_loop.py` | Periodic check |
| 5.6 | Frontend real-time updates | WS-based live UI |

**Test:** Dashboard updates in real time as orderbooks change.

### Phase 6: Backtesting Infrastructure

**Goal:** Run all 7 experiments against historical Kalshi data and produce performance metrics.

| Step | File | What |
|------|------|------|
| 6.1 | `backend/strategies/backtesting/feature_builder.py` | Feature calculation (executed volume, momentum, depth, spread) |
| 6.2 | `backend/strategies/backtesting/entry_simulator.py` | Taker + maker fill simulation |
| 6.3 | `backend/strategies/backtesting/exit_simulator.py` | Settlement, profit target, stop loss, time stop |
| 6.4 | `backend/strategies/backtesting/metrics.py` | Win rate, ROI, profit factor, drawdown, Sharpe-like |
| 6.5 | `backend/strategies/backtesting/backtest_engine.py` | Main backtest loop (iterate events × thresholds × experiments) |
| 6.6 | `scripts/fetch_historical_data.py` | Pull markets, trades, candlesticks from Kalshi historical API |
| 6.7 | `scripts/run_backtest.py` | CLI to run backtest across all experiments and thresholds |

**Test:** `python scripts/run_backtest.py --experiment A --threshold 60` produces result CSV.

### Phase 7: Production Readiness

| Step | What |
|------|------|
| 7.1 | Docker setup (backend + frontend via docker-compose) |
| 7.2 | Auth key management (env vars, .env file) |
| 7.3 | CSV logging + trade persistence |
| 7.4 | Live paper-trading logger (orderbook snapshots, trade decisions, market snapshots) |
| 7.5 | Error handling + recovery (reconnect, rate limiting) |
| 7.6 | Tests: unit + integration + simulation |
| 7.7 | Documentation |

---

## Project File Structure (Complete)

```
nunu/
├── docs/
│   ├── api-contract.md                                         ← BE↔FE contract
│   ├── plans/
│   │   └── generic-prediction-market-scanner-platform.md       ← you are here
│   ├── adapters/
│   │   ├── adapter-contract.md
│   │   └── kalshi-adapter-spec.md
│   ├── engines/
│   │   ├── engine-1-discovery.md
│   │   ├── engine-2-classification.md
│   │   ├── engine-3-grouping.md
│   │   ├── engine-4-orderbook.md
│   │   ├── engine-5-ranking.md
│   │   ├── engine-6-progress-gate.md
│   │   ├── engine-7-validation.md
│   │   ├── engine-8-orchestration.md
│   │   └── strategy-system.md
│   └── existing-refs/
│       ├── Kalshi Live Event Scanner Logic.md
│       ├── Kalshi Live Today Event Scanner Logic.md
│       └── Kalshi Scanner Simulation Report.md
│
├── backend/
│   ├── main.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── defaults.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── interfaces.py
│   │   └── scanner_state.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── kalshi/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py
│   │   │   ├── client.py
│   │   │   ├── websocket.py
│   │   │   └── types.py
│   │   └── registry.py
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── engine1_discovery.py
│   │   ├── engine2_classification.py
│   │   ├── engine3_grouping.py
│   │   ├── engine4_orderbook.py
│   │   ├── engine5_ranking.py
│   │   ├── engine6_progress_gate.py
│   │   ├── engine7_validation.py
│   │   ├── engine8_orchestrator.py
│   │   └── live/
│   │       ├── __init__.py
│   │       ├── discovery_poller.py
│   │       ├── orderbook_loader.py
│   │       ├── websocket_updater.py
│   │       ├── event_reranker.py
│   │       └── progress_gate_loop.py
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── trade_executor.py
│   │   ├── dry_run_simulator.py
│   │   ├── position_tracker.py
│   │   └── risk_manager.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── rest.py
│   │   ├── websocket_handler.py
│   │   └── schemas.py
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── csv_logger.py
│   │   └── trade_history.py
│   └── requirements.txt
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Events.tsx
│   │   │   ├── EventDetail.tsx
│   │   │   ├── Candidates.tsx
│   │   │   ├── Trades.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── Dashboard/
│   │   │   ├── Orderbook/
│   │   │   ├── Candidates/
│   │   │   ├── Trading/
│   │   │   ├── Controls/
│   │   │   └── Common/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── styles/
│   └── public/
│
├── tests/
│   ├── backend/
│   │   ├── test_engines/
│   │   ├── test_adapters/
│   │   ├── test_trading/
│   │   └── test_api/
│   └── frontend/
│       └── ...
│
├── config/
│   └── settings.yaml
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Research Questions (to answer from backtests)

| Question | Why it matters |
|----------|---------------|
| Does the most-volume child market outperform random child-market selection? | Tests if market selection has value. |
| Does following the dominant side outperform fading it? | Tests directionality. |
| Does 60% progress outperform 50%, 65%, 75%, or 85%? | Tests timing. |
| Does win rate exceed breakeven entry price? | Prevents false confidence. |
| Are returns positive after fees and slippage? | Main business viability question. |
| Are returns concentrated in one category? | Detects overfitting. |
| Does maker execution outperform taker execution after fill-rate adjustment? | Execution model decision. |
| Do filters improve or destroy the signal? | Determines production rules. |
| Does the edge persist in forward paper trading? | Final validation before real capital. |

---

## Decision Thresholds for Auto-Trading

Do not build auto-trading unless the backtest shows:

| Requirement | Minimum |
|-------------|--------:|
| Sample size | 500+ trades |
| Preferred sample size | 2,000+ trades |
| Net ROI after fees/slippage | 5%+ |
| Profit factor | 1.15+ |
| Max drawdown | Less than 20% |
| Positive months | At least 3 separate months |
| Positive categories | More than one event category |
| Threshold robustness | Positive at multiple thresholds |
| Stress test | Positive after conservative slippage |

## Suggested Implementation Order

| Step | Task | Output |
|---:|---|---|
| 1 | Pull historical settled events and markets | `events.csv`, `markets.csv` |
| 2 | Pull historical trades for each market | `trades.csv` |
| 3 | Pull historical candlesticks for each market | `candles.csv` |
| 4 | Build event progress calculator | `entry_times.csv` |
| 5 | Implement Experiment A (executed-volume follower) | `exp_a_results.csv` |
| 6 | Implement Experiment B (executed-volume fade) | `exp_b_results.csv` |
| 7 | Implement Experiment C (favorite-side follower) | `exp_c_results.csv` |
| 8 | Implement Experiment D (momentum follower) | `exp_d_results.csv` |
| 9 | Add filters and Experiment E (liquidity-filtered) | `exp_e_results.csv` |
| 10 | Add paper-trading live orderbook logger | `orderbook_snapshots.csv` |
| 11 | Implement Experiment F (resting-depth) from snapshots | `exp_f_results.csv` |
| 12 | Implement hybrid score (Experiment G) | `exp_g_results.csv` |
| 13 | Compare all strategies | `strategy_leaderboard.csv` |
