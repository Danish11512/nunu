# Phase 5 — Backtesting Infrastructure: Validation & Alignment Document

> **Scope:** Steps 42–46 of `docs/build-plan.md`  
> **Cross-references:** `docs/engines/strategy-system.md`, `backend/core/interfaces/strategy.py`  
> **Date:** 2026-06-18  
> **Status:** Planning only — no Phase 5 code has been implemented yet.

---

## 1. Executive Summary

Phase 5 creates the backtesting infrastructure for the Nunu prediction market scanner. It consists of 6 files under `backend/strategies/backtesting/`:

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `feature_builder.py` | Enriches `MarketFeatures` from historical trade/candle/orderbook data |
| `entry_simulator.py` | Simulates trade entry (taker/maker fills) |
| `exit_simulator.py` | Simulates trade exit (settlement, stop-loss, etc.) |
| `metrics.py` | Computes per-experiment performance metrics |
| `backtest_engine.py` | Orchestrator — runs all experiments across thresholds |

**Key finding:** The pseudocode in `build-plan.md` uses a *different, older version* of the data models (`MarketFeatures`, `EventFeatures`, `TradeDecision`) than what is actually checked into `backend/core/interfaces/strategy.py`. The existing pseudocode will not compile against the current core without significant field renames and type fixes.

---

## 2. Data Model Alignment

### 2.1 `HistoricalTrade` — from `docs/engines/strategy-system.md`

```python
# strategy-system.md definition (needs a home):
@dataclass
class HistoricalTrade:
    market_ticker: str
    trade_time: datetime
    yes_price: float       # cents
    no_price: float        # cents
    count: int
    taker_side: Optional[str]  # "YES" | "NO" | None
    is_block_trade: bool = False
```

**Issues with current core:**

| Issue | Details |
|-------|---------|
| `yes_price: float` | Core uses `int` cents everywhere (e.g., `yes_bid: int`). Recommend `int` for consistency, or keep `float` if the raw API returns decimal — but document that it represents cents. |
| `no_price: float` | Same as above. |
| `taker_side: "YES" / "NO"` | Core convention is lowercase `"yes" / "no"` (see `TradeDecision.side`, `MarketFeatures.yes_bid`). Recommend aligning to lowercase. |
| No existing home | Does not exist in any current file. Must be created. |

**Recommendation:** Create in `backend/core/models/backtesting.py` (see Section 8).

### 2.2 `Candlestick` — from `docs/engines/strategy-system.md`

```python
@dataclass
class Candlestick:
    market_ticker: str
    bucket_start: datetime
    open_yes_price: float
    high_yes_price: float
    low_yes_price: float
    close_yes_price: float
    volume: float = 0.0
```

**Issues:**

| Issue | Details |
|-------|---------|
| `*_price: float` | Core uses `int` cents. However, candlestick prices may be midpoints or averages, which legitimately need float. **Acceptable** — document that prices are in cents but may be fractional. |
| `volume: float` | Core uses `int` for volume. If volume comes from raw Kalshi API (integer counts), `int` is more appropriate. Recommend `int`. |

### 2.3 `OrderbookSnapshot` — from `docs/engines/strategy-system.md`

```python
@dataclass
class OrderbookSnapshot:
    market_ticker: str
    snapshot_time: datetime
    yes_bid_price: float
    yes_bid_quantity: float
    no_bid_price: float
    no_bid_quantity: float
    yes_total_depth: float
    no_total_depth: float
    spread: float
```

**Issues:**

| Issue | Details |
|-------|---------|
| `*_price: float` | Core uses `int` cents (e.g., `OrderbookLevel.price: int`). Recommend `int`. |
| `*_quantity: float` | Quantities in Kalshi are integer contract counts. Recommend `int`. |
| `*_depth: float` | Same — integer contract counts. Recommend `int`. |
| `spread: float` | Spread in cents — should be `int` to match `MarketFeatures.spread_cents: int`. |
| `yes_bid_price` name | Slightly redundant with `yes_bid` naming in core; but acceptable for a snapshot model. |

---

## 3. `feature_builder.py` — Alignment Map

The pseudocode in `build-plan.md` §5.2 constructs `MarketFeatures` using field names that **do not exist** on the current `MarketFeatures` dataclass. Below is the full mapping.

### Constructor Call Mapping

| Plan Pseudocode Field | Current `MarketFeatures` Field | Type Delta | Action |
|---|---|---|---|
| `market_ticker=` | `ticker=` | Name mismatch | Rename parameter |
| `total_executed_volume=` | `total_executed_volume=` | ✅ Matches | No change |
| `yes_executed_volume=` | `yes_executed_volume=` | ✅ Matches | No change |
| `no_executed_volume=` | `no_executed_volume=` | ✅ Matches | No change |
| `trade_count=` | `trade_count=` | ✅ Matches | No change |
| `yes_price=` (float) | `yes_bid=` (int) | Name + type mismatch | Map `yes_price_at_entry` → `yes_bid`; cast to `int` |
| `no_price=` (float) | `no_bid=` (int) | Name + type mismatch | Map `no_price_at_entry` → `no_bid`; cast to `int` |
| `yes_price_momentum=` (Optional[float]) | `yes_price_momentum=` (float) | Type: Optional[float] vs float | Assign `0.0` when None |
| `yes_total_depth=` (Optional[float]) | `yes_total_depth=` (int) | Name ✅, type mismatch | Cast to `int`; use `0` when None |
| `no_total_depth=` (Optional[float]) | `no_total_depth=` (int) | Name ✅, type mismatch | Cast to `int`; use `0` when None |
| `spread=` (Optional[float]) | `spread_cents=` (int) | Name + type mismatch | Map → `spread_cents`; cast to `int` |
| `yes_best_bid=` (Optional[float]) | `yes_bid=` (int) | Duplicate of `yes_price` / `yes_bid` | Remove — already set from price_at_entry |
| `no_best_bid=` (Optional[float]) | `no_bid=` (int) | Duplicate of `no_price` / `no_bid` | Remove — already set from price_at_entry |

### Remaining Fields on `MarketFeatures` Not Set by Pseudocode

These will keep their default values (0 / 0.0 / "") unless explicitly populated:

| Field | Default | Notes |
|-------|---------|-------|
| `volume` | 0 | Could set from HistoricalTrade aggregation if desired |
| `volume_24h` | 0 | Not available from historical data |
| `yes_ask` | 0 | Not set in plan — could enrich from OrderbookSnapshot |
| `no_ask` | 0 | Same |
| `last_price` | 0 | Not set |
| `open_interest` | 0 | Not set |
| `total_resting_order_quantity` | 0 | Not set — could derive from OrderbookSnapshot |
| `progress_pct` | 0.0 | Not set — caller should populate from event timing |

### Import Change

| Plan Code | Correct Import |
|-----------|---------------|
| `from backend.strategies.base import MarketFeatures` | `from backend.core.interfaces.strategy import MarketFeatures` |

`MarketFeatures` lives in `backend/core/interfaces/strategy.py`, not in `backend/strategies/base.py`. The existing strategies already import from the correct location.

---

## 4. `entry_simulator.py` — Alignment Map

### Data Types

| Plan Pseudocode | Current Core Convention | Action |
|---|---|---|
| `price_cents: float` | `int` cents everywhere in core | Change to `int` |
| `spread_cents: float` | `int` (e.g., `spread_cents: int`) | Change to `int` |
| `best_bid: float` | `int` (`yes_bid: int`, `no_bid: int`) | Change to `int` |
| `best_ask: float` | `int` | Change to `int` |
| `slippage_cents: float` | `int` | Change to `int` |

### Side Convention

| Plan Pseudocode | Current Core Convention |
|---|---|
| `side == "YES"` (uppercase) | `side == "yes"` (lowercase) — see `TradeDecision.side` |

The `simulate_taker_entry` and `simulate_maker_entry` functions use `"YES"` — must change to `"yes"`.

### `FillResult.price_cents`

Currently `float` in plan — must be `int`.

### Maker Entry Logic

The plan pseudocode for `simulate_maker_entry` uses:
```python
limit_price = best_bid if side == "YES" else (100 - best_ask)
```
This logic assumes price is in a 0–100 cent scale. That's correct for prediction markets. However:
- For side="no", `(100 - best_ask)` gives the implied no price. If `best_ask` is 60¢ no, the no price is 40¢. This is correct.
- All values should be `int`.

---

## 5. `exit_simulator.py` — Alignment Map

### Data Types

| Plan Pseudocode | Current Core Convention | Action |
|---|---|---|
| `entry_price: float` | `int` cents | Change to `int` |
| `exit_price_cents: float` | `int` | Change to `int` |
| `pnl_cents: float` | `int` (PnL in cents) | Change to `int` |
| `roi_percent: float` | `float` | ✅ Already float — correct |

### `ExitResult`

| Field | Plan Type | Recommended Type | Notes |
|-------|-----------|-----------------|-------|
| `exit_price_cents` | `float` | `int` | Cents are integer |
| `exit_reason` | `ExitReason` | `ExitReason` | ✅ Correct |
| `pnl_cents` | `float` | `int` | Integer cents |
| `roi_percent` | `float` | `float` | ✅ Correct |

### `hold_to_settlement` Logic

```python
payout = 100.0 if won else 0.0  # Plan uses float
```

Should be `int`:
```python
payout = 100 if won else 0
```

**Side alignment:** The `settlement_result` parameter should be lowercase `"yes"` / `"no"` to match core convention.

### Missing Exit Simulation Types

The plan doesn't include exit simulations for:
- **Profit target** (`exit_at_progress` / `PROFIT_TARGET`) — mentioned in `ExitReason` enum but not implemented in any function
- **Stop loss** — same
- **Time stop** — same

These are placeholders for future expansion.

---

## 6. `metrics.py` — Alignment Map

### `TradeResult` Fields

| Plan Pseudocode Field | Issue | Recommendation |
|---|---|---|
| `experiment_id: str` | ✅ Reasonable — but `TradeDecision` in core doesn't have this field | See Section 9 — either add to `TradeDecision` or compute from experiment name + threshold |
| `threshold: float` | ✅ Not a core field — belongs in metrics | Keep — it's a backtest parameter, not part of core interfaces |
| `event_ticker: str` | ✅ Fine | No change |
| `market_ticker: str` | ✅ Matches `TradeDecision.market_ticker` | No change |
| `side: str` | Plan uses `"YES"/"NO"` (uppercase) | Change to lowercase `"yes"/"no"` |
| `entry_price: float` | Core uses `int` cents | Change to `int` |
| `exit_price: float` | Core uses `int` cents | Change to `int` |
| `won: bool` | ✅ Fine | No change |
| `pnl_cents: float` | Should be `int` | Change to `int` |
| `roi_percent: float` | ✅ Fine | No change |
| `category: str` | ✅ Fine (metadata) | No change |
| `fill_mode: str` | ✅ Fine | No change |

### `StrategyMetrics` Fields

| Field | Plan Type | Issue | Recommendation |
|---|---|---|---|
| `experiment_id: str` | `str` | ✅ Fine | No change |
| `threshold: float` | `float` | ✅ Fine | No change |
| `total_trades: int` | `int` | ✅ | No change |
| `wins: int` | `int` | ✅ | No change |
| `losses: int` | `int` | ✅ | No change |
| `win_rate: float` | `float` | ✅ | No change |
| `avg_entry_price: float` | `float` | Should be `int` cents | Change to `int` |
| `breakeven_win_rate: float` | `float` | ✅ | No change |
| `gross_roi: float` | `float` | Formula is wrong (see below) | Fix |
| `net_roi: float` | `float` | Formula is fragile | Fix |
| `profit_factor: float` | `float` | ✅ | No change |
| `max_drawdown: float` | `float` | Computed as `0.0` (placeholder) | Flagged as incomplete |
| `sharpe_like: float` | `float` | ✅ | No change |
| `avg_roi_per_trade: float` | `float` | ✅ | No change |

### Formula Bugs in `compute_metrics`

1. **`gross_roi`** is computed as:
   ```python
   gross_profit / (gross_profit + gross_loss)
   ```
   This does not compute ROI. It computes the **profit ratio** (wins / total PnL magnitude), which is better named `profit_ratio` or `win_pnl_ratio`. A true gross ROI would be `total_pnl / total_cost_basis`.

2. **`net_roi`** formula:
   ```python
   total_pnl / (statistics.mean(entry_prices) * len(results))
   ```
   This averages entry prices, which is misleading when entries have different prices. Better to sum cost basis per trade: `sum(r.entry_price * r.quantity for r in results)` but `TradeResult` doesn't have `quantity`. Currently `quantity` is always 1 in the plan's backtest engine. This is acceptable for a v1 approximation but should be documented.

3. **`breakeven_win_rate`** formula:
   ```python
   statistics.mean(entry_prices) / 100
   ```
   This computes the average premium paid. If average entry is 60¢, breakeven WR = 0.60 = 60%. This is correct logic but poorly named — it's the **minimum win rate needed to break even given average entry price**.

4. **`max_drawdown`** is hardcoded to `0.0`. This is a placeholder and should be flagged as known incomplete.

---

## 7. `backtest_engine.py` — Alignment Map

This is the most impacted file. Every data model reference from the plan pseudocode conflicts with current core.

### 7.1 EventFeatures Construction

| Plan Pseudocode | Current `EventFeatures` | Action |
|---|---|---|
| `EventFeatures(event_ticker=..., event_title=...)` | ✅ Matches | No change |
| `category=event.get("category", "")` | ❌ No `category` field on `EventFeatures` | **Remove** — or add `category` to `EventFeatures` (not recommended; events don't have categories in the current model) |
| `event_progress=threshold` | ❌ No `event_progress` field | **Remove** — `EventFeatures` has `max_progress_pct`, `min_progress_pct`, but not a single `event_progress`. If needed, use a new field or pass separately. |
| `threshold=threshold` | ❌ No `threshold` field on `EventFeatures` | **Remove** — threshold is a backtest parameter, not an event feature. Pass to the backtest loop separately. |
| `entry_time=entry_time` | ❌ No `entry_time` field on `EventFeatures` | **Remove** — entry_time is computed in the backtest loop, not part of EventFeatures |
| `child_markets=market_features_list` | ✅ Matches | No change |

### 7.2 TradeDecision Access Patterns

| Plan Pseudocode | Current `TradeDecision` | Action |
|---|---|---|
| `decision.trade_decision == "SKIP"` | `decision.should_trade` (bool) | Change to `not decision.should_trade` |
| `decision.selected_side` | `decision.side` | Rename to `decision.side` |
| `decision.skip_reason` | `decision.reason` | Rename to `decision.reason` |
| `decision.entry_price_cents` | `decision.entry_price_cents` (int) | ✅ Matches — but plan uses it as `Optional[float]`. Cast to int. |
| `decision.experiment_id` | ❌ Does not exist on `TradeDecision` | See Section 9 |
| `decision.market_ticker` | `decision.market_ticker` | ✅ Matches |
| `decision.selected_market_reason` | ❌ No such field | Use `decision.reason` |
| `decision.entry_threshold` | ❌ No such field | Not needed — threshold is a loop variable |
| `decision.event_progress_at_entry` | ❌ No such field | Not needed — computed in loop |
| `decision.side_signal_strength` | ❌ No such field | Not needed — stored in `decision.confidence` proxy |
| `decision.max_acceptable_price_cents` | ❌ No such field | Not needed for backtesting v1 |

### 7.3 Strategy Decision Logic Flow

The plan pseudocode calls `decision.trade_decision == "SKIP"` to check if a strategy decided not to trade. The current `TradeDecision` uses `should_trade: bool`. The correct flow is:

```python
decision = experiment.select_trade(event_features)
if not decision.should_trade:
    continue  # Skip this experiment for this event
```

### 7.4 Event Data Assumptions

The plan assumes `historical_events` is a list of dicts with:
- `"child_markets"` — list of market dicts with `"ticker"`, `"yes_price"`, `"no_price"`
- `"start_time"` / `"end_time"` — for progress computation
- `"event_ticker"` — string
- `"title"` — string
- `"category"` — string (not in core EventFeatures)
- `"result"` — "YES" / "NO"

There is no existing `HistoricalEvent` dataclass in the project. The backtest engine needs to define or document the expected shape. **Recommendation:** Create a `HistoricalEvent` dataclass or use a TypedDict to document the interface.

### 7.5 `run_backtest` Function Signature

| Parameter | Plan Type | Issue |
|-----------|-----------|-------|
| `historical_events: list` | Untyped | Should be typed — recommend `list[HistoricalEvent]` where `HistoricalEvent` is a new dataclass |
| `get_trades_fn` | Callable | ✅ Fine but should be typed: `Callable[[str, datetime], list[HistoricalTrade]]` |
| `get_candles_fn` | Callable | ✅ Same |
| `thresholds: list[float]` | list of floats | ✅ Fine — but threshold values should be 0.0–1.0 range |
| `experiment_names: list[str]` | list of strings | ✅ Fine |
| `default_threshold: float` | float | ✅ Fine |

---

## 8. Suggested Data Model Location

**Create a new file:** `backend/core/models/backtesting.py`

This file should house the three data models from `strategy-system.md` that have no current home:

```python
"""Backtesting data models.

These dataclasses represent historical data consumed by the Phase 5
backtesting FeatureBuilder. They are not used at runtime — they exist
only for simulation/replay.

Terminology:
  - Prices are in integer cents (matching core conventions).
  - Sides use lowercase "yes" / "no" (matching TradeDecision.side).
  - Quantities are integer contract counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class HistoricalTrade:
    """A single historical trade from the exchange.

    Used by: Experiment A (executed-volume-follower),
             Experiment B (executed-volume-fade),
             Experiment E (liquidity-filtered-follower),
             Experiment G (hybrid-score-follower).
    """
    market_ticker: str
    trade_time: datetime
    yes_price: int          # cents (integer)
    no_price: int           # cents (integer)
    count: int              # contract count
    taker_side: Optional[str]  # "yes" | "no" | None
    is_block_trade: bool = False


@dataclass
class Candlestick:
    """Aggregated candlestick over a time bucket.

    Used by: Experiment C (favorite-side-follower),
             Experiment D (momentum-follower),
             Experiment G (hybrid-score-follower).

    Prices may be fractional (midpoints/averages) — stored as float
    but represent cents.
    """
    market_ticker: str
    bucket_start: datetime
    open_yes_price: float
    high_yes_price: float
    low_yes_price: float
    close_yes_price: float
    volume: int = 0          # integer contract count


@dataclass
class OrderbookSnapshot:
    """Point-in-time snapshot of the orderbook for a market.

    Used by: Experiment F (resting-depth-follower),
             Experiment G (hybrid-score-follower).
    """
    market_ticker: str
    snapshot_time: datetime
    yes_bid_price: int      # cents
    yes_bid_quantity: int   # contracts
    no_bid_price: int       # cents
    no_bid_quantity: int    # contracts
    yes_total_depth: int    # contracts
    no_total_depth: int     # contracts
    spread: int             # cents


@dataclass
class HistoricalEvent:
    """A historical event used in backtesting.

    This is the top-level input to run_backtest(). It packages the
    event metadata together with its child markets and settlement info.
    """
    event_ticker: str
    event_title: str
    start_time: datetime
    end_time: datetime
    child_market_tickers: list[str]
    settlement_result: Optional[str] = None  # "yes" | "no" | None
```

The existing `backend/core/models/__init__.py` should be updated to re-export these:

```python
# Add to existing __all__ and imports:
from backend.core.models.backtesting import HistoricalTrade, Candlestick, OrderbookSnapshot, HistoricalEvent
```

---

## 9. Suggested `TradeDecision` Extension — `experiment_id`

### The Problem

The plan pseudocode uses `decision.experiment_id` to tag each `TradeResult` with the originating experiment. This field does not exist on the current `TradeDecision`.

### Options

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **A:** Add `experiment_id: str = ""` to `TradeDecision` | Clean, self-contained. Backtest engine can read it directly. | Pollutes the core interface with a field that has no meaning at runtime (Engine 6/7). Every runtime strategy would leave it empty. | ⭐ **Recommended for Phase 5** — the field defaults to `""` at runtime, costs nothing, and avoids awkward workarounds. |
| **B:** Pass `experiment_id` alongside `TradeDecision` in backtest loop | No core interface change. | Awkward API — every backtest iteration must carry a separate variable. Easy to get wrong. | ❌ Not recommended. |
| **C:** Compute `experiment_id` from context in `backtest_engine.py` | No model changes needed. | Fragile — `exp_name + threshold` is already the metrics key; adding it to TradeResult is redundant. But without it, individual TradeResults cannot be traced back. | Acceptable if we want to keep core clean, but tradeoff is worth it. |

**Decision:** Add `experiment_id: str = ""` to `TradeDecision`. It defaults to `""` so runtime usage is unaffected. The backtest engine sets it when constructing decisions. **Minimal change, maximum benefit.**

### Other Candidate Fields — Rejected

The `strategy-system.md` version of `TradeDecision` has many additional fields that the current core does not:

| Field | Present in Core? | Should Add? | Reason |
|-------|-----------------|-------------|--------|
| `experiment_id` | ❌ | ✅ Yes | Needed for backtest tracing |
| `entry_threshold` | ❌ | ❌ No | Threshold is a loop variable in backtesting |
| `event_progress_at_entry` | ❌ | ❌ No | Computed in backtest loop |
| `side_signal_strength` | ❌ | ❌ No | Redundant with `confidence` |
| `market_signal_strength` | ❌ | ❌ No | Not needed at runtime |
| `selected_market_reason` | ❌ | ❌ No | Can go in `reason` |
| `selected_side_reason` | ❌ | ❌ No | Can go in `reason` |
| `estimated_fee_cents` | ❌ | ❌ No | Backtest parameter, not per-decision |
| `max_acceptable_price_cents` | ❌ | ❌ No | Not used in v1 |

---

## 10. Implementation Order

### Recommended sequence

```
Step 1:  backend/core/models/backtesting.py
         └── HistoricalTrade, Candlestick, OrderbookSnapshot, HistoricalEvent
         └── Update backend/core/models/__init__.py to re-export

Step 2:  backend/core/interfaces/strategy.py (MINOR)
         └── Add experiment_id: str = "" to TradeDecision

Step 3:  backend/strategies/backtesting/__init__.py
         └── Empty file with docstring

Step 4:  backend/strategies/backtesting/feature_builder.py
         └── No dependencies on other Phase 5 files
         └── Depends only on core models + interfaces

Step 5:  backend/strategies/backtesting/entry_simulator.py
         └── Standalone — no Phase 5 dependencies

Step 6:  backend/strategies/backtesting/exit_simulator.py
         └── Standalone — no Phase 5 dependencies

Step 7:  backend/strategies/backtesting/metrics.py
         └── Standalone — depends only on its own TradeResult/StrategyMetrics

Step 8:  backend/strategies/backtesting/backtest_engine.py
         └── Depends on all above files
         └── Depends on backend.strategies.get_experiment
```

### Dependency Graph

```
core/models/backtesting.py             (standalone)
    ↑
core/interfaces/strategy.py            (add experiment_id)
    ↑
backtesting/__init__.py                (package marker)
    ↑
feature_builder.py entry_simulator.py exit_simulator.py metrics.py
    ↑          ↑              ↑             ↑
    └──────────┴──────────────┴─────────────┘
                      ↑
              backtest_engine.py
```

---

## 11. Risk Assessment

### Critical Risks (will cause compile errors)

| # | Risk | File | Mitigation |
|---|------|------|------------|
| R1 | `MarketFeatures` field names in plan pseudocode (`market_ticker`, `yes_price`, `spread`, etc.) don't match current core (`ticker`, `yes_bid`, `spread_cents`) | `feature_builder.py` | Use alignment map in Section 3 — rename every field |
| R2 | `EventFeatures` in plan has fields (`category`, `event_progress`, `threshold`, `entry_time`) that don't exist in current core | `backtest_engine.py` | Remove these fields; pass threshold/progress/entry_time as local variables |
| R3 | `decision.trade_decision == "SKIP"` — `TradeDecision` has `should_trade: bool`, not `trade_decision: str` | `backtest_engine.py` | Change to `not decision.should_trade` |
| R4 | `decision.selected_side` — current field is `decision.side` | `backtest_engine.py` | Rename to `decision.side` |
| R5 | `decision.experiment_id` doesn't exist | `backtest_engine.py`, `metrics.py` | Add to `TradeDecision` (Section 9) or compute in loop |
| R6 | Import path: plan imports from `backend.strategies.base`, but `MarketFeatures` lives in `backend.core.interfaces.strategy` | `feature_builder.py` | Fix import statement |

### Medium Risks (will produce wrong results or fragile code)

| # | Risk | Details |
|---|-------|---------|
| R7 | `float` vs `int` type mismatches throughout | Plan uses `float` for prices, spreads, depths — core expects `int` in cents. Every file needs casting. |
| R8 | Side casing: `"YES"/"NO"` vs `"yes"/"no"` | Plan uses uppercase, core uses lowercase. Silent mismatch — comparisons will fail. |
| R9 | `compute_metrics` formula errors | `gross_roi` formula computes profit ratio, not ROI. `net_roi` uses average entry price which is misleading. |
| R10 | `max_drawdown = 0.0` placeholder | Will silently produce 0 drawdown in reports. Must be flagged as incomplete. |
| R11 | `FillResult.price_cents` as `float` | Downstream consumers expecting `int` cents will get floats. Silent precision issues. |

### Low Risks (non-blocking, can be improved later)

| # | Risk | Details |
|---|-------|---------|
| R12 | `historical_events` is untyped `list` | No `HistoricalEvent` dataclass exists. Typing is loose. |
| R13 | `category` field in `TradeResult` | `EventFeatures` has no `category` — this will always be `""` unless added. |
| R14 | `fill_mode: str = "taker"` hardcoded | Backtest engine always uses `simulate_taker_entry` — maker fills not tested. |
| R15 | Entry quantity always `1` | `simulate_taker_entry(quantity=1)` hardcoded — no position sizing. |
| R16 | Settlement exit only | No profit-target, stop-loss, or time-stop exit simulation. |

### `max_drawdown` Implementation Note

The plan leaves `max_drawdown = 0.0` as a placeholder. A correct implementation requires computing peak-to-trough decline across the sequence of trades within each experiment×threshold bucket. This needs:

```python
def _compute_max_drawdown(pnls: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / max(peak, 1e-9)
        max_dd = max(max_dd, dd)
    return max_dd
```

This should be implemented in `metrics.py` rather than left as `0.0`.

---

## Appendix A: Complete Cross-Reference Table

| Strategy-System Model | Core Equivalent | Status | Home File |
|---|---|---|---|
| `HistoricalTrade` | None | ❌ Missing | → `core/models/backtesting.py` |
| `Candlestick` | None | ❌ Missing | → `core/models/backtesting.py` |
| `OrderbookSnapshot` | None | ❌ Missing | → `core/models/backtesting.py` |
| `HistoricalEvent` | None | ❌ Missing | → `core/models/backtesting.py` |
| `MarketFeatures` (strategy-system) | `MarketFeatures` (core) | ⚠️ Field/type mismatch | `core/interfaces/strategy.py` (exists) |
| `EventFeatures` (strategy-system) | `EventFeatures` (core) | ⚠️ Missing fields | `core/interfaces/strategy.py` (exists) |
| `TradeDecision` (strategy-system) | `TradeDecision` (core) | ⚠️ Different structure | `core/interfaces/strategy.py` (exists) |
| `StrategyExperiment` | `StrategyExperiment` | ✅ Aligned | `strategies/base.py` (exists) |

## Appendix B: Corrected `backtest_engine.py` Pseudocode Sketch

```python
def run_backtest(
    historical_events: list[HistoricalEvent],
    get_trades_fn: Callable[[str, datetime], list[HistoricalTrade]],
    get_candles_fn: Callable[[str, datetime], list[Candlestick]],
    thresholds: list[float] | None = None,
    experiment_names: list[str] | None = None,
) -> dict[str, StrategyMetrics]:
    thresholds = thresholds or [0.50, 0.60, 0.65, 0.75, 0.85]
    experiment_names = experiment_names or list(EXPERIMENT_REGISTRY.keys())

    all_results: dict[str, list[TradeResult]] = {}

    for event in historical_events:
        for threshold in thresholds:
            entry_time = event.start_time + (event.end_time - event.start_time) * threshold
            
            market_features_list = []
            for ticker in event.child_market_tickers:
                trades = get_trades_fn(ticker, entry_time)
                candles = get_candles_fn(ticker, entry_time)
                mf = build_market_features(
                    market_ticker=ticker,
                    trades=trades,
                    candles=candles,
                    entry_time=entry_time,
                    # ... other params mapped per Section 3
                )
                market_features_list.append(mf)

            event_features = EventFeatures(
                event_ticker=event.event_ticker,
                event_title=event.event_title,
                child_markets=market_features_list,
            )

            for exp_name in experiment_names:
                experiment = get_experiment(exp_name, {})
                decision = experiment.select_trade(event_features)

                if not decision.should_trade:
                    continue

                fill = simulate_taker_entry(
                    side=decision.side,
                    price_cents=decision.entry_price_cents,
                    quantity=1,
                )

                exit_result = hold_to_settlement(
                    entry_price=fill.price_cents,
                    side=decision.side,
                    settlement_result=event.settlement_result or "no",
                )

                result = TradeResult(
                    experiment_id=decision.experiment_id or exp_name,
                    threshold=threshold,
                    event_ticker=event.event_ticker,
                    market_ticker=decision.market_ticker,
                    side=decision.side,
                    entry_price=fill.price_cents,
                    exit_price=exit_result.exit_price_cents,
                    won=exit_result.pnl_cents > 0,
                    pnl_cents=exit_result.pnl_cents,
                    roi_percent=exit_result.roi_percent,
                    category="",
                )
                # ... store result

    # Compute metrics per experiment × threshold
    return {
        key: compute_metrics(results)
        for key, results in all_results.items()
    }
```

---

*End of Phase 5 Alignment Document. This is a planning document only — no code changes have been made.*
