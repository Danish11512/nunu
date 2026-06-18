# Phase 6 — Trading + Logging + Portfolio: Validation & Alignment Document

> **Scope:** Steps 47–51 of `docs/build-plan.md`
> **Cross-references:** `backend/core/models/trading.py`, `backend/core/interfaces/strategy.py`, `backend/core/interfaces/adapter.py`, `backend/engines/engine7_validation.py`, `backend/config/settings.py`
> **Date:** 2026-06-18
> **Status:** Planning only — no Phase 6 code has been implemented yet.

---

## 1. Executive Summary

Phase 6 creates 5 files that form the trading, logging, and portfolio layer:

| # | File | Purpose |
|---|------|---------|
| 47 | `backend/trading/portfolio.py` | Portfolio + position tracking, PnL |
| 48 | `backend/trading/execution_engine.py` | Async signal queue, dry-run/live execution |
| 49 | `backend/trading/trade_executor.py` | Thin facade over ExecutionEngine |
| 50 | `backend/logging/csv_logger.py` | CSV per event type (candidates, trades, opportunities) |
| 51 | `backend/logging/log_setup.py` | Logging initializer with rotation + custom levels |

**Key finding:** The pseudocode in `build-plan.md` references field names on `ProgressBasedOrderCandidate`, `ValidatedOrderCandidate`, `TradeRecord`, and the Kalshi adapter that **do not exist** in the actual core models. Every file except `log_setup.py` is affected. The most impacted files are `execution_engine.py` (~15 misaligned references) and `csv_logger.py` (~13 misaligned references).

---

## 2. Data Model Alignment

### 2.1 `TradeRecord` — Actual vs. Plan

```python
# Current core (backend/core/models/trading.py):
@dataclass
class TradeRecord:
    market_ticker: str
    event_ticker: str
    side: str
    entry_price: int
    exit_price: int | None = None
    quantity: int = 0
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    pnl: float = 0.0
    status: str = "open"
    trade_id: str = ""
```

| Plan Field Reference | Actual `TradeRecord` Field | Type Delta | Action |
|---|---|---|---|
| `trade.price` | `trade.entry_price` (int) | Name mismatch | Rename |
| `trade.size` | `trade.quantity` (int) | Name + type mismatch | Rename, change type |
| `trade.timestamp` | `trade.entry_time` (datetime\|None) | Name mismatch | Rename |
| `trade.mode` | ❌ Does not exist | Missing field | Add to `TradeRecord` OR remove reference |
| `trade.validation_latency_ms` | ❌ Does not exist | Missing field | Add to `TradeRecord` OR remove reference |
| `trade.error` | ❌ Does not exist | Missing field | Add to `TradeRecord` OR remove reference |

### 2.2 `ProgressBasedOrderCandidate` — Actual vs. Plan

```python
# Current core (backend/core/models/trading.py):
@dataclass
class OrderCandidate:
    event_ticker: str
    market_ticker: str
    side: str
    price: int
    confidence: float = 0.0
    reason: str = ""
    volume: int = 0
    progress_pct: float = 0.0
    created_at: datetime | None = None

@dataclass
class ProgressBasedOrderCandidate(OrderCandidate):
    most_bet_side: str = ""
    threshold_pct: float = 0.0
    is_overtime: bool = False
```

| Plan Field Reference | Actual Field | Action |
|---|---|---|
| `candidate.selected_market.ticker` | `candidate.market_ticker` (str, direct) | Flatten: `candidate.market_ticker` |
| `candidate.selected_market_stats.best_yes_bid` | `candidate.price` (int) | Use `candidate.price` |
| `candidate.total_resting_order_quantity` | `candidate.volume` (int) | Rename |
| `candidate.event_progress_percent` | `candidate.progress_pct` (float) | Rename |
| `candidate.threshold_percent` | `candidate.threshold_pct` (float) | Rename |
| `candidate.selected_market` (object) | ❌ No such attribute | Remove — ticker is a flat `str` |
| `candidate.selected_market_stats` (object) | ❌ No such attribute | Remove — price is a flat `int` |
| `candidate.yes_order_quantity` | ❌ Does not exist | Remove from CSV logger |
| `candidate.no_order_quantity` | ❌ Does not exist | Remove from CSV logger |
| `candidate.should_create_order_candidate` | ❌ Does not exist | Remove from CSV logger |
| `candidate.requires_manual_review` | ❌ Does not exist | Remove from CSV logger |
| `candidate.reasons` (plural list) | `candidate.reason` (singular str) | Rename + change type |

### 2.3 `ValidatedOrderCandidate` — Actual vs. Plan

```python
# Current core (backend/core/models/trading.py):
@dataclass
class ValidatedOrderCandidate:
    original_candidate: OrderCandidate
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    estimated_entry_price: int = 0
    estimated_exit_price: int = 0
    max_contracts: int = 0
```

| Plan Field Reference | Actual Field | Action |
|---|---|---|
| `validated.can_trade` | `validated.is_valid` (bool) | Rename |
| `validated.reason` | `validated.validation_errors` (list[str]) | Check `len(errors) == 0` instead |
| `validated.confirmed_side` | ❌ Does not exist | Use `validated.original_candidate.side` |
| `validated.validation_timestamp` | ❌ Does not exist | Compute at call site |
| `validated.validation_latency_ms` | ❌ Does not exist | Compute at call site |

### 2.4 `MarketOrderbookStats` — for context

```python
@dataclass
class MarketOrderbookStats:
    market_ticker: str
    event_ticker: str
    spread_cents: int | None = None
    yes_bid: int | None = None
    yes_ask: int | None = None
    no_bid: int | None = None
    no_ask: int | None = None
    last_price: int | None = None
    volume: int = 0
    open_interest: int = 0
    volume_24h: int | None = None
    total_resting_order_quantity: int = 0
```

Note: `total_resting_order_quantity` exists here but **not** on `ProgressBasedOrderCandidate`. The plan pseudocode accesses it on the candidate, but it belongs on orderbook stats.

### 2.5 KalshiAdapter `place_order` Signature

```python
# Actual signature (backend/adapters/kalshi/adapter.py):
async def place_order(
    self, ticker: str, side: str, price: int, count: int, **kwargs: Any
) -> dict[str, Any]:
```

| Plan Reference | Actual | Action |
|---|---|---|
| `adapter.place_order(size=size)` | `count=count` (int) | Rename parameter; keep as `int` |

The plan passes `size` (float) — the actual parameter is `count` (int).

---

## 3. `portfolio.py` — Alignment Map

### `PortfolioPosition` Fields

| Plan Field | Plan Type | Issue | Recommendation |
|---|---|---|---|
| `size` | `float` | Core uses `int` for contract quantities everywhere | Change to `int` |
| `avg_entry_price` | `float` | Running average may be fractional — keep `float` | ✅ Keep `float`, document as cents (may be fractional) |
| `realized_pnl` | `float` | ✅ Fine | No change |
| `cost_basis` | `float` | ✅ Fine | No change |
| `trade_count` | `int` | ✅ Fine | No change |

### `Portfolio.record_fill` — Field Mismatches

| Plan Code | Issue | Correct Code |
|---|---|---|
| `trade.size` (4 occurrences) | Field is `trade.quantity` | `trade.quantity` |
| `trade.price` (3 occurrences) | Field is `trade.entry_price` | `trade.entry_price` |

### `PortfolioStats` Fields

| Plan Field | Plan Type | Issue | Recommendation |
|---|---|---|---|
| `total_volume` | `float` | Volume is contracts × price in cents — could be large. `float` is acceptable for aggregate | ✅ Keep `float` |

### ⚠️ Win/Loss Heuristic Bug

```python
# Plan pseudocode:
if trade.price > pos.avg_entry_price:
    self.stats.winning_trades += 1
else:
    self.stats.losing_trades += 1
```

This compares the **new trade's price** against the **running average entry price** of the position. This is **logically flawed**:

- If you built a position with an avg_entry of 60¢ and then buy more at 65¢ (higher), the code counts this as a "winning trade" — but you bought at a worse price, which is a loss relative to the original entry.
- Conversely, if you buy more at 55¢ (lower), it counts as a "losing trade" — but you improved your average entry.
- PnL categorization should be determined by **exit outcome** (was the position closed at a profit?), not by comparing individual fill prices against a running average.

**Recommendation:** Remove the win/loss tracking from `record_fill`. Defer PnL categorization to when positions are closed (exits), not when entries occur. Alternatively, if the intent is to track "was this fill at a favorable price," use a comparison against a reference price (e.g., fair value or last traded price), not against the running average.

### `Portfolio.reset()`

Existed in plan. ✅ No issues — straightforward.

### `Portfolio.get_pnl()` Return Shape

Returns `{"realized": ..., "unrealized": ..., "total": ...}`. The `realized` and `unrealized` fields are never updated by `record_fill` (only `initial_balance` and `stats` are touched). These will always be `0.0` until a `close_position` method is implemented. **Flag as incomplete** — either implement PnL settlement on position close or remove these fields.

---

## 4. `execution_engine.py` — Alignment Map

### 4.1 `_execute_signal` — Candidate Field Access

| Plan Code | Actual Field | Fix |
|---|---|---|
| `candidate.selected_market.ticker` | `candidate.market_ticker` (str) | `candidate.market_ticker` |
| `candidate.selected_market_stats.best_yes_bid` | `candidate.price` (int) | `candidate.price` |
| `candidate.total_resting_order_quantity` | `candidate.volume` (int) | `candidate.volume` |

The plan builds `side, price, size` from three fake "nested object" fields that don't exist. All three are flat fields on the candidate itself.

### 4.2 `_execute_signal` — Validation Result Access

| Plan Code | Actual Field | Fix |
|---|---|---|
| `validated.can_trade` | `validated.is_valid` (bool) | `validated.is_valid` |
| `validated.reason` | `validated.validation_errors` (list[str]) | `len(validated.validation_errors) == 0` |
| `validated.confirmed_side` | ❌ Does not exist | `validated.original_candidate.side` |

The plan's guard clause:
```python
if not validated.can_trade:
    logger.info(f"Signal rejected ... {validated.reason}")
```
Should be:
```python
if not validated.is_valid:
    reasons = "; ".join(validated.validation_errors)
    logger.info(f"Signal rejected ... {reasons}")
```

### 4.3 `validate_candidate` Call — Signature Mismatch

| Plan Code | Actual Signature |
|---|---|
| `validate_candidate(candidate, self.adapter, self.strategy, ValidationConfig())` | `validate_candidate(candidate, client, strategy, config, now=None)` |

The plan passes the **adapter** as the second argument. The actual function expects a **`MarketReader`** (the `client` parameter). `KalshiAdapter` implements `MarketReader`, so `self.adapter` will work at runtime — but the parameter name is misleading. The plan omits the `now` keyword argument, which is acceptable since it defaults `None`.

### 4.4 `TradeRecord` Construction — Dry Run

```python
# Plan pseudocode:
trade = TradeRecord(
    trade_id=trade_id,
    event_ticker=candidate.event_ticker,
    market_ticker=candidate.selected_market.ticker,  # ← candidate.market_ticker
    side=side,
    price=price,          # ← entry_price
    size=size if is_filled else 0,  # ← quantity
    mode="dry_run",       # ← does not exist
    status="filled" if is_filled else "failed",
    timestamp=...,        # ← entry_time
    validation_latency_ms=...,  # ← does not exist
)
```

**All issues at once:**

| Plan Field | Correct Field | Action |
|---|---|---|
| `market_ticker=candidate.selected_market.ticker` | `market_ticker=candidate.market_ticker` | Flatten |
| `price=price` | `entry_price=price` | Rename |
| `size=size if is_filled else 0` | `quantity=size if is_filled else 0` | Rename; keep `int` |
| `mode="dry_run"` | ❌ Does not exist | Add field or remove |
| `timestamp=...` | `entry_time=...` | Rename |
| `validation_latency_ms=...` | ❌ Does not exist | Add field or remove |

### 4.5 `TradeRecord` Construction — Live

Same issues as dry run, plus:

| Plan Code | Signature Issue |
|---|---|
| `result = await self.adapter.place_order(ticker=..., side=..., price=..., size=...)` | Actual parameter is `count`, not `size` |

Should be:
```python
result = await self.adapter.place_order(
    ticker=candidate.market_ticker,
    side=side,
    price=price,
    count=size,  # not size=size
)
```

### 4.6 `datetime.utcnow()` Usage

Both `_execute_dry_run` and `_execute_live` use:
```python
self._order_timestamps[trade_id] = datetime.utcnow()
```

`datetime.utcnow()` is **deprecated** in Python 3.12+. Additionally, the project convention (seen in engines) uses `ZoneInfo("America/New_York")`. However, for a monotonic timeout monitor, UTC is fine. Use:
```python
from datetime import datetime, timezone
self._order_timestamps[trade_id] = datetime.now(timezone.utc)
```

### 4.7 `size` as Float in Log Messages

The plan uses `f"{size:.2f}x@{price:.4f}"` — float format specifiers. With `size` as `int` and `price` as `int`, these should be:
```python
f"{size}x@{price}¢"
```

### 4.8 `ExecutionConfig` — Slippage Type

`ExecutionConfig.slippage_tolerance: float = 0.02` — represents 2%. This is fine as `float` since it's a proportional value, not a price.

---

## 5. `trade_executor.py` — Alignment Map

The facade is minimal (3 lines of logic). No model dependency issues.

| Plan Code | Issue | Resolution |
|---|---|---|
| `return None, None` | Callers must handle `None` returns | Document that this returns `(None, None)` — results flow through portfolio + stats |

Only concern: if any caller unpacks the return value without checking for `None`, it will crash. **Recommendation:** either return an empty results object, or document clearly that the facade returns `None, None` and remove the return values from the API contract.

---

## 6. `csv_logger.py` — Alignment Map

### 6.1 Candidate CSV — Field Mismatches

```python
# Plan header row:
headers = [
    "timestamp", "event_ticker", "market_ticker", "side",
    "progress_pct", "threshold_pct", "total_orders",
    "yes_orders", "no_orders", "actionable", "manual_review", "reasons",
]

# Plan log_candidate body:
csv.writer(f).writerow([
    datetime.now().isoformat(), c.event_ticker,
    c.selected_market.ticker if c.selected_market else "",  # ← ISSUE
    c.most_bet_side, f"{c.event_progress_percent:.1f}",    # ← ISSUE
    c.threshold_percent, c.total_resting_order_quantity,   # ← ISSUE (2×)
    c.yes_order_quantity, c.no_order_quantity,              # ← ISSUE (2×)
    c.should_create_order_candidate, c.requires_manual_review,  # ← ISSUE (2×)
    "; ".join(c.reasons),  # ← ISSUE
])
```

| Header | Plan Reference | Actual | Fix |
|--------|---------------|--------|-----|
| `market_ticker` | `c.selected_market.ticker` (nested object) | `c.market_ticker` (flat str) | `c.market_ticker` |
| `progress_pct` | `c.event_progress_percent` | `c.progress_pct` | Rename |
| `threshold_pct` | `c.threshold_percent` | `c.threshold_pct` | Rename |
| `total_orders` | `c.total_resting_order_quantity` | `c.volume` | Rename |
| `yes_orders` | `c.yes_order_quantity` | ❌ Does not exist | **Remove column** — no split by side on candidates |
| `no_orders` | `c.no_order_quantity` | ❌ Does not exist | **Remove column** |
| `actionable` | `c.should_create_order_candidate` | ❌ Does not exist | **Remove column** — compute from `side in ("yes","no") and confidence > 0` |
| `manual_review` | `c.requires_manual_review` | ❌ Does not exist | **Remove column** |
| `reasons` | `"; ".join(c.reasons)` (list) | `c.reason` (single str) | Change to `c.reason` |

### 6.2 Trades CSV — Field Mismatches

```python
# Plan header row:
headers = [
    "timestamp", "trade_id", "event_ticker", "market_ticker",
    "side", "price", "size", "mode", "status", "latency_ms", "error",
]

# Plan log_trade body:
csv.writer(f).writerow([
    t.timestamp, t.trade_id, t.event_ticker, t.market_ticker,
    t.side, t.price, t.size, t.mode, t.status,
    f"{t.validation_latency_ms:.1f}", t.error or "",
])
```

| Header | Plan Reference | Actual Field | Fix |
|--------|---------------|--------|-----|
| `timestamp` | `t.timestamp` | `t.entry_time` | Rename; convert to ISO string |
| `price` | `t.price` | `t.entry_price` | Rename |
| `size` | `t.size` | `t.quantity` | Rename |
| `mode` | `t.mode` | ❌ Does not exist | Add field or remove column |
| `latency_ms` | `t.validation_latency_ms` | ❌ Does not exist | Add field or remove column |
| `error` | `t.error` | ❌ Does not exist | Add field or remove column |

### 6.3 Opportunities CSV — Field Mismatches

```python
# Plan header row:
headers = [
    "timestamp", "event_ticker", "market_ticker", "side",
    "progress_pct", "total_orders", "yes_orders", "no_orders", "edge",
]
```

- `total_orders`, `yes_orders`, `no_orders` — same issues as candidates CSV.
- `edge` — not defined in any core model. Must be computed or removed.

The `log_opportunity` method is referenced in the header but never implemented in the pseudocode body. Only `log_candidate` and `log_trade` are shown. **Incomplete.**

---

## 7. `log_setup.py` — Alignment Map

### 7.1 Custom Log Levels

| Level | Value | Python Standard | Conflict? |
|-------|-------|----------------|-----------|
| `TRADE` | 25 | Between INFO (20) and WARNING (30) | ✅ No conflict |
| `OPPORTUNITY` | 26 | Between TRADE (25) and WARNING (30) | ✅ No conflict |

Python's `logging` module reserves 1–50. Levels 25 and 26 are unused by the stdlib. However, there is a potential conflict with third-party libraries that might define custom levels at these values. **Recommendation:** Use `TRADE = 25` and `OPPORTUNITY = 26` — low risk.

### 7.2 Logger Names

The plan creates named loggers `"trades"` and `"opportunities"` with separate handlers. This is fine — standard Python logging practice. Ensure these logger names are used consistently across the codebase:
- `logging.getLogger("trades")` — for trade-specific events
- `logging.getLogger("opportunities")` — for opportunity-specific events

### 7.3 `trade_history_path` Setting

The `LoggingConfig` has a `trade_history_path` field (in `settings.py`). This is not used by `log_setup.py` — the CSV logger handles trade history via CSV files. If JSON trade history is desired separately, `log_setup.py` is the wrong place (it's for log files). The CSV logger should handle structured trade output. **Minor cleanup note.**

### 7.4 Project `settings.yaml` Presence

The `LoggingConfig` section in `settings.py` has `csv_path: str = ""` and `trade_history_path: str = ""` — these could be wired to `CSVLogger` in Phase 6. The `log_setup.py` file uses its own `log_dir` parameter; consider reading the default from `settings.scanner.out_dir` or `settings.logging.csv_path` for consistency.

---

## 8. Suggested `TradeRecord` Extensions

Based on what Phase 6 needs, the following fields should be added to `TradeRecord` to avoid awkward workarounds:

### 8.1 New Fields

```python
@dataclass
class TradeRecord:
    # ... existing fields ...
    mode: str = ""                # "dry_run" | "live" | "read_only"
    validation_latency_ms: float = 0.0  # milliseconds
    error: str = ""               # error message on failed trades
```

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `mode` | `str` | `""` | Track execution mode for CSV logging and audit |
| `validation_latency_ms` | `float` | `0.0` | Performance monitoring of Engine 7 |
| `error` | `str` | `""` | Store error messages on failed trades |

### 8.2 Rationale

- The alternative (removing references from the build plan) would lose useful audit/debug information.
- These fields are simple `str`/`float` with sensible defaults — zero cost when unused.
- All three are used in both `execution_engine.py` and `csv_logger.py` — removing them from models would still require the plan to carry them through local variables, making the code more fragile.

### 8.3 Rejected Candidates

| Field | Rejected Because |
|-------|-----------------|
| `validation_timestamp` | Redundant with `entry_time` — the entry time IS the validation timestamp in the current flow |
| `confirmed_side` | Already on `original_candidate.side` — adding it to `TradeRecord` would duplicate `side` |

---

## 9. Implementation Order

### Recommended Sequence

```
Step 1:  backend/core/models/trading.py (MINOR)
         └── Add mode, validation_latency_ms, error fields to TradeRecord

Step 2:  backend/logging/log_setup.py
         └── Standalone — no internal dependencies

Step 3:  backend/trading/portfolio.py
         └── Depends only on TradeRecord model (after Step 1)

Step 4:  backend/trading/execution_engine.py
         └── Depends on portfolio + adapter + Engine 7 validation

Step 5:  backend/trading/trade_executor.py
         └── Thin facade over ExecutionEngine (after Step 4)

Step 6:  backend/logging/csv_logger.py
         └── Depends on models only (after Step 1)
```

### Dependency Graph

```
core/models/trading.py (minor: +3 fields)
    │
    ├──────────────────────────────────┐
    │                                  │
    ▼                                  ▼
log_setup.py (standalone)      csv_logger.py (models only)
                                     │
portfolio.py (TradeRecord only)      │
    │                                │
    ▼                                │
execution_engine.py ─────────────────┤
    │                                │
    ▼                                │
trade_executor.py                    │
    │                                │
    └──── (no cross-dep with csv) ───┘
```

---

## 10. Risk Assessment

### Critical Risks (will cause compile errors)

| # | Risk | File | Mitigation |
|---|------|------|------------|
| R1 | `candidate.selected_market.ticker` — no `selected_market` attribute on `ProgressBasedOrderCandidate` | `execution_engine.py`, `csv_logger.py` | Use `candidate.market_ticker` (flat `str`) |
| R2 | `candidate.selected_market_stats.best_yes_bid` — no such attribute | `execution_engine.py` | Use `candidate.price` |
| R3 | `candidate.total_resting_order_quantity` — no such attribute on candidate | `execution_engine.py`, `csv_logger.py` | Use `candidate.volume` |
| R4 | `validated.can_trade` — no such field on `ValidatedOrderCandidate` | `execution_engine.py` | Use `validated.is_valid` |
| R5 | `validated.reason` — no such field | `execution_engine.py` | Use `validated.validation_errors` (list) |
| R6 | `validated.confirmed_side` — no such field | `execution_engine.py` | Use `validated.original_candidate.side` |
| R7 | `TradeRecord(price=..., size=..., ...)` — fields are `entry_price`, `quantity` | `execution_engine.py` | Rename constructor kwargs |
| R8 | `TradeRecord(mode=..., validation_latency_ms=..., error=...)` — fields don't exist | `execution_engine.py`, `csv_logger.py` | Add 3 fields to `TradeRecord` (Section 8) |
| R9 | `adapter.place_order(size=size)` — parameter is `count` | `execution_engine.py` | Use `count=size` |

### Medium Risks (will produce wrong results or fragile code)

| # | Risk | Details |
|---|-------|---------|
| R10 | Win/loss heuristic in `Portfolio.record_fill` compares `trade.price > pos.avg_entry_price` | This does **not** measure PnL — it compares a fill price against a running average. A buy at a higher price than average is counted as a "win," which is backwards. See Section 3. |
| R11 | `Portfolio.get_pnl()` returns `realized=0.0, unrealized=0.0` — these are never updated | The portfolio has no `close_position` method. PnL settlement is incomplete. |
| R12 | `datetime.utcnow()` used in `_execute_dry_run` and `_execute_live` | Deprecated in Python 3.12+. Use `datetime.now(timezone.utc)`. |
| R13 | `candidate.yes_order_quantity`, `no_order_quantity`, `should_create_order_candidate`, `requires_manual_review` — none exist | These 4 fields referenced in `csv_logger.py` must be removed or replaced with existing fields. Loss of CSV column data. |
| R14 | `c.reasons` (plural) — actual field is `c.reason` (singular `str`) | `"; ".join(c.reasons)` will crash. Use `c.reason` directly. |
| R15 | `c.event_progress_percent` — actual field is `c.progress_pct` | Silent data loss — CSV column will be empty unless renamed. |
| R16 | `c.threshold_percent` — actual field is `c.threshold_pct` | Silent data loss — same as R15. |
| R17 | `log_opportunity` method referenced in header but not implemented | Opportunities CSV will never be written. **Missing method.** |

### Low Risks (non-blocking, can be improved later)

| # | Risk | Details |
|---|-------|---------|
| R18 | `ExecutionConfig.slippage_tolerance: float = 0.02` — never used in the pseudocode | The `_execute_signal` method doesn't check slippage against the actual orderbook. The field exists but does nothing. |
| R19 | `ExecutionConfig.order_timeout_seconds: float = 60.0` — used only in `_monitor_order_timeouts` | This is fine, but the timeout monitor only cancels open orders — it doesn't notify the portfolio or trigger any recovery logic. |
| R20 | `Portfolio.initial_balance` is never enforced | The portfolio allows trading regardless of available cash. No position sizing or balance check exists. |
| R21 | `fill_probability: float = 0.8` — hardcoded in `ExecutionConfig` | Dry-run fill probability is configurable but there's no mechanism to make it realistic (e.g., based on orderbook depth). |
| R22 | `trade_executor.py` returns `None, None` | Callers must handle this. Low risk if the facade is only used as documented. |

---

## 11. Appendix: Corrected Pseudocode Sketches

### 11.1 Corrected `execution_engine.py` — `_execute_signal`

```python
async def _execute_signal(self, candidate: ProgressBasedOrderCandidate):
    """Execute a single signal (validated candidate)."""
    if self.mode == "read_only":
        logger.info(f"[READ-ONLY] Would execute: {candidate.event_ticker}")
        return

    validated = await validate_candidate(
        candidate, self.adapter, self.strategy, ValidationConfig()
    )
    if not validated.is_valid:
        reasons = "; ".join(validated.validation_errors)
        logger.info(f"Signal rejected by validation: {candidate.event_ticker} — {reasons}")
        return

    side = validated.original_candidate.side or candidate.most_bet_side
    price = candidate.price
    quantity = candidate.volume

    if self.mode == "dry_run":
        await self._execute_dry_run(candidate, validated, side, price, quantity)
    else:
        await self._execute_live(candidate, validated, side, price, quantity)
```

### 11.2 Corrected `execution_engine.py` — `_execute_dry_run`

```python
async def _execute_dry_run(self, candidate, validated, side, price, quantity):
    import random
    from datetime import datetime, timezone
    trade_id = f"dry_{uuid.uuid4().hex[:12]}"
    is_filled = (
        not self.config.simulate_fills
        or random.random() < self.config.fill_probability
    )
    now = datetime.now(timezone.utc)
    trade = TradeRecord(
        trade_id=trade_id,
        event_ticker=candidate.event_ticker,
        market_ticker=candidate.market_ticker,
        side=side,
        entry_price=price,
        quantity=quantity if is_filled else 0,
        mode="dry_run",
        status="filled" if is_filled else "failed",
        entry_time=now,
    )
    self._open_orders[trade_id] = trade
    self._order_timestamps[trade_id] = now
    self.stats.orders_placed += 1
    if is_filled:
        self.stats.orders_filled += 1
        self.portfolio.record_fill(trade)
    logger.info(
        f"[DRY-RUN] {'FILLED' if is_filled else 'REJECTED'}: "
        f"{candidate.event_ticker} {side} {quantity}x@{price}¢"
    )
```

### 11.3 Corrected `execution_engine.py` — `_execute_live`

```python
async def _execute_live(self, candidate, validated, side, price, quantity):
    from datetime import datetime, timezone
    try:
        result = await self.adapter.place_order(
            ticker=candidate.market_ticker,
            side=side,
            price=price,
            count=quantity,
        )
        now = datetime.now(timezone.utc)
        trade_id = result.get("order_id", f"live_{uuid.uuid4().hex[:12]}")
        trade = TradeRecord(
            trade_id=trade_id,
            event_ticker=candidate.event_ticker,
            market_ticker=candidate.market_ticker,
            side=side,
            entry_price=price,
            quantity=quantity,
            mode="live",
            status="filled",
            entry_time=now,
        )
        self._open_orders[trade_id] = trade
        self._order_timestamps[trade_id] = now
        self.stats.orders_placed += 1
        self.stats.orders_filled += 1
        self.portfolio.record_fill(trade)
        logger.info(f"[LIVE] ORDER PLACED: {candidate.event_ticker} {side} {quantity}x@{price}¢")
    except Exception as e:
        logger.error(f"[LIVE] ORDER FAILED: {candidate.event_ticker} — {e}")
        self.stats.orders_rejected += 1
```

### 11.4 Corrected `csv_logger.py` — `log_candidate`

```python
def log_candidate(self, c: ProgressBasedOrderCandidate):
    path = os.path.join(self.log_dir, "candidates.csv")
    with open(path, "a", newline="") as f:
        is_actionable = c.side in ("yes", "no") and c.confidence > 0
        csv.writer(f).writerow([
            datetime.now().isoformat(),
            c.event_ticker,
            c.market_ticker,
            c.most_bet_side or c.side,
            f"{c.progress_pct:.1f}",
            f"{c.threshold_pct:.1f}",
            c.volume,
            is_actionable,
            c.reason,
        ])
```

With corrected headers:
```python
self._init_csv("candidates.csv", [
    "timestamp", "event_ticker", "market_ticker", "side",
    "progress_pct", "threshold_pct", "total_resting_quantity",
    "actionable", "reason",
])
```

### 11.5 Corrected `csv_logger.py` — `log_trade`

```python
def log_trade(self, t: TradeRecord):
    path = os.path.join(self.log_dir, "trades.csv")
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow([
            t.entry_time.isoformat() if t.entry_time else "",
            t.trade_id,
            t.event_ticker,
            t.market_ticker,
            t.side,
            t.entry_price,
            t.quantity,
            t.mode,
            t.status,
            f"{t.validation_latency_ms:.1f}",
            t.error or "",
        ])
```

With corrected headers:
```python
self._init_csv("trades.csv", [
    "timestamp", "trade_id", "event_ticker", "market_ticker",
    "side", "entry_price", "quantity", "mode", "status", "latency_ms", "error",
])
```

### 11.6 Corrected `portfolio.py` — `record_fill`

```python
def record_fill(self, trade: TradeRecord):
    """Update portfolio from a trade fill (real or simulated).

    NOTE: Win/loss tracking is not computed here. PnL categorization
    should be determined when positions are closed, not on entry fills.
    See Phase 6 Alignment doc Section 3 for details.
    """
    key = f"{trade.market_ticker}:{trade.side}"
    pos = self._positions.get(key)
    if not pos:
        pos = PortfolioPosition(
            event_ticker=trade.event_ticker,
            market_ticker=trade.market_ticker,
            side=trade.side,
        )
        self._positions[key] = pos

    # Update position
    new_size = pos.size + trade.quantity
    total_cost = (pos.avg_entry_price * pos.size) + (trade.entry_price * trade.quantity)
    pos.avg_entry_price = total_cost / new_size if new_size > 0 else 0.0
    pos.size = new_size
    pos.trade_count += 1
    self.cash_balance -= trade.entry_price * trade.quantity

    # Track trade
    self._trades.append(trade)
    self.stats.total_trades += 1
    self.stats.total_volume += float(trade.entry_price * trade.quantity)
```

---

## Appendix A: Complete Cross-Reference Table

| Build Plan Model/Field | Core Model/Field | Status | Action |
|---|---|---|---|
| `TradeRecord.price` | `TradeRecord.entry_price: int` | ⚠️ Name mismatch | Rename |
| `TradeRecord.size` | `TradeRecord.quantity: int` | ⚠️ Name + type mismatch | Rename, change to int |
| `TradeRecord.timestamp` | `TradeRecord.entry_time: datetime\|None` | ⚠️ Name mismatch | Rename |
| `TradeRecord.mode` | ❌ Missing | Missing field | Add to model (Section 8) |
| `TradeRecord.validation_latency_ms` | ❌ Missing | Missing field | Add to model (Section 8) |
| `TradeRecord.error` | ❌ Missing | Missing field | Add to model (Section 8) |
| `candidate.selected_market.ticker` | `candidate.market_ticker: str` | ⚠️ Flatten nested access | Direct field access |
| `candidate.selected_market_stats.best_yes_bid` | `candidate.price: int` | ⚠️ Flatten nested access | Use `candidate.price` |
| `candidate.total_resting_order_quantity` | `candidate.volume: int` | ⚠️ Name mismatch | Rename |
| `candidate.event_progress_percent` | `candidate.progress_pct: float` | ⚠️ Name mismatch | Rename |
| `candidate.threshold_percent` | `candidate.threshold_pct: float` | ⚠️ Name mismatch | Rename |
| `candidate.yes_order_quantity` | ❌ Missing | Remove | Drop from CSV |
| `candidate.no_order_quantity` | ❌ Missing | Remove | Drop from CSV |
| `candidate.should_create_order_candidate` | ❌ Missing | Remove | Compute from `side + confidence` |
| `candidate.requires_manual_review` | ❌ Missing | Remove | Drop from CSV |
| `candidate.reasons` (list) | `candidate.reason: str` (singular) | ⚠️ Name + type mismatch | Use `candidate.reason` |
| `candidate.selected_market` (object) | ❌ Missing | Remove | Ticker is flat `str` |
| `candidate.selected_market_stats` (object) | ❌ Missing | Remove | Price is flat `int` |
| `validated.can_trade` | `validated.is_valid: bool` | ⚠️ Name mismatch | Rename |
| `validated.reason` | `validated.validation_errors: list[str]` | ⚠️ Name + type mismatch | Check list length |
| `validated.confirmed_side` | ❌ Missing | Remove | Use `original_candidate.side` |
| `validated.validation_timestamp` | ❌ Missing | Compute at call site | N/A |
| `validated.validation_latency_ms` | ❌ Missing | Compute at call site | N/A |
| `adapter.place_order(size=...)` | `adapter.place_order(count=...)` | ⚠️ Parameter name mismatch | Use `count=` |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | ⚠️ Deprecated API | Replace call |

## Appendix B: Summary of Model Changes Required

### Changes to `backend/core/models/trading.py` (TradeRecord)

Add three optional fields with sensible defaults:

```python
@dataclass
class TradeRecord:
    # ... existing 11 fields unchanged ...
    mode: str = ""                          # "dry_run" | "live" | "read_only"
    validation_latency_ms: float = 0.0      # milliseconds
    error: str = ""                         # error message on failed trades
```

**No existing field types or defaults change.** The addition is fully backward-compatible.

---

*End of Phase 6 Alignment Document. This is a planning document only — no code changes have been made.*
