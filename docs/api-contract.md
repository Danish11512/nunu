# API Contract — Backend ↔ Frontend

## Purpose

This document is the **binding contract** between the Python backend (FastAPI) and the TypeScript frontend (React/Vite). Both sides implement against this spec independently.

---

## Communication Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (Python/FastAPI)                      │
│                                                                      │
│  Port 8000                                                           │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │ REST API      │    │ WebSocket Server │    │ SSE Event Stream  │  │
│  │ /api/v1/*     │    │ /api/v1/ws/*     │    │ (future)          │  │
│  └──────┬───────┘    └────────┬─────────┘    └───────────────────┘  │
│         │                     │                                      │
└─────────┼─────────────────────┼──────────────────────────────────────┘
          │ HTTP/JSON           │ WebSocket
          ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (TypeScript/React)                   │
│                                                                      │
│  Port 5173                                                           │
│  ┌──────────────┐    ┌──────────────────┐                           │
│  │ REST Client   │    │ WebSocket Client │                           │
│  │ (Zustand API) │    │ (wsStore)        │                           │
│  └──────────────┘    └──────────────────┘                           │
│                                                                      │
│  State: Zustand (WS status) + TanStack React Query (REST data)         │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Frontend boots:
  1. GET /api/v1/config          → load saved settings
  2. GET /api/v1/scanner/status  → get current mode + state
  3. POST /api/v1/scanner/start  → begin scanning
  4. WS /api/v1/ws/events        → receive real-time event updates
  5. WS /api/v1/ws/candidates    → receive real-time candidates

User action:
  6. PUT /api/v1/config          → change threshold/strategy
  7. POST /api/v1/mode           → switch dry-run ↔ live
  8. POST /api/v1/candidates/{id}/approve → approve for trading

Polling fallback (if WS disconnects):
  9. GET /api/v1/events          → refresh event list
  10. GET /api/v1/candidates     → refresh candidates
```

---

## REST Endpoints

### Standard Response Envelope

Every response follows this shape:

```python
# Backend (Pydantic)
class APIResponse[T]:
    success: bool
    data: T | None = None
    error: APIError | None = None
    meta: ResponseMeta | None = None

class APIError:
    code: str          # Machine-readable: "MODE_NOT_LIVE", "RATE_LIMITED"
    message: str       # Human-readable: "Scanner is in read-only mode"
    details: dict | None = None

class ResponseMeta:
    timestamp: str     # ISO 8601
    duration_ms: float
```

```typescript
// Frontend (TypeScript)
interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: APIError;
  meta?: ResponseMeta;
}

interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

interface ResponseMeta {
  timestamp: string;
  duration_ms: number;
}
```

---

### GET /api/v1/scanner/status

Get current scanner state and operating mode.

**Response `data`:**

```python
# Backend produces:
class ScannerStatus:
    mode: str                    # "dry_run" | "read_only" | "live"
    is_running: bool
    connected_to_kalshi: bool
    uptime_seconds: float
    markets_tracked: int
    events_tracked: int
    active_candidates: int
    last_discovery: str | None   # ISO 8601
    last_progress_check: str | None
```

```typescript
// Frontend consumes:
interface ScannerStatus {
  mode: "dry_run" | "read_only" | "live";
  is_running: boolean;
  connected_to_kalshi: boolean;
  uptime_seconds: number;
  markets_tracked: number;
  events_tracked: number;
  active_candidates: number;
  last_discovery: string | null;
  last_progress_check: string | null;
}
```

**Example:**

```json
{
  "success": true,
  "data": {
    "mode": "dry_run",
    "is_running": true,
    "connected_to_kalshi": true,
    "uptime_seconds": 342.5,
    "markets_tracked": 847,
    "events_tracked": 12,
    "active_candidates": 3,
    "last_discovery": "2026-06-17T14:32:00-04:00",
    "last_progress_check": "2026-06-17T14:32:15-04:00"
  }
}
```

---

### POST /api/v1/scanner/start

Start the scanner (one-shot or live mode).

**Request:**

```python
class StartScannerRequest:
    mode: str = "live"           # "one-shot" | "live"
    strategy: str = "most-bet"   # from STRATEGY_REGISTRY keys
    threshold_percent: int = 65
```

```typescript
interface StartScannerRequest {
  mode?: "one-shot" | "live";
  strategy?: string;
  threshold_percent?: number;
}
```

**Response `data`:**

```python
class StartScannerResult:
    scanner_id: str
    started_at: str              # ISO 8601
```

---

### POST /api/v1/scanner/stop

Stop a running scanner.

**Response `data`:**

```python
class StopScannerResult:
    stopped_at: str
    scan_duration_seconds: float
    events_processed: int
    candidates_generated: int
```

---

### GET /api/v1/events

List all same-day live events with their top markets.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `min_progress` | float | 0 | Filter events with progress >= this % |
| `has_candidate` | bool | false | Only events with active candidates |
| `sort_by` | str | "total_orders" | "total_orders" \| "progress" \| "market_count" |

**Response `data`:**

```python
class EventSummary:
    event_ticker: str
    market_count: int
    live_market_count: int
    total_resting_order_quantity: float
    active_orderbook_market_count: int
    top_markets: list[MarketSummary]     # top 3
    event_progress_percent: float
    has_active_candidate: bool
    candidate_side: str | None           # "yes" | "no" | null

class MarketSummary:
    ticker: str
    title: str
    yes_bid: float | None
    no_bid: float | None
    total_resting_order_quantity: float
    yes_order_quantity: float
    no_order_quantity: float
    volume_24h: float
```

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

interface MarketSummary {
  ticker: string;
  title: string;
  yes_bid: number | null;
  no_bid: number | null;
  total_resting_order_quantity: number;
  yes_order_quantity: number;
  no_order_quantity: number;
  volume_24h: number;
}
```

**Example:**

```json
{
  "success": true,
  "data": [
    {
      "event_ticker": "EVTA",
      "market_count": 5,
      "live_market_count": 3,
      "total_resting_order_quantity": 250,
      "active_orderbook_market_count": 2,
      "top_markets": [
        {
          "ticker": "EVTA-M2",
          "title": "Will X happen?",
          "yes_bid": 0.65,
          "no_bid": 0.35,
          "total_resting_order_quantity": 150,
          "yes_order_quantity": 50,
          "no_order_quantity": 100,
          "volume_24h": 300
        }
      ],
      "event_progress_percent": 68.75,
      "has_active_candidate": true,
      "candidate_side": "no"
    }
  ]
}
```

---

### GET /api/v1/events/{event_ticker}

Get full detail for a single event.

**Response `data`:**

```python
class EventDetail:
    event_ticker: str
    event_title: str
    top_markets: list[RankedMarket]
    total_volume: float
    num_top_markets: int
    candidate: ValidatedOrderCandidate | None

class RankedMarket:
    market_ticker: str
    volume: int
    spread_cents: int
    yes_price_cents: int
    no_price_cents: int
    yes_price: float
    no_price: float
    rank: int
    score: float
```

```typescript
interface RankedMarket {
  market_ticker: string;
  volume: number;
  spread_cents: number;
  yes_price_cents: number;
  no_price_cents: number;
  yes_price: number;
  no_price: number;
  rank: number;
  score: number;
}

interface EventDetail {
  event_ticker: string;
  event_title: string;
  top_markets: RankedMarket[];
  total_volume: number;
  num_top_markets: number;
  candidate: CandidateResponse | null;
}
```

---

### GET /api/v1/events/{event_ticker}/orderbook

Get full orderbook for a specific market within an event.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `market_ticker` | str | required | Which market's orderbook |
| `max_levels` | int | 20 | Max depth levels per side |

**Response `data`:**

```python
class OrderbookSnapshot:
    market_ticker: str
    event_ticker: str
    yes_bids: list[OrderbookLevel]
    no_bids: list[OrderbookLevel]
    fetch_time: str | null

class OrderbookLevel:
    price: int       # cents
    price_cents: int # cents (same as price, for clarity)
    count: int       # contracts at this level
```

```typescript
interface OrderbookSnapshot {
  market_ticker: string;
  event_ticker: string;
  yes_bids: OrderbookLevel[];
  no_bids: OrderbookLevel[];
  fetch_time: string | null;
}

interface OrderbookLevel {
  price: number;
  price_cents: number;
  count: number;
}
```

---

### GET /api/v1/candidates

List all progress-based order candidates.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | str | "all" | "actionable" \| "manual_review" \| "all" |
| `event_ticker` | str | — | Filter by event |

**Response `data`:**

```python
# ValidatedOrderCandidate from backend/core/models/trading.py
class CandidateResponse:
    event_ticker: str
    market_ticker: str
    side: str                    # "yes" | "no"
    price_cents: int             # entry price in cents
    price: float                 # entry price in dollars
    confidence: float            # 0-1
    volume: int                  # estimated contract volume
    progress_pct: float          # 0-100
    is_valid: bool
    validation_errors: list[str]
    risk_score: float
    estimated_entry_price_cents: int
    estimated_entry_price: float
    estimated_exit_price_cents: int
    estimated_exit_price: float
    max_contracts: int
```

```typescript
interface CandidateResponse {
  event_ticker: string;
  market_ticker: string;
  side: string;
  price_cents: number;
  price: number;
  confidence: number;
  volume: number;
  progress_pct: number;
  is_valid: boolean;
  validation_errors: string[];
  risk_score: number;
  estimated_entry_price_cents: number;
  estimated_entry_price: number;
  estimated_exit_price_cents: number;
  estimated_exit_price: number;
  max_contracts: number;
}
```

---

### POST /api/v1/candidates/{id}/approve

Approve a candidate for trade execution (in live mode).

**Request:**

```python
class ApproveCandidateRequest:
    max_price: float | None = None    # Price limit for the order
    size_override: float | None = None  # Override estimated size
```

**Response `data`:**

```python
class ApproveCandidateResult:
    event_ticker: str
    market_ticker: str
    side: str
    price_cents: int
    price: float
    volume: int
    approved: bool
```

---

### POST /api/v1/candidates/{id}/reject

Reject a candidate.

**Request:**

```python
class RejectCandidateRequest:
    reason: str = ""    # Optional user-provided reason
```

---

### GET /api/v1/trades

Get trade history (real or dry-run simulated).

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | str | "all" | "real" \| "dry_run" \| "all" |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Pagination offset |

**Response `data`:**

The response wraps results in a paginated envelope:

```python
class TradesResponse:
    trades: list[TradeRecord]
    total: int
    limit: int
    offset: int

class TradeRecord:
    trade_id: str
    event_ticker: str
    market_ticker: str
    side: str                         # "yes" | "no"
    entry_price_cents: int
    entry_price: float
    exit_price_cents: int | None
    exit_price: float | None
    quantity: int
    entry_time: str | None            # ISO 8601
    exit_time: str | None             # ISO 8601
    pnl: float
    status: str                       # "open" | "closed" | "cancelled"
    mode: str                         # "dry_run" | "live" | "read_only"
    error: str
```

```typescript
interface TradesResponse {
  trades: TradeRecord[];
  total: number;
  limit: number;
  offset: number;
}

interface TradeRecord {
  trade_id: string;
  event_ticker: string;
  market_ticker: string;
  side: string;
  entry_price_cents: number;
  entry_price: number;
  exit_price_cents: number | null;
  exit_price: number | null;
  quantity: number;
  entry_time: string | null;
  exit_time: string | null;
  pnl: number;
  status: TradeStatus;
  mode: string;
  error: string;
}
```

---

### GET /api/v1/config

Get current scanner configuration.

**Response `data`:**

```python
class ScannerConfigResponse:
    mode: str                                               # "dry_run" | "read_only" | "live"
    strategy: StrategyConfig
    threshold_percent: int
    available_strategies: list[str]                         # strategy names only
    kalshi: KalshiConfig
    scanner: ScannerConfig
    risk: RiskConfig

class StrategyConfig:
    name: str | None
    params: dict

class KalshiConfig:
    connected: bool
    base_url: str
    rate_limit: int

class ScannerConfig:
    min_markets_per_event: int
    min_volume_before_entry: int
    min_side_signal_strength: float
    poll_interval_seconds: int

class RiskConfig:
    max_position_size_per_market: int
    max_total_positions: int
    max_daily_trades: int
```

```typescript
interface ScannerConfigResponse {
  mode: ScannerMode;
  strategy: {
    name: string | null;
    params: Record<string, unknown>;
  };
  threshold_percent: number;
  available_strategies: string[];
  kalshi: {
    connected: boolean;
    base_url: string;
    rate_limit: number;
  };
  scanner: {
    min_markets_per_event: number;
    min_volume_before_entry: number;
    min_side_signal_strength: number;
    poll_interval_seconds: number;
  };
  risk: {
    max_position_size_per_market: number;
    max_total_positions: number;
    max_daily_trades: number;
  };
}
```

---

### PUT /api/v1/config

Update scanner configuration.

**Request:**

```python
class UpdateConfigRequest:
    strategy: str | None = None       # Switch strategy profile
    threshold_percent: int | None = None  # Update progress threshold
```

```typescript
interface UpdateConfigRequest {
  strategy?: string;
  threshold_percent?: number;
}
```

---

### POST /api/v1/mode

Switch operating mode.

**Request:**

```python
class SwitchModeRequest:
    mode: str                         # "dry_run" | "live"
    confirm: bool = False             # Safety confirmation required
```

```typescript
interface SwitchModeRequest {
  mode: "dry_run" | "live";
  confirm?: boolean;
}
```

**Response `data`:**

```python
class SwitchModeResult:
    previous_mode: str
    current_mode: str
    switched_at: str
    requires_auth: bool              # true if switching to live without creds
    auth_configured: bool
```

---

## WebSocket Contract

### Connection

```
ws://localhost:5173/api/v1/ws/{channel}
```

In development, the Vite dev server proxies `/api` → `localhost:8000` with WebSocket passthrough (`ws: true`), so the frontend connects to the same origin as the page.

Where `{channel}` is one of: `scanner`, `events`, `candidates`, `trades`.

### Connection Architecture (App-level)

WebSocket connections are **established at app startup** by `initialize()` in `wsStore.ts` (called in `main.tsx`), not per-hook. The Zustand store manages:

- 4 persistent connections (`scanner`, `events`, `candidates`, `trades`)
- Automatic reconnection with 3s delay
- Ping/pong heartbeat every 30s
- Reactive `connectedChannels` state available via `useWSStore`

Hooks (`useWebSocket`) only register/unregister message listeners — they never open or close WebSocket connections. This prevents mount/unmount reconnect storms.

### Ping / Pong

The frontend sends `{"type": "ping"}` every 30 seconds on each open channel. The backend responds with `{"type": "pong"}`. Pong messages are silently dropped (not forwarded to listeners).

### Authentication

WebSocket connections do not require auth for read-only/dry-run modes. Live mode may require a token passed as a query param:

```
ws://localhost:5173/api/v1/ws/events?token=...
```

### Message Envelope

Every WebSocket message follows this shape:

```python
class WSMessage:
    type: str       # Message type (see below)
    data: any       # Payload
    timestamp: str  # ISO 8601
```

```typescript
interface WSMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
}
```

### Channel: `/api/v1/ws/scanner`

Broadcasts scanner-level state changes.

| Message Type | Payload | When |
|-------------|---------|------|
| `scanner:started` | `{ scanner_id, mode, started_at }` | Scanner begins |
| `scanner:stopped` | `{ scan_duration, events_processed, candidates_generated }` | Scanner stops |
| `scanner:mode_changed` | `{ previous_mode, current_mode }` | Mode switch |
| `scanner:status` | `ScannerStatus` (same as REST) | Periodic heartbeat (every 5s) |
| `scanner:error` | `{ code, message }` | Error event |

**Example:**

```json
{
  "type": "scanner:mode_changed",
  "data": {
    "previous_mode": "dry_run",
    "current_mode": "live"
  },
  "timestamp": "2026-06-17T14:32:15-04:00"
}
```

### Channel: `/api/v1/ws/events`

Broadcasts event-level updates in real time.

| Message Type | Payload | When |
|-------------|---------|------|
| `event:discovered` | `EventSummary` | New event found |
| `event:updated` | `EventSummary` | Event data changed (rerank, progress) |
| `event:removed` | `{ event_ticker }` | Event no longer same-day live |
| `event:orderbook_update` | `{ event_ticker, market_ticker, yes_bids[], no_bids[] }` | Partial orderbook update |
| `event:progress_updated` | `{ event_ticker, progress_percent, threshold_percent, passes_threshold }` | Progress recalculated |

**Example:**

```json
{
  "type": "event:progress_updated",
  "data": {
    "event_ticker": "EVTA",
    "progress_percent": 68.75,
    "threshold_percent": 65,
    "passes_threshold": true
  },
  "timestamp": "2026-06-17T14:32:15-04:00"
}
```

### Channel: `/api/v1/ws/candidates`

Broadcasts candidate creation and status changes.

| Message Type | Payload | When |
|-------------|---------|------|
| `candidate:created` | `CandidateResponse` | New candidate generated |
| `candidate:approved` | `{ candidate_id, event_ticker, market_ticker, side }` | User approved candidate |
| `candidate:rejected` | `{ candidate_id, reason }` | User rejected candidate |
| `candidate:executed` | `TradeRecord` | Candidate resulted in a trade |
| `candidate:expired` | `{ candidate_id, reason }` | Candidate became invalid |

**Example:**

```json
{
  "type": "candidate:created",
  "data": {
    "event_ticker": "EVTA",
    "market_ticker": "EVTA-M2",
    "side": "no",
    "price_cents": 65,
    "price": 0.65,
    "confidence": 0.82,
    "volume": 500,
    "progress_pct": 68.75,
    "is_valid": true,
    "validation_errors": [],
    "risk_score": 0.15,
    "estimated_entry_price_cents": 65,
    "estimated_entry_price": 0.65,
    "estimated_exit_price_cents": 55,
    "estimated_exit_price": 0.55,
    "max_contracts": 400
  },
  "timestamp": "2026-06-17T14:32:15-04:00"
}
```

### Channel: `/api/v1/ws/trades`

Broadcasts trade execution events.

| Message Type | Payload | When |
|-------------|---------|------|
| `trade:executed` | `TradeRecord` | Order filled |
| `trade:partial` | `TradeRecord` | Partial fill |
| `trade:failed` | `{ trade_id, reason }` | Order failed |
| `trade:dry_run` | `TradeRecord` | Simulated fill in dry-run |

---

## Error Contract

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Everything worked |
| 400 | Bad Request | Invalid params or body |
| 401 | Unauthorized | Missing/invalid auth (live mode) |
| 403 | Forbidden | Mode blocks the action (e.g., approve in read-only) |
| 429 | Rate Limited | Too many requests |
| 500 | Internal Error | Backend bug or Kalshi API failure |
| 503 | Service Unavailable | Kalshi API is down |

### Error Response Shape

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "MODE_NOT_LIVE",
    "message": "Cannot approve candidates in read-only mode. Switch to live mode first.",
    "details": {
      "current_mode": "read_only",
      "required_mode": "live"
    }
  }
}
```

### Error Codes

| Code | Meaning | HTTP Status |
|------|---------|-------------|
| `MODE_NOT_LIVE` | Action requires live mode | 403 |
| `MODE_READ_ONLY` | Action blocked in read-only | 403 |
| `CANDIDATE_NOT_ACTIONABLE` | Candidate failed validation | 400 |
| `CANDIDATE_EXPIRED` | Candidate too old | 400 |
| `MARKET_NOT_FOUND` | Ticker doesn't exist | 404 |
| `STRATEGY_NOT_FOUND` | Unknown strategy name | 400 |
| `RATE_LIMITED` | Kalshi API rate limit | 429 |
| `KALSHI_API_ERROR` | Kalshi API returned error | 502 |
| `AUTH_REQUIRED` | Credentials not configured | 401 |
| `VALIDATION_FAILED` | Pre-trade validation failed | 400 |

---

## TypeScript ↔ Python Type Alignment

### Shared Types

```python
# backend/core/models/market.py (Python — actual model)

@dataclass
class OrderbookLevel:
    price: int       # cents
    count: int       # contracts at this level

@dataclass
class MarketOrderbookStats:
    market_ticker: str           # NOT market_id
    event_ticker: str            # NOT event_id
    spread_cents: int | None = None
    yes_bid: int | None = None
    yes_ask: int | None = None
    no_bid: int | None = None
    no_ask: int | None = None
    last_price: int | None = None
    volume: int = 0
    open_interest: int = 0
```

```typescript
// frontend/src/lib/types.ts (TypeScript — must match backend)

interface OrderbookLevel {
  price: number;    // cents
  price_cents: number;
  count: number;    // contracts
}
```

> **IMPORTANT**: The backend uses `_ticker` suffix (event_ticker, market_ticker),
> NOT `_id` suffix. The frontend types must match. The `OrderCandidate` model
> from `backend/core/models/trading.py` uses: `event_ticker`, `market_ticker`,
> `side` ("yes"/"no"), `price` (int cents), `volume` (int contracts),
> `confidence` (float 0-1), `reason` (str), `progress_pct` (float 0-100).
```

### Field Mapping Rules

| Python | TypeScript | Notes |
|--------|------------|-------|
| `str | None` | `string \| null` | Optional fields use `null`, not `undefined` |
| `float` | `number` | Always emit, never omit |
| `int` | `number` | Always emit |
| `bool` | `boolean` | Always emit |
| `list[T]` | `T[]` | Always emit, even if empty |
| `dict[str, V]` | `Record<string, V>` | Always emit, even if empty |
| `datetime` | `string` (ISO 8601) | Always include timezone offset |
| `Enum` | union of string literals | Define both sides explicitly |

---

## Frontend API Client

```typescript
// frontend/src/lib/api.ts — Contract-aligned client

const BASE = "http://localhost:8000/api/v1";

class ScannerAPI {
  // Status
  async getStatus(): Promise<APIResponse<ScannerStatus>> { ... }
  async startScanner(req: StartScannerRequest): Promise<APIResponse<StartScannerResult>> { ... }
  async stopScanner(): Promise<APIResponse<StopScannerResult>> { ... }

  // Events
  async getEvents(params?: { min_progress?: number; has_candidate?: boolean; sort_by?: string }): Promise<APIResponse<EventSummary[]>> { ... }
  async getEvent(ticker: string): Promise<APIResponse<EventDetail>> { ... }
  async getOrderbook(eventTicker: string, marketTicker: string, maxLevels?: number): Promise<APIResponse<OrderbookSnapshot>> { ... }

  // Candidates
  async getCandidates(params?: { status?: string; event_ticker?: string }): Promise<APIResponse<CandidateResponse[]>> { ... }
  async approveCandidate(id: string, req?: ApproveCandidateRequest): Promise<APIResponse<ApproveCandidateResult>> { ... }
  async rejectCandidate(id: string, reason?: string): Promise<APIResponse<void>> { ... }

  // Trades
  async getTrades(params?: { mode?: string; limit?: number; offset?: number }): Promise<APIResponse<TradeRecord[]>> { ... }

  // Config
  async getConfig(): Promise<APIResponse<ScannerConfigResponse>> { ... }
  async updateConfig(req: UpdateConfigRequest): Promise<APIResponse<ScannerConfigResponse>> { ... }

  // Mode
  async switchMode(req: SwitchModeRequest): Promise<APIResponse<SwitchModeResult>> { ... }
}

// WebSocket hooks consume the WSMessage<T> envelope
type WSMessageHandler<T> = (msg: WSMessage<T>) => void;
```

---

## Rate Limiting

Backend enforces rate limits per frontend session:

| Limit | Window | Behavior |
|-------|--------|----------|
| 30 REST requests | 1 second | HTTP 429, retry-after header |
| 1 mode switch | 5 seconds | 429 if too frequent |
| 1 candidate approval | 2 seconds | 429 if too frequent |

Rate limit headers on all responses:

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 28
X-RateLimit-Reset: 1623948750
```

---

## Change Management

This contract is versioned. Both backend and frontend pin to a contract version:

```python
# Backend: in settings.py
API_CONTRACT_VERSION = "1.0.0"
```

```typescript
// Frontend: in constants.ts
export const API_CONTRACT_VERSION = "1.0.0";
```

Breaking changes (field removals, type changes) increment the major version. Additions (new fields, new endpoints) increment the minor version.
