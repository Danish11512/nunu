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
7. Selects the **most-bet market** and **most-bet side** (YES/NO) using current resting order quantity
8. Framework supports future strategy profiles (but ships with one default: **most-bet**)

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
    status: str                # "open" | "closed" | "settled" | "unopened"
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
│   ├── __init__.py                # STRATEGY_REGISTRY + get_strategy()
│   ├── base.py                    # StrategyProfile ABC
│   ├── most_bet.py                # ✅ Default, tested
│   ├── highest_volume.py          # ⏸ Built, untested
│   ├── widest_spread.py           # ⏸ Built, untested
│   ├── deepest_book.py            # ⏸ Built, untested
│   ├── momentum_shift.py          # ⏸ Built, untested
│   └── custom_threshold.py        # ⏸ Built, untested
│       ├── __init__.py
│       ├── discovery_poller.py    # Periodic re-discovery
│       ├── orderbook_loader.py    # Batch orderbook snapshot
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

## Strategy Profiles

### Design: Configurable, Pluggable, All-Built

All strategy profiles are built from day one. The user switches between them via config. Only **most-bet** is tested initially — the others are wired and ready but untested.

### Config

```yaml
# config/settings.yaml
strategy:
  active_profile: most-bet           # switch here
  profiles:
    most-bet: {}
    highest-volume: {}
    widest-spread: {}
    deepest-book: {}
    momentum-shift:
      lookback_seconds: 300          # 5 min lookback for momentum calc
    custom-threshold:
      per_event_type:
        default: 65
        sports: 50
        politics: 75
```

The frontend `StrategySelector` dropdown reads available profiles from the backend `/api/v1/config` endpoint.

### Strategy Interface

```python
class StrategyProfile(ABC):
    """Interface for pluggable strategy profiles."""
    name: str
    description: str
    config: dict  # profile-specific config from settings.yaml

    @abstractmethod
    def select_market(
        self,
        ranked_markets: list[RankedMarket],
        event: Event,
    ) -> Optional[RankedMarket]:
        """Pick the best market from the ranked list."""
        ...

    @abstractmethod
    def select_side(
        self,
        market: RankedMarket,
        stats: MarketOrderbookStats,
    ) -> OrderCandidateSide:
        """Pick YES or NO for the selected market."""
        ...
```

### Profile Implementations

#### 1. Most-Bet (default)

```python
class MostBetStrategy(StrategyProfile):
    """
    Market with the highest total resting order quantity.
    Side with more resting orders (YES or NO).
    """
    name = "most-bet"
    description = "Follows the crowd: highest order activity → most-bet side"

    def select_market(self, ranked_markets, event):
        return ranked_markets[0] if ranked_markets else None

    def select_side(self, market, stats):
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

#### 2. Highest Volume

```python
class HighestVolumeStrategy(StrategyProfile):
    """
    Market with the highest 24h traded volume.
    Side with more volume-weighted order activity.
    """
    name = "highest-volume"
    description = "Follows actual traded action: highest 24h volume → most-traded side"

    def select_market(self, ranked_markets, event):
        # Re-rank by volume_24h DESC instead of resting orders
        sorted_by_volume = sorted(
            ranked_markets,
            key=lambda rm: rm.orderbook_stats.volume_24h,
            reverse=True,
        )
        return sorted_by_volume[0] if sorted_by_volume else None

    def select_side(self, market, stats):
        # Weight side preference by volume on each side
        # If YES has more resting orders AND more volume → YES
        # If NO has more resting orders AND more volume → NO
        # Tiebreaker: higher order quantity wins
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

#### 3. Widest Spread

```python
class WidestSpreadStrategy(StrategyProfile):
    """
    Market with the biggest gap between YES and NO prices.
    Bets on the *cheaper* side (fading the move — contrarian).
    """
    name = "widest-spread"
    description = "Contrarian: widest YES/NO price gap → bet the cheap side"

    def select_market(self, ranked_markets, event):
        # Re-rank by spread size DESC (|best_yes_bid - best_no_bid|)
        def spread(rm):
            y = rm.orderbook_stats.best_yes_bid or 0
            n = rm.orderbook_stats.best_no_bid or 0
            return abs(y - n)

        sorted_by_spread = sorted(
            ranked_markets,
            key=lambda rm: spread(rm),
            reverse=True,
        )
        # Only consider markets with non-zero spread
        return next(
            (m for m in sorted_by_spread if spread(m) > 0),
            ranked_markets[0] if ranked_markets else None,
        )

    def select_side(self, market, stats):
        # Contrarian: pick the CHEAPER side (less bid activity)
        yes_bid = stats.best_yes_bid or 0
        no_bid = stats.best_no_bid or 0
        if yes_bid == 0 and no_bid == 0:
            return "none"
        if yes_bid < no_bid:
            return "yes"   # YES is cheaper → bet YES
        elif no_bid < yes_bid:
            return "no"    # NO is cheaper → bet NO
        return "tie"
```

#### 4. Deepest Book

```python
class DeepestBookStrategy(StrategyProfile):
    """
    Market with the most orderbook depth levels.
    Side with deeper orderbook (more liquidity).
    """
    name = "deepest-book"
    description = "Most liquid market: highest depth level count → deeper side"

    def select_market(self, ranked_markets, event):
        # Already ranked by depth_level_count in Engine 5 (tiebreaker #2)
        # But re-rank with depth_level_count as PRIMARY sort
        sorted_by_depth = sorted(
            ranked_markets,
            key=lambda rm: rm.orderbook_stats.depth_level_count,
            reverse=True,
        )
        return sorted_by_depth[0] if sorted_by_depth else None

    def select_side(self, market, stats):
        # Pick the side with more depth levels
        # We don't track per-side depth count directly in stats,
        # so fall back to resting order quantity as proxy
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

#### 5. Momentum Shift

```python
class MomentumShiftStrategy(StrategyProfile):
    """
    Market with the biggest recent change in YES/NO bid ratio.
    Bets with the momentum (side whose relative bid share increased most).
    """
    name = "momentum-shift"
    description = "Catches reversals: biggest recent bid ratio change → momentum side"

    def __init__(self, config: dict):
        super().__init__(config)
        self.lookback_seconds = config.get("lookback_seconds", 300)
        # Stores historical snapshots: {market_id: [(timestamp, yes_qty, no_qty), ...]}
        self.history: dict[str, list] = {}

    def record_snapshot(self, market_id: str, stats: MarketOrderbookStats, now: float):
        """Called by the live updater on each orderbook change."""
        if market_id not in self.history:
            self.history[market_id] = []
        self.history[market_id].append((now, stats.yes_order_quantity, stats.no_order_quantity))
        # Prune old entries
        cutoff = now - self.lookback_seconds
        self.history[market_id] = [
            entry for entry in self.history[market_id]
            if entry[0] >= cutoff
        ]

    def _get_momentum_score(self, market_id: str, current_yes: float, current_no: float, now: float) -> float:
        """Positive = YES momentum, Negative = NO momentum. 0 = no change."""
        if market_id not in self.history or len(self.history[market_id]) < 2:
            return 0.0

        oldest = self.history[market_id][0]
        _, old_yes, old_no = oldest

        old_total = old_yes + old_no
        cur_total = current_yes + current_no

        if old_total == 0 or cur_total == 0:
            return 0.0

        old_ratio = old_yes / old_total
        cur_ratio = current_yes / cur_total

        return cur_ratio - old_ratio

    def select_market(self, ranked_markets, event):
        if not ranked_markets:
            return None
        # Among markets with history, pick the one with highest absolute momentum change
        now = time.time()
        scored = []
        for rm in ranked_markets:
            score = abs(self._get_momentum_score(
                rm.market.id,
                rm.orderbook_stats.yes_order_quantity,
                rm.orderbook_stats.no_order_quantity,
                now,
            ))
            scored.append((score, rm))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else ranked_markets[0]

    def select_side(self, market, stats):
        now = time.time()
        score = self._get_momentum_score(
            market.market.id,
            stats.yes_order_quantity,
            stats.no_order_quantity,
            now,
        )
        if score > 0.01:    # momentum toward YES
            return "yes"
        elif score < -0.01: # momentum toward NO
            return "no"
        # No clear momentum → fall back to most-bet
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

#### 6. Custom Threshold

```python
class CustomThresholdStrategy(StrategyProfile):
    """
    Same market/side selection as most-bet, but with per-event-type
    progress thresholds instead of a single global threshold.
    """
    name = "custom-threshold"
    description = "Most-bet logic with per-event-type progress thresholds"

    def __init__(self, config: dict):
        super().__init__(config)
        self.event_type_thresholds = config.get("per_event_type", {"default": 65})

    def get_threshold_for_event(self, event_type: str) -> int:
        return self.event_type_thresholds.get(event_type, self.event_type_thresholds.get("default", 65))

    def select_market(self, ranked_markets, event):
        return ranked_markets[0] if ranked_markets else None

    def select_side(self, market, stats):
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

### Strategy Registry

```python
STRATEGY_REGISTRY: dict[str, type[StrategyProfile]] = {
    "most-bet": MostBetStrategy,
    "highest-volume": HighestVolumeStrategy,
    "widest-spread": WidestSpreadStrategy,
    "deepest-book": DeepestBookStrategy,
    "momentum-shift": MomentumShiftStrategy,
    "custom-threshold": CustomThresholdStrategy,
}

def get_strategy(name: str, config: dict) -> StrategyProfile:
    """Factory: instantiate a strategy by name with its config."""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    strategy_cls = STRATEGY_REGISTRY[name]
    return strategy_cls(config)
```

### How the Pipeline Consumes the Strategy

Engine 6 (`engine6_progress_gate.py`) receives the active strategy as a dependency:

```python
class ProgressGateEngine:
    def __init__(self, strategy: StrategyProfile, default_threshold: int = 65):
        self.strategy = strategy
        self.default_threshold = default_threshold

    def process_event(self, event: EventWithTopMarkets, now: datetime) -> ProgressBasedOrderCandidate:
        # Step 1: Strategy picks the market
        selected = self.strategy.select_market(event.all_markets_ranked, event.event_data)
        if not selected:
            return self._empty_candidate(event, "No market selected by strategy")

        # Step 2: Calculate progress
        progress = calculate_market_progress(selected.market, now)

        # Step 3: Strategy picks the side
        side = self.strategy.select_side(selected, selected.orderbook_stats)

        # Step 4: Apply threshold (strategy-specific if CustomThreshold)
        if isinstance(self.strategy, CustomThresholdStrategy):
            threshold = self.strategy.get_threshold_for_event(event.event_data.category or "default")
        else:
            threshold = self.default_threshold

        # Step 5: Build candidate
        return self._build_candidate(event, selected, side, progress, threshold)
```

### Testing: Most-Bet Only

All six strategies are implemented and registered. The test suite covers only **most-bet**:

```python
# tests/test_strategies/test_most_bet.py  ✅  comprehensive tests
# tests/test_strategies/test_highest_volume.py   ❌  skipped
# tests/test_strategies/test_widest_spread.py    ❌  skipped
# tests/test_strategies/test_deepest_book.py     ❌  skipped
# tests/test_strategies/test_momentum_shift.py   ❌  skipped
# tests/test_strategies/test_custom_threshold.py ❌  skipped
```

Each untested strategy has a `# TODO: implement tests when strategy is activated` marker.

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
| 1.10 | `backend/strategies/__init__.py` | `STRATEGY_REGISTRY` + `get_strategy()` factory |
| 1.11 | `backend/strategies/most_bet.py` | `MostBetStrategy` ✅ tested |
| 1.12 | `backend/strategies/highest_volume.py` | `HighestVolumeStrategy` ⏸ untested |
| 1.13 | `backend/strategies/widest_spread.py` | `WidestSpreadStrategy` ⏸ untested |
| 1.14 | `backend/strategies/deepest_book.py` | `DeepestBookStrategy` ⏸ untested |
| 1.15 | `backend/strategies/momentum_shift.py` | `MomentumShiftStrategy` ⏸ untested |
| 1.16 | `backend/strategies/custom_threshold.py` | `CustomThresholdStrategy` ⏸ untested |
| 1.17 | `backend/engines/engine6_progress_gate.py` | Consumes active strategy from registry |
| 1.18 | `backend/engines/engine7_validation.py` | `pre_trade_validate()` |
| 1.19 | `backend/engines/engine8_orchestrator.py` | Pipeline runner |
| 1.20 | `backend/config/settings.py` | Pydantic settings |

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

### Phase 6: Production Readiness

| Step | What |
|------|------|
| 6.1 | Docker setup (backend + frontend via docker-compose) |
| 6.2 | Auth key management (env vars, .env file) |
| 6.3 | CSV logging + trade persistence |
| 6.4 | Error handling + recovery (reconnect, rate limiting) |
| 6.5 | Tests: unit + integration + simulation |
| 6.6 | Documentation |

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

## Next Questions for You

1. **Strategy profiles:** Ship with `most-bet` only, add framework for plugins? Or do you want multiple profiles from the start?

2. **Dry-run → Live transition:** How safe should the gate be?
   - **Confirmation dialog** in UI ("Are you sure?")
   - **Separate process** (live mode = different port/container)
   - **Physical auth step** (re-enter API key to enable live)

3. **Frontend framework:** **React + Vite** (simpler, SPA) or **Next.js** (SSR, more structure)?

4. **Kalshi API auth:** How do you want to handle credentials for live trading?
   - `.env` file loaded at startup (static)
   - UI form → sent to backend on demand (dynamic)
   - System keychain (macOS Keychain)

5. **Kalshi WebSocket:** I should research the exact Kalshi WebSocket API before we implement Engine 4/5 live mode. Want me to look it up via Context7 MCP?
