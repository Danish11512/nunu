# Phase 7 — API Layer (FastAPI): Validation & Alignment Document

> **Scope:** Steps 54–56 of `docs/build-plan.md` (labeled "Phase 6: API Layer" in the detailed pseudocode)  
> **Cross-references:** `backend/core/models/`, `backend/core/scanner_state.py`, `backend/core/interfaces/`, `backend/trading/`, `backend/logging/`, `backend/engines/`, `backend/config/settings.py`, `docs/api-contract.md`  
> **Date:** 2026-06-18  
> **Status:** Planning only — Phase 7 code does not yet exist. `backend/api/__init__.py` exists but is empty.

---

## 1. Executive Summary

Phase 7 creates 4 files that form the FastAPI layer:

| Step | File | Purpose |
|------|------|---------|
| 54 | `backend/api/errors.py` | DRY response helpers (`APIResponse`, `ok()`, `err()`) |
| 55 | `backend/api/rest.py` | REST endpoints (9 endpoints) |
| 56 | `backend/main.py` | FastAPI bootstrap + `TradingBot` orchestrator |

The `backend/api/websocket_handler.py` is mentioned in build-plan pseudocode imports but **no pseudocode is provided** for it.

**Key findings:**

1. **Field references across all 3 files use names that do not match actual core models.** ~40+ misaligned references identified. The most impactful category: the build plan treats `ScannerState` fields as dicts (`.values()`, `.get_candidate()`) but they are actually lists; treats `ProgressBasedOrderCandidate` as having nested objects (`.selected_market.ticker`) but they are flat fields; and references settings paths that don't exist.

2. **`MarketOrderbookStats` is missing 5 fields** that the API contract and build plan pseudocode both depend on: `yes_order_quantity`, `no_order_quantity`, `depth_level_count`, `best_yes_bid`, `best_no_bid`.

3. **`ScannerState` lacks dict-like access methods** (`get_event()`, `get_candidate()`, `markets_by_ticker`). The plan assumes these exist.

4. **Settings path references are deeply wrong** — the plan accesses `bot.settings.kalshi_api_key_id` (should be `bot.settings.kalshi.key_id`), `bot.settings.strategy.active_experiment` (field doesn't exist), and `bot.settings.strategy.experiments` (field doesn't exist).

5. **The `approve_candidate` endpoint has an undefined variable bug** — it references `validated` and `trade` that don't exist in scope.

6. **Existing Phase 6 code** (`portfolio.py`, `execution_engine.py`, `trade_executor.py`, `csv_logger.py`, `log_setup.py`) is already implemented and generally correct against core models, with a few residual issues noted below.

---

## 2. Data Model Alignment

### 2.1 `MarketOrderbookStats` — Missing Fields Needed by API

```python
# Current core (backend/core/models/market.py):
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

| Plan/Contract Reference | Actual Field | Severity | Action |
|---|---|---|---|
| `stats.yes_order_quantity` | ❌ Missing | **Critical** | Add field or compute at API layer |
| `stats.no_order_quantity` | ❌ Missing | **Critical** | Add field or compute at API layer |
| `stats.depth_level_count` | ❌ Missing | **Critical** | Add field or compute at API layer |
| `stats.best_yes_bid` | `stats.yes_bid` (`int \| None`) | Low | Rename in plan/contract (field already exists as `yes_bid`) |
| `stats.best_no_bid` | `stats.no_bid` (`int \| None`) | Low | Rename in plan/contract (field already exists as `no_bid`) |

**Important:** The `calculate_orderbook_stats()` function in `adapters/kalshi/types.py` only populates the fields that exist. It does **not** compute `yes_order_quantity`, `no_order_quantity`, or `depth_level_count`. These would need to be added to both the dataclass and the computation function.

**Must be fixed before rest.py can compile.**

### 2.2 `ProgressBasedOrderCandidate` — Fields Referenced by API

```python
# Current core (backend/core/models/trading.py):
@dataclass
class ProgressBasedOrderCandidate(OrderCandidate):
    most_bet_side: str = ""
    threshold_pct: float = 0.0
    is_overtime: bool = False

# Inherited from OrderCandidate:
#   event_ticker: str, market_ticker: str, side: str, price: int
#   confidence: float, reason: str, volume: int, progress_pct: float
#   created_at: datetime | None
```

| Plan Reference | Actual | Severity | Action |
|---|---|---|---|
| `candidate.selected_market.ticker` | `candidate.market_ticker` (flat `str`) | **Critical** | Plan: flatten to `candidate.market_ticker` |
| `candidate.selected_market.title` | ❌ No such attribute | **Medium** | Plan: remove or fetch from `Market` |
| `candidate.event_progress_percent` | `candidate.progress_pct` (`float`) | **Critical** | Plan: rename to `candidate.progress_pct` |
| `candidate.threshold_percent` | `candidate.threshold_pct` (`float`) | **Critical** | Plan: rename to `candidate.threshold_pct` |
| `candidate.event_passes_progress_threshold` | ❌ Does not exist | **Critical** | Compute at API layer from `progress_pct >= threshold_pct` |
| `candidate.selected_market_ticker` (API response field) | `candidate.market_ticker` | **Critical** | Plan: rename response field |
| `candidate.selected_market_title` (API response field) | ❌ Not on candidate | **Critical** | Plan: remove or compute by looking up market |
| `candidate.most_bet_side` | `candidate.most_bet_side` ✅ | — | Correct |
| `candidate.yes_order_quantity` | ❌ Does not exist | **Critical** | Not on candidate — belongs on `MarketOrderbookStats` |
| `candidate.no_order_quantity` | ❌ Does not exist | **Critical** | Same — belongs on `MarketOrderbookStats` |
| `candidate.total_resting_order_quantity` | `candidate.volume` (`int`) | **Critical** | Plan: rename to `candidate.volume` |
| `candidate.should_create_order_candidate` | ❌ Does not exist | **Critical** | Compute from `side in ("yes","no") and confidence > 0` |
| `candidate.requires_manual_review` | ❌ Does not exist | **Medium** | Remove — not in core model |
| `candidate.reasons` (plural list) | `candidate.reason` (singular `str`) | **Medium** | Change to `[candidate.reason]` or wrap as single-element list |

### 2.3 `ScannerState` — Structure Mismatches

```python
# Current core (backend/core/scanner_state.py):
@dataclass
class ScannerState:
    markets: list[dict[str, Any]]
    classified_events: dict[str, ClassifiedEvent]
    ranked_events: list[EventWithTopMarkets]
    candidates: list[ValidatedOrderCandidate]
    errors: list[str]
    warnings: list[str]
    last_discovery: datetime | None
    last_progress_check: datetime | None
    # ... (no methods — pure dataclass)
```

| Plan Reference | Actual | Severity | Action |
|---|---|---|---|
| `state.candidates.values()` | `state.candidates` is `list`, not `dict` | **Critical** | Plan: use `list(state.candidates)` instead |
| `state.get_candidate(event_ticker)` | ❌ No such method | **Critical** | Add helper method to `ScannerState` OR inline filter |
| `state.get_event(event_ticker)` | ❌ No such method | **Critical** | Add helper method to `ScannerState` OR inline filter |
| `state.markets_by_ticker` | ❌ No such attribute | **Medium** | Build inline or add property to `ScannerState` |
| `state.ranked_events` used as dict (`.values()`) | `state.ranked_events` is `list` | **Critical** | Plan: already iterable — just use it directly |
| `state.ranked_events` as dict for `get_event()` | No key-based lookup | **Critical** | Either convert to `dict[str, EventWithTopMarkets]` in state, or iterate |
| `state.active_candidates` (count) | ❌ No such attribute | Low | Compute as `sum(... for c in state.candidates if c.is_valid)` |

**The API endpoints heavily depend on dict-like access patterns that the current `ScannerState` does not support.** The plan treats `ranked_events` as a dict keyed by `event_ticker` and `candidates` as a dict keyed by `event_ticker`. Neither is true.

**Recommendation:** Either:
- **(A)** Refactor `ScannerState.ranked_events` to `dict[str, EventWithTopMarkets]` keyed by `event_ticker`, and `candidates` to `dict[str, ValidatedOrderCandidate]` keyed by `event_ticker`, **OR**
- **(B)** Add query methods `get_event(ticker)`, `get_candidate(ticker)` that iterate and filter.

Option (B) is less disruptive to existing code.

### 2.4 `ValidatedOrderCandidate` — API Endpoint References

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

| Plan Reference | Actual | Severity | Action |
|---|---|---|---|
| `validated.can_trade` | `validated.is_valid` | **Critical** | Rename in plan |
| `validated.reason` | `validated.validation_errors` (list) | **Critical** | Check `len(errors) == 0` or join list |
| `validated.confirmed_side` | ❌ Does not exist | **Medium** | Use `validated.original_candidate.side` |
| `validated.validation_timestamp` | ❌ Does not exist | Low | Compute at call site |
| `validated.validation_latency_ms` | ❌ Does not exist | Low | Compute at call site |

### 2.5 `Settings` — Path Mismatches (main.py)

```python
# Settings structure:
#   settings.kalshi.api_base_url (NOT base_url)
#   settings.kalshi.key_id (NOT kalshi_api_key_id)
#   settings.kalshi.private_key (NOT kalshi_private_key)
#   settings.kalshi.rate_limit ✅
#   settings.scanner.default_mode ✅
#   settings.scanner.default_threshold ✅
#   settings.strategy.name (NOT active_experiment)
#   settings.strategy.params (NOT experiments)
#   settings.logging.csv_path ✅
#   settings.logging.level ✅
```

| Plan Code | Actual Path | Severity | Action |
|---|---|---|---|
| `self.settings.kalshi.base_url` | `self.settings.kalshi.api_base_url` | **Critical** | Fix plan; nested under `kalshi` sub-config |
| `self.settings.kalshi_api_key_id` | `self.settings.kalshi.key_id` | **Critical** | Fix plan; nested access |
| `self.settings.kalshi_private_key` | `self.settings.kalshi.private_key` | **Critical** | Fix plan; nested access |
| `settings.strategy.active_experiment` | `settings.strategy.name` | **Critical** | Field name mismatch; `active_experiment` doesn't exist |
| `settings.strategy.experiments.get(active, {})` | `settings.strategy.params` | **Critical** | `experiments` doesn't exist; `params` is a `dict[str, Any]` |
| `settings.kalshi_private_key` (boolean check) | `settings.kalshi.private_key` | **Critical** | Same nested access issue |
| `settings.scanner.default_mode` | `settings.scanner.default_mode` | ✅ Correct | No change |
| `settings.scanner.default_threshold` | `settings.scanner.default_threshold` | ✅ Correct | No change |
| `settings.logging.csv_path` | `settings.logging.csv_path` | ✅ Correct | No change |
| `settings.logging.level` | `settings.logging.level` | ✅ Correct | No change |

---

## 3. Per-File Alignment Maps

### 3.1 `backend/api/errors.py` (Step 54)

**Plan pseudocode** references:
- `from fastapi import HTTPException` ✅
- `from pydantic import BaseModel` ✅
- `from zoneinfo import ZoneInfo` ✅
- `APIResponse(BaseModel)` fields: `success: bool`, `data: Optional[Any]`, `error: Optional[APIError]`, `meta: Optional[dict]` ✅
- `APIError(BaseModel)` fields: `code: str`, `message: str`, `details: Optional[dict]` ✅
- `ok()` returns `APIResponse` with `meta={"timestamp": ...}` ✅
- `err()` raises `HTTPException` wrapping `APIError` ✅

**Verdict: ✅ No alignment issues.** This file has no dependency on core models. The pseudocode will compile as-is.

---

### 3.2 `backend/api/rest.py` (Step 55)

#### GET `/scanner/status`

```python
# Plan pseudocode:
state = bot.scanner_state
return ok({
    "mode": bot.mode,
    "is_running": state.is_running,
    "connected_to_kalshi": bot.kalshi_client is not None,
    "markets_tracked": len(state.markets_by_ticker),    # ← ISSUE
    "events_tracked": len(state.ranked_events),
    "active_candidates": sum(1 for c in state.candidates.values()  # ← ISSUE
                             if c.should_create_order_candidate),   # ← ISSUE
    "last_discovery": state.last_discovery,
    "last_progress_check": state.last_progress_check,
})
```

| Issue | Fix |
|---|---|
| `state.markets_by_ticker` | `state.markets` (list of dicts) |
| `state.candidates.values()` | `state.candidates` (already a list) |
| `c.should_create_order_candidate` | Compute: `c.original_candidate.side in ("yes","no") and c.original_candidate.confidence > 0` |

Also: the plan uses `ValidatedOrderCandidate` in `candidates`, but `should_create_order_candidate` is a concept from `ProgressBasedOrderCandidate`. At the API layer, the candidates list contains already-validated candidates. The "active" check should use `c.is_valid`.

**Additionally**, the API contract's `ScannerStatus` specifies `uptime_seconds: float` which is **missing from the plan pseudocode**. This should be computed from `state.started_at`.

#### POST `/scanner/start`

```python
# Plan pseudocode:
result = await run_one_shot(
    adapter=bot.kalshi_adapter,                        # ← ISSUE (kwarg name)
    strategy=bot.strategy,
    threshold_percent=bot.settings.scanner.default_threshold,  # ← ISSUE (kwarg name)
    mode=bot.mode,
)
```

| Issue | Fix |
|---|---|
| `adapter=bot.kalshi_adapter` | Parameter is named `client`, not `adapter`. Object is compatible since `KalshiAdapter` implements `MarketReader`, but kwarg must be `client=` |
| `threshold_percent=` | Parameter is `threshold_pct=` (underscore mismatch) |
| Missing `now=` | Optional (defaults to `datetime.now(ET)`) — acceptable to omit |

The plan also accesses `result.scanned_market_count`, `result.events`, `result.actionable`, `result.manual_review`, `result.validated`. Actual `ScannerOutput` fields:

| Plan Reference | Actual `ScannerOutput` Field | Severity |
|---|---|---|
| `result.scanned_market_count` | `result.num_markets_scanned` | **Critical** |
| `result.events` | `result.events` | ✅ Correct |
| `result.actionable` | `result.num_candidates_found` (int, not list) | **Critical** — plan expects list, actual is int |
| `result.manual_review` | ❌ Does not exist | **Medium** — not in `ScannerOutput` |
| `result.validated` | `result.trades` (list of `ValidatedOrderCandidate`) | **Critical** |

The build plan's response shape for `/scanner/start` also doesn't match the API contract. The contract says:
```python
class StartScannerResult:
    scanner_id: str
    started_at: str  # ISO 8601
```
But the plan returns scan summary stats. **Fix needed in either plan or contract.**

#### GET `/events`

```python
# Plan pseudocode:
events = list(bot.scanner_state.ranked_events.values())   # ← ISSUE
```

`ranked_events` is `list[EventWithTopMarkets]`, not a dict. Should be:
```python
events = bot.scanner_state.ranked_events
```

Accesses on `e` (`EventWithTopMarkets`):
| Plan Reference | Actual | Severity |
|---|---|---|
| `e.event_ticker` | ✅ `e.event_ticker` | Correct |
| `e.market_count` | ❌ Does not exist | **Medium** — `EventWithTopMarkets` has `num_top_markets` |
| `e.same_day_live_market_count` | ❌ Does not exist | **Medium** — use `num_top_markets` |
| `e.total_event_resting_order_quantity` | ❌ Does not exist | **Medium** — compute from top_markets |
| `e.active_orderbook_market_count` | ❌ Does not exist | **Medium** — compute from top_markets |
| `e.event_progress_percent` (from candidate) | ✅ candidate's `progress_pct` | Correct if accessed via candidate |
| `e.top_3_markets_by_current_orders` | ❌ Does not exist | **Critical** — `EventWithTopMarkets` has `top_markets` (list of `RankedMarket`) |

The `top_markets` list items are `RankedMarket` objects with fields:
| Plan Reference | Actual `RankedMarket` | Severity |
|---|---|---|
| `m.market.ticker` | `m.market_ticker` (flat `str`) | **Critical** |
| `m.market.title` | ❌ No `title` on `RankedMarket` | **Critical** |
| `m.orderbook_stats.best_yes_bid` | `m.yes_price` (`int`) | **Critical** — nested object vs flat field |
| `m.orderbook_stats.best_no_bid` | `m.no_price` (`int`) | **Critical** |
| `m.orderbook_stats.total_resting_order_quantity` | `m.score` (`float`) — proxy value | **Medium** — `score` holds resting order quantity |
| `m.orderbook_stats.yes_order_quantity` | ❌ Missing on `RankedMarket` | **Critical** |
| `m.orderbook_stats.no_order_quantity` | ❌ Missing on `RankedMarket` | **Critical** |
| `m.orderbook_stats.volume_24h` | ❌ Missing on `RankedMarket` | **Critical** |

#### GET `/events/{event_ticker}`

```python
# Plan pseudocode:
event = bot.scanner_state.get_event(event_ticker)   # ← ISSUE: no such method
```

Same structural issues as `/events`: `ScannerState` has no `get_event()` method. Must iterate `ranked_events` to find by ticker.

The plan accesses `event.all_same_day_live_markets_ranked` — this **does not exist** on `EventWithTopMarkets`. The actual field is `top_markets` (list of `RankedMarket`).

The `MarketDetail` fields from the API contract also include:
- `open_time`, `close_time`, `expected_expiration_time`, `latest_expiration_time` — none of these exist on `RankedMarket` (only on `Market` model)
- `total_volume` — not on `RankedMarket`

To fulfill the API contract's `MarketDetail`, the endpoint needs to fetch the full `Market` object for each rank entry, not just the `RankedMarket` summary.

#### GET `/candidates`

```python
# Plan pseudocode:
candidates = list(bot.scanner_state.candidates.values())   # ← ISSUE
```

`candidates` is a list. Just use `bot.scanner_state.candidates` directly.

Each candidate is a `ValidatedOrderCandidate`. The plan accesses:
| Plan Reference | Actual | Severity |
|---|---|---|
| `c.event_ticker` | `c.original_candidate.event_ticker` | **Medium** — needs `.original_candidate.` prefix |
| `c.threshold_percent` | `c.original_candidate.threshold_pct` | **Critical** — name + nesting |
| `c.event_progress_percent` | `c.original_candidate.progress_pct` | **Critical** — name + nesting |
| `c.event_passes_progress_threshold` | ❌ Compute | **Critical** — compute at API layer |
| `c.selected_market.ticker` | `c.original_candidate.market_ticker` | **Critical** — flatten |
| `c.most_bet_side` | `c.original_candidate.most_bet_side` | **Medium** — needs nesting |
| `c.yes_order_quantity` | ❌ Not on candidate | **Critical** |
| `c.no_order_quantity` | ❌ Not on candidate | **Critical** |
| `c.total_resting_order_quantity` | `c.original_candidate.volume` | **Critical** |
| `c.should_create_order_candidate` | ❌ Not on candidate | **Critical** |
| `c.requires_manual_review` | ❌ Not on candidate | **Medium** |
| `c.reasons` | `c.original_candidate.reason` (singular) | **Medium** |

#### POST `/candidates/{event_ticker}/approve`

**This endpoint has an undefined variable bug:**

```python
# Plan pseudocode:
executor = TradeExecutor(bot.execution_engine)
await executor.execute(candidate)

return ok({
    "approved": validated.can_trade,   # ← validated is never defined
    "reason": validated.reason,         # ← same
    "trade": trade,                      # ← trade is never defined
})
```

The `TradeExecutor.execute()` returns `(None, None)` — it never assigns to `validated` or `trade`. Even if it did, the response shape doesn't match the API contract's `ApproveCandidateResult`.

Additionally:
- `candidate.should_create_order_candidate` — field doesn't exist on `ProgressBasedOrderCandidate`
- `bot.mode == "read_only"` check — mode string `"read_only"` vs ScannerConfig's `default_mode` which is `"oneshot"` or `"live"` — **potential inconsistency**
- The `bot.scanner_state.get_candidate(event_ticker)` method doesn't exist

#### POST `/mode`

```python
# Plan pseudocode checks:
if mode not in ("dry_run", "live"):
    err("INVALID_MODE", ...)
```

**Issue:** The `ScannerConfig.default_mode` can be `"oneshot"` or `"live"`. The `mode` field on `TradingBot` could be any string. There's no `"read_only"` mode in the mode-switching endpoint, but `execution_engine.py` checks for `"read_only"`. The API contract defines `ScannerMode` as `"dry_run" | "read_only" | "live"`. **These three sources disagree on valid mode values.**

| Source | Valid Modes |
|---|---|
| API Contract | `dry_run`, `read_only`, `live` |
| Plan pseudocode (switch) | `dry_run`, `live` |
| `execution_engine.py` | `read_only` (checked), `dry_run`, `live` |
| `ScannerConfig.default_mode` | `oneshot`, `live` |

**Recommendation:** Settle on `["dry_run", "read_only", "live"]` as the canonical set. Update `ScannerConfig.default_mode` default to `"dry_run"`.

#### GET `/config`

```python
# Plan pseudocode:
return ok({
    "mode": bot.mode,
    "experiment": {
        "active_experiment": bot.settings.strategy.active_experiment,  # ← ISSUE
    },
    "threshold_percent": bot.settings.scanner.default_threshold,   # ✅ correct
    "available_experiments": [
        {"name": name, "description": cls({}).description}
        for name, cls in EXPERIMENT_REGISTRY.items()
    ],
    "kalshi_connected": bot.kalshi_client is not None,   # ✅
    "has_credentials": bool(bot.settings.kalshi_private_key),  # ← ISSUE
})
```

| Issue | Fix |
|---|---|
| `bot.settings.strategy.active_experiment` | `bot.settings.strategy.name` |
| `bot.settings.kalshi_private_key` | `bot.settings.kalshi.private_key` |
| `cls({}).description` | `StrategyExperiment.__init__` expects `name=`. `cls({})` passes a dict as positional arg. Should be `cls(name=name, **config).description` or similar |

**Also:** The API contract's `ScannerConfigResponse` includes `strategy.profiles` (dict) but the plan only returns `active_experiment`. The contract expects nested `strategy` object with `active_profile` and `profiles`.

#### PUT `/config`

```python
# Plan pseudocode:
if experiment:
    bot.experiment = get_experiment(experiment, {})    # ← ISSUE
    bot.settings.strategy.active_experiment = experiment   # ← ISSUE
if threshold_percent:
    bot.settings.scanner.default_threshold = threshold_percent   # ✅
return await get_config()
```

| Issue | Fix |
|---|---|
| `bot.experiment` — no such attribute | `bot.strategy = get_experiment(...)` |
| `bot.settings.strategy.active_experiment` | `bot.settings.strategy.name` |
| `threshold_percent` param type | Contract says `int \| None` but engine uses `threshold_pct`. Cast as needed |

---

### 3.3 `backend/main.py` (Step 56)

#### `TradingBot.__init__`

```python
# Plan pseudocode:
self.kalshi_client: KalshiClient = None
self.kalshi_adapter: KalshiAdapter = None
self.scanner_state = ScannerState()
self.strategy: StrategyProfile = None
self.portfolio: Portfolio = None
self.execution_engine: ExecutionEngine = None
self.mode: str = settings.scanner.default_mode   # ← "oneshot" vs expected "dry_run"
```

`ScannerConfig.default_mode` defaults to `"oneshot"`. The build plan and API contract use `"dry_run"` for local development. These should be aligned — either change the default to `"dry_run"` or add a validation/translation layer.

#### `TradingBot.start`

```python
# Plan pseudocode:
self.kalshi_client = KalshiClient(
    base_url=self.settings.kalshi.base_url,             # ← ISSUE
    api_key=self.settings.kalshi_api_key_id,              # ← ISSUE
    private_key=self.settings.kalshi_private_key,         # ← ISSUE
    rate_limit=self.settings.kalshi.rate_limit,           # ✅
)
```

| Plan Code | Actual KalshiClient Init | Fix |
|---|---|---|
| `base_url=self.settings.kalshi.base_url` | `self.settings.kalshi.api_base_url` | Rename |
| `api_key=self.settings.kalshi_api_key_id` | `self.settings.kalshi.key_id` | Fix path |
| `private_key=self.settings.kalshi_private_key` | `self.settings.kalshi.private_key` | Fix path |

**Additional issues:**
- `self.strategy = get_experiment(active, self.settings.strategy.experiments.get(active, {}))`  
  `strategy.experiments` doesn't exist; should be `strategy.params`  
  Also, `active = self.settings.strategy.active_experiment` → `self.settings.strategy.name`

- The plan initializes `self.scanner_state = ScannerState()` **twice** (once in `__init__`, once at end of `start()`). This is redundant and would wipe state on restart. Remove the duplicate in `start()`.

- The plan never wires `scanner_state` into `execution_engine` — the engine receives `adapter`, `strategy`, `portfolio`, `mode`, but not `scanner_state`. If the API needs the execution engine to update state, this wiring is missing.

#### Lifespan / Bootstrap

```python
# Plan pseudocode:
settings = load_settings()
setup_logging(
    log_dir=settings.logging.csv_path.rsplit("/", 1)[0]
    if "/" in settings.logging.csv_path else "logs",
    console_level=settings.logging.level,
)
```

- `settings.logging.csv_path.rsplit("/", 1)[0]` — if `csv_path` is empty string (the default), `rsplit` returns `[""]`, and `[0]` is `""`, which will create `setup_logging(log_dir="")`. This should handle the empty-string case explicitly.

- `from backend.strategies import get_experiment` — this import will load all strategy modules. Verify circular imports don't occur (unlikely, but should be tested).

#### Module Imports

The plan imports:
```python
from backend.api.websocket_handler import router as ws_router
```

This file doesn't exist yet. The build plan provides **no pseudocode** for `websocket_handler.py`. This import will fail at runtime unless the file is created (even as a stub).

---

### 3.4 `backend/api/websocket_handler.py` — Pseudocode Missing

The build plan mentions this file in imports but provides **zero pseudocode** for it. It's listed in the file creation order but the detailed section only covers `errors.py`, `main.py`, and `rest.py`.

The API contract defines 4 WebSocket channels (`scanner`, `events`, `candidates`, `trades`) with specific message types. These will need to be implemented with no existing plan pseudocode to align against.

**Files that are referenced but don't exist yet:**
- `backend/api/websocket_handler.py` — no pseudocode at all
- `backend/api/errors.py` — has pseudocode, independent of models ✅

---

## 4. Phase 6 Code Verification

The Phase 6 files (`portfolio.py`, `execution_engine.py`, `trade_executor.py`, `csv_logger.py`, `log_setup.py`) were checked in the [Phase 6 alignment doc](./phase-6-alignment.md). This section verifies their **current implementation** against the core models, since Phase 7's API layer will depend on them.

### 4.1 `portfolio.py` — Current State

The implementation was updated from the Phase 6 plan pseudocode and is **mostly correct**. Residual issues:

| Issue | Line | Severity | Detail |
|---|---|---|---|
| `trade.price` | ~120 | Resolved ✅ | Uses `trade.entry_price` correctly |
| `trade.size` | ~120 | Resolved ✅ | Uses `trade.quantity` correctly |
| Win/loss heuristic | ~130 | Low | Compares fill price to running avg entry — logically flawed but doesn't crash. Flagged in Phase 6 alignment. |
| `get_pnl()` unrealized/realized = 0 | ~170 | Low | No `close_position` method exists, so realized PnL is always 0 |

**Verdict: ✅ Safe to use from API layer.**

### 4.2 `execution_engine.py` — Current State

The implementation is **substantially correct** against core models:

| Issue | Status | Detail |
|---|---|---|
| `candidate.market_ticker` | ✅ Correct | Uses flat field |
| `candidate.price` | ✅ Correct | Uses flat field |
| `candidate.volume` | ✅ Correct | Uses flat field |
| `validated.is_valid` | ✅ Correct | Uses correct field name |
| `validated.validation_errors` | ✅ Correct | List join pattern |
| `TradeRecord` construction | ✅ Correct | Uses `entry_price`, `quantity`, `entry_time`, `mode`, `validation_latency_ms`, `error` — all exist |
| `adapter.place_order(count=size)` | ✅ Correct | Uses `count=` not `size=` |
| `datetime.now(timezone.utc)` | ✅ Correct | Uses modern UTC (not deprecated `utcnow()`) |

**Note:** The engine imports `from backend.engines.engine7_validation import validate_candidate`, which calls `adapter.fetch_markets()` and `adapter.fetch_orderbook()`. Both methods exist on `KalshiAdapter`. ✅

**Verdict: ✅ Safe to use from API layer.**

### 4.3 `trade_executor.py` — Current State

Minimal facade. Returns `(None, None)`. Any API endpoint that calls `executor.execute()` and unpacks the result must handle `None`.

**Verdict: ⚠️ `execute()` returns `(None, None)` — API callers must not unpack.**

### 4.4 `csv_logger.py` — Current State

The implementation already differs from the Phase 6 plan pseudocode and is **mostly correct**:

| Plan Issue | Actual Fix | Status |
|---|---|---|
| `c.selected_market.ticker` | `c.market_ticker` | ✅ Correct |
| `c.event_progress_percent` | `c.progress_pct` | ✅ Correct |
| `c.threshold_percent` | `c.threshold_pct` | ✅ Correct |
| `c.total_resting_order_quantity` | `c.volume` | ✅ Correct |
| `c.yes_order_quantity` / `c.no_order_quantity` | Removed | ✅ Correct |
| `c.should_create_order_candidate` | Removed | ✅ Correct |
| `c.requires_manual_review` | Removed | ✅ Correct |
| `c.reasons` (plural) | `c.reason` (singular) | ✅ Correct |
| `t.timestamp` | `t.entry_time.isoformat()` | ✅ Correct |
| `t.price` | `t.entry_price` | ✅ Correct |
| `t.size` | `t.quantity` | ✅ Correct |
| `t.mode` | `t.mode` | ✅ Correct (field exists) |
| `t.validation_latency_ms` | `t.validation_latency_ms` | ✅ Correct (field exists) |
| `t.error` | `t.error` | ✅ Correct (field exists) |
| `c.edge` in opportunities | Uses `""` placeholder | ⚠️ No edge metric computed yet |

**Verdict: ✅ Safe to use from API layer.** The opportunities CSV `edge` column is a placeholder — acceptable.

### 4.5 `log_setup.py` — Current State

No issues. Standard Python logging configuration with custom levels `TRADE=25` and `OPPORTUNITY=26`.

**Verdict: ✅ Safe to use from API layer.**

---

## 5. API Contract Alignment

### 5.1 Field Name Conventions

The API contract uses **float prices** (e.g., `0.65` for 65¢), while the core backend uses **int cents** (e.g., `65`).

| API Contract (float) | Core Backend (int cents) | Endpoints Affected |
|---|---|---|
| `yes_bid: float \| None` | `yes_bid: int \| None` | `/events`, `/events/{ticker}`, WS events |
| `no_bid: float \| None` | `no_bid: int \| None` | Same |
| `price: float` | `price: int` | `/candidates`, approve |
| `size: float` | `volume: int` | `/candidates`, approve |
| `total_resting_order_quantity: float` | `total_resting_order_quantity: int` | Multiple |

**Decision needed:** The API layer should either:
- **(A)** Convert all int cents to float dollars in the API response (BFF pattern — backend for frontend)
- **(B)** Keep int cents in the API and update the contract

Option (A) is more conventional for a frontend-facing API. The plan pseudocode already uses raw model values without conversion, so it assumes option (B).

### 5.2 Endpoint Feasibility Matrix

| Endpoint | Feasible with Current Models? | Issues | Action Needed |
|---|---|---|---|
| `GET /scanner/status` | ⚠️ Partial | `markets_by_ticker` doesn't exist; need to track `started_at` for `uptime_seconds` | Minor state + ScannerState refactor |
| `POST /scanner/start` | ⚠️ Partial | `run_one_shot` kwarg names differ; `ScannerOutput` field names differ | Fix kwarg names in call; map response fields |
| `GET /events` | ❌ Major | `EventWithTopMarkets` lacks `market_count`, `same_day_live_market_count`, `total_event_resting_order_quantity`, `active_orderbook_market_count`. `RankedMarket` lacks orderbook detail fields, title. | Either add fields to models or compute at API layer from `Market` + `Orderbook` |
| `GET /events/{ticker}` | ❌ Major | Same as `/events` plus `all_same_day_live_markets_ranked` doesn't exist. `MarketDetail` requires `Market` data not available on `RankedMarket`. | API layer must fetch full `Market` objects |
| `GET /events/{ticker}/orderbook` | ❌ Missing | Endpoint exists in API contract but **not in plan pseudocode** | Must be implemented separately |
| `GET /candidates` | ❌ Major | `ScannerState.candidates` is `list[ValidatedOrderCandidate]`, not dict; fields are nested under `.original_candidate` | Flatten in API response |
| `POST /candidates/{id}/approve` | ❌ Critical | Undefined variables `validated` and `trade`; missing field `should_create_order_candidate`; no `get_candidate` method | Rewrite endpoint logic |
| `POST /candidates/{id}/reject` | ❌ Missing | Endpoint exists in API contract but **not in plan pseudocode** | Must be implemented |
| `GET /trades` | ❌ Missing | Endpoint exists in API contract but **not in plan pseudocode** | Must be implemented |
| `GET /config` | ⚠️ Partial | Settings path mismatches; response shape differs from contract | Fix paths; align response shape |
| `PUT /config` | ⚠️ Partial | Settings path + attribute mismatches | Fix paths |
| `POST /mode` | ⚠️ Partial | Mode values inconsistent across sources | Align mode vocabulary |
| WebSocket (4 channels) | ❌ Missing | No pseudocode exists for `websocket_handler.py` | Must be implemented from scratch |

### 5.3 Missing Endpoints vs Plan Pseudocode

The API contract defines these endpoints that have **no pseudocode** in the build plan:

| Endpoint | In Contract | In Plan Pseudocode | Status |
|---|---|---|---|
| `GET /events/{ticker}/orderbook` | ✅ | ❌ | Missing from build plan |
| `POST /candidates/{id}/reject` | ✅ | ❌ | Missing from build plan |
| `GET /trades` | ✅ | ❌ | Missing from build plan |
| `POST /scanner/stop` | ✅ | ❌ | Missing from build plan |
| WebSocket channels (4) | ✅ | ❌ | Missing from build plan |

---

## 6. Risk Assessment

### Critical (will crash at runtime)

| # | Issue | File | Fix |
|---|---|---|---|
| C1 | `state.candidates.values()` — list used as dict | `rest.py: L1, L40` | Change to `state.candidates` |
| C2 | `state.ranked_events.values()` — list used as dict | `rest.py: L40` | Change to `state.ranked_events` |
| C3 | `state.get_candidate(ticker)` — no such method | `rest.py: L45, L96` | Add helper or inline filter |
| C4 | `state.get_event(ticker)` — no such method | `rest.py: L84` | Add helper or inline filter |
| C5 | `state.markets_by_ticker` — no such attribute | `rest.py: L8` | Use `state.markets` |
| C6 | `candidate.selected_market.ticker` — nested object | `rest.py: multiple` | Flatten to `candidate.market_ticker` |
| C7 | `candidate.selected_market.title` — doesn't exist | `rest.py` | Remove or fetch from Market |
| C8 | `candidate.event_progress_percent` → `progress_pct` | `rest.py` | Rename |
| C9 | `candidate.threshold_percent` → `threshold_pct` | `rest.py` | Rename |
| C10 | `candidate.should_create_order_candidate` — doesn't exist | `rest.py: L47, L99` | Compute from side + confidence |
| C11 | `candidate.total_resting_order_quantity` → `candidate.volume` | `rest.py` | Rename |
| C12 | `candidate.yes_order_quantity` / `no_order_quantity` — missing | `rest.py` | Add to `MarketOrderbookStats` |
| C13 | `validated.can_trade` → `validated.is_valid` | `rest.py: approve` | Rename |
| C14 | `validated` / `trade` variables undefined in approve endpoint | `rest.py: approve` | Fix scope — capture return values |
| C15 | `bot.settings.kalshi_api_key_id` → `bot.settings.kalshi.key_id` | `main.py` | Fix path |
| C16 | `bot.settings.kalshi_private_key` → `bot.settings.kalshi.private_key` | `main.py` | Fix path |
| C17 | `bot.settings.kalshi.base_url` → `bot.settings.kalshi.api_base_url` | `main.py` | Fix path |
| C18 | `bot.settings.strategy.active_experiment` → `bot.settings.strategy.name` | `main.py`, `rest.py` | Fix path |
| C19 | `bot.settings.strategy.experiments` → `bot.settings.strategy.params` | `main.py` | Fix path |
| C20 | `run_one_shot(adapter=..., threshold_percent=...)` — kwarg names | `rest.py` | Change to `client=`, `threshold_pct=` |
| C21 | `result.scanned_market_count` → `result.num_markets_scanned` | `rest.py` | Rename |
| C22 | `result.actionable` (list) → `result.num_candidates_found` (int) | `rest.py` | Return type mismatch |
| C23 | `result.validated` → `result.trades` | `rest.py` | Rename |
| C24 | `event.top_3_markets_by_current_orders` — no such field | `rest.py` | Use `event.top_markets` |
| C25 | `m.market.ticker` → `m.market_ticker` (RankedMarket) | `rest.py` | Flatten |
| C26 | `m.market.title` — no title on RankedMarket | `rest.py` | Fetch from Market or add to RankedMarket |
| C27 | `m.orderbook_stats.*` — no such nesting on RankedMarket | `rest.py` | Fields are flat on RankedMarket |
| C28 | `bot.experiment = ...` — no such attribute | `rest.py: PUT /config` | Use `bot.strategy` |
| C29 | `state.ranked_events` type mismatch (list vs dict for event lookup) | `rest.py` | Add lookup helper |
| C30 | `e.market_count`, `e.same_day_live_market_count` — missing | `rest.py` | Add to EventWithTopMarkets or compute |
| C31 | `e.all_same_day_live_markets_ranked` — no such field | `rest.py` | Use `event.top_markets` |
| C32 | `event.all_markets_ranked[*].status, .volume_24h` — on Market, not RankedMarket | `rest.py` | Need full Market objects |
| C33 | No `websocket_handler.py` file exists | All | Create stub or implementation |
| C34 | `ScannerState` initialized twice in `TradingBot` | `main.py` | Remove duplicate in `start()` |

### Medium (produces wrong data)

| # | Issue | File | Fix |
|---|---|---|---|
| M1 | `e.market_count` missing from `EventWithTopMarkets` | `rest.py` | Use `num_top_markets` |
| M2 | Prices in cents (int) returned as-is; API contract expects float dollars | `rest.py` | Convert `int` cents → `float` dollars |
| M3 | `uptime_seconds` missing from `/scanner/status` | `rest.py` | Compute from `started_at` |
| M4 | `strategy.experiments` used as dict but `StrategyConfig.params` is dict | `main.py` | Rename in settings or plan |
| M5 | Mode vocabulary mismatch (`"oneshot"` vs `"dry_run"` vs `"read_only"`) | Multiple | Settle on canonical set |
| M6 | `MarketOrderbookStats` missing `yes_order_quantity`, `no_order_quantity`, `depth_level_count` | Multiple | Add to model + computation |
| M7 | `RankedMarket` has no `volume_24h` field | `rest.py` | Add field or compute separately |
| M8 | `c.original_candidate.*` nesting in candidates endpoint | `rest.py` | Flatten in response construction |
| M9 | `log_setup(log_dir="")` when `csv_path` is empty | `main.py` | Add empty-string guard |
| M10 | `EventWithTopMarkets` only has `num_top_markets`, not full market count | `rest.py` | Add `total_market_count` field |

### Low (cosmetic / minor)

| # | Issue | File | Fix |
|---|---|---|---|
| L1 | `c.reason` (singular) vs API contract's `reasons` (plural array) | `rest.py` | Wrap in single-element list |
| L2 | `portfolio.get_pnl()` returns 0 for realized/unrealized (no close_position) | `portfolio.py` | Implement position close |
| L3 | `csv_logger.log_opportunity()` uses `""` for `edge` | `csv_logger.py` | Compute edge metric |
| L4 | `cls({}).description` in config endpoint — incorrect init pattern | `rest.py` | Fix strategy instantiation |
| L5 | `threshold_percent` as query param vs engine's `threshold_pct` | `rest.py` | Align naming convention |

---

## 7. Recommended Implementation Order

Given the alignment findings, the recommended order for implementing Phase 7:

### Pre-Requisite (do before any Phase 7 code)

1. **Add missing fields to `MarketOrderbookStats`:**
   - `yes_order_quantity: int = 0`
   - `no_order_quantity: int = 0`  
   - `depth_level_count: int = 0`
   - Update `calculate_orderbook_stats()` in `adapters/kalshi/types.py` to populate them

2. **Add query methods to `ScannerState`:**
   - `def get_event(self, ticker: str) -> EventWithTopMarkets | None`
   - `def get_candidate(self, ticker: str) -> ValidatedOrderCandidate | None`
   - `def markets_by_ticker(self) -> dict[str, dict]` property or method
   - OR (better): Add `started_at` field tracking to enable `uptime_seconds`

3. **Fix settings paths that main.py will use:**
   - This is a plan-only issue until main.py is written, but note the corrections needed

### Phase 7 Implementation (corrected)

1. **`backend/api/errors.py`** — No changes needed from plan pseudocode ✅

2. **`backend/api/rest.py`** — Major rewrite needed:
   - Flatten all nested field accesses (`selected_market.ticker` → `market_ticker`)
   - Rename field references (`.event_progress_percent` → `.progress_pct`, etc.)
   - Replace dict-style collection access with list iteration
   - Add helper methods for converting cents to float dollars
   - Fix `approve_candidate` endpoint logic (capture validation result)
   - Add missing endpoints: `/events/{ticker}/orderbook`, `/candidates/{id}/reject`, `/trades`, `/scanner/stop`

3. **`backend/api/websocket_handler.py`** — Implement from scratch using API contract spec:
   - 4 channels: `scanner`, `events`, `candidates`, `trades`
   - Message envelope: `{ type, data, timestamp }`
   - Handle reconnection gracefully

4. **`backend/main.py`** — Fix settings paths, mode alignment, import stubs:
   - Use nested settings access: `settings.kalshi.api_base_url`, `settings.kalshi.key_id`, etc.
   - Fix `TradingBot.__init__` mode default
   - Remove duplicate `ScannerState()` initialization
   - Add `started_at` tracking for uptime computation
   - Handle empty `csv_path` in log setup

---

## 8. Complete Action Item List

### A. Fix Core Models (pre-requisite)

| # | File | Action | Severity |
|---|---|---|---|
| A1 | `backend/core/models/market.py` | Add `yes_order_quantity: int = 0`, `no_order_quantity: int = 0`, `depth_level_count: int = 0` to `MarketOrderbookStats` | **Critical** |
| A2 | `backend/adapters/kalshi/types.py` | Update `calculate_orderbook_stats()` to compute `yes_order_quantity`, `no_order_quantity`, `depth_level_count` | **Critical** |
| A3 | `backend/core/scanner_state.py` | Add `get_event(ticker)`, `get_candidate(ticker)` methods; add `started_at` tracking | **Critical** |
| A4 | `backend/core/models/trading.py` | Optionally add `volume_24h` to `RankedMarket` or keep as API-layer computation | Medium |

### B. Fix Build Plan Pseudocode

| # | Section | Action | Severity |
|---|---|---|---|
| B1 | `rest.py` — All endpoints | Replace nested `selected_market.*` with flat `market_ticker` | **Critical** |
| B2 | `rest.py` — All endpoints | Replace `.event_progress_percent` with `.progress_pct` | **Critical** |
| B3 | `rest.py` — All endpoints | Replace `.threshold_percent` with `.threshold_pct` | **Critical** |
| B4 | `rest.py` — All endpoints | Replace `candidates.values()` / `ranked_events.values()` with direct list access | **Critical** |
| B5 | `rest.py` — All endpoints | Replace `total_resting_order_quantity` on candidates with `volume` | **Critical** |
| B6 | `rest.py` — GET `/events` | Replace `e.top_3_markets_by_current_orders` with `e.top_markets` | **Critical** |
| B7 | `rest.py` — GET `/events/{ticker}` | Replace `e.all_same_day_live_markets_ranked` with `e.top_markets` | **Critical** |
| B8 | `rest.py` — GET `/events` | Add missing fields (`market_count`, `same_day_live_market_count`, etc.) or compute | Medium |
| B9 | `rest.py` — GET `/candidates` | Flatten `ValidatedOrderCandidate` fields (`.original_candidate.*`) | **Critical** |
| B10 | `rest.py` — POST `/candidates/approve` | Fix undefined `validated`/`trade` variables; capture executor return values | **Critical** |
| B11 | `rest.py` — POST `/candidates/approve` | Replace `.can_trade` → `.is_valid`, `.reason` → `.validation_errors` | **Critical** |
| B12 | `rest.py` — POST `/config` | Fix `bot.experiment` → `bot.strategy` | **Critical** |
| B13 | `main.py` — Settings paths | Replace all flat paths with nested access (kalshi.*, strategy.*) | **Critical** |
| B14 | `main.py` — `KalshiClient` init | Fix kwarg names and settings paths | **Critical** |
| B15 | `main.py` — Strategy init | Fix `strategy.experiments` → `strategy.params` | **Critical** |
| B16 | `main.py` — ScannerState init | Remove duplicate initialization in `start()` | Medium |
| B17 | `main.py` — Log setup | Handle empty `csv_path` gracefully | Low |
| B18 | `rest.py` — All responses | Convert int cents to float dollars for API contract compliance | Medium |
| B19 | `rest.py` — All | Add `uptime_seconds` to `/scanner/status` | Medium |
| B20 | `rest.py` — POST `/scanner/start` | Fix `run_one_shot` kwarg names and `ScannerOutput` field names | **Critical** |

### C. Add Missing Endpoints (not in plan pseudocode)

| # | Endpoint | Action | Severity |
|---|---|---|---|
| C1 | `GET /events/{ticker}/orderbook` | Implement in `rest.py` per API contract | Medium |
| C2 | `POST /candidates/{id}/reject` | Implement in `rest.py` per API contract | Medium |
| C3 | `GET /trades` | Implement in `rest.py` — pull from `portfolio._trades` | Medium |
| C4 | `POST /scanner/stop` | Implement in `rest.py` per API contract | Medium |
| C5 | WebSocket 4 channels | Create `websocket_handler.py` from scratch | **Critical** (referenced in imports) |

### D. Align Mode Vocabulary

| # | Source | Current | Target | Severity |
|---|---|---|---|---|
| D1 | API Contract | `"dry_run"`, `"read_only"`, `"live"` | Canonical set | Medium |
| D2 | `ScannerConfig.default_mode` | `"oneshot"` | `"dry_run"` | Medium |
| D3 | POST `/mode` plan | `"dry_run"`, `"live"` | Add `"read_only"` | Low |
| D4 | `execution_engine.py` | Checks for `"read_only"` | Already aligned | ✅ |

### E. Verify After Implementation

| # | Check | Command/Test |
|---|---|---|
| E1 | Import check | `python -c "from backend.api.rest import router"` |
| E2 | Import check | `python -c "from backend.main import app"` |
| E3 | API smoke test | `curl -s http://localhost:8000/api/v1/scanner/status` |
| E4 | Field alignment | Verify every response field against `docs/api-contract.md` |
| E5 | Type alignment | Verify all cents ↔ dollars conversions |

---

## 9. Summary Statistics

| Category | Count |
|---|---|
| Critical issues (will crash) | 34 |
| Medium issues (wrong data) | 10 |
| Low issues (cosmetic) | 5 |
| **Total issues** | **49** |
| ✅ Correct references | ~15 |

**Overall verdict: Phase 7 cannot be implemented from the current plan pseudocode alone.** The settings path mismatches, ScannerState structural differences, and field naming gaps will cause crashes on first execution. The plan needs a full rewrite of `rest.py` endpoint bodies and `main.py` settings access patterns before implementation begins. The pseudocode for `errors.py` is the only file that can be implemented as-is.
