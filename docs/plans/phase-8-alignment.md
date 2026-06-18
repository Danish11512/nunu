# Phase 8 Alignment: Frontend Lib (Types + API Client)

> **Purpose:** Compare the build plan's Phase 8/7 pseudocode, the API contract (`docs/api-contract.md`), and the actual backend implementation (`backend/api/rest.py`) to produce a faithful TypeScript type-and-client scaffold.
>
> **Guiding principle:** The **actual backend implementation** is the source of truth for what the wire format looks like. The API contract is aspirational and should be updated to match reality; in the meantime, the frontend must consume what `rest.py` actually returns.

---

## 1. Response Envelope Alignment

The standard envelope used by every endpoint.

| Field | Contract | Actual (`errors.py`) | Actual (`rest.py` usage) | Verdict |
|-------|----------|----------------------|--------------------------|---------|
| `success` | `boolean` | `bool` | Always `True` in `ok()` | ✅ Match |
| `data` | `T \| null` | `T \| None` | The payload | ✅ Match |
| `error` | `APIError \| null` | `APIError \| None` | Only on error (HTTPException) | ✅ Match |
| `meta.timestamp` | `string` (ISO 8601) | `str` via `now_iso()` | Provided by `ok()` | ✅ Match |
| `meta.duration_ms` | `number` | `float` (default `0.0`) | **Never populated** | ⚠️ Contract says it's optional; actual always `0.0` |

**Decision:** Define `ResponseMeta` with `timestamp` required and `duration_ms` optional (default 0).

---

## 2. TypeScript Interface Alignment

### 2.1 Scanner Mode Types

```typescript
type ScannerMode = "dry_run" | "read_only" | "live";
type CandidateSide = "yes" | "no" | "tie" | "none";
type TradeStatus = "open" | "closed" | "cancelled";  // from TradeRecord model
```

All three sources agree. `TradeStatus` in the contract says `"filled" | "partial" | "failed"` but the actual `TradeRecord` model uses `"open" | "closed" | "cancelled"`. **Prefer the actual model.**

---

### 2.2 `ScannerStatus` — GET /api/v1/scanner/status

| Field | Contract | Actual (`rest.py` ~L275) | Verdict |
|-------|----------|------------------------|---------|
| `mode` | `"dry_run" \| "read_only" \| "live"` | `bot.mode` (same str) | ✅ Match |
| `is_running` | `boolean` | `state.is_running` | ✅ Match |
| `connected_to_kalshi` | `boolean` | `hasattr(bot, "kalshi_client") and bot.kalshi_client.signer is not None` | ✅ Match |
| `uptime_seconds` | `number` | `(now - state.started_at).total_seconds()` or `null` | ✅ Match |
| `markets_tracked` | `number` | `len(state.markets)` | ✅ Match |
| `events_tracked` | `number` | `len(state.ranked_events)` | ✅ Match |
| `active_candidates` | `number` | `len(state.active_candidates)` | ✅ Match |
| `last_discovery` | `string \| null` (ISO 8601) | `state.last_discovery.isoformat()` or `null` | ✅ Match |
| `last_progress_check` | `string \| null` (ISO 8601) | `state.last_progress_check.isoformat()` or `null` | ✅ Match |

**Verdict:** ✅ Perfect alignment. No changes needed.

---

### 2.3 `StartResult` — POST /api/v1/scanner/start

| Field | Contract | Actual (`rest.py` ~L320) | Verdict |
|-------|----------|------------------------|---------|
| `scanner_id` | `string` | `f"scan_{state.current_cycle}"` | ✅ Match |
| `started_at` | `string` (ISO 8601) | `state.started_at.isoformat()` | ✅ Match |
| *(extra)* `events_processed` | — | `output.num_events_scanned` | ⚠️ Not in contract |
| *(extra)* `candidates_generated` | — | `output.num_candidates_found` | ⚠️ Not in contract |
| *(extra)* `trades_executed` | — | `output.num_trades_executed` | ⚠️ Not in contract |

**Decision:** Add the three extra fields. The build plan's pseudocode had a completely different shape (`scanned_market_count`, `same_day_live_event_count`, etc.) — **ignore build plan pseudocode**; use actual `rest.py`.

---

### 2.4 `StopResult` — POST /api/v1/scanner/stop

| Field | Contract | Actual (`rest.py` ~L355) | Verdict |
|-------|----------|------------------------|---------|
| `stopped_at` | `string` (ISO 8601) | `now.isoformat()` | ✅ Match |
| `scan_duration_seconds` | `number` | `(now - state.started_at).total_seconds()` | ✅ Match |
| `events_processed` | `number` | `len(state.ranked_events)` | ✅ Match |
| `candidates_generated` | `number` | `len(state.candidates)` | ✅ Match |

**Verdict:** ✅ Perfect alignment.

---

### 2.5 `EventSummary` — GET /api/v1/events

**Contract defines:**
```typescript
interface EventSummary {
  event_ticker: string;
  market_count: number;
  live_market_count: number;
  total_resting_order_quantity: number;
  active_orderbook_market_count: number;
  top_markets: MarketSummary[];
  event_progress_percent: number;
  has_active_candidate: boolean;
  candidate_side: "yes" | "no" | null;
}
```

**Actual returns (`rest.py` ~L380–415):**
| Field | Actual Value | Match? |
|-------|-------------|--------|
| `event_ticker` | `ev.event_ticker` | ✅ |
| `market_count` | `ev.num_top_markets` | ✅ (semantically) |
| `live_market_count` | `ev.num_top_markets` | ⚠️ Same as `market_count`, no distinction |
| `total_resting_order_quantity` | `float(ev.total_volume)` | ⚠️ Uses `total_volume`, not actual resting qty |
| `active_orderbook_market_count` | `ev.num_top_markets` | ⚠️ Same as market_count |
| `top_markets` | see below | ⚠️ Different shape |
| `event_progress_percent` | `ev.top_markets[0].score * 100` (or `0.0`) | ⚠️ Uses score as proxy |
| `has_active_candidate` | `state.get_candidate(ev.event_ticker) is not None` | ✅ |
| `candidate_side` | `candidate.original_candidate.side` or `null` | ✅ |

#### `MarketSummary` in events list

| Field | Contract | Actual (`rest.py` ~L389–404) | Verdict |
|-------|----------|------------------------------|---------|
| `ticker` | `string` | `rm.market_ticker` | ✅ (key name matches) |
| `title` | `string` | `""` (always empty) | ⚠️ **Always empty string** — backend doesn't populate |
| `yes_bid` | `number \| null` | `_cents_to_dollars(rm.yes_price)` or `None` | ✅ (dollars) |
| `no_bid` | `number \| null` | `_cents_to_dollars(rm.no_price)` or `None` | ✅ (dollars) |
| `total_resting_order_quantity` | `number` | `float(max(rm.score, 0))` | ⚠️ **Not actual resting qty** — uses ranking score as proxy |
| `yes_order_quantity` | `number` | `0.0` | ⚠️ **Always 0** — backend doesn't have this data |
| `no_order_quantity` | `number` | `0.0` | ⚠️ **Always 0** — backend doesn't have this data |
| `volume_24h` | `number` | `float(rm.volume)` | ✅ |

**Decision:** Define `MarketSummary` matching actual backend output. The backend returns `yes_order_quantity` and `no_order_quantity` as `0` always — frontend must handle this. `title` is always `""`.

---

### 2.6 `EventDetail` — GET /api/v1/events/{event_ticker}

**This has the largest discrepancy.** The contract and actual are completely different shapes.

**Contract says:**
```typescript
interface EventDetail {
  event_ticker: string;
  market_count: number;
  same_day_live_market_count: number;
  total_event_resting_order_quantity: number;
  active_orderbook_market_count: number;
  event_progress_percent: number;
  threshold_percent: number;
  all_markets_ranked: MarketDetail[];
  active_candidate: ... | null;
}
```

**Actual returns (`rest.py` ~L420–430):**
```python
{
    "event_ticker": ev.event_ticker,
    "event_title": ev.event_title,
    "top_markets": [_serialize_ranked_market(rm) for rm in (ev.top_markets or [])],
    "total_volume": ev.total_volume,
    "num_top_markets": ev.num_top_markets,
    "candidate": candidate_info,  # from _serialize_candidate() or None
}
```

Where `_serialize_ranked_market` returns:
```python
{
    "market_ticker": rm.market_ticker,  # NOTE: uses "market_ticker" not "ticker"
    "volume": rm.volume,
    "spread_cents": rm.spread_cents,
    "yes_price_cents": rm.yes_price,
    "no_price_cents": rm.no_price,
    "yes_price": _cents_to_dollars(rm.yes_price),
    "no_price": _cents_to_dollars(rm.no_price),
    "rank": rm.rank,
    "score": rm.score,
}
```

And `_serialize_candidate` returns:
```python
{
    "event_ticker": oc.event_ticker,
    "market_ticker": oc.market_ticker,
    "side": oc.side,                    # "yes" | "no"
    "price_cents": oc.price,
    "price": _cents_to_dollars(oc.price),
    "confidence": oc.confidence,
    "volume": oc.volume,
    "progress_pct": oc.progress_pct,
    "is_valid": c.is_valid,
    "validation_errors": c.validation_errors,
    "risk_score": c.risk_score,
    "estimated_entry_price_cents": c.estimated_entry_price,
    "estimated_entry_price": _cents_to_dollars(c.estimated_entry_price),
    "estimated_exit_price_cents": c.estimated_exit_price,
    "estimated_exit_price": _cents_to_dollars(c.estimated_exit_price),
    "max_contracts": c.max_contracts,
}
```

**Key differences from contract:**
| Aspect | Contract | Actual |
|--------|----------|--------|
| Market list key | `all_markets_ranked` | `top_markets` |
| Market field names | `ticker`, `title`, `status`, `open_time`, `close_time`, etc. | `market_ticker`, `volume`, `spread_cents`, `yes_price_cents`, `no_price_cents`, `yes_price`, `no_price`, `rank`, `score` |
| Candidate shape | `ProgressBasedOrderCandidate`-like with `most_bet_side`, `should_create_order_candidate`, etc. | `ValidatedOrderCandidate`-like with `side`, `price_cents`, `confidence`, `is_valid`, `validation_errors`, etc. |
| Extra fields | — | `event_title`, `total_volume`, `num_top_markets` |
| Missing fields | `event_progress_percent`, `threshold_percent`, `market_count`, `same_day_live_market_count`, etc. | — |

**Decision:** Define `EventDetail` matching the **actual** response shape. The fields `event_progress_percent`, `threshold_percent`, `same_day_live_market_count` etc. from the contract are not available from this endpoint — they'd need to be computed client-side or added to the backend later.

---

### 2.7 `RankedMarket` — used in EventDetail

Define from actual `_serialize_ranked_market`:
```typescript
interface RankedMarket {
  market_ticker: string;
  volume: number;
  spread_cents: number;
  yes_price_cents: number;
  no_price_cents: number;
  yes_price: number;    // dollars
  no_price: number;     // dollars
  rank: number;
  score: number;
}
```

---

### 2.8 `ValidatedCandidate` — used in EventDetail and Candidates list

Define from actual `_serialize_candidate`:
```typescript
interface ValidatedCandidate {
  event_ticker: string;
  market_ticker: string;
  side: "yes" | "no";
  price_cents: number;
  price: number;                        // dollars
  confidence: number;
  volume: number;
  progress_pct: number;                 // 0–100
  is_valid: boolean;
  validation_errors: string[];
  risk_score: number;
  estimated_entry_price_cents: number;
  estimated_entry_price: number;         // dollars
  estimated_exit_price_cents: number;
  estimated_exit_price: number;           // dollars
  max_contracts: number;
}
```

---

### 2.9 GET /api/v1/events/{event_ticker}/orderbook

**Contract says:**
```typescript
interface OrderbookSnapshot {
  market_ticker: string;
  event_ticker: string;
  yes_bids: OrderbookLevel[];  // { price: number, size: number }
  no_bids: OrderbookLevel[];
  timestamp: string;
}
```

**Actual returns (`rest.py` ~L440–455):**
```python
{
    "market_ticker": market_ticker,
    "event_ticker": event_ticker,
    "yes_bids": [{"price": ..., "price_cents": ..., "count": ...}],
    "no_bids": [{"price": ..., "price_cents": ..., "count": ...}],
    "fetch_time": orderbook.fetch_time.isoformat() or None,
}
```

**Key differences:**
| Field | Contract | Actual |
|-------|----------|--------|
| `timestamp` | `string` | `fetch_time` (name differs) |
| `OrderbookLevel.size` | `number` | `count` (name differs) |
| Extra | — | `price_cents` per level |

**Decision:** Define `OrderbookLevel` with `price`, `price_cents`, `count`. Use `fetch_time` instead of `timestamp`.

---

### 2.10 `CandidateResponse` — GET /api/v1/candidates

**Contract says** (uses `CandidateResponse` with `selected_market_ticker`, `most_bet_side`, `should_create_order_candidate`, `requires_manual_review`, etc.):

**Actual returns (`rest.py` ~L462–470):** Same as `ValidatedCandidate` above — calls `_serialize_candidate(c)` directly.

**Decision:** The `/candidates` endpoint returns `ValidatedCandidate[]` (the same shape as the candidate field in `EventDetail`). **Ignore the contract's `CandidateResponse` shape entirely.**

---

### 2.11 `ApproveResult` — POST /api/v1/candidates/{event_ticker}/approve

**Contract says:**
```typescript
interface ApproveCandidateResult {
  candidate_id: string;
  approved: boolean;
  validation: ValidationResult;
  order_result: OrderResult | null;
}
```

**Actual returns (`rest.py` ~L485–510):**
```python
{
    "event_ticker": event_ticker,
    "market_ticker": exec_candidate.market_ticker,
    "side": exec_candidate.side,
    "price_cents": exec_candidate.price,
    "price": _cents_to_dollars(exec_candidate.price),
    "volume": exec_candidate.volume,
    "approved": True,
}
```

**Key differences:**
- Path uses `{event_ticker}` not `{id}` as contract states
- Response is simpler — just confirms what was approved
- No `candidate_id` (identifies by `event_ticker`)

**Decision:** Match actual response. Also note the path parameter is `event_ticker` not `id`.

---

### 2.12 `RejectResult` — POST /api/v1/candidates/{event_ticker}/reject

**Actual returns:** `ok(None)` — just `success: true, data: null`. No specific result type needed.

---

### 2.13 `TradeListResponse` — GET /api/v1/trades

**Contract says** returns `TradeRecord[]` directly.

**Actual returns (`rest.py` ~L530–570):**
```python
{
    "trades": [...],
    "total": total,
    "limit": limit,
    "offset": offset,
}
```

Each trade:
```python
{
    "trade_id": t.trade_id,
    "event_ticker": t.event_ticker,
    "market_ticker": t.market_ticker,
    "side": t.side,                           # "yes" | "no"
    "entry_price_cents": t.entry_price,
    "entry_price": _cents_to_dollars(t.entry_price),
    "exit_price_cents": t.exit_price,
    "exit_price": _cents_or_none(t.exit_price),
    "quantity": t.quantity,
    "entry_time": t.entry_time.isoformat() or None,
    "exit_time": t.exit_time.isoformat() or None,
    "pnl": t.pnl,
    "status": t.status,                       # "open" | "closed" | "cancelled"
    "mode": t.mode,                           # "dry_run" | "live" | "read_only"
    "error": t.error,
}
```

**Contract says:**
```typescript
interface TradeRecord {
  trade_id: string;
  event_ticker: string;
  market_ticker: string;
  side: "yes" | "no";
  price: number;
  size: number;
  mode: "dry_run" | "live";
  status: "filled" | "partial" | "failed";
  timestamp: string;
  validation_latency_ms: number;
}
```

**Major differences:**
| Field | Contract | Actual |
|-------|----------|--------|
| `price` | single field | split into `entry_price_cents`, `entry_price`, `exit_price_cents`, `exit_price` |
| `size` | `number` | `quantity` (name differs) |
| `timestamp` | single field | `entry_time`, `exit_time` |
| `status` | `filled | partial | failed` | `open | closed | cancelled` |
| Extra | — | `pnl`, `error`, `mode` (actual has it) |
| Extra | — | Pagination wrapper: `{ trades, total, limit, offset }` |

**Decision:** Define `TradeRecord` matching actual shape AND wrap in a paginated response.

---

### 2.14 `ScannerConfigResponse` — GET /api/v1/config

**Contract says:**
```typescript
interface ScannerConfigResponse {
  mode: string;
  strategy: { active_profile: string; profiles: Record<string, unknown> };
  threshold_percent: number;
  available_strategies: Array<{ name: string; description: string }>;
  kalshi_connected: boolean;
  has_credentials: boolean;
}
```

**Actual returns (`rest.py` ~L575–610):**
```python
{
    "mode": bot.mode,
    "strategy": {
        "name": bot.strategy.name if bot.strategy else None,
        "params": settings.strategy.params,
    },
    "available_strategies": list(EXPERIMENT_REGISTRY.keys()),  # just string[]!
    "threshold_percent": settings.scanner.default_threshold,
    "kalshi": {
        "connected": bot.kalshi_adapter is not None,
        "base_url": settings.kalshi.api_base_url,
        "rate_limit": settings.kalshi.rate_limit,
    },
    "scanner": {
        "min_markets_per_event": settings.scanner.min_markets_per_event,
        "min_volume_before_entry": settings.scanner.min_volume_before_entry,
        "min_side_signal_strength": settings.scanner.min_side_signal_strength,
        "poll_interval_seconds": settings.scanner.poll_interval_seconds,
    },
    "risk": {
        "max_position_size_per_market": settings.risk.max_position_size_per_market,
        "max_total_positions": settings.risk.max_total_positions,
        "max_daily_trades": settings.risk.max_daily_trades,
    },
}
```

**Key differences:**
| Aspect | Contract | Actual |
|--------|----------|--------|
| `strategy.active_profile` | `string` | `strategy.name` (different key) |
| `strategy.profiles` | `Record<string, unknown>` | `strategy.params` (different key, different shape) |
| `available_strategies` | `{name, description}[]` | `string[]` (just names, no descriptions) |
| `kalshi_connected` | top-level `boolean` | nested under `kalshi.connected` |
| `has_credentials` | top-level `boolean` | not directly exposed |
| Extra `kalshi.*` | — | `base_url`, `rate_limit` |
| Extra `scanner.*` | — | Sub-object with scanner params |
| Extra `risk.*` | — | Sub-object with risk limits |

**Decision:** Match actual response shape. The actual config endpoint is much richer than the contract specifies.

---

### 2.15 `SwitchModeResult` — POST /api/v1/mode

**Contract says:**
```typescript
interface SwitchModeResult {
  previous_mode: string;
  current_mode: string;
  switched_at: string;
  requires_auth: boolean;
  auth_configured: boolean;
}
```

**Actual returns (`rest.py` ~L620–640):**
```python
{
    "previous_mode": old_mode,
    "current_mode": body.mode,
    "switched_at": datetime.now(timezone.utc).isoformat(),
    "requires_auth": body.mode == "live" and not bot.settings.kalshi.private_key,
    "auth_configured": bool(bot.settings.kalshi.private_key),
}
```

**Verdict:** ✅ Perfect alignment!

---

### 2.16 Request Body Types

| Request | Contract | Actual | Match? |
|---------|----------|--------|--------|
| `StartScannerRequest` | `{mode?, strategy?, threshold_percent?}` | Same fields | ✅ |
| `ApproveCandidateRequest` | `{max_price?, size_override?}` | Same fields (max_price in dollars, size_override as int) | ✅ |
| `RejectCandidateRequest` | `{reason?}` | Same field | ✅ |
| `UpdateConfigRequest` | `{strategy?, threshold_percent?}` | Same fields | ✅ |
| `SwitchModeRequest` | `{mode, confirm?}` | Same fields | ✅ |

**Decision:** Match contract — all request bodies align well.

---

### 2.17 WebSocket Types

**Contract** defines detailed message types per channel with specific payload shapes.
**Actual (`websocket_handler.py`):** Implements basic WS accept + read + broadcast infrastructure. No specific message-type routing is implemented server-side.

| Channel | Contract Message Types | Actual Implementation |
|---------|----------------------|----------------------|
| `ws/scanner` | `scanner:started`, `scanner:stopped`, `scanner:mode_changed`, `scanner:status`, `scanner:error` | Accepts + handles `ping`/`pong`, broadcasts go through `manager.broadcast()` |
| `ws/events` | `event:discovered`, `event:updated`, `event:removed`, `event:orderbook_update`, `event:progress_updated` | Accepts + reads only, no specific message handling |
| `ws/candidates` | `candidate:created`, `candidate:approved`, `candidate:rejected`, `candidate:executed`, `candidate:expired` | Accepts + reads only |
| `ws/trades` | `trade:executed`, `trade:partial`, `trade:failed`, `trade:dry_run` | Accepts + reads only |

**Decision:** Define the `WSMessage<T>` envelope type as specified in the contract (it's already implemented in `errors.py` as a Pydantic model). The frontend `useWebSocket` hook from the build plan (Phase 8.1) is forward-looking — the actual server only supports the `ping`/`pong` interaction on the scanner channel. The frontend should be ready to consume all message types, but they won't be emitted until the backend live pollers are connected.

---

## 3. API Client Method Alignment

### 3.1 Methods vs. Endpoints

| # | Method | Path | Contract? | Actual? | Aligned Signature |
|---|--------|------|-----------|---------|-------------------|
| 1 | `getStatus()` | `GET /api/v1/scanner/status` | ✅ | ✅ | `() => Promise<ScannerStatus>` |
| 2 | `startScanner(req?)` | `POST /api/v1/scanner/start` | ✅ | ✅ | `(req?: StartScannerRequest) => Promise<StartResult>` |
| 3 | `stopScanner()` | `POST /api/v1/scanner/stop` | ✅ | ✅ | `() => Promise<StopResult>` |
| 4 | `getEvents(params?)` | `GET /api/v1/events` | ✅ | ✅ | `(params?: EventsQueryParams) => Promise<EventSummary[]>` |
| 5 | `getEvent(ticker)` | `GET /api/v1/events/{event_ticker}` | ✅ | ✅ | `(ticker: string) => Promise<EventDetail>` |
| 6 | `getOrderbook(eventTicker, marketTicker, maxLevels?)` | `GET /api/v1/events/{event_ticker}/orderbook` | ✅ | ✅ | `(eventTicker: string, marketTicker: string, maxLevels?: number) => Promise<OrderbookSnapshot>` |
| 7 | `getCandidates(status?, eventTicker?)` | `GET /api/v1/candidates` | ✅ | ✅ | `(status?: string, eventTicker?: string) => Promise<ValidatedCandidate[]>` |
| 8 | `approveCandidate(eventTicker, req?)` | `POST /api/v1/candidates/{event_ticker}/approve` | ⚠️ **Uses `{id}` in contract** | ✅ Uses `{event_ticker}` | `(eventTicker: string, req?: ApproveCandidateRequest) => Promise<ApproveResult>` |
| 9 | `rejectCandidate(eventTicker, req?)` | `POST /api/v1/candidates/{event_ticker}/reject` | ⚠️ **Uses `{id}` in contract** | ✅ Uses `{event_ticker}` | `(eventTicker: string, req?: RejectCandidateRequest) => Promise<void>` |
| 10 | `getTrades(mode?, limit?, offset?)` | `GET /api/v1/trades` | ✅ | ✅ | `(mode?: string, limit?: number, offset?: number) => Promise<TradeListResponse>` |
| 11 | `getConfig()` | `GET /api/v1/config` | ✅ | ✅ | `() => Promise<ScannerConfigResponse>` |
| 12 | `updateConfig(req)` | `PUT /api/v1/config` | ✅ | ✅ | `(req: UpdateConfigRequest) => Promise<ScannerConfigResponse>` |
| 13 | `switchMode(req)` | `POST /api/v1/mode` | ✅ | ✅ | `(req: SwitchModeRequest) => Promise<SwitchModeResult>` |

**Key finding:** The contract uses `{id}` for approve/reject paths, but the actual implementation uses `{event_ticker}`. **Use `{event_ticker}`.**

---

### 3.2 Build Plan API Client vs. Actual

The build plan's Phase 7.2 API client pseudocode lists 9 methods, missing:
- `stopScanner()`
- `getOrderbook()`
- `rejectCandidate()`
- `getTrades()`
- `switchMode()` (listed as `/mode` in contract but not in Phase 7.2 list)

The actual backend has 13 endpoints, all should be covered.

**Decision:** Implement all 13 methods.

---

## 4. Constants Alignment

The build plan mentions `frontend/src/lib/constants.ts`. Based on analysis:

```typescript
// Required constants:
export const API_BASE = "/api/v1";

export const SCANNER_MODES = {
  DRY_RUN: "dry_run",
  READ_ONLY: "read_only",
  LIVE: "live",
} as const;

export const CANDIDATE_SIDES = {
  YES: "yes",
  NO: "no",
  TIE: "tie",
  NONE: "none",
} as const;

export const TRADE_STATUSES = {
  OPEN: "open",
  CLOSED: "closed",
  CANCELLED: "cancelled",
} as const;

export const CANDIDATE_FILTERS = {
  ALL: "all",
  ACTIONABLE: "actionable",
  MANUAL_REVIEW: "manual_review",
} as const;

export const WS_CHANNELS = {
  SCANNER: "scanner",
  EVENTS: "events",
  CANDIDATES: "candidates",
  TRADES: "trades",
} as const;

export const DEFAULT_PAGE_SIZE = 50;
export const DEFAULT_ORDERBOOK_DEPTH = 10;
export const WS_RECONNECT_DELAY_MS = 3000;
```

---

## 5. Frontend API Client (`api.ts`) Specification

```typescript
class ScannerAPI {
  constructor(base?: string)         // defaults to "/api/v1"
  
  // Core
  async getStatus(): Promise<APIResponse<ScannerStatus>>
  async startScanner(req?: StartScannerRequest): Promise<APIResponse<StartResult>>
  async stopScanner(): Promise<APIResponse<StopResult>>
  
  // Events
  async getEvents(params?: EventsQueryParams): Promise<APIResponse<EventSummary[]>>
  async getEvent(ticker: string): Promise<APIResponse<EventDetail>>
  async getOrderbook(eventTicker: string, marketTicker: string, maxLevels?: number): Promise<APIResponse<OrderbookSnapshot>>
  
  // Candidates
  async getCandidates(status?: string, eventTicker?: string): Promise<APIResponse<ValidatedCandidate[]>>
  async approveCandidate(eventTicker: string, req?: ApproveCandidateRequest): Promise<APIResponse<ApproveResult>>
  async rejectCandidate(eventTicker: string, req?: RejectCandidateRequest): Promise<APIResponse<null>>
  
  // Trades
  async getTrades(mode?: string, limit?: number, offset?: number): Promise<APIResponse<TradeListResponse>>
  
  // Config
  async getConfig(): Promise<APIResponse<ScannerConfigResponse>>
  async updateConfig(req: UpdateConfigRequest): Promise<APIResponse<ScannerConfigResponse>>
  async switchMode(req: SwitchModeRequest): Promise<APIResponse<SwitchModeResult>>
}
```

---

## 6. Named Type Discrepancies — Summary Table

| Type | Contract Shape | Actual Backend Shape | Recommendation |
|------|---------------|---------------------|----------------|
| `MarketSummary` | `{ticker, title, yes_bid, no_bid, total_resting_order_quantity, yes_order_quantity, no_order_quantity, volume_24h}` | `{ticker, title: "", yes_bid, no_bid, total_resting_order_quantity: score_proxy, yes_order_quantity: 0, no_order_quantity: 0, volume_24h}` | Match actual; note `title` is always `""`. |
| `EventDetail` | Full market detail with `all_markets_ranked: MarketDetail[]`, `active_candidate`, `event_progress_percent`, etc. | `{event_ticker, event_title, top_markets: RankedMarket[], total_volume, num_top_markets, candidate: ValidatedCandidate\|null}` | **Match actual.** Completely different shape. |
| `RankedMarket` (non-contract type) | Not in contract | `{market_ticker, volume, spread_cents, yes_price_cents, no_price_cents, yes_price, no_price, rank, score}` | Define new type matching actual. |
| `CandidateResponse` | `{selected_market_ticker, selected_market_title, most_bet_side, event_passes_progress_threshold, should_create_order_candidate, requires_manual_review, ...}` | **Not used.** Actual returns `ValidatedCandidate` shape instead. | **Remove `CandidateResponse`.** Use `ValidatedCandidate`. |
| `ValidatedCandidate` (non-contract type) | Not in contract | `{event_ticker, market_ticker, side, price_cents, price, confidence, volume, progress_pct, is_valid, validation_errors, risk_score, estimated_entry_price_cents, estimated_entry_price, estimated_exit_price_cents, estimated_exit_price, max_contracts}` | Define new type matching actual. |
| `OrderbookLevel` | `{price: dollars, size: contracts}` | `{price: dollars, price_cents: cents, count: contracts}` | Match actual (add `price_cents`, use `count` not `size`). |
| `OrderbookSnapshot` | `{..., timestamp}` | `{..., fetch_time}` | Match actual (`fetch_time` not `timestamp`). |
| `TradeRecord` | `{price, size, timestamp, status: filled\|partial\|failed}` | `{entry_price, exit_price, entry_price_cents, exit_price_cents, quantity, entry_time, exit_time, status: open\|closed\|cancelled, pnl, error}` | **Match actual.** Completely different shape. |
| `TradeListResponse` (non-contract type) | Not in contract — returns `TradeRecord[]` directly | `{trades: TradeRecord[], total, limit, offset}` | Define paginated wrapper. |
| `ScannerConfigResponse` | `{strategy: {active_profile, profiles}, available_strategies: {name,description}[], kalshi_connected, has_credentials}` | `{strategy: {name, params}, available_strategies: string[], kalshi: {connected, base_url, rate_limit}, scanner: {...}, risk: {...}}` | **Match actual.** Richer structure. |
| `ApproveCandidateResult` | `{candidate_id, approved, validation, order_result}` | `{event_ticker, market_ticker, side, price_cents, price, volume, approved}` | Match actual. |

---

## 7. Implementation Checklist

### Step 1: Scaffold frontend project
- [ ] Run `bun create vite frontend --template react-ts`
- [ ] `cd frontend && bun add @tanstack/react-query tailwindcss`
- [ ] Verify `tsc --noEmit` passes with scaffold

### Step 2: Create `frontend/src/lib/types.ts`

**Enums & Literal Types:**
- [ ] `ScannerMode` — `"dry_run" | "read_only" | "live"`
- [ ] `CandidateSide` — `"yes" | "no" | "tie" | "none"`
- [ ] `TradeStatus` — `"open" | "closed" | "cancelled"`

**Envelope:**
- [ ] `APIError` — `{ code: string; message: string; details?: Record<string, unknown> }`
- [ ] `ResponseMeta` — `{ timestamp: string; duration_ms?: number }`
- [ ] `APIResponse<T>` — `{ success: boolean; data?: T; error?: APIError; meta?: ResponseMeta }`

**Scanner Status:**
- [ ] `ScannerStatus` — per Section 2.2 (match actual exactly)

**Scanner Control:**
- [ ] `StartScannerRequest` — `{ mode?: ScannerMode; strategy?: string; threshold_percent?: number }`
- [ ] `StartResult` — `{ scanner_id: string; started_at: string; events_processed: number; candidates_generated: number; trades_executed: number }`
- [ ] `StopResult` — `{ stopped_at: string; scan_duration_seconds: number; events_processed: number; candidates_generated: number }`

**Events:**
- [ ] `EventsQueryParams` — `{ min_progress?: number; has_candidate?: boolean; sort_by?: "progress" | "market_count" | "total_orders" }`
- [ ] `MarketSummary` — per Section 2.5 (match actual, with `title: string` but note it's always `""`)
- [ ] `EventSummary` — per Section 2.5
- [ ] `RankedMarket` — per Section 2.7
- [ ] `ValidatedCandidate` — per Section 2.8
- [ ] `EventDetail` — per Section 2.6 (match actual: `{ event_ticker, event_title, top_markets: RankedMarket[], total_volume: number, num_top_markets: number, candidate: ValidatedCandidate | null }`)
- [ ] `OrderbookLevel` — `{ price: number; price_cents: number; count: number }`
- [ ] `OrderbookSnapshot` — `{ market_ticker: string; event_ticker: string; yes_bids: OrderbookLevel[]; no_bids: OrderbookLevel[]; fetch_time: string | null }`

**Candidates:**
- [ ] `ApproveCandidateRequest` — `{ max_price?: number; size_override?: number }`
- [ ] `ApproveResult` — `{ event_ticker: string; market_ticker: string; side: string; price_cents: number; price: number; volume: number; approved: boolean }`
- [ ] `RejectCandidateRequest` — `{ reason?: string }`

**Trades:**
- [ ] `TradeRecord` — per Section 2.13 (match actual field names)
- [ ] `TradeListResponse` — `{ trades: TradeRecord[]; total: number; limit: number; offset: number }`

**Config:**
- [ ] `UpdateConfigRequest` — `{ strategy?: string; threshold_percent?: number }`
- [ ] `ScannerConfigResponse` — per Section 2.14 (match actual)
- [ ] `SwitchModeRequest` — `{ mode: ScannerMode; confirm?: boolean }`
- [ ] `SwitchModeResult` — `{ previous_mode: string; current_mode: string; switched_at: string; requires_auth: boolean; auth_configured: boolean }`

**WebSocket:**
- [ ] `WSMessage<T>` — `{ type: string; data: T; timestamp: string }`

### Step 3: Create `frontend/src/lib/constants.ts`
- [ ] `API_BASE`
- [ ] `SCANNER_MODES`, `CANDIDATE_SIDES`, `TRADE_STATUSES`, `CANDIDATE_FILTERS`
- [ ] `WS_CHANNELS`
- [ ] `DEFAULT_PAGE_SIZE`, `DEFAULT_ORDERBOOK_DEPTH`, `WS_RECONNECT_DELAY_MS`

### Step 4: Create `frontend/src/lib/api.ts`
- [ ] `ScannerAPI` class with constructor taking optional base URL
- [ ] Private `_fetch<T>(method, path, body?, params?)` helper
- [ ] `getStatus()` → `APIResponse<ScannerStatus>`
- [ ] `startScanner(req?)` → `APIResponse<StartResult>`
- [ ] `stopScanner()` → `APIResponse<StopResult>`
- [ ] `getEvents(params?)` → `APIResponse<EventSummary[]>`
- [ ] `getEvent(ticker)` → `APIResponse<EventDetail>`
- [ ] `getOrderbook(eventTicker, marketTicker, maxLevels?)` → `APIResponse<OrderbookSnapshot>`
- [ ] `getCandidates(status?, eventTicker?)` → `APIResponse<ValidatedCandidate[]>`
- [ ] `approveCandidate(eventTicker, req?)` → `APIResponse<ApproveResult>`
- [ ] `rejectCandidate(eventTicker, req?)` → `APIResponse<null>`
- [ ] `getTrades(mode?, limit?, offset?)` → `APIResponse<TradeListResponse>`
- [ ] `getConfig()` → `APIResponse<ScannerConfigResponse>`
- [ ] `updateConfig(req)` → `APIResponse<ScannerConfigResponse>`
- [ ] `switchMode(req)` → `APIResponse<SwitchModeResult>`

### Step 5: Verify
- [ ] `cd frontend && npx tsc --noEmit` passes with no errors

---

## 8. Open Issues / Follow-Ups

1. **`title` is always `""` in `MarketSummary`** — The backend's `EventWithTopMarkets` doesn't carry market titles into the `RankedMarket` model. Frontend will render empty titles. Consider enriching `RankedMarket` with a `title` field.

2. **`yes_order_quantity` / `no_order_quantity` are always `0`** — The backend doesn't expose side-specific order quantities. The ranking `score` is used as a proxy for `total_resting_order_quantity`. Consider adding real orderbook stats to the events list endpoint.

3. **`threshold_percent` not in `EventDetail`** — The actual endpoint doesn't return the threshold. The frontend will need to get it from config or hardcode a default.

4. **`event_progress_percent` not in actual `EventDetail`** — Only the candidate has `progress_pct`. The event detail itself doesn't expose progress.

5. **WebSocket message types are aspirational** — The actual WS handler only handles `ping`/`pong` on the scanner channel. All other WS message types are defined in the contract but never sent by the server. The frontend hook should be resilient to this.

6. **API contract should be updated** — Several response shapes differ significantly from the contract. Recommend updating `docs/api-contract.md` to match actual backend output after this alignment is settled.

7. **`_serialize_ranked_market` vs `top_markets` field name** — The event list endpoint uses `ticker` in `MarketSummary`, but the event detail endpoint uses `market_ticker` in `RankedMarket`. Consider standardizing to `market_ticker` everywhere (or `ticker` everywhere).
