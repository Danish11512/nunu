# Master Build Plan — Nunu Prediction Market Scanner

## Overview

This document defines the **exact order, dependencies, and pseudocode** for every file to build. Organized in 11 phases. Each phase lists files in dependency order.

### Dependency Graph

```
Phase 0: Scaffolding (dirs + configs)
    │
Phase 1: Core (models, interfaces, state)
    │
    ├──▶ Phase 2: Kalshi Adapter (client, types, ws)
    │           │
    │           └──▶ Phase 3: Engines (1→2→3→4→5→6→7→8 + live/)
    │                       │
    │                       ├──▶ Phase 4: Strategies (6 profiles + registry)
    │                       │
    │                       └──▶ Phase 5: Trading + Logging
    │                                   │
    │                                   └──▶ Phase 6: API Layer (FastAPI)
    │                                               │
    └───────────────────────────────────────────────┘
                                                    │
                                            Phase 7: Frontend Setup + Types
                                                    │
                                            Phase 8: Frontend Hooks
                                                    │
                                            Phase 9: Frontend Pages
                                                    │
                                            Phase 10: Frontend Components
                                                    │
                                            Phase 11: Integration + Docker
```

---

## Phase 0: Project Scaffolding

### Files to Create

```
backend/
  requirements.txt
  .env.example
  __init__.py

frontend/
  package.json
  vite.config.ts
  tsconfig.json
  tsconfig.node.json
  index.html
  postcss.config.js
  tailwind.config.js
  src/
    styles/
      globals.css
    vite-env.d.ts

config/
  settings.yaml

docker-compose.yml
.gitignore
```

### 0.1 — `backend/requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
httpx==0.27.0
websockets==12.0
pydantic==2.7.4
pydantic-settings==2.3.4
python-dotenv==1.0.1
pyyaml==6.0.1
python-dateutil==2.9.0
```

### 0.2 — `backend/.env.example`

```
# Kalshi API
KALSHI_API_BASE_URL=https://external-api.kalshi.com/trade-api/v2
KALSHI_PRIVATE_KEY=
KALSHI_FUNDER_ADDRESS=

# Scanner
SCANNER_DEFAULT_MODE=dry_run
SCANNER_DEFAULT_THRESHOLD=65
SCANNER_DEFAULT_STRATEGY=most-bet

# Logging
LOG_LEVEL=INFO
CSV_LOG_PATH=logs/scanner.csv
TRADE_HISTORY_PATH=logs/trades.json
```

### 0.3 — `backend/config/settings.yaml`

```yaml
kalshi:
  base_url: "https://external-api.kalshi.com/trade-api/v2"
  rate_limit: 10  # requests per second

scanner:
  default_mode: dry_run         # dry_run | read_only | live
  default_threshold: 65
  default_strategy: most-bet
  discovery_poll_interval: 30   # seconds
  progress_gate_interval: 10    # seconds
  max_candidate_age: 30         # seconds

strategy:
  active_profile: most-bet
  profiles:
    most-bet: {}
    highest-volume: {}
    widest-spread: {}
    deepest-book: {}
    momentum-shift:
      lookback_seconds: 300
    custom-threshold:
      per_event_type:
        default: 65
        sports: 50
        politics: 75

validation:
  max_price_movement_percent: 10.0
  max_spread_width: 0.05
  min_liquidity: 100.0
  allow_partial_fill: true

risk:
  max_exposure_per_market: 1000.0
  max_total_exposure: 5000.0
  max_positions: 10
  daily_loss_limit: 500.0

logging:
  level: INFO
  csv_path: "logs/scanner.csv"
  trade_history_path: "logs/trades.json"
```

### 0.4 — `frontend/package.json`

```json
{
  "name": "nunu-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "recharts": "^2.12.7"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.39",
    "tailwindcss": "^3.4.6",
    "typescript": "^5.5.3",
    "vite": "^5.4.0"
  }
}
```

### 0.5 — `frontend/vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## Phase 1: Backend Core

### Files (in creation order)

```
backend/core/models.py
backend/core/interfaces.py
backend/core/scanner_state.py
backend/config/settings.py
backend/config/defaults.py
```

### 1.1 — `backend/core/models.py`

All shared dataclasses. Every other module imports from here.

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Market:
    """A single Kalshi market (tradable binary outcome)."""
    ticker: str                    # Primary ID, e.g. "EVTA-M1"
    event_ticker: str              # Parent event ID, e.g. "EVTA"
    status: str                    # "open" | "closed" | "settled" | "unopened"
    title: str                     # Human-readable question
    open_time: str                 # ISO 8601
    close_time: str                # ISO 8601
    expected_expiration_time: Optional[str] = None
    latest_expiration_time: Optional[str] = None
    yes_bid: Optional[str] = None
    yes_ask: Optional[str] = None
    no_bid: Optional[str] = None
    no_ask: Optional[str] = None
    volume_24h: Optional[str] = None
    total_volume: Optional[str] = None
    category: Optional[str] = None
    series_ticker: Optional[str] = None

@dataclass
class OrderbookLevel:
    """Single price level in an orderbook."""
    price: float     # In dollars
    size: float      # Quantity at this level

@dataclass
class Orderbook:
    """Resting bids for YES and NO outcomes."""
    market_id: str
    yes_bids: list[OrderbookLevel] = field(default_factory=list)
    no_bids: list[OrderbookLevel] = field(default_factory=list)

@dataclass
class MarketClassification:
    """Result of same-day-live classification for one market."""
    ticker: str
    event_ticker: str
    live_now: bool
    expected_to_resolve_today: bool
    latest_expiration_today: bool
    same_day_live_market: bool
    reasons: list[str] = field(default_factory=list)

@dataclass
class MarketOrderbookStats:
    """Derived statistics from an orderbook."""
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
class ClassifiedEvent:
    """Event with its same-day-live child markets."""
    event_ticker: str
    market_count: int
    same_day_live_market_count: int
    same_day_live_markets: list[tuple[Market, MarketClassification]] = field(default_factory=list)

@dataclass
class RankedMarket:
    """Market with classification and orderbook stats, ready for ranking."""
    market: Market
    classification: MarketClassification
    orderbook_stats: MarketOrderbookStats

@dataclass
class EventWithTopMarkets:
    """Ranked event with top 3 markets + full ranked list."""
    event_ticker: str
    market_count: int
    same_day_live_market_count: int
    total_event_resting_order_quantity: float
    active_orderbook_market_count: int
    top_3_markets_by_current_orders: list[RankedMarket] = field(default_factory=list)
    all_same_day_live_markets_ranked: list[RankedMarket] = field(default_factory=list)

@dataclass
class OrderCandidate:
    """A potential trade, produced by Engine 6."""
    event_id: str
    market_id: str
    side: str                      # "yes" | "no" | "tie" | "none"
    estimated_price: float
    estimated_size: float
    progress_percent: float
    threshold_percent: float
    confidence: str                # "high" | "medium" | "low"
    requires_manual_review: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def is_actionable(self) -> bool:
        return self.side in ("yes", "no") and not self.requires_manual_review

@dataclass
class ProgressBasedOrderCandidate:
    """Full candidate from Engine 6 with all context."""
    event_ticker: str
    threshold_percent: int
    event_progress_percent: float
    event_passes_progress_threshold: bool
    selected_market: Optional[Market] = None
    selected_market_stats: Optional[MarketOrderbookStats] = None
    most_bet_side: str = "none"
    yes_order_quantity: float = 0.0
    no_order_quantity: float = 0.0
    total_resting_order_quantity: float = 0.0
    should_create_order_candidate: bool = False
    requires_manual_review: bool = False
    reasons: list[str] = field(default_factory=list)

@dataclass
class ValidatedOrderCandidate:
    """A candidate that passed pre-trade validation."""
    candidate: ProgressBasedOrderCandidate
    validation_timestamp: str
    validation_latency_ms: float
    can_trade: bool
    reason: Optional[str] = None
    latest_market: Optional[Market] = None
    latest_orderbook: Optional[Orderbook] = None
    latest_stats: Optional[MarketOrderbookStats] = None
    confirmed_side: Optional[str] = None

@dataclass
class TradeRecord:
    """A record of an executed trade (real or dry-run)."""
    trade_id: str
    event_ticker: str
    market_ticker: str
    side: str                      # "yes" | "no"
    price: float
    size: float
    mode: str                      # "dry_run" | "live"
    status: str                    # "filled" | "partial" | "failed"
    timestamp: str
    validation_latency_ms: float
    error: Optional[str] = None

@dataclass
class ValidationConfig:
    max_price_movement_percent: float = 10.0
    max_spread_width: float = 0.05
    min_liquidity: float = 100.0
    max_candidate_age_seconds: float = 30.0
    allow_partial_fill: bool = True

@dataclass
class RiskConfig:
    max_exposure_per_market: float = 1000.0
    max_total_exposure: float = 5000.0
    max_positions: int = 10
    daily_loss_limit: float = 500.0
```

### 1.2 — `backend/core/interfaces.py`

Abstract contracts. Strategy profiles and adapter interface.

```python
from abc import ABC, abstractmethod
from typing import Optional

from .models import (
    Market, Orderbook, OrderCandidate, ValidatedOrderCandidate,
    RankedMarket, MarketOrderbookStats, OrderbookLevel,
)

class StrategyProfile(ABC):
    """Plug-in strategy for market/side selection."""
    name: str = ""
    description: str = ""
    config: dict = {}

    def __init__(self, config: dict = None):
        self.config = config or {}

    @abstractmethod
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        """Pick the best market from the ranked list."""
        ...

    @abstractmethod
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        """Pick "yes" | "no" | "tie" | "none"."""
        ...

class LiveConnection(ABC):
    """WebSocket connection for live updates."""
    @abstractmethod
    async def on_orderbook_update(self, callback) -> None: ...
    @abstractmethod
    async def on_market_update(self, callback) -> None: ...
    @abstractmethod
    async def close(self) -> None: ...
```

### 1.3 — `backend/core/scanner_state.py`

Central runtime state for the live scanner.

```python
from dataclasses import dataclass, field
from typing import Optional
from .models import (
    Market, ClassifiedEvent, EventWithTopMarkets,
    ProgressBasedOrderCandidate, MarketOrderbookStats,
)

@dataclass
class ScannerState:
    markets_by_ticker: dict[str, Market] = field(default_factory=dict)
    events: dict[str, ClassifiedEvent] = field(default_factory=dict)
    orderbook_stats: dict[str, MarketOrderbookStats] = field(default_factory=dict)
    ranked_events: dict[str, EventWithTopMarkets] = field(default_factory=dict)
    candidates: dict[str, ProgressBasedOrderCandidate] = field(default_factory=dict)
    last_discovery: Optional[str] = None
    last_progress_check: Optional[str] = None
    is_running: bool = False

    def get_event(self, ticker: str) -> Optional[EventWithTopMarkets]:
        return self.ranked_events.get(ticker)

    def get_candidate(self, event_ticker: str) -> Optional[ProgressBasedOrderCandidate]:
        return self.candidates.get(event_ticker)

    def update_event(self, event: EventWithTopMarkets):
        self.ranked_events[event.event_ticker] = event

    def remove_event(self, event_ticker: str):
        self.ranked_events.pop(event_ticker, None)
        self.candidates.pop(event_ticker, None)

    def set_candidate(self, event_ticker: str, candidate: ProgressBasedOrderCandidate):
        self.candidates[event_ticker] = candidate
```

### 1.4 — `backend/config/settings.py`

Pydantic-settings loader.

```python
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Optional
import yaml
from pathlib import Path

class KalshiConfig(BaseModel):
    base_url: str = "https://external-api.kalshi.com/trade-api/v2"
    rate_limit: int = 10

class ScannerConfig(BaseModel):
    default_mode: str = "dry_run"
    default_threshold: int = 65
    default_strategy: str = "most-bet"
    discovery_poll_interval: int = 30
    progress_gate_interval: int = 10
    max_candidate_age: int = 30

class ValidationConfig(BaseModel):
    max_price_movement_percent: float = 10.0
    max_spread_width: float = 0.05
    min_liquidity: float = 100.0
    allow_partial_fill: bool = True

class RiskConfig(BaseModel):
    max_exposure_per_market: float = 1000.0
    max_total_exposure: float = 5000.0
    max_positions: int = 10
    daily_loss_limit: float = 500.0

class LoggingConfig(BaseModel):
    level: str = "INFO"
    csv_path: str = "logs/scanner.csv"
    trade_history_path: str = "logs/trades.json"

class Settings(BaseSettings):
    kalshi: KalshiConfig = KalshiConfig()
    scanner: ScannerConfig = ScannerConfig()
    validation: ValidationConfig = ValidationConfig()
    risk: RiskConfig = RiskConfig()
    logging: LoggingConfig = LoggingConfig()

    kalshi_private_key: Optional[str] = None
    kalshi_funder_address: Optional[str] = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

def load_settings(config_path: str = "config/settings.yaml") -> Settings:
    """Load settings from YAML + env overrides."""
    settings = Settings()
    yaml_path = Path(config_path)
    if yaml_path.exists():
        with open(yaml_path) as f:
            yaml_config = yaml.safe_load(f) or {}
        if "kalshi" in yaml_config:
            settings.kalshi = KalshiConfig(**yaml_config["kalshi"])
        if "scanner" in yaml_config:
            settings.scanner = ScannerConfig(**yaml_config["scanner"])
        if "validation" in yaml_config:
            settings.validation = ValidationConfig(**yaml_config["validation"])
        if "risk" in yaml_config:
            settings.risk = RiskConfig(**yaml_config["risk"])
        if "logging" in yaml_config:
            settings.logging = LoggingConfig(**yaml_config["logging"])
    return settings
```

---

## Phase 2: Kalshi Adapter

### Files (in creation order)

```
backend/adapters/kalshi/types.py
backend/adapters/kalshi/client.py
backend/adapters/kalshi/websocket.py
backend/adapters/kalshi/adapter.py
```

### 2.1 — `backend/adapters/kalshi/types.py`

Maps raw Kalshi API JSON to core models.

```python
from backend.core.models import Market, Orderbook, OrderbookLevel

def parse_market(raw: dict) -> Market:
    """Convert Kalshi API market JSON to core Market."""
    return Market(
        ticker=raw.get("ticker", ""),
        event_ticker=raw.get("event_ticker", ""),
        status=raw.get("status", ""),
        title=raw.get("title", ""),
        open_time=raw.get("open_time", ""),
        close_time=raw.get("close_time", ""),
        expected_expiration_time=raw.get("expected_expiration_time"),
        latest_expiration_time=raw.get("latest_expiration_time"),
        yes_bid=raw.get("yes_bid"),
        yes_ask=raw.get("yes_ask"),
        no_bid=raw.get("no_bid"),
        no_ask=raw.get("no_ask"),
        volume_24h=raw.get("volume_24h"),
        total_volume=raw.get("volume"),
        category=raw.get("category"),
        series_ticker=raw.get("series_ticker"),
    )

def parse_orderbook(raw: dict, ticker: str) -> Orderbook:
    """Convert Kalshi orderbook JSON to core Orderbook.
    
    Kalshi format: orderbook_fp.yes_dollars = [["0.65", "1000"], ...]
    Each inner tuple is [price_dollars, count_fp].
    """
    ob_fp = raw.get("orderbook_fp", {})
    yes_raw = ob_fp.get("yes_dollars", [])
    no_raw = ob_fp.get("no_dollars", [])

    def parse_levels(levels: list) -> list[OrderbookLevel]:
        return [
            OrderbookLevel(price=float(p), size=float(c))
            for p, c in levels if p and c
        ]

    return Orderbook(
        market_id=ticker,
        yes_bids=parse_levels(yes_raw),
        no_bids=parse_levels(no_raw),
    )

def calculate_orderbook_stats(market: Market, orderbook: Orderbook) -> MarketOrderbookStats:
    """Derive stats from orderbook data."""
    yes_qty = sum(level.size for level in orderbook.yes_bids)
    no_qty = sum(level.size for level in orderbook.no_bids)
    
    return MarketOrderbookStats(
        market_id=market.ticker,
        event_id=market.event_ticker,
        total_resting_order_quantity=yes_qty + no_qty,
        yes_order_quantity=yes_qty,
        no_order_quantity=no_qty,
        depth_level_count=len(orderbook.yes_bids) + len(orderbook.no_bids),
        best_yes_bid=orderbook.yes_bids[0].price if orderbook.yes_bids else None,
        best_no_bid=orderbook.no_bids[0].price if orderbook.no_bids else None,
        volume_24h=float(market.volume_24h or 0),
        total_volume=float(market.total_volume or 0),
    )
```

### 2.2 — `backend/adapters/kalshi/client.py`

HTTP client for all Kalshi REST endpoints.

Key design:
- Uses `httpx.AsyncClient` with connection pooling
- Cursor-based pagination for market list
- Exponential backoff on rate limits (429)
- All methods return parsed Python dicts (raw JSON → caller parses)

```python
import httpx
import asyncio
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

class KalshiClient:
    """Async HTTP client for Kalshi REST API."""
    
    BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
    
    def __init__(self, base_url: str = None, api_key: str = None, rate_limit: int = 10):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(rate_limit)
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with'.")
        return self._client
    
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Rate-limited request with error handling."""
        async with self._semaphore:
            url = f"{self.base_url}{path}"
            headers = kwargs.pop("headers", {})
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            for attempt in range(3):
                try:
                    response = await self.client.request(method, url, headers=headers, **kwargs)
                    
                    if response.status_code == 429:
                        wait = 2 ** attempt
                        logger.warning(f"Rate limited. Retrying in {wait}s.")
                        await asyncio.sleep(wait)
                        continue
                    
                    response.raise_for_status()
                    return response.json()
                
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1)
                
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500 and attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
            
            raise RuntimeError("Request failed after 3 retries.")
    
    async def list_markets(self, status: str = "open", limit: int = 1000, cursor: str = None) -> dict:
        """GET /markets"""
        params = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/markets", params=params)
    
    async def get_market(self, ticker: str) -> Optional[dict]:
        """GET /markets/{ticker}"""
        try:
            return await self._request("GET", f"/markets/{ticker}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_orderbook(self, ticker: str) -> dict:
        """GET /markets/{ticker}/orderbook"""
        return await self._request("GET", f"/markets/{ticker}/orderbook")
    
    async def place_order(self, ticker: str, side: str, price: float, size: float) -> dict:
        """POST /orders — requires authentication."""
        if not self.api_key:
            raise RuntimeError("API key required to place orders.")
        payload = {
            "ticker": ticker,
            "side": side.upper(),   # Kalshi uses "BUY" / "SELL"
            "type": "limit",
            "price": str(price),
            "count": str(int(size)),
        }
        return await self._request("POST", "/orders", json=payload)
    
    async def fetch_all_open_markets(self) -> list[dict]:
        """Paginate through all open markets, deduplicate by ticker."""
        all_markets: list[dict] = []
        cursor: Optional[str] = None
        
        while True:
            data = await self.list_markets(cursor=cursor)
            all_markets.extend(data.get("markets", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        
        # Deduplicate
        seen: set[str] = set()
        unique: list[dict] = []
        for m in all_markets:
            ticker = m.get("ticker")
            if ticker not in seen:
                seen.add(ticker)
                unique.append(m)
        
        return unique
```

### 2.3 — `backend/adapters/kalshi/websocket.py`

WebSocket client for real-time orderbook updates.

```python
import json
import asyncio
import logging
from typing import Optional, Callable, Awaitable
import websockets

logger = logging.getLogger(__name__)

class KalshiWebSocket:
    """WebSocket client for Kalshi real-time updates."""
    
    def __init__(self, url: str = "wss://..."):  # Kalshi WS URL TBD
        self.url = url
        self._ws = None
        self._running = False
        self._callbacks: list[Callable] = []
        self._subscribed_tickers: list[str] = []
    
    def on_message(self, callback: Callable[[dict], Awaitable[None]]):
        self._callbacks.append(callback)
    
    async def connect(self):
        self._ws = await websockets.connect(self.url)
        logger.info("WebSocket connected")
    
    async def subscribe(self, tickers: list[str]):
        self._subscribed_tickers = tickers
        message = {
            "type": "subscribe",
            "channel": "market",
            "markets": tickers,
        }
        await self._ws.send(json.dumps(message))
    
    async def listen(self):
        self._running = True
        while self._running:
            try:
                raw = await self._ws.recv()
                data = json.loads(raw)
                for cb in self._callbacks:
                    await cb(data)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WS disconnected. Reconnecting...")
                await asyncio.sleep(5)
                await self.connect()
                if self._subscribed_tickers:
                    await self.subscribe(self._subscribed_tickers)
    
    async def close(self):
        self._running = False
        if self._ws:
            await self._ws.close()
```

### 2.4 — `backend/adapters/kalshi/adapter.py`

High-level adapter wrapping client + types.

```python
from backend.core.models import Market, Orderbook, MarketOrderbookStats
from .client import KalshiClient
from .types import parse_market, parse_orderbook, calculate_orderbook_stats

class KalshiAdapter:
    """High-level interface to Kalshi, used by engines."""
    
    def __init__(self, client: KalshiClient):
        self.client = client
    
    async def get_all_open_markets(self) -> list[Market]:
        raw_markets = await self.client.fetch_all_open_markets()
        return [parse_market(m) for m in raw_markets]
    
    async def get_market(self, ticker: str) -> Optional[Market]:
        raw = await self.client.get_market(ticker)
        return parse_market(raw) if raw else None
    
    async def get_orderbook(self, ticker: str) -> Orderbook:
        raw = await self.client.get_orderbook(ticker)
        return parse_orderbook(raw, ticker)
    
    async def get_market_with_orderbook(self, ticker: str) -> tuple[Optional[Market], Optional[Orderbook]]:
        market = await self.get_market(ticker)
        if not market:
            return None, None
        orderbook = await self.get_orderbook(ticker)
        return market, orderbook
    
    async def get_orderbook_stats(self, ticker: str) -> Optional[MarketOrderbookStats]:
        market = await self.get_market(ticker)
        if not market:
            return None
        orderbook = await self.get_orderbook(ticker)
        return calculate_orderbook_stats(market, orderbook)
    
    async def place_order(self, ticker: str, side: str, price: float, size: float) -> dict:
        return await self.client.place_order(ticker, side, price, size)
```

---

## Phase 3: Engines

### File ordering (strict dependency order)

```
backend/engines/engine1_discovery.py      # No engine deps
backend/engines/engine2_classification.py # No engine deps (uses core + zoneinfo)
backend/engines/engine3_grouping.py       # Uses engine2 output types
backend/engines/engine4_orderbook.py      # Uses adapter + core
backend/engines/engine5_ranking.py        # Uses core models
backend/engines/engine6_progress_gate.py  # Uses engine2, strategies
backend/engines/engine7_validation.py     # Uses engine2, engine5, strategies
backend/engines/engine8_orchestrator.py   # Uses every engine above
backend/engines/live/                     # Live update modules
```

### 3.1 — `backend/engines/engine1_discovery.py`

```python
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.models import Market

async def fetch_all_open_markets(adapter: KalshiAdapter) -> list[Market]:
    """
    Engine 1: Fetch all currently open markets from Kalshi.
    
    Delegates to KalshiAdapter which handles pagination + dedup.
    This engine is intentionally thin — the adapter owns HTTP concerns.
    
    Returns:
        Deduplicated list of all open Markets.
    
    Error handling:
        - Propagates adapter errors (network, auth, rate limit)
        - Returns empty list on total failure (never None)
    """
    try:
        markets = await adapter.get_all_open_markets()
        return markets
    except Exception as e:
        logger.error(f"Engine 1 failed: {e}")
        return []
```

### 3.2 — `backend/engines/engine2_classification.py`

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from backend.core.models import Market, MarketClassification

ET = ZoneInfo("America/New_York")

def day_key_et(date: datetime) -> str:
    """YYYY-MM-DD in America/New_York."""
    return date.astimezone(ET).strftime("%Y-%m-%d")

def same_et_day(a: datetime, b: datetime) -> bool:
    return day_key_et(a) == day_key_et(b)

def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None

def classify_market(market: Market, now: Optional[datetime] = None) -> MarketClassification:
    """
    Engine 2: Classify a single market as same-day-live or not.
    
    SAME_DAY_LIVE_MARKET iff:
      - status == "open"
      - open_time <= now
      - close_time > now
      - expected_expiration_time is today in America/New_York
      - latest_expiration_time is today in America/New_York
    
    Returns MarketClassification with reasons for failure.
    """
    if now is None:
        now = datetime.now(ET)
    
    reasons: list[str] = []
    
    open_time = parse_date(market.open_time)
    close_time = parse_date(market.close_time)
    expected_exp = parse_date(market.expected_expiration_time)
    latest_exp = parse_date(market.latest_expiration_time)
    
    # Rule 1: Currently open
    live_now = (
        market.status == "open"
        and open_time is not None
        and close_time is not None
        and open_time <= now
        and close_time > now
    )
    if not live_now:
        reasons.append("Market not currently open.")
    
    # Rule 2: Expected expiration is today ET
    expected_today = (expected_exp is not None and same_et_day(expected_exp, now))
    if not expected_today:
        reasons.append("expected_expiration_time is not today ET.")
    
    # Rule 3: Latest expiration is today ET
    latest_today = (latest_exp is not None and same_et_day(latest_exp, now))
    if not latest_today:
        reasons.append("latest_expiration_time is not today ET.")
    
    return MarketClassification(
        ticker=market.ticker,
        event_ticker=market.event_ticker,
        live_now=live_now,
        expected_to_resolve_today=expected_today,
        latest_expiration_today=latest_today,
        same_day_live_market=(live_now and expected_today and latest_today),
        reasons=reasons,
    )

def get_same_day_live_markets(
    markets: list[Market],
    now: Optional[datetime] = None,
) -> tuple[list[tuple[Market, MarketClassification]], list[tuple[Market, MarketClassification]]]:
    """
    Classify all markets. Returns (all_classified, same_day_live_only).
    Second list is a subset of the first.
    """
    if now is None:
        now = datetime.now(ET)
    
    all_classified: list[tuple[Market, MarketClassification]] = []
    live: list[tuple[Market, MarketClassification]] = []
    
    for market in markets:
        classification = classify_market(market, now)
        all_classified.append((market, classification))
        if classification.same_day_live_market:
            live.append((market, classification))
    
    return all_classified, live
```

### 3.3 — `backend/engines/engine3_grouping.py`

```python
from backend.core.models import Market, MarketClassification, ClassifiedEvent

def group_by_event_ticker(
    same_day_live_markets: list[tuple[Market, MarketClassification]]
) -> list[ClassifiedEvent]:
    """
    Engine 3: Group same-day-live markets by event_ticker.
    
    An event qualifies if ANY child market passes SAME_DAY_LIVE_MARKET.
    Events are sorted by event_ticker for deterministic output.
    """
    by_event: dict[str, list[tuple[Market, MarketClassification]]] = {}
    
    for market, classification in same_day_live_markets:
        ticker = market.event_ticker
        if ticker not in by_event:
            by_event[ticker] = []
        by_event[ticker].append((market, classification))
    
    events = [
        ClassifiedEvent(
            event_ticker=ticker,
            market_count=len(markets),
            same_day_live_market_count=len(markets),
            same_day_live_markets=markets,
        )
        for ticker, markets in by_event.items()
    ]
    
    events.sort(key=lambda e: e.event_ticker)
    return events
```

### 3.4 — `backend/engines/engine4_orderbook.py`

```python
import asyncio
import logging
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.models import (
    ClassifiedEvent, Orderbook, Market, MarketClassification,
)

logger = logging.getLogger(__name__)

async def fetch_orderbooks(
    events: list[ClassifiedEvent],
    adapter: KalshiAdapter,
    concurrency: int = 10,
) -> list[tuple[ClassifiedEvent, dict[str, Orderbook]]]:
    """
    Engine 4: Fetch orderbooks for all same-day-live markets.
    
    Returns events paired with their orderbooks keyed by ticker.
    Markets with no orderbook data still get an empty Orderbook.
    Uses bounded concurrency to respect rate limits.
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def fetch_one(ticker: str) -> tuple[str, Orderbook]:
        async with semaphore:
            try:
                ob = await adapter.get_orderbook(ticker)
                return ticker, ob
            except Exception as e:
                logger.warning(f"Orderbook fetch failed for {ticker}: {e}")
                return ticker, Orderbook(market_id=ticker)
    
    result: list[tuple[ClassifiedEvent, dict[str, Orderbook]]] = []
    
    for event in events:
        tickers = [m.ticker for m, _ in event.same_day_live_markets]
        tasks = [fetch_one(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        orderbooks = dict(results)
        result.append((event, orderbooks))
    
    return result
```

### 3.5 — `backend/engines/engine5_ranking.py`

```python
from backend.core.models import (
    ClassifiedEvent, Orderbook, Market, MarketClassification,
    MarketOrderbookStats, RankedMarket, EventWithTopMarkets,
)
from backend.adapters.kalshi.types import calculate_orderbook_stats

def rank_event_markets(
    event: ClassifiedEvent,
    orderbooks: dict[str, Orderbook],
) -> EventWithTopMarkets:
    """
    Engine 5: Rank markets inside an event by resting order activity.
    
    Sort order:
      1. total_resting_order_quantity DESC
      2. depth_level_count DESC
      3. volume_24h DESC
      4. total_volume DESC
    
    Returns EventWithTopMarkets with top 3 + full ranked list.
    """
    ranked: list[RankedMarket] = []
    
    for market, classification in event.same_day_live_markets:
        ob = orderbooks.get(market.ticker, Orderbook(market_id=market.ticker))
        stats = calculate_orderbook_stats(market, ob)
        ranked.append(RankedMarket(
            market=market,
            classification=classification,
            orderbook_stats=stats,
        ))
    
    ranked.sort(
        key=lambda r: (
            r.orderbook_stats.total_resting_order_quantity,
            r.orderbook_stats.depth_level_count,
            r.orderbook_stats.volume_24h,
            r.orderbook_stats.total_volume,
        ),
        reverse=True,
    )
    
    return EventWithTopMarkets(
        event_ticker=event.event_ticker,
        market_count=event.market_count,
        same_day_live_market_count=event.same_day_live_market_count,
        total_event_resting_order_quantity=sum(
            r.orderbook_stats.total_resting_order_quantity for r in ranked
        ),
        active_orderbook_market_count=sum(
            1 for r in ranked if r.orderbook_stats.total_resting_order_quantity > 0
        ),
        top_3_markets_by_current_orders=ranked[:3],
        all_same_day_live_markets_ranked=ranked,
    )

def rank_all_events(
    event_books: list[tuple[ClassifiedEvent, dict[str, Orderbook]]]
) -> list[EventWithTopMarkets]:
    """Run ranking across all events."""
    return [rank_event_markets(e, ob) for e, ob in event_books]
```

### 3.6 — `backend/engines/engine6_progress_gate.py`

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from backend.core.models import (
    EventWithTopMarkets, Market, ProgressBasedOrderCandidate,
    MarketOrderbookStats,
)
from backend.core.interfaces import StrategyProfile
from backend.engines.engine2_classification import classify_market, parse_date

ET = ZoneInfo("America/New_York")

def get_end_time(market: Market) -> Optional[datetime]:
    return (
        parse_date(market.expected_expiration_time)
        or parse_date(market.latest_expiration_time)
        or parse_date(market.close_time)
    )

def calculate_progress(market: Market, now: datetime) -> float:
    """
    Calculate event progress as percentage of time elapsed.
    Returns 0–100, clamped.
    """
    start = parse_date(market.open_time)
    end = get_end_time(market)
    
    if not start or not end:
        return 0.0
    
    total_ms = (end - start).total_seconds() * 1000
    elapsed_ms = (now - start).total_seconds() * 1000
    
    if total_ms <= 0:
        return 100.0
    
    return max(0.0, min(100.0, (elapsed_ms / total_ms) * 100))

def create_candidate(
    event: EventWithTopMarkets,
    strategy: StrategyProfile,
    threshold_percent: int,
    now: Optional[datetime] = None,
) -> ProgressBasedOrderCandidate:
    """
    Engine 6: Create order candidate if event passes threshold.
    
    1. Strategy selects market from ranked list
    2. Calculate event progress
    3. Re-classify market as same-day-live
    4. Strategy selects side (YES/NO)
    5. Return candidate with creation decision
    """
    if now is None:
        now = datetime.now(ET)
    
    reasons: list[str] = []
    
    selected = strategy.select_market(event.all_same_day_live_markets_ranked)
    if not selected:
        return ProgressBasedOrderCandidate(
            event_ticker=event.event_ticker,
            threshold_percent=threshold_percent,
            event_progress_percent=0,
            event_passes_progress_threshold=False,
            should_create_order_candidate=False,
            reasons=["No market selected by strategy."],
        )
    
    market = selected.market
    stats = selected.orderbook_stats
    
    progress = calculate_progress(market, now)
    passes = progress >= threshold_percent
    
    if not passes:
        reasons.append(f"Progress {progress:.1f}% < threshold {threshold_percent}%.")
    
    classification = classify_market(market, now)
    still_live = classification.same_day_live_market
    if not still_live:
        reasons.append("Market no longer same-day live.")
    
    has_orders = stats.total_resting_order_quantity > 0
    if not has_orders:
        reasons.append("Market has zero resting order quantity.")
    
    side = strategy.select_side(selected, stats)
    if side == "tie":
        reasons.append("YES/NO tied.")
    elif side == "none":
        reasons.append("No order activity.")
    
    should_create = passes and still_live and has_orders and side in ("yes", "no")
    
    return ProgressBasedOrderCandidate(
        event_ticker=event.event_ticker,
        threshold_percent=threshold_percent,
        event_progress_percent=progress,
        event_passes_progress_threshold=passes,
        selected_market=market,
        selected_market_stats=stats,
        most_bet_side=side,
        yes_order_quantity=stats.yes_order_quantity,
        no_order_quantity=stats.no_order_quantity,
        total_resting_order_quantity=stats.total_resting_order_quantity,
        should_create_order_candidate=should_create,
        requires_manual_review=(side == "tie"),
        reasons=reasons,
    )

def process_all_events(
    events: list[EventWithTopMarkets],
    strategy: StrategyProfile,
    threshold_percent: int = 65,
    now: Optional[datetime] = None,
) -> tuple[list[ProgressBasedOrderCandidate], list[ProgressBasedOrderCandidate], list[ProgressBasedOrderCandidate]]:
    """
    Run Engine 6 across all events.
    Returns (all_candidates, actionable, manual_review).
    """
    if now is None:
        now = datetime.now(ET)
    
    candidates = [
        create_candidate(e, strategy, threshold_percent, now)
        for e in events
    ]
    
    actionable = [c for c in candidates if c.should_create_order_candidate]
    manual = [c for c in candidates if c.requires_manual_review]
    
    return candidates, actionable, manual
```

### 3.7 — `backend/engines/engine7_validation.py`

```python
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.models import (
    ProgressBasedOrderCandidate, ValidatedOrderCandidate, ValidationConfig,
)
from backend.core.interfaces import StrategyProfile
from backend.engines.engine2_classification import classify_market
from backend.adapters.kalshi.types import calculate_orderbook_stats

ET = ZoneInfo("America/New_York")

async def validate_candidate(
    candidate: ProgressBasedOrderCandidate,
    adapter: KalshiAdapter,
    strategy: StrategyProfile,
    config: ValidationConfig,
    now: Optional[datetime] = None,
) -> ValidatedOrderCandidate:
    """
    Engine 7: Pre-trade validation.
    
    Steps:
    1. Re-fetch market
    2. Re-classify same-day-live
    3. Re-fetch orderbook
    4. Recalculate stats
    5. Recalculate side
    6. Check price movement
    7. Check liquidity
    
    Returns ValidatedOrderCandidate with can_trade decision.
    """
    if now is None:
        now = datetime.now(ET)
    
    if not candidate.should_create_order_candidate or not candidate.selected_market:
        return ValidatedOrderCandidate(
            candidate=candidate,
            validation_timestamp=now.isoformat(),
            validation_latency_ms=0,
            can_trade=False,
            reason="Candidate not actionable.",
        )
    
    start = time.monotonic()
    ticker = candidate.selected_market.ticker
    
    # Re-fetch market
    market = await adapter.get_market(ticker)
    if not market:
        return ValidatedOrderCandidate(
            candidate=candidate,
            validation_timestamp=now.isoformat(),
            validation_latency_ms=(time.monotonic() - start) * 1000,
            can_trade=False,
            reason=f"Market {ticker} not found.",
        )
    
    # Re-classify
    classification = classify_market(market, now)
    if not classification.same_day_live_market:
        return ValidatedOrderCandidate(
            candidate=candidate,
            validation_timestamp=now.isoformat(),
            validation_latency_ms=(time.monotonic() - start) * 1000,
            can_trade=False,
            reason="Market no longer same-day live.",
        )
    
    # Re-fetch orderbook
    orderbook = await adapter.get_orderbook(ticker)
    stats = calculate_orderbook_stats(market, orderbook)
    
    # Recalculate side
    from backend.engines.engine5_ranking import RankedMarket
    ranked = RankedMarket(market=market, classification=classification, orderbook_stats=stats)
    current_side = strategy.select_side(ranked, stats)
    
    if current_side != candidate.most_bet_side:
        return ValidatedOrderCandidate(
            candidate=candidate,
            validation_timestamp=now.isoformat(),
            validation_latency_ms=(time.monotonic() - start) * 1000,
            can_trade=False,
            reason=f"Side changed: {candidate.most_bet_side} → {current_side}.",
        )
    
    # Check price movement
    if candidate.selected_market_stats and candidate.selected_market_stats.best_yes_bid:
        orig = candidate.selected_market_stats.best_yes_bid
        curr = stats.best_yes_bid or 0
        if orig > 0:
            movement = abs(curr - orig) / orig * 100
            if movement > config.max_price_movement_percent:
                return ValidatedOrderCandidate(
                    candidate=candidate,
                    validation_timestamp=now.isoformat(),
                    validation_latency_ms=(time.monotonic() - start) * 1000,
                    can_trade=False,
                    reason=f"Price moved {movement:.1f}%.",
                )
    
    # Check liquidity
    if stats.total_resting_order_quantity < config.min_liquidity:
        return ValidatedOrderCandidate(
            candidate=candidate,
            validation_timestamp=now.isoformat(),
            validation_latency_ms=(time.monotonic() - start) * 1000,
            can_trade=False,
            reason=f"Insufficient liquidity: {stats.total_resting_order_quantity:.0f}.",
        )
    
    latency = (time.monotonic() - start) * 1000
    
    return ValidatedOrderCandidate(
        candidate=candidate,
        validation_timestamp=now.isoformat(),
        validation_latency_ms=latency,
        can_trade=True,
        latest_market=market,
        latest_orderbook=orderbook,
        latest_stats=stats,
        confirmed_side=current_side,
    )
```

### 3.8 — `backend/engines/engine8_orchestrator.py`

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import logging

from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.models import (
    EventWithTopMarkets, ProgressBasedOrderCandidate,
    ValidatedOrderCandidate, ValidationConfig,
)
from backend.core.interfaces import StrategyProfile
from backend.engines.engine1_discovery import fetch_all_open_markets
from backend.engines.engine2_classification import get_same_day_live_markets
from backend.engines.engine3_grouping import group_by_event_ticker
from backend.engines.engine4_orderbook import fetch_orderbooks
from backend.engines.engine5_ranking import rank_all_events
from backend.engines.engine6_progress_gate import process_all_events
from backend.engines.engine7_validation import validate_candidate

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

class ScannerResult:
    """Result of a full scanner run."""
    def __init__(self):
        self.scanned_market_count: int = 0
        self.events: list[EventWithTopMarkets] = []
        self.candidates: list[ProgressBasedOrderCandidate] = []
        self.actionable: list[ProgressBasedOrderCandidate] = []
        self.manual_review: list[ProgressBasedOrderCandidate] = []
        self.validated: list[ValidatedOrderCandidate] = []
        self.timestamp: str = ""
        self.errors: list[str] = []

async def run_one_shot(
    adapter: KalshiAdapter,
    strategy: StrategyProfile,
    threshold_percent: int = 65,
    mode: str = "dry_run",
    now: Optional[datetime] = None,
) -> ScannerResult:
    """
    Engine 8: Run all engines once and return results.
    
    Pipeline: E1 → E2 → E3 → E4 → E5 → E6 → E7
    """
    if now is None:
        now = datetime.now(ET)
    
    result = ScannerResult()
    result.timestamp = now.isoformat()
    
    # E1
    markets = await fetch_all_open_markets(adapter)
    result.scanned_market_count = len(markets)
    logger.info(f"E1: Found {len(markets)} open markets.")
    
    if not markets:
        return result
    
    # E2
    _, live = get_same_day_live_markets(markets, now)
    logger.info(f"E2: {len(live)} same-day-live markets.")
    
    if not live:
        return result
    
    # E3
    events = group_by_event_ticker(live)
    logger.info(f"E3: {len(events)} same-day-live events.")
    
    # E4
    event_books = await fetch_orderbooks(events, adapter)
    logger.info("E4: Orderbooks fetched.")
    
    # E5
    ranked_events = rank_all_events(event_books)
    result.events = ranked_events
    logger.info("E5: Events ranked.")
    
    # E6
    candidates, actionable, manual = process_all_events(
        ranked_events, strategy, threshold_percent, now,
    )
    result.candidates = candidates
    result.actionable = actionable
    result.manual_review = manual
    logger.info(f"E6: {len(actionable)} actionable, {len(manual)} manual review.")
    
    # E7 (only for actionable candidates in dry_run or live mode)
    if mode != "read_only":
        for candidate in actionable:
            validated = await validate_candidate(
                candidate, adapter, strategy,
                ValidationConfig(), now,
            )
            result.validated.append(validated)
        logger.info(f"E7: {len(result.validated)} validated.")
    
    return result
```

### 3.9 — Live update modules (`backend/engines/live/`)

These are poller/updater classes for the live scanner loop. Each runs as an asyncio task.

```python
# backend/engines/live/discovery_poller.py
# Periodically re-runs E1→E2→E3, diffs with previous state, triggers rerank

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, Awaitable

from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.scanner_state import ScannerState
from backend.engines.engine1_discovery import fetch_all_open_markets
from backend.engines.engine2_classification import get_same_day_live_markets
from backend.engines.engine3_grouping import group_by_event_ticker

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

class DiscoveryPoller:
    """Periodically re-discovers markets and updates state."""
    
    def __init__(self, adapter: KalshiAdapter, state: ScannerState, interval: int = 30):
        self.adapter = adapter
        self.state = state
        self.interval = interval
        self.on_new_events: list[Callable[[list], Awaitable[None]]] = []
    
    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                now = datetime.now(ET)
                markets = await fetch_all_open_markets(self.adapter)
                _, live = get_same_day_live_markets(markets, now)
                events = group_by_event_ticker(live)
                
                # Diff with current state
                current_tickers = set(self.state.events.keys())
                new_tickers = {e.event_ticker for e in events}
                
                added = new_tickers - current_tickers
                removed = current_tickers - new_tickers
                
                for t in removed:
                    self.state.remove_event(t)
                
                for callback in self.on_new_events:
                    await callback([e for e in events if e.event_ticker in added])
                
                # Update state
                self.state.events = {e.event_ticker: e for e in events}
                self.state.last_discovery = now.isoformat()
                
                logger.info(f"Discovery: {len(live)} live markets, {len(events)} events. +{len(added)} -{len(removed)}")
            
            except Exception as e:
                logger.error(f"Discovery poller error: {e}")
            
            await asyncio.sleep(self.interval)
```

```python
# backend/engines/live/event_reranker.py
# Re-ranks a single event when its markets change

from backend.core.models import ClassifiedEvent, Orderbook, EventWithTopMarkets
from backend.engines.engine5_ranking import rank_event_markets

def rerank_event(event: ClassifiedEvent, orderbooks: dict[str, Orderbook]) -> EventWithTopMarkets:
    """Re-rank a single event when its orderbooks change."""
    return rank_event_markets(event, orderbooks)
```

```python
# backend/engines/live/progress_gate_loop.py
# Periodically re-runs Engine 6 for all ranked events

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from backend.core.interfaces import StrategyProfile
from backend.engines.engine6_progress_gate import create_candidate

ET = ZoneInfo("America/New_York")

class ProgressGateLoop:
    def __init__(self, state, strategy: StrategyProfile, threshold: int = 65, interval: int = 10):
        self.state = state
        self.strategy = strategy
        self.threshold = threshold
        self.interval = interval
        self.on_new_candidate = None  # callback
    
    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                now = datetime.now(ET)
                for event in self.state.ranked_events.values():
                    candidate = create_candidate(event, self.strategy, self.threshold, now)
                    self.state.set_candidate(event.event_ticker, candidate)
                    
                    if candidate.should_create_order_candidate and self.on_new_candidate:
                        await self.on_new_candidate(candidate)
                
                self.state.last_progress_check = now.isoformat()
            
            except Exception as e:
                logger.error(f"Progress gate error: {e}")
            
            await asyncio.sleep(self.interval)
```

---

## Phase 4: Strategies

### 4.1 — `backend/strategies/base.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from backend.core.models import RankedMarket, MarketOrderbookStats

class StrategyProfile(ABC):
    name: str = ""
    description: str = ""
    config: dict = {}
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    @abstractmethod
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        ...
    
    @abstractmethod
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        ...
```

### 4.2 — `backend/strategies/most_bet.py`

```python
from typing import Optional
from backend.core.models import RankedMarket, MarketOrderbookStats
from .base import StrategyProfile

class MostBetStrategy(StrategyProfile):
    name = "most-bet"
    description = "Highest resting order quantity → side with more orders"
    
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        return ranked_markets[0] if ranked_markets else None
    
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

### 4.3 — `backend/strategies/highest_volume.py`

```python
from typing import Optional
from backend.core.models import RankedMarket, MarketOrderbookStats
from .base import StrategyProfile

class HighestVolumeStrategy(StrategyProfile):
    name = "highest-volume"
    description = "Highest 24h volume → most-traded side"
    
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        if not ranked_markets:
            return None
        return max(ranked_markets, key=lambda r: r.orderbook_stats.volume_24h)
    
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

### 4.4 — `backend/strategies/widest_spread.py`

```python
from typing import Optional
from backend.core.models import RankedMarket, MarketOrderbookStats
from .base import StrategyProfile

class WidestSpreadStrategy(StrategyProfile):
    name = "widest-spread"
    description = "Widest YES/NO price gap → bet the cheaper side (contrarian)"
    
    def _spread(self, stats: MarketOrderbookStats) -> float:
        y = stats.best_yes_bid or 0
        n = stats.best_no_bid or 0
        return abs(y - n)
    
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        if not ranked_markets:
            return None
        return max(ranked_markets, key=lambda r: self._spread(r.orderbook_stats))
    
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        yes_bid = stats.best_yes_bid or 0
        no_bid = stats.best_no_bid or 0
        if yes_bid == 0 and no_bid == 0:
            return "none"
        if yes_bid < no_bid:
            return "yes"   # YES is cheaper
        elif no_bid < yes_bid:
            return "no"    # NO is cheaper
        return "tie"
```

### 4.5 — `backend/strategies/deepest_book.py`

```python
from typing import Optional
from backend.core.models import RankedMarket, MarketOrderbookStats
from .base import StrategyProfile

class DeepestBookStrategy(StrategyProfile):
    name = "deepest-book"
    description = "Highest depth level count → deeper side"
    
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        if not ranked_markets:
            return None
        return max(ranked_markets, key=lambda r: r.orderbook_stats.depth_level_count)
    
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

### 4.6 — `backend/strategies/momentum_shift.py`

```python
import time
from typing import Optional
from backend.core.models import RankedMarket, MarketOrderbookStats
from .base import StrategyProfile

class MomentumShiftStrategy(StrategyProfile):
    """
    Tracks historical snapshots of YES/NO bid ratios.
    Selects market with biggest recent ratio change.
    Bets with the momentum.
    """
    name = "momentum-shift"
    description = "Biggest recent bid ratio change → momentum side"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.lookback = self.config.get("lookback_seconds", 300)
        self.history: dict[str, list[tuple[float, float, float]]] = {}  # market_id → [(timestamp, yes_qty, no_qty)]
    
    def record_snapshot(self, market_id: str, yes_qty: float, no_qty: float):
        now = time.time()
        if market_id not in self.history:
            self.history[market_id] = []
        self.history[market_id].append((now, yes_qty, no_qty))
        # Prune old
        cutoff = now - self.lookback
        self.history[market_id] = [e for e in self.history[market_id] if e[0] >= cutoff]
    
    def _momentum(self, market_id: str, current_yes: float, current_no: float) -> float:
        if market_id not in self.history or len(self.history[market_id]) < 2:
            return 0.0
        oldest = self.history[market_id][0]
        _, old_yes, old_no = oldest
        old_total = old_yes + old_no
        cur_total = current_yes + current_no
        if old_total == 0 or cur_total == 0:
            return 0.0
        return (current_yes / cur_total) - (old_yes / old_total)
    
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        if not ranked_markets:
            return None
        scored = [(abs(self._momentum(r.market.ticker, r.orderbook_stats.yes_order_quantity, r.orderbook_stats.no_order_quantity)), r) for r in ranked_markets]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        score = self._momentum(market.market.ticker, stats.yes_order_quantity, stats.no_order_quantity)
        if score > 0.01:
            return "yes"
        elif score < -0.01:
            return "no"
        # Fallback to most-bet
        if stats.yes_order_quantity > stats.no_order_quantity:
            return "yes"
        elif stats.no_order_quantity > stats.yes_order_quantity:
            return "no"
        elif stats.total_resting_order_quantity > 0:
            return "tie"
        return "none"
```

### 4.7 — `backend/strategies/custom_threshold.py`

```python
from typing import Optional
from backend.core.models import RankedMarket, MarketOrderbookStats
from .most_bet import MostBetStrategy

class CustomThresholdStrategy(MostBetStrategy):
    """
    Same market/side selection as most-bet, but with per-event-type
    progress thresholds. The threshold lookup is used by Engine 6.
    """
    name = "custom-threshold"
    description = "Most-bet logic with per-event-type progress thresholds"
    
    def get_threshold_for_event(self, event_type: str) -> int:
        return self.config.get("per_event_type", {}).get(event_type, self.config.get("per_event_type", {}).get("default", 65))
```

### 4.8 — `backend/strategies/__init__.py`

```python
from .base import StrategyProfile
from .most_bet import MostBetStrategy
from .highest_volume import HighestVolumeStrategy
from .widest_spread import WidestSpreadStrategy
from .deepest_book import DeepestBookStrategy
from .momentum_shift import MomentumShiftStrategy
from .custom_threshold import CustomThresholdStrategy

STRATEGY_REGISTRY: dict[str, type[StrategyProfile]] = {
    "most-bet": MostBetStrategy,
    "highest-volume": HighestVolumeStrategy,
    "widest-spread": WidestSpreadStrategy,
    "deepest-book": DeepestBookStrategy,
    "momentum-shift": MomentumShiftStrategy,
    "custom-threshold": CustomThresholdStrategy,
}

def get_strategy(name: str, config: dict = None) -> StrategyProfile:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    cls = STRATEGY_REGISTRY[name]
    return cls(config or {})
```

---

## Phase 5: Trading + Logging

### 5.1 — `backend/trading/trade_executor.py`

```python
from typing import Optional
from backend.core.models import (
    ProgressBasedOrderCandidate, ValidatedOrderCandidate,
    TradeRecord, ValidationConfig,
)
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.interfaces import StrategyProfile
from backend.engines.engine7_validation import validate_candidate

class TradeExecutor:
    """
    Mode-aware trade executor.
    
    - dry_run: validates then returns simulated TradeRecord
    - read_only: never places, always returns error
    - live: validates then calls Kalshi API
    """
    
    def __init__(self, adapter: KalshiAdapter, strategy: StrategyProfile, mode: str = "dry_run"):
        self.adapter = adapter
        self.strategy = strategy
        self.mode = mode
        self.config = ValidationConfig()
    
    async def execute(self, candidate: ProgressBasedOrderCandidate) -> tuple[ValidatedOrderCandidate, Optional[TradeRecord]]:
        """Validate and (if live) place an order for a candidate."""
        
        if self.mode == "read_only":
            return None, None
        
        validated = await validate_candidate(candidate, self.adapter, self.strategy, self.config)
        
        if not validated.can_trade:
            return validated, None
        
        if self.mode == "dry_run":
            trade = TradeRecord(
                trade_id=f"dry_{candidate.event_ticker}_{candidate.selected_market.ticker}",
                event_ticker=candidate.event_ticker,
                market_ticker=candidate.selected_market.ticker,
                side=validated.confirmed_side or candidate.most_bet_side,
                price=candidate.selected_market_stats.best_yes_bid or 0.5,
                size=candidate.total_resting_order_quantity,
                mode="dry_run",
                status="filled",
                timestamp=validated.validation_timestamp,
                validation_latency_ms=validated.validation_latency_ms,
            )
            return validated, trade
        
        # Live mode
        try:
            result = await self.adapter.place_order(
                ticker=candidate.selected_market.ticker,
                side=validated.confirmed_side or candidate.most_bet_side,
                price=candidate.selected_market_stats.best_yes_bid or 0.5,
                size=candidate.total_resting_order_quantity,
            )
            trade = TradeRecord(
                trade_id=result.get("order_id", f"live_{candidate.event_ticker}"),
                event_ticker=candidate.event_ticker,
                market_ticker=candidate.selected_market.ticker,
                side=validated.confirmed_side or candidate.most_bet_side,
                price=candidate.selected_market_stats.best_yes_bid or 0.5,
                size=candidate.total_resting_order_quantity,
                mode="live",
                status="filled",
                timestamp=validated.validation_timestamp,
                validation_latency_ms=validated.validation_latency_ms,
            )
            return validated, trade
        except Exception as e:
            trade = TradeRecord(
                trade_id=f"failed_{candidate.event_ticker}",
                event_ticker=candidate.event_ticker,
                market_ticker=candidate.selected_market.ticker,
                side=validated.confirmed_side or candidate.most_bet_side,
                price=0,
                size=0,
                mode="live",
                status="failed",
                timestamp=validated.validation_timestamp,
                validation_latency_ms=validated.validation_latency_ms,
                error=str(e),
            )
            return validated, trade
```

### 5.2 — `backend/logging/csv_logger.py`

```python
import csv
import os
from datetime import datetime
from backend.core.models import ProgressBasedOrderCandidate, TradeRecord

class CSVLogger:
    """Logs candidates and trades to CSV files."""
    
    def __init__(self, path: str = "logs/scanner.csv"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._ensure_header()
    
    def _ensure_header(self):
        headers = [
            "timestamp", "event_ticker", "market_ticker", "side",
            "progress_percent", "threshold_percent", "total_orders",
            "yes_orders", "no_orders", "actionable", "manual_review",
            "reasons",
        ]
        if not os.path.exists(self.path):
            with open(self.path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def log_candidate(self, candidate: ProgressBasedOrderCandidate):
        with open(self.path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                candidate.event_ticker,
                candidate.selected_market.ticker if candidate.selected_market else "",
                candidate.most_bet_side,
                f"{candidate.event_progress_percent:.1f}",
                candidate.threshold_percent,
                candidate.total_resting_order_quantity,
                candidate.yes_order_quantity,
                candidate.no_order_quantity,
                candidate.should_create_order_candidate,
                candidate.requires_manual_review,
                "; ".join(candidate.reasons),
            ])
```

---

## Phase 6: API Layer (FastAPI)

### 6.1 — `backend/main.py`

```python
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import load_settings
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.scanner_state import ScannerState
from backend.strategies import get_strategy
from backend.api.rest import router as api_router
from backend.api.websocket_handler import router as ws_router

settings = load_settings()
logger = logging.getLogger(__name__)

# Global state (shared across routes via dependency injection)
class AppState:
    def __init__(self):
        self.settings = settings
        self.kalshi_client: KalshiClient = None
        self.kalshi_adapter: KalshiAdapter = None
        self.scanner_state = ScannerState()
        self.strategy = get_strategy(
            settings.strategy.active_profile,
            settings.strategy.profiles.get(settings.strategy.active_profile, {}),
        )
        self.mode = settings.scanner.default_mode
        self._tasks: list[asyncio.Task] = []
        self._stop_event: asyncio.Event = None

app_state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    api_key = settings.kalshi_private_key
    app_state.kalshi_client = KalshiClient(
        base_url=settings.kalshi.base_url,
        api_key=api_key,
        rate_limit=settings.kalshi.rate_limit,
    )
    await app_state.kalshi_client.__aenter__()
    app_state.kalshi_adapter = KalshiAdapter(app_state.kalshi_client)
    app_state._stop_event = asyncio.Event()
    logger.info("App started")
    yield
    # Shutdown
    app_state._stop_event.set()
    for task in app_state._tasks:
        task.cancel()
    await app_state.kalshi_client.__aexit__(None, None, None)
    logger.info("App stopped")

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
```

### 6.2 — `backend/api/rest.py`

FastAPI router with all REST endpoints.

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.main import app_state
from backend.core.models import (
    EventWithTopMarkets, ProgressBasedOrderCandidate, TradeRecord,
    ValidationConfig,
)
from backend.engines.engine8_orchestrator import run_one_shot

router = APIRouter()
ET = ZoneInfo("America/New_York")

# ──── Response wrappers ────

class APIError(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[APIError] = None
    meta: Optional[dict] = None

def ok(data: Any) -> APIResponse:
    return APIResponse(success=True, data=data, meta={"timestamp": datetime.now(ET).isoformat()})

def err(code: str, message: str, status: int = 400, details: dict = None):
    raise HTTPException(status_code=status, detail=APIError(code=code, message=message, details=details).model_dump())

# ──── Endpoints ────

@router.get("/scanner/status")
async def get_status():
    state = app_state.scanner_state
    return ok({
        "mode": app_state.mode,
        "is_running": state.is_running,
        "connected_to_kalshi": app_state.kalshi_client is not None,
        "markets_tracked": len(state.markets_by_ticker),
        "events_tracked": len(state.ranked_events),
        "active_candidates": sum(1 for c in state.candidates.values() if c.should_create_order_candidate),
        "last_discovery": state.last_discovery,
        "last_progress_check": state.last_progress_check,
    })

@router.post("/scanner/start")
async def start_scanner():
    """Run a one-shot scan."""
    state = app_state.scanner_state
    state.is_running = True
    
    result = await run_one_shot(
        adapter=app_state.kalshi_adapter,
        strategy=app_state.strategy,
        threshold_percent=app_state.settings.scanner.default_threshold,
        mode=app_state.mode,
    )
    
    state.is_running = False
    
    return ok({
        "scanned_market_count": result.scanned_market_count,
        "same_day_live_event_count": len(result.events),
        "actionable_candidate_count": len(result.actionable),
        "manual_review_count": len(result.manual_review),
        "validated_count": len(result.validated),
    })

@router.get("/events")
async def list_events():
    """List all ranked events."""
    events = list(app_state.scanner_state.ranked_events.values())
    
    summaries = []
    for e in events:
        candidate = app_state.scanner_state.get_candidate(e.event_ticker)
        summaries.append({
            "event_ticker": e.event_ticker,
            "market_count": e.market_count,
            "live_market_count": e.same_day_live_market_count,
            "total_resting_order_quantity": e.total_event_resting_order_quantity,
            "active_orderbook_market_count": e.active_orderbook_market_count,
            "event_progress_percent": candidate.event_progress_percent if candidate else 0,
            "has_active_candidate": candidate.should_create_order_candidate if candidate else False,
            "candidate_side": candidate.most_bet_side if candidate and candidate.should_create_order_candidate else None,
            "top_markets": [
                {
                    "ticker": m.market.ticker,
                    "title": m.market.title,
                    "yes_bid": m.orderbook_stats.best_yes_bid,
                    "no_bid": m.orderbook_stats.best_no_bid,
                    "total_resting_order_quantity": m.orderbook_stats.total_resting_order_quantity,
                    "yes_order_quantity": m.orderbook_stats.yes_order_quantity,
                    "no_order_quantity": m.orderbook_stats.no_order_quantity,
                    "volume_24h": m.orderbook_stats.volume_24h,
                }
                for m in e.top_3_markets_by_current_orders
            ],
        })
    
    return ok(summaries)

@router.get("/events/{event_ticker}")
async def get_event(event_ticker: str):
    event = app_state.scanner_state.get_event(event_ticker)
    if not event:
        err("EVENT_NOT_FOUND", f"Event {event_ticker} not found.", 404)
    
    candidate = app_state.scanner_state.get_candidate(event_ticker)
    
    return ok({
        "event_ticker": event.event_ticker,
        "market_count": event.market_count,
        "same_day_live_market_count": event.same_day_live_market_count,
        "total_event_resting_order_quantity": event.total_event_resting_order_quantity,
        "active_orderbook_market_count": event.active_orderbook_market_count,
        "event_progress_percent": candidate.event_progress_percent if candidate else 0,
        "threshold_percent": candidate.threshold_percent if candidate else 65,
        "all_markets_ranked": [
            {
                "ticker": r.market.ticker,
                "title": r.market.title,
                "status": r.market.status,
                "total_resting_order_quantity": r.orderbook_stats.total_resting_order_quantity,
                "yes_order_quantity": r.orderbook_stats.yes_order_quantity,
                "no_order_quantity": r.orderbook_stats.no_order_quantity,
                "depth_level_count": r.orderbook_stats.depth_level_count,
                "best_yes_bid": r.orderbook_stats.best_yes_bid,
                "best_no_bid": r.orderbook_stats.best_no_bid,
                "volume_24h": r.orderbook_stats.volume_24h,
                "rank": i + 1,
            }
            for i, r in enumerate(event.all_same_day_live_markets_ranked)
        ],
        "active_candidate": {
            "most_bet_side": candidate.most_bet_side,
            "event_progress_percent": candidate.event_progress_percent,
            "should_create_order_candidate": candidate.should_create_order_candidate,
            "reasons": candidate.reasons,
        } if candidate else None,
    })

@router.get("/candidates")
async def list_candidates():
    candidates = list(app_state.scanner_state.candidates.values())
    return ok([
        {
            "event_ticker": c.event_ticker,
            "threshold_percent": c.threshold_percent,
            "event_progress_percent": c.event_progress_percent,
            "event_passes_progress_threshold": c.event_passes_progress_threshold,
            "selected_market_ticker": c.selected_market.ticker if c.selected_market else None,
            "most_bet_side": c.most_bet_side,
            "yes_order_quantity": c.yes_order_quantity,
            "no_order_quantity": c.no_order_quantity,
            "total_resting_order_quantity": c.total_resting_order_quantity,
            "should_create_order_candidate": c.should_create_order_candidate,
            "requires_manual_review": c.requires_manual_review,
            "reasons": c.reasons,
        }
        for c in candidates
    ])

@router.post("/candidates/{event_ticker}/approve")
async def approve_candidate(event_ticker: str):
    if app_state.mode == "read_only":
        err("MODE_READ_ONLY", "Cannot approve in read-only mode.", 403)
    
    candidate = app_state.scanner_state.get_candidate(event_ticker)
    if not candidate or not candidate.should_create_order_candidate:
        err("CANDIDATE_NOT_ACTIONABLE", "Candidate is not actionable.", 400)
    
    from backend.trading.trade_executor import TradeExecutor
    executor = TradeExecutor(app_state.kalshi_adapter, app_state.strategy, app_state.mode)
    validated, trade = await executor.execute(candidate)
    
    return ok({
        "approved": validated.can_trade,
        "reason": validated.reason,
        "trade": trade,
    })

@router.post("/mode")
async def switch_mode(mode: str, confirm: bool = False):
    if mode not in ("dry_run", "live"):
        err("INVALID_MODE", f"Invalid mode: {mode}. Use dry_run or live.", 400)
    if mode == "live" and not confirm:
        err("CONFIRMATION_REQUIRED", "Must set confirm=true to switch to live.", 400)
    if mode == "live" and not app_state.settings.kalshi_private_key:
        err("AUTH_REQUIRED", "Kalshi API credentials not configured.", 401)
    
    previous = app_state.mode
    app_state.mode = mode
    return ok({"previous_mode": previous, "current_mode": mode})

@router.get("/config")
async def get_config():
    from backend.strategies import STRATEGY_REGISTRY
    return ok({
        "mode": app_state.mode,
        "strategy": {
            "active_profile": app_state.settings.strategy.active_profile,
        },
        "threshold_percent": app_state.settings.scanner.default_threshold,
        "available_strategies": [
            {"name": name, "description": cls("").description}
            for name, cls in STRATEGY_REGISTRY.items()
        ],
        "kalshi_connected": app_state.kalshi_client is not None,
        "has_credentials": bool(app_state.settings.kalshi_private_key),
    })

@router.put("/config")
async def update_config(strategy: str = None, threshold_percent: int = None):
    if strategy:
        from backend.strategies import get_strategy
        app_state.strategy = get_strategy(strategy, {})
        app_state.settings.strategy.active_profile = strategy
    if threshold_percent:
        app_state.settings.scanner.default_threshold = threshold_percent
    return await get_config()
```

---

## Phase 7–10: Frontend Implementation Spec

### Files (in creation order)

```
frontend/src/lib/types.ts          # TypeScript interfaces matching API contract
frontend/src/lib/api.ts             # ScannerAPI class
frontend/src/lib/constants.ts       # Constants
frontend/src/hooks/useWebSocket.ts  # WebSocket hook
frontend/src/hooks/useScanner.ts    # Scanner state hook
frontend/src/hooks/useCandidates.ts # Candidates hook
frontend/src/App.tsx                # Router + layout
frontend/src/pages/Dashboard.tsx    # Main dashboard
frontend/src/pages/Events.tsx       # Events list
frontend/src/pages/EventDetail.tsx  # Single event
frontend/src/pages/Candidates.tsx   # Candidates review
frontend/src/pages/Trades.tsx       # Trade history
frontend/src/pages/Settings.tsx     # Config panel
frontend/src/components/*            # All components
```

### 7.1 — `frontend/src/lib/types.ts`

Full TypeScript types matching the API contract. See `docs/api-contract.md` for the complete list. Every `interface`, every union type, every field.

### 7.2 — `frontend/src/lib/api.ts`

```typescript
const BASE = '/api/v1';

interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string; details?: Record<string, unknown> };
  meta?: { timestamp: string };
}

export class ScannerAPI {
  // Implement every endpoint from docs/api-contract.md
  async getStatus(): Promise<APIResponse<ScannerStatus>> { ... }
  async startScanner(): Promise<APIResponse<StartResult>> { ... }
  async getEvents(): Promise<APIResponse<EventSummary[]>> { ... }
  async getEvent(ticker: string): Promise<APIResponse<EventDetail>> { ... }
  async getCandidates(): Promise<APIResponse<CandidateResponse[]>> { ... }
  async approveCandidate(eventTicker: string): Promise<APIResponse<ApproveResult>> { ... }
  async getConfig(): Promise<APIResponse<ScannerConfigResponse>> { ... }
  async updateConfig(opts: { strategy?: string; threshold_percent?: number }): Promise<APIResponse<ScannerConfigResponse>> { ... }
  async switchMode(mode: 'dry_run' | 'live', confirm: boolean): Promise<APIResponse<SwitchResult>> { ... }
}
```

### 7.3 — `frontend/src/hooks/useWebSocket.ts`

```typescript
import { useEffect, useRef, useCallback } from 'react';

interface WSMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
}

export function useWebSocket<T = unknown>(
  channel: string,
  onMessage: (msg: WSMessage<T>) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number>();

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/api/v1/ws/${channel}`;
    
    const ws = new WebSocket(url);
    ws.onmessage = (event) => {
      const msg: WSMessage<T> = JSON.parse(event.data);
      onMessage(msg);
    };
    ws.onclose = () => {
      reconnectTimer.current = window.setTimeout(connect, 3000);
    };
    wsRef.current = ws;
  }, [channel, onMessage]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { ws: wsRef };
}
```

### 7.4 — Pages (key pseudocode)

**Dashboard.tsx:**
```
Layout:
  - ScannerStatus bar at top (mode badge, connection status, uptime)
  - EventGrid below showing EventCard for each ranked event
  
Data flow:
  - On mount: GET /api/v1/events → populate grid
  - WS /api/v1/ws/events → real-time updates (event:updated, event:progress_updated)
  - WS /api/v1/ws/candidates → candidate badge updates
  
States:
  - Loading: skeleton grid
  - Empty: "No same-day-live events found" message
  - Error: error banner + retry button
  - Live: real-time updating grid
  
EventCard renders:
  - event_ticker
  - progress bar (colored: green if passes threshold, gray if not)
  - top 3 markets with YES/NO prices
  - candidate badge (if actionable: green "YES"/"NO" pill, if manual review: yellow "REVIEW")
```

**EventDetail.tsx:**
```
Layout:
  - Event header: ticker, progress bar, threshold indicator
  - Ranked markets table (all markets in event, ranked)
    - Each row: ticker, title, YES bid, NO bid, total qty, depth
  - Orderbook panel (maybe toggled): depth bars for selected market
  - Candidate section (if exists): side, progress, action buttons

Data flow:
  - On mount: GET /api/v1/events/{ticker}
  - WS /api/v1/ws/events → event:orderbook_update, event:updated
```

**Candidates.tsx:**
```
Layout:
  - Filter tabs: Actionable | Manual Review | All
  - CandidateCard list

CandidateCard:
  - event_ticker, selected market, side (YES/NO large badge)
  - Progress bar with threshold line
  - Stats: YES qty, NO qty, total qty
  - Action buttons: Approve (green) / Reject (red) — only in live mode
  - Reasons list (why it passed/failed)

Data flow:
  - GET /api/v1/candidates
  - POST /api/v1/candidates/{id}/approve
  - POST /api/v1/candidates/{id}/reject
```

**Settings.tsx:**
```
Layout:
  - Mode section: current mode badge + switch button + ConfirmDialog
  - Strategy section: dropdown selector from GET /api/v1/config
  - Threshold section: slider (0-100%) + current value
  - Save button → PUT /api/v1/config
```

### 7.5 — Key Components

**ModeSelector.tsx:**
```
Props:
  - currentMode: 'dry_run' | 'read_only' | 'live'
  - onSwitch: (mode: 'dry_run' | 'live') => void
  - hasCredentials: boolean

Renders:
  - Mode badge (colored: green for live, yellow for dry_run, gray for read_only)
  - Toggle button (disabled in read_only)
  - On click → ConfirmDialog
```

**ConfirmDialog.tsx:**
```
Props:
  - isOpen: boolean
  - title: string
  - message: string
  - confirmLabel: string
  - onConfirm: () => void
  - onCancel: () => void
  - danger?: boolean  (red styling for live mode switch)

Renders:
  - Modal overlay with styled dialog
  - Confirm button (disabled for 3 seconds — safety delay)
  - Cancel button
```

**ThresholdSlider.tsx:**
```
Props:
  - value: number (0-100)
  - onChange: (value: number) => void
  - disabled?: boolean

Renders:
  - Label with current value
  - HTML range input styled with Tailwind
  - Tick marks at 0, 25, 50, 65 (default), 75, 100
```

**ProgressBar.tsx:**
```
Props:
  - percent: number
  - threshold?: number  (optional line marker)
  - size?: 'sm' | 'md' | 'lg'
  - color?: 'green' | 'yellow' | 'gray'

Renders:
  - Colored bar filling to percent
  - Threshold line (vertical dashed line at threshold position)
  - Percentage label
```

**Badge.tsx:**
```
Props:
  - variant: 'yes' | 'no' | 'tie' | 'dry_run' | 'live' | 'read_only' | 'info'
  - label: string
  - size?: 'sm' | 'md'

Renders:
  - Colored pill with text
  - YES = green, NO = red, tie = yellow, dry_run = amber, live = green, read_only = gray
```

---

## Phase 11: Docker + Integration

### 11.1 — `docker-compose.yml`

```yaml
version: '3.8'
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://localhost:8000
```

### 11.2 — `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 11.3 — Testing Script

```bash
# backend/tests/run_simulation.py
# Quick smoke test script to verify the pipeline works

python -c "
import asyncio
from backend.config.settings import load_settings
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.strategies import get_strategy
from backend.engines.engine8_orchestrator import run_one_shot

async def test():
    settings = load_settings()
    async with KalshiClient() as client:
        adapter = KalshiAdapter(client)
        strategy = get_strategy('most-bet')
        result = await run_one_shot(adapter, strategy, mode='dry_run')
        print(f'Scanned: {result.scanned_market_count} markets')
        print(f'Events: {len(result.events)}')
        print(f'Actionable: {len(result.actionable)}')
        for c in result.actionable[:3]:
            print(f'  {c.event_ticker}: {c.most_bet_side} @ {c.event_progress_percent:.1f}%')

asyncio.run(test())
"
```

---

## Build Execution Order

Following this exact order ensures each file's dependencies exist before it's created:

```
Step 0:  mkdir -p backend/{config,core,adapters/kalshi,engines/live,strategies,trading,logging,api}
         mkdir -p frontend/src/{lib,hooks,pages,components/{Dashboard,Orderbook,Candidates,Trading,Controls,Common},styles}
         mkdir -p config tests logs

Step 1:  backend/core/models.py                    # No deps
Step 2:  backend/core/interfaces.py                 # Depends on models.py
Step 3:  backend/core/scanner_state.py              # Depends on models.py
Step 4:  backend/config/settings.py                 # No deps
Step 5:  backend/config/defaults.py                 # Depends on settings.py
Step 6:  backend/adapters/kalshi/types.py           # Depends on core/models.py
Step 7:  backend/adapters/kalshi/client.py          # No internal deps
Step 8:  backend/adapters/kalshi/adapter.py         # Depends on client.py, types.py
Step 9:  backend/adapters/kalshi/websocket.py       # No internal deps
Step 10: backend/engines/engine1_discovery.py       # Depends on adapter
Step 11: backend/engines/engine2_classification.py  # Depends on core/models.py
Step 12: backend/engines/engine3_grouping.py        # Depends on core/models.py
Step 13: backend/engines/engine4_orderbook.py       # Depends on adapter, models
Step 14: backend/engines/engine5_ranking.py         # Depends on types.py, models
Step 15: backend/strategies/base.py                 # Depends on core/models.py
Step 16: backend/strategies/most_bet.py             # Depends on base.py
Step 17: backend/strategies/highest_volume.py       # Depends on base.py
Step 18: backend/strategies/widest_spread.py        # Depends on base.py
Step 19: backend/strategies/deepest_book.py         # Depends on base.py
Step 20: backend/strategies/momentum_shift.py       # Depends on base.py
Step 21: backend/strategies/custom_threshold.py     # Depends on most_bet.py
Step 22: backend/strategies/__init__.py             # Depends on all strategies
Step 23: backend/engines/engine6_progress_gate.py   # Depends on engine2, strategies
Step 24: backend/engines/engine7_validation.py      # Depends on engine2, engine5, strategies
Step 25: backend/engines/engine8_orchestrator.py    # Depends on E1-E7
Step 26: backend/engines/live/discovery_poller.py   # Depends on E1-E3
Step 27: backend/engines/live/event_reranker.py     # Depends on E5
Step 28: backend/engines/live/progress_gate_loop.py # Depends on E6
Step 29: backend/trading/trade_executor.py          # Depends on adapter, strategies, E7
Step 30: backend/logging/csv_logger.py              # Depends on models
Step 31: backend/api/rest.py                        # Depends on everything above
Step 32: backend/main.py                            # Depends on everything above

Step 33: frontend/src/lib/types.ts                  # No deps (mirrors API contract)
Step 34: frontend/src/lib/api.ts                    # Depends on types.ts
Step 35: frontend/src/hooks/useWebSocket.ts         # No deps
Step 36: frontend/src/hooks/useScanner.ts           # Depends on api.ts
Step 37: frontend/src/hooks/useCandidates.ts        # Depends on api.ts
Step 38: frontend/src/App.tsx                       # Depends on all pages
Step 39-44: frontend/src/pages/*.tsx                # Depends on hooks, api
Step 45-54: frontend/src/components/**/*.tsx        # Depends on types
```

---

## Scaffold Script

```bash
#!/bin/bash
# scripts/scaffold.sh — Create all directories

mkdir -p backend/{config,core,adapters/kalshi,engines/live,strategies,trading,logging,api}
mkdir -p frontend/src/{lib,hooks,pages,components/{Dashboard,Orderbook,Candidates,Trading,Controls,Common},styles}
mkdir -p config tests logs

touch backend/__init__.py
touch backend/config/__init__.py
touch backend/core/__init__.py
touch backend/adapters/__init__.py
touch backend/adapters/kalshi/__init__.py
touch backend/engines/__init__.py
touch backend/engines/live/__init__.py
touch backend/strategies/__init__.py
touch backend/trading/__init__.py
touch backend/logging/__init__.py
touch backend/api/__init__.py
touch tests/__init__.py

echo "Scaffold complete. Directories created:"
find backend -type d | sort
find frontend -type d | sort
```
