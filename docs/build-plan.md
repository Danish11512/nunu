# Master Build Plan — Nunu Prediction Market Scanner

> **Single source of truth for implementation.** Follow the phases in order.
> Each phase links to detailed specs in other `.md` files when available.

---

## Quick Start (start here)

```bash
# 1. Prerequisites: Python 3.11+, bun (or npm), Docker (optional)

# 2. Create directories
bash scripts/scaffold.sh

# 3. Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 4. Configure environment
cp backend/.env.example backend/.env
# → Edit backend/.env with your Kalshi API credentials

# 5. Install frontend deps
cd frontend && bun install && cd ..

# 6. Start development (Phase 1 = backend only)
./run.sh --phase 1

# 7. Follow phases below — each tells you what to build and how to verify
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| bun (or npm) | Latest | Frontend package management |
| Docker | Latest (optional) | Containerized deployment |
| Kalshi API keys | — | Required for live/trading modes |

## Document Map — Cross-References

Every file below is referenced from this build plan. Read them alongside the corresponding phase.

| Document | Covers | Referenced In |
|----------|--------|---------------|
| `docs/api-contract.md` | Full REST + WS API contract, TypeScript types | Phase 6 (routes), Phase 7 (types) |
| `docs/architecture.md` | 10 Mermaid diagrams (system context, pipeline, deployment) | Overview |
| `docs/adapters/adapter-contract.md` | Abstract `MarketPlatformAdapter` interface | Phase 2 (design context) |
| `docs/engines/engine-1-discovery.md` | E1 spec: fetch all open markets | Phase 3.1 |
| `docs/engines/engine-2-classification.md` | E2 spec: same-day-live classification | Phase 3.2 |
| `docs/engines/engine-3-grouping.md` | E3 spec: group by event_ticker | Phase 3.3 |
| `docs/engines/engine-4-orderbook.md` | E4 spec: fetch orderbooks | Phase 3.4 |
| `docs/engines/engine-5-ranking.md` | E5 spec: rank by resting orders | Phase 3.5 |
| `docs/engines/engine-6-progress-gate.md` | E6 spec: threshold gate + candidate creation | Phase 3.6 |
| `docs/engines/engine-7-validation.md` | E7 spec: pre-trade validation | Phase 3.7 |
| `docs/engines/engine-8-orchestration.md` | E8 spec: pipeline orchestrator | Phase 3.8 |
| `docs/engines/strategy-system.md` | All 7 strategy experiments, registry, backtesting framework | Phase 4 |
| `docs/plans/generic-prediction-market-scanner-platform.md` | Main plan doc (goals, data model, architecture) | Overall context |

## Setup Steps (do once)

1. **Generate Kalshi API keys** at `https://kalshi.com/account/api` → generate RSA keypair
2. **Copy env template**: `cp backend/.env.example backend/.env`
3. **Fill in `.env`**: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY` (PEM), `KALSHI_FUNDER_ADDRESS`
4. **Create venv**: `python3 -m venv venv && source venv/bin/activate`
5. **Install Python deps**: `pip install -r backend/requirements.txt`
6. **Scaffold dirs**: `bash scripts/scaffold.sh` (creates all empty dirs + `__init__.py` files)
7. **Install frontend deps**: `cd frontend && bun install && cd ..`

---

## Build Execution Order (54 Steps)

Phases build in dependency order. Within each phase, create files in the order listed.
For the full detailed step list with pseudocode references, see the [Full Build Execution Order](#full-build-execution-order-54-steps) section at the end.

**Quick reference:**
```
Phase 0:  Scaffolding (dirs + configs)      — Step 0
Phase 1:  Backend Core + Utils              — Steps 1–16
Phase 2:  Kalshi Adapter (SOLID split)      — Steps 17–22
Phase 3:  Engines + Live                     — Steps 23–33
Phase 4:  Strategies + Registry              — Steps 34–41
Phase 5:  Backtesting Infrastructure         — Steps 42–46
Phase 6:  Trading + Logging + Portfolio       — Steps 47–51
Phase 7:  API Layer (DRY errors.py)         — Steps 52–54
Phase 8:  Frontend lib (Types + API Client)  — Steps 55–56
Phase 9:  Frontend Hooks                     — Steps 57–59
Phase 10: Frontend Pages                     — Steps 60–66
Phase 11: Frontend Components                — Steps 67–76
Phase 12: Test Infrastructure                — After all steps
Phase 13: Docker + Integration               — After all steps
```

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
    │                       ├──▶ Phase 4: Strategies (7 experiments + registry)
    │                       │       │
    │                       │       └──▶ Phase 5: Backtesting Infrastructure
    │                       │
    │                       └──▶ Phase 6: Trading + Logging
    │                                   │
    │                                   └──▶ Phase 7: API Layer (FastAPI)
    │                                               │
    └───────────────────────────────────────────────┘
                                                    │
                                            Phase 8: Frontend Setup + Types
                                                    │
                                            Phase 9: Frontend Hooks
                                                    │
                                            Phase 10: Frontend Pages
                                                    │
                                            Phase 11: Frontend Components
                                                    │
                                            Phase 12: Test Infrastructure
                                                    │
                                            Phase 13: Docker + Integration
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

scripts/
  scaffold.sh
```

### 0.1 — `run.sh` (project root)

See the actual file at `run.sh`. It contains phase-gated startup for backend,
frontend, and Docker. Initially runs backend only — edit `PHASE` or pass
`--phase N` to add more services.

**Phase progression:**
- `./run.sh --phase 1` — Backend only (current, Phase 1 implementation)
- `./run.sh --phase 2` — Backend + Frontend (Phase 2+)
- `./run.sh --phase 3` — Docker Compose (Phase 4+)

**No changes needed during implementation.** The script is pre-built to handle
all phases. Just update `PHASE="${PHASE:-1}"` at the top of `run.sh` when
you're ready to enable frontend.

### 0.2 — `backend/requirements.txt`

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
KALSHI_API_KEY_ID=             # API key ID from Kalshi dashboard
KALSHI_PRIVATE_KEY=            # RSA private key in PEM format (for signing)
KALSHI_MEMBER_ID=              # Kalshi member ID (from account settings)
KALSHI_FUNDER_ADDRESS=

# Scanner
SCANNER_DEFAULT_MODE=dry_run
SCANNER_DEFAULT_THRESHOLD=65
SCANNER_DEFAULT_STRATEGY=executed-volume-follower

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
  default_threshold: 60
  default_strategy: executed-volume-follower
  discovery_poll_interval: 30   # seconds
  progress_gate_interval: 10    # seconds
  max_candidate_age: 30         # seconds

strategy:
  active_experiment: executed-volume-follower
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

### SOLID Changes
- **SRP**: Split monolithic `models.py` into domain-specific modules (market, classification, trading)
- **DIP**: Extract abstract `Engine` interface from concrete engines
- **ISP**: Segregate `StrategyProfile` into `MarketSelector` + `SideSelector`

### Files (in creation order)

```
backend/core/
  __init__.py
  models/
    __init__.py               # Re-exports all models
    market.py                 # Market, Orderbook, OrderbookLevel
    classification.py         # MarketClassification, ClassifiedEvent
    trading.py                # OrderCandidate, TradeRecord, configs
  interfaces/
    __init__.py               # Re-exports all interfaces
    adapter.py                # AbstractMarketAdapter (ISP: read-only vs trading)
    strategy.py               # IMarketSelector, ISideSelector (ISP: segregated)
    engine.py                 # AbstractEngine (single-method interface)
  scanner_state.py

backend/config/
  __init__.py
  settings.py
  defaults.py

backend/utils/
  __init__.py
  datetime_utils.py           # parse_date, day_key_et, same_et_day, calculate_progress
  http_utils.py               # RateLimiter, RetryHandler
  auth_utils.py               # RSA-PSS signer (extracted from client)
  poller.py                   # Generic async poller loop (used by live/ modules)
  logging_utils.py            # Logger setup, custom log levels
```

**Verification:**
```bash
cd backend && python -c "
from backend.core.models import Market, OrderCandidate, MarketClassification
from backend.core.interfaces import AbstractMarketAdapter, IMarketSelector, AbstractEngine
from backend.utils.datetime_utils import parse_date, calculate_progress
from backend.utils.http_utils import RateLimiter
from backend.utils.auth_utils import KalshiSigner
print('Phase 1: Core + Utils import OK')
"
```

### 1.1 — `backend/core/models/market.py`

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Market:
    """A single Kalshi market (tradable binary outcome)."""
    ticker: str                    # Primary ID, e.g. "EVTA-M1"
    event_ticker: str              # Parent event ID, e.g. "EVTA"
    status: str                    # "active" | "closed" | "settled"
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
    overtime_category: str = "standard"      # "standard" | "overtime_short" | "overtime_medium" | "overtime_long" | "composite"
    overtime_window_hours: float = 0.0       # Gap between expected and latest expiration
    progress_percent: float = 0.0            # % time elapsed between open and expected_exp
    reasons: list[str] = field(default_factory=list)

### 1.2 — `backend/core/models/classification.py`

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class MarketClassification:
    """Result of same-day-live classification for one market."""
    ticker: str
    event_ticker: str
    live_now: bool
    expected_to_resolve_today: bool
    latest_expiration_today: bool
    same_day_live_market: bool
    overtime_category: str = "standard"
    overtime_window_hours: float = 0.0
    progress_percent: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class ClassifiedEvent:
    """Event with its same-day-live child markets."""
    event_ticker: str
    market_count: int
    same_day_live_market_count: int
    same_day_live_markets: list[tuple['Market', 'MarketClassification']] = field(default_factory=list)
```

### 1.3 — `backend/core/models/trading.py`

```python
from dataclasses import dataclass, field
from typing import Optional
from .market import Market, MarketOrderbookStats, Orderbook
from .classification import MarketClassification

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
    side: str
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

### 1.4 — `backend/core/models/__init__.py`

```python
from .market import Market, Orderbook, OrderbookLevel, MarketOrderbookStats
from .classification import MarketClassification, ClassifiedEvent
from .trading import (
    RankedMarket, EventWithTopMarkets, OrderCandidate,
    ProgressBasedOrderCandidate, ValidatedOrderCandidate,
    TradeRecord, ValidationConfig, RiskConfig,
)
```

### 1.5 — `backend/core/interfaces/` (SOLID: segregated interfaces)

> **ISP**: Instead of one monolithic `StrategyProfile`, we split into two single-method interfaces.
> **DIP**: Engines depend on `AbstractMarketAdapter`, not `KalshiAdapter`.
> **OCP**: Add new adapters by implementing `AbstractMarketAdapter` — no existing code changes.

#### `backend/core/interfaces/adapter.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from ..models.market import Market, Orderbook, MarketOrderbookStats


class MarketReader(ABC):
    """Read-only market data access (ISP: segregated from trading)."""
    
    @abstractmethod
    async def get_all_open_markets(self) -> list[Market]:
        ...

    @abstractmethod
    async def get_market(self, ticker: str) -> Optional[Market]:
        ...

    @abstractmethod
    async def get_orderbook(self, ticker: str) -> Orderbook:
        ...

    @abstractmethod
    async def get_orderbook_stats(self, ticker: str) -> Optional[MarketOrderbookStats]:
        ...


class Trader(ABC):
    """Write-side order placement (ISP: only needed for live mode)."""

    @abstractmethod
    async def place_order(self, ticker: str, side: str, price: float, size: float) -> dict:
        ...


class AbstractMarketAdapter(MarketReader, Trader):
    """Full adapter combining read + write."""
    pass
```

#### `backend/core/interfaces/strategy.py` (ISP: segregated selection)

```python
from abc import ABC, abstractmethod
from typing import Optional
from ..models.trading import RankedMarket
from ..models.market import MarketOrderbookStats


class IMarketSelector(ABC):
    """Single-responsibility: pick the best market from ranked list."""
    
    @abstractmethod
    def select_market(self, ranked_markets: list[RankedMarket]) -> Optional[RankedMarket]:
        ...


class ISideSelector(ABC):
    """Single-responsibility: pick YES/NO for a given market."""
    
    @abstractmethod
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> str:
        ...


class StrategyProfile(IMarketSelector, ISideSelector):
    """Combined strategy (extends both interfaces for convenience)."""
    name: str = ""
    description: str = ""
    config: dict = {}

    def __init__(self, config: dict = None):
        self.config = config or {}
```

#### `backend/core/interfaces/engine.py` (OCP: new engines via implementation)

```python
from abc import ABC, abstractmethod
from typing import Any


class AbstractEngine(ABC):
    """
    Every pipeline engine implements this single-method interface.
    The orchestrator can run any engine without knowing its concrete type.
    """
    
    @abstractmethod
    async def run(self, context: dict) -> dict:
        """Execute this engine step with the pipeline context.
        Returns updated context with this engine's results.
        """
        ...
```

#### `backend/core/interfaces/__init__.py`

```python
from .adapter import AbstractMarketAdapter, MarketReader, Trader
from .strategy import StrategyProfile, IMarketSelector, ISideSelector
from .engine import AbstractEngine
```

### 1.6 — `backend/core/scanner_state.py`

(Content unchanged from original — central runtime state dataclass.)

### 1.7 — `backend/utils/` (DRY: shared utilities extracted from engines and client)

#### `backend/utils/datetime_utils.py`

> **DRY**: Extracted from Engine 2 (parse_date, day_key_et, same_et_day) and
> Engine 6 (calculate_progress). Single source of truth for time handling.

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

ET = ZoneInfo("America/New_York")


def parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 string to datetime. Handles 'Z' suffix."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def day_key_et(date: datetime) -> str:
    """YYYY-MM-DD in America/New_York."""
    return date.astimezone(ET).strftime("%Y-%m-%d")


def same_et_day(a: datetime, b: datetime) -> bool:
    """True if both datetimes fall on the same calendar day in ET."""
    return day_key_et(a) == day_key_et(b)


def calculate_progress(start_str: str, end_str: str, now: datetime) -> float:
    """
    0–100: time elapsed between start and end.
    Uses expected_expiration_time as the primary end anchor.
    """
    start = parse_date(start_str)
    end = parse_date(end_str)
    if not start or not end:
        return 0.0
    total = (end - start).total_seconds()
    if total <= 0:
        return 100.0
    elapsed = (now - start).total_seconds()
    return max(0.0, min(100.0, elapsed / total * 100))
```

#### `backend/utils/http_utils.py`

> **DRY**: Extracted from client.py — rate limiter and retry handler reused
> across all HTTP-calling modules.

```python
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Async semaphore-based rate limiter."""
    
    def __init__(self, max_concurrent: int = 10):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def acquire(self):
        await self._semaphore.acquire()

    def release(self):
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()


async def retry_with_backoff(
    coro_factory,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_statuses: set[int] = None,
):
    """Execute coro_factory() with exponential backoff on retryable errors."""
    if retryable_statuses is None:
        retryable_statuses = {429, 500, 502, 503, 504}
    
    import httpx
    
    for attempt in range(max_retries):
        try:
            return await coro_factory()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in retryable_statuses and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s (status={e.response.status_code})")
                await asyncio.sleep(delay)
                continue
            raise
        except (httpx.TimeoutException, httpx.RequestError) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s ({type(e).__name__})")
                await asyncio.sleep(delay)
                continue
            raise
    
    raise RuntimeError("Request failed after all retries.")
```

#### `backend/utils/auth_utils.py`

> **SRP**: RSA-PSS signing extracted from KalshiClient. Single responsibility.

```python
import base64
import time
from typing import Optional


class KalshiSigner:
    """RSA-PSS request signing for Kalshi API authentication."""

    def __init__(self, api_key_id: str, private_key_pem: Optional[str] = None):
        self.api_key_id = api_key_id
        self.private_key_pem = private_key_pem

    def sign(self, method: str, path: str, body: str = "") -> tuple[str, str, str]:
        """
        Generate KALSHI-ACCESS headers.
        Returns (api_key, signature_b64, timestamp_ms).
        """
        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + path + body

        if not self.private_key_pem:
            return self.api_key_id or "", "", timestamp

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private_key = load_pem_private_key(self.private_key_pem.encode(), password=None)
        signature = private_key.sign(
            message.encode(),
            asym_padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return self.api_key_id, base64.b64encode(signature).decode(), timestamp
```

#### `backend/utils/poller.py` (DRY: generic async poller)

> **DRY**: The live/ modules (discovery_poller, progress_gate_loop) both follow
> the same poll-sleep pattern. Extracted into a reusable async poller.

```python
import asyncio
import logging
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class AsyncPoller:
    """
    Generic async poller that runs a callback on a fixed interval.
    Used by DiscoveryPoller and ProgressGateLoop (DRY).
    """

    def __init__(
        self,
        callback: Callable[[], Awaitable[None]],
        interval_seconds: float,
        name: str = "poller",
    ):
        self.callback = callback
        self.interval = interval_seconds
        self.name = name
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self):
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name=self.name)
        logger.info(f"Poller '{self.name}' started (interval={self.interval}s)")

    async def stop(self):
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Poller '{self.name}' stopped")

    async def _run(self):
        while not self._stop_event.is_set():
            try:
                await self.callback()
            except Exception as e:
                logger.error(f"Poller '{self.name}' error: {e}")
            await asyncio.sleep(self.interval)
```

#### `backend/config/settings.py`

(Content unchanged — pydantic-settings loader.)

#### `backend/config/defaults.py`

(Content unchanged — default config values.)

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
    default_strategy: str = "executed-volume-follower"
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

    kalshi_api_key_id: Optional[str] = None
    kalshi_private_key: Optional[str] = None    # RSA private key PEM
    kalshi_member_id: Optional[str] = None      # Kalshi member ID
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

## Phase 2: Kalshi Adapter (SOLID refactored)

> **SRP**: Split monolithic `client.py` into three single-responsibility modules.
> **DIP**: `KalshiAdapter` implements `AbstractMarketAdapter` from `core/interfaces/`.
> **Cross-ref:** `docs/adapters/adapter-contract.md`.

### Files (in creation order)

```
backend/adapters/kalshi/
  __init__.py
  auth.py              # RSA-PSS signing (was embedded in client)
  http_client.py       # Raw HTTP + rate limiting + retry (was in client)
  client.py            # Kalshi REST methods (thin, delegates auth+http)
  types.py             # Parsers + stats calculators
  websocket.py         # WS client (uses auth.py for connect signing)
  adapter.py           # Facade: implements AbstractMarketAdapter
```

**Verification:**
```bash
cd backend && python -c "
from backend.adapters.kalshi.auth import KalshiSigner
from backend.adapters.kalshi.http_client import KalshiHttpClient
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.types import parse_market, parse_orderbook
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.interfaces import AbstractMarketAdapter
print('Kalshi adapter classes import OK')
assert issubclass(KalshiAdapter, AbstractMarketAdapter), 'KalshiAdapter must implement AbstractMarketAdapter'
"
```

### 2.1 — `backend/adapters/kalshi/auth.py`

> **SRP**: Single responsibility — RSA-PSS request signing. Extracted from
> the original `client.py._sign_request()`. Now also used by `websocket.py`.

```python
import base64
import time
from typing import Optional

class KalshiSigner:
    """RSA-PSS request signing for Kalshi API authentication.
    
    Uses three headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE,
    KALSHI-ACCESS-TIMESTAMP.
    """
    
    def __init__(self, api_key_id: str = "", private_key_pem: Optional[str] = None):
        self.api_key_id = api_key_id
        self.private_key_pem = private_key_pem
    
    def sign(self, method: str, path: str, body: str = "") -> tuple[str, str, str]:
        """
        Sign a Kalshi API request.
        Returns (api_key_id, signature_b64, timestamp_ms).
        """
        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + path + body
        
        if not self.private_key_pem:
            return self.api_key_id or "", "", timestamp
        
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        
        private_key = load_pem_private_key(self.private_key_pem.encode(), password=None)
        signature = private_key.sign(
            message.encode(),
            asym_padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return self.api_key_id, base64.b64encode(signature).decode(), timestamp
    
    def get_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        """Convenience: returns dict of KALSHI-ACCESS-* headers."""
        key, sig, ts = self.sign(method, path, body)
        headers = {
            "KALSHI-ACCESS-KEY": key,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }
        return headers
```

### 2.2 — `backend/adapters/kalshi/http_client.py`

> **SRP**: Single responsibility — raw HTTP transport with rate limiting and
> retry logic. No knowledge of Kalshi endpoints or auth.

```python
import httpx
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class KalshiHttpClient:
    """Raw HTTP transport for Kalshi API.
    
    - Connection pooling via httpx.AsyncClient
    - Rate limiting via asyncio.Semaphore
    - Retry with exponential backoff
    - Auth headers injected at call time (caller provides signer)
    """
    
    BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
    
    def __init__(self, base_url: str = None, rate_limit: int = 10, timeout: float = 30.0):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(rate_limit)
        self.timeout = timeout
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HTTP client not initialized. Use 'async with'.")
        return self._client
    
    async def request(self, method: str, path: str, auth_headers: dict = None, **kwargs) -> dict:
        """Rate-limited request with retry. Auth headers injected by caller."""
        async with self._semaphore:
            url = f"{self.base_url}{path}"
            headers = kwargs.pop("headers", {}) | (auth_headers or {})
            
            for attempt in range(3):
                try:
                    response = await self.client.request(method, url, headers=headers, **kwargs)
                    
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("retry-after", str(2 ** attempt)))
                        logger.warning(f"Rate limited. Retrying in {retry_after}s.")
                        await asyncio.sleep(retry_after)
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
```

### 2.3 — `backend/adapters/kalshi/client.py`

> **SRP**: Kalshi-specific REST methods only. Uses `KalshiSigner` for auth,
> `KalshiHttpClient` for transport. Thin — delegates to components.

```python
import asyncio
import json
import logging
from typing import Optional

from .auth import KalshiSigner
from .http_client import KalshiHttpClient

logger = logging.getLogger(__name__)


class KalshiClient:
    """Kalshi REST API client — endpoint-specific methods only."""
    
    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        private_key: str = None,
        rate_limit: int = 10,
    ):
        self.http = KalshiHttpClient(base_url, rate_limit)
        self.signer = KalshiSigner(api_key, private_key)
    
    async def __aenter__(self):
        await self.http.__aenter__()
        return self
    
    async def __aexit__(self, *args):
        await self.http.__aexit__(*args)
    
    async def list_markets(self, status: str = "open", limit: int = 1000, cursor: str = None) -> dict:
        params = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        headers = self.signer.get_headers("GET", "/markets")
        return await self.http.request("GET", "/markets", headers=headers, params=params)
    
    async def get_market(self, ticker: str) -> Optional[dict]:
        path = f"/markets/{ticker}"
        headers = self.signer.get_headers("GET", path)
        try:
            data = await self.http.request("GET", path, headers=headers)
            return data.get("market")  # Unwrap response wrapper
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_orderbook(self, ticker: str) -> dict:
        path = f"/markets/{ticker}/orderbook"
        headers = self.signer.get_headers("GET", path)
        return await self.http.request("GET", path, headers=headers)
    
    async def place_order(self, ticker: str, side: str, price: float, size: float) -> dict:
        if not self.signer.private_key_pem:
            raise RuntimeError("Private key required to place orders.")
        body = {
            "ticker": ticker,
            "side": "bid" if side == "yes" else "ask",
            "count": f"{size:.2f}",
            "price": f"{price:.4f}",
            "time_in_force": "good_till_canceled",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": False,
            "reduce_only": False,
            "cancel_order_on_pause": False,
        }
        payload = json.dumps(body, separators=(",", ":"))
        path = "/portfolio/events/orders"
        headers = self.signer.get_headers("POST", path, payload)
        headers["Content-Type"] = "application/json"
        return await self.http.request("POST", path, headers=headers, content=payload)
    
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
        
        seen: set[str] = set()
        unique: list[dict] = []
        for m in all_markets:
            ticker = m.get("ticker")
            if ticker not in seen:
                seen.add(ticker)
                unique.append(m)
        return unique
```

### 2.4 — `backend/adapters/kalshi/types.py`

(Content unchanged from original — pure parsing functions, no change needed.)

### 2.5 — `backend/adapters/kalshi/websocket.py`

(Minor change: uses `KalshiSigner` for connect auth instead of inline signing.)

### 2.6 — `backend/adapters/kalshi/adapter.py`

```python
"""
KalshiAdapter implements AbstractMarketAdapter (core/interfaces/adapter.py).
Follows DIP: engines depend on AbstractMarketAdapter, not this concrete class.
"""
from backend.core.interfaces import AbstractMarketAdapter
from backend.core.models.market import Market, Orderbook, MarketOrderbookStats
from .client import KalshiClient
from .types import parse_market, parse_orderbook, calculate_orderbook_stats


class KalshiAdapter(AbstractMarketAdapter):
    """High-level Kalshi interface implementing the abstract adapter contract."""
    
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
    
    async def get_orderbook_stats(self, ticker: str) -> Optional[MarketOrderbookStats]:
        market = await self.get_market(ticker)
        if not market:
            return None
        orderbook = await self.get_orderbook(ticker)
        return calculate_orderbook_stats(market, orderbook)
    
    async def place_order(self, ticker: str, side: str, price: float, size: float) -> dict:
        return await self.client.place_order(ticker, side, price, size)
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
    """WebSocket client for Kalshi real-time updates (RSA-PSS auth)."""
    
    def __init__(self, url: str = "wss://external-api-ws.kalshi.com/trade-api/ws/v2",
                 api_key: str = None, private_key: str = None):
        self.url = url
        self.api_key = api_key
        self.private_key = private_key
        self._ws = None
        self._running = False
        self._callbacks: list[Callable] = []
        self._subscribed_tickers: list[str] = []
    
    def on_message(self, callback: Callable[[dict], Awaitable[None]]):
        self._callbacks.append(callback)
    
    async def connect(self):
        """Connect with API key auth via headers."""
        import time, base64
        extra_headers = {}
        if hasattr(self, 'api_key') and self.api_key and hasattr(self, 'private_key') and self.private_key:
            timestamp = str(int(time.time() * 1000))
            message = timestamp + "GET" + "/trade-api/ws/v2"
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            private_key = load_pem_private_key(self.private_key.encode(), password=None)
            signature = private_key.sign(message.encode(), asym_padding.PKCS1v15(), hashes.SHA256())
            extra_headers = {
                "KALSHI-ACCESS-KEY": self.api_key,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
                "KALSHI-ACCESS-TIMESTAMP": timestamp,
            }
        self._ws = await websockets.connect(self.url, additional_headers=extra_headers)
        logger.info("WebSocket connected")
    
    async def subscribe(self, tickers: list[str]):
        """Subscribe to orderbook_delta channel for given tickers.
        
        Kalshi WS uses 'id' for request tracking and 'params' for subscription config.
        """
        self._subscribed_tickers = tickers
        message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": tickers,
            },
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
        """Place order via Kalshi V2 API. Requires RSA-PSS auth configured on client."""
        return await self.client.place_order(ticker, side, price, size)
```

---

## Phase 3: Engines

> **OCP**: Every engine implements `AbstractEngine` from `core/interfaces/`.
> Add new engines by implementing the interface — no orchestrator changes needed.
> **DRY**: Engines use shared utilities from `backend/utils/datetime_utils.py`
> (parse_date, calculate_progress) instead of defining their own.
> **Cross-ref:** Each engine has a detailed spec doc in `docs/engines/`.

| Engine | File | Spec Doc | Implements |
|--------|------|----------|------------|
| E1 Discovery | `engine1_discovery.py` | `docs/engines/engine-1-discovery.md` | `AbstractEngine` |
| E2 Classification | `engine2_classification.py` | `docs/engines/engine-2-classification.md` | `AbstractEngine` |
| E3 Grouping | `engine3_grouping.py` | `docs/engines/engine-3-grouping.md` | `AbstractEngine` |
| E4 Orderbook | `engine4_orderbook.py` | `docs/engines/engine-4-orderbook.md` | `AbstractEngine` |
| E5 Ranking | `engine5_ranking.py` | `docs/engines/engine-5-ranking.md` | `AbstractEngine` |
| E6 Progress Gate | `engine6_progress_gate.py` | `docs/engines/engine-6-progress-gate.md` | `AbstractEngine` |
| E7 Validation | `engine7_validation.py` | `docs/engines/engine-7-validation.md` | `AbstractEngine` |
| E8 Orchestrator | `engine8_orchestrator.py` | `docs/engines/engine-8-orchestration.md` | — (uses engines) |
| Live Poller | `live/discovery_poller.py` | — | (uses `AsyncPoller`) |
| Live Reranker | `live/event_reranker.py` | — | — |
| Live Progress Gate | `live/progress_gate_loop.py` | — | (uses `AsyncPoller`) |

### File ordering (strict dependency order)

```
backend/engines/engine1_discovery.py      # No engine deps
backend/engines/engine2_classification.py # Uses utils/datetime_utils.py
backend/engines/engine3_grouping.py       # Uses engine2 output types
backend/engines/engine4_orderbook.py      # Uses adapter + core
backend/engines/engine5_ranking.py        # Uses core models
backend/engines/engine6_progress_gate.py  # Uses engine2, strategies, utils
backend/engines/engine7_validation.py     # Uses engine2, engine5, strategies
backend/engines/engine8_orchestrator.py   # Uses every engine above
backend/engines/live/                     # Live update modules (use utils/poller.py)
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

> **Cross-ref:** `docs/engines/engine-2-classification.md` for full overtime
> model, edge cases, and verification results against live Kalshi API.

```python
"""
Engine 2: Overtime-aware same-day-live classification.

Uses a two-field expiration model (expected_expiration_time + latest_expiration_time)
to handle overtime events. Markets with expected_exp today but latest_exp days/weeks
later are classified as "composite" (multi-event bundles) and excluded.

Verified against 2,000 live Kalshi markets on 2026-06-17:
  - 100% have both expiration fields
  - Standard same-day: ~0.5% of open markets
  - Overtime-aware (≤48h gap): ~2.5%
  - Composite (>48h gap): ~22.5%
  - Non-today: ~74.5%
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from backend.core.models import Market, MarketClassification

ET = ZoneInfo("America/New_York")
MAX_OVERTIME_HOURS = 48.0  # Cap: exclude composite multi-event bundles


def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def day_key_et(date: datetime) -> str:
    """YYYY-MM-DD in America/New_York."""
    return date.astimezone(ET).strftime("%Y-%m-%d")


def same_et_day(a: datetime, b: datetime) -> bool:
    return day_key_et(a) == day_key_et(b)


def calculate_progress(market: Market, now: datetime) -> float:
    """
    Progress as % of time elapsed between open_time and expected_expiration_time.
    
    Uses expected_expiration_time as the end anchor (not latest_expiration_time,
    which is an overtime backstop, not the expected outcome).
    """
    start = parse_date(market.open_time)
    end = (parse_date(market.expected_expiration_time)
           or parse_date(market.latest_expiration_time)
           or parse_date(market.close_time))
    if not start or not end:
        return 0.0
    total = (end - start).total_seconds()
    if total <= 0:
        return 100.0
    elapsed = (now - start).total_seconds()
    return max(0.0, min(100.0, elapsed / total * 100))


def classify_market(market: Market, now: Optional[datetime] = None) -> MarketClassification:
    """
    Overtime-aware classification.
    
    SAME_DAY_LIVE_MARKET iff:
      - status == "active"
      - open_time <= now
      - close_time > now
      - expected_expiration_time is today ET
      - AND (latest_expiration_time is today ET
             OR gap <= MAX_OVERTIME_HOURS)
    
    Returns MarketClassification with overtime category and reasons.
    """
    if now is None:
        now = datetime.now(ET)
    
    reasons: list[str] = []
    
    open_time = parse_date(market.open_time)
    close_time = parse_date(market.close_time)
    expected_exp = parse_date(market.expected_expiration_time)
    latest_exp = parse_date(market.latest_expiration_time)
    
    # ── Rule 1: Currently trading ──
    live_now = (
        market.status == "active"
        and open_time is not None
        and close_time is not None
        and open_time <= now
        and close_time > now
    )
    if not live_now:
        reasons.append(f"Market not currently active (status={market.status}).")
    
    # ── Rule 2: Expected expiration is today ET ──
    expected_today = (expected_exp is not None and same_et_day(expected_exp, now))
    if not expected_today:
        reasons.append("expected_expiration_time is not today ET.")
    
    # ── Rule 3: Overtime window analysis ──
    overtime_category = "standard"
    overtime_window_hours = 0.0
    latest_today = False
    
    if latest_exp is not None:
        latest_today = same_et_day(latest_exp, now)
        if expected_exp and latest_exp:
            overtime_window_hours = (latest_exp - expected_exp).total_seconds() / 3600
        
        if expected_today and not latest_today and expected_exp and latest_exp:
            gap = overtime_window_hours
            if gap <= 0:
                overtime_category = "standard"
            elif gap <= 6:
                overtime_category = "overtime_short"
                reasons.append(f"Short OT window ({gap:.1f}h).")
            elif gap <= 24:
                overtime_category = "overtime_medium"
                reasons.append(f"Medium OT window ({gap:.1f}h).")
            elif gap <= MAX_OVERTIME_HOURS:
                overtime_category = "overtime_long"
                reasons.append(f"Long OT window ({gap:.1f}h).")
            else:
                overtime_category = "composite"
                reasons.append(f"Composite event (gap={gap:.0f}h).")
        elif latest_today:
            reasons.append("Latest expiration also today — standard same-day.")
    
    same_day_live = (
        live_now
        and expected_today
        and overtime_category != "composite"
    )
    
    return MarketClassification(
        ticker=market.ticker,
        event_ticker=market.event_ticker,
        live_now=live_now,
        expected_to_resolve_today=expected_today,
        latest_expiration_today=latest_today,
        same_day_live_market=same_day_live,
        overtime_category=overtime_category,
        overtime_window_hours=overtime_window_hours,
        progress_percent=calculate_progress(market, now),
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

def calculate_progress(market: Market, now: datetime) -> float:
    """
    Calculate event progress as percentage of time elapsed.
    
    Uses expected_expiration_time as the primary end anchor (not latest,
    which is an overtime backstop). Falls back to latest then close_time
    only if expected is missing (defensive — 100% of markets have it).
    
    Returns 0–100, clamped.
    """
    start = parse_date(market.open_time)
    end = (
        parse_date(market.expected_expiration_time)
        or parse_date(market.latest_expiration_time)
        or parse_date(market.close_time)
    )
    
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

**Phase 3 Verification:** After building all engine files, run:
```bash
cd backend && python -c "
from backend.engines.engine1_discovery import fetch_all_open_markets
from backend.engines.engine2_classification import classify_market, get_same_day_live_markets
from backend.engines.engine3_grouping import group_by_event_ticker
from backend.engines.engine4_orderbook import fetch_orderbooks
from backend.engines.engine5_ranking import rank_event_markets, rank_all_events
from backend.engines.engine6_progress_gate import create_candidate, process_all_events
from backend.engines.engine7_validation import validate_candidate
from backend.engines.engine8_orchestrator import run_one_shot, ScannerResult
print('All 8 engines import OK')
"
```

---

## Phase 4: Strategies

> **Cross-ref:** `docs/engines/strategy-system.md` defines all 7 experiments,
> the `EXPERIMENT_REGISTRY` pattern, and per-experiment pseudocode.
> Build from the pseudocode below.

**Critical change from earlier logic:** The old "most-bet" strategy used resting
orderbook quantity as a proxy for "most bet." The new default uses **executed
trade volume** from historical trades, which is a better signal for actual
betting activity. Experiment F (resting-depth-follower) preserves the original
logic for comparison.

**Verification:** After building all strategy files, run:
```bash
cd backend && python -c "
from backend.strategies import get_experiment, EXPERIMENT_REGISTRY
print('Available experiments:', list(EXPERIMENT_REGISTRY.keys()))
exp = get_experiment('executed-volume-follower', {})
print(f'Default experiment: {exp.name} — {exp.description}')
"
```

### 4.1 — `backend/strategies/base.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class MarketFeatures:
    market_ticker: str
    market_title: str
    result: Optional[str] = None
    status: str = ""
    total_executed_volume: float = 0.0
    yes_executed_volume: float = 0.0
    no_executed_volume: float = 0.0
    trade_count: int = 0
    yes_price: float = 0.0
    no_price: float = 0.0
    yes_best_bid: Optional[float] = None
    no_best_bid: Optional[float] = None
    yes_total_depth: Optional[float] = None
    no_total_depth: Optional[float] = None
    spread: Optional[float] = None
    yes_price_momentum: Optional[float] = None
    open_interest: Optional[float] = None

@dataclass
class EventFeatures:
    event_ticker: str
    event_title: str = ""
    category: str = ""
    event_progress: float = 0.0
    threshold: float = 0.0
    entry_time: Optional[datetime] = None
    child_markets: list = field(default_factory=list)

@dataclass
class TradeDecision:
    event_ticker: str = ""
    market_ticker: str = ""
    selected_side: str = ""
    trade_decision: str = "SKIP"
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

class StrategyExperiment(ABC):
    name: str = ""
    description: str = ""
    config: dict = {}

    def __init__(self, config: dict = None):
        self.config = config or {}

    @abstractmethod
    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        ...
```

### 4.2 — `backend/strategies/executed_volume_follower.py`

```python
from typing import Optional
from .base import StrategyExperiment, EventFeatures, TradeDecision

class ExecutedVolumeFollower(StrategyExperiment):
    name = "executed-volume-follower"
    description = "Highest executed trade volume → most-bet side"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        valid = [m for m in event_features.child_markets if m.total_executed_volume > 0]
        if not valid:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                trade_decision="SKIP",
                skip_reason="no_markets_with_volume",
                experiment_id=f"EXP_A_{int(event_features.threshold * 100)}",
            )
        selected = max(valid, key=lambda m: m.total_executed_volume)
        side = "YES" if selected.yes_executed_volume > selected.no_executed_volume else "NO"
        return TradeDecision(
            event_ticker=event_features.event_ticker,
            market_ticker=selected.market_ticker,
            selected_side=side,
            trade_decision=f"BUY_{side}",
            entry_price_cents=selected.yes_price if side == "YES" else selected.no_price,
            entry_threshold=event_features.threshold,
            event_progress_at_entry=event_features.event_progress,
            selected_market_reason="highest_executed_volume",
            selected_side_reason=f"{side.lower()}_executed_volume_gt_opposite",
            experiment_id=f"EXP_A_{int(event_features.threshold * 100)}",
        )
```

### 4.3 — `backend/strategies/executed_volume_fade.py`

```python
from .base import StrategyExperiment, EventFeatures, TradeDecision

class ExecutedVolumeFade(StrategyExperiment):
    name = "executed-volume-fade"
    description = "Highest volume market → fade the dominant side"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        valid = [m for m in event_features.child_markets if m.total_executed_volume > 0]
        if not valid:
            return TradeDecision(event_ticker=event_features.event_ticker, trade_decision="SKIP", skip_reason="no_markets_with_volume", experiment_id=f"EXP_B_{int(event_features.threshold * 100)}")
        selected = max(valid, key=lambda m: m.total_executed_volume)
        dominant = "YES" if selected.yes_executed_volume > selected.no_executed_volume else "NO"
        fade = "NO" if dominant == "YES" else "YES"
        return TradeDecision(event_ticker=event_features.event_ticker, market_ticker=selected.market_ticker, selected_side=fade, trade_decision=f"BUY_{fade}", entry_price_cents=selected.yes_price if fade == "YES" else selected.no_price, selected_market_reason="highest_executed_volume", selected_side_reason=f"fade_dominant_{dominant.lower()}", experiment_id=f"EXP_B_{int(event_features.threshold * 100)}")
```

### 4.4 — `backend/strategies/favorite_side_follower.py`

```python
from .base import StrategyExperiment, EventFeatures, TradeDecision

class FavoriteSideFollower(StrategyExperiment):
    name = "favorite-side-follower"
    description = "Highest volume market → buy the favorite (price > 50 = YES)"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        valid = [m for m in event_features.child_markets if m.total_executed_volume > 0]
        if not valid:
            return TradeDecision(event_ticker=event_features.event_ticker, trade_decision="SKIP", skip_reason="no_markets_with_volume", experiment_id=f"EXP_C_{int(event_features.threshold * 100)}")
        selected = max(valid, key=lambda m: m.total_executed_volume)
        side = "YES" if selected.yes_price > 50 else "NO"
        return TradeDecision(event_ticker=event_features.event_ticker, market_ticker=selected.market_ticker, selected_side=side, trade_decision=f"BUY_{side}", entry_price_cents=selected.yes_price if side == "YES" else selected.no_price, selected_market_reason="highest_executed_volume", selected_side_reason=f"favorite_side_{side.lower()}", experiment_id=f"EXP_C_{int(event_features.threshold * 100)}")
```

### 4.5 — `backend/strategies/momentum_follower.py`

```python
from .base import StrategyExperiment, EventFeatures, TradeDecision

class MomentumFollower(StrategyExperiment):
    name = "momentum-follower"
    description = "Largest absolute price move → direction of movement"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.early_reference = self.config.get("early_reference_progress", 0.40)

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        with_momentum = [m for m in event_features.child_markets if m.yes_price_momentum is not None]
        if not with_momentum:
            return TradeDecision(event_ticker=event_features.event_ticker, trade_decision="SKIP", skip_reason="no_momentum_data", experiment_id=f"EXP_D_{int(event_features.threshold * 100)}")
        selected = max(with_momentum, key=lambda m: abs(m.yes_price_momentum))
        side = "YES" if selected.yes_price_momentum > 0 else "NO"
        return TradeDecision(event_ticker=event_features.event_ticker, market_ticker=selected.market_ticker, selected_side=side, trade_decision=f"BUY_{side}", entry_price_cents=selected.yes_price if side == "YES" else selected.no_price, selected_market_reason="largest_absolute_price_move", selected_side_reason=f"momentum_toward_{side.lower()}", experiment_id=f"EXP_D_{int(event_features.threshold * 100)}")
```

### 4.6 — `backend/strategies/liquidity_filtered_follower.py`

```python
from .base import StrategyExperiment, EventFeatures, TradeDecision

class LiquidityFilteredFollower(StrategyExperiment):
    name = "liquidity-filtered-follower"
    description = "Volume follower with liquidity guards"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.min_volume = self.config.get("min_total_executed_volume", 500)
        self.min_trades = self.config.get("min_trade_count", 20)
        self.max_spread = self.config.get("max_spread_cents", 5)
        self.max_price = self.config.get("max_entry_price_cents", 85)
        self.min_price = self.config.get("min_entry_price_cents", 15)

    def _passes(self, m) -> bool:
        if m.total_executed_volume < self.min_volume: return False
        if m.trade_count < self.min_trades: return False
        if m.spread is not None and m.spread > self.max_spread: return False
        if m.yes_price > self.max_price or m.yes_price < self.min_price: return False
        return True

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        filtered = [m for m in event_features.child_markets if self._passes(m)]
        if not filtered:
            return TradeDecision(event_ticker=event_features.event_ticker, trade_decision="SKIP", skip_reason="no_markets_pass_filters", experiment_id=f"EXP_E_{int(event_features.threshold * 100)}")
        selected = max(filtered, key=lambda m: m.total_executed_volume)
        side = "YES" if selected.yes_executed_volume > selected.no_executed_volume else "NO"
        return TradeDecision(event_ticker=event_features.event_ticker, market_ticker=selected.market_ticker, selected_side=side, trade_decision=f"BUY_{side}", entry_price_cents=selected.yes_price if side == "YES" else selected.no_price, selected_market_reason="highest_executed_volume_with_filters", experiment_id=f"EXP_E_{int(event_features.threshold * 100)}")
```

### 4.7 — `backend/strategies/resting_depth_follower.py`

```python
from .base import StrategyExperiment, EventFeatures, TradeDecision

class RestingDepthFollower(StrategyExperiment):
    name = "resting-depth-follower"
    description = "Highest total resting depth → deeper side (original most-bet logic)"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        with_depth = [m for m in event_features.child_markets if m.yes_total_depth is not None and m.no_total_depth is not None]
        if not with_depth:
            return TradeDecision(event_ticker=event_features.event_ticker, trade_decision="SKIP", skip_reason="no_depth_data", experiment_id=f"EXP_F_{int(event_features.threshold * 100)}")
        selected = max(with_depth, key=lambda m: (m.yes_total_depth or 0) + (m.no_total_depth or 0))
        side = "YES" if (selected.yes_total_depth or 0) > (selected.no_total_depth or 0) else "NO"
        return TradeDecision(event_ticker=event_features.event_ticker, market_ticker=selected.market_ticker, selected_side=side, trade_decision=f"BUY_{side}", entry_price_cents=selected.yes_price if side == "YES" else selected.no_price, selected_market_reason="highest_total_resting_depth", experiment_id=f"EXP_F_{int(event_features.threshold * 100)}")
```

### 4.8 — `backend/strategies/hybrid_score_follower.py`

```python
from .base import StrategyExperiment, EventFeatures, TradeDecision

class HybridScoreFollower(StrategyExperiment):
    name = "hybrid-score-follower"
    description = "Weighted combination of volume, momentum, depth, and liquidity"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        child_markets = event_features.child_markets
        if not child_markets:
            return TradeDecision(event_ticker=event_features.event_ticker, trade_decision="SKIP", skip_reason="no_markets", experiment_id=f"EXP_G_{int(event_features.threshold * 100)}")

        # Normalize values across markets for scoring
        max_vol = max((m.total_executed_volume for m in child_markets), default=1)
        max_trades = max((m.trade_count for m in child_markets), default=1)
        max_momentum = max((abs(m.yes_price_momentum or 0) for m in child_markets), default=1)
        max_depth = max(((m.yes_total_depth or 0) + (m.no_total_depth or 0) for m in child_markets), default=1)

        def market_score(m):
            return (
                0.40 * (m.total_executed_volume / max_vol)
                + 0.25 * (m.trade_count / max_trades)
                + 0.20 * (abs(m.yes_price_momentum or 0) / max_momentum)
                + 0.15 * (((m.yes_total_depth or 0) + (m.no_total_depth or 0)) / max_depth)
            )

        selected = max(child_markets, key=market_score)
        side = "YES" if selected.yes_executed_volume > selected.no_executed_volume else "NO"
        return TradeDecision(event_ticker=event_features.event_ticker, market_ticker=selected.market_ticker, selected_side=side, trade_decision=f"BUY_{side}", entry_price_cents=selected.yes_price if side == "YES" else selected.no_price, selected_market_reason="highest_hybrid_score", experiment_id=f"EXP_G_{int(event_features.threshold * 100)}")
```

### 4.9 — `backend/strategies/__init__.py`

```python
from .base import StrategyExperiment, EventFeatures, MarketFeatures, TradeDecision
from .executed_volume_follower import ExecutedVolumeFollower
from .executed_volume_fade import ExecutedVolumeFade
from .favorite_side_follower import FavoriteSideFollower
from .momentum_follower import MomentumFollower
from .liquidity_filtered_follower import LiquidityFilteredFollower
from .resting_depth_follower import RestingDepthFollower
from .hybrid_score_follower import HybridScoreFollower

EXPERIMENT_REGISTRY: dict[str, type[StrategyExperiment]] = {
    "executed-volume-follower": ExecutedVolumeFollower,
    "executed-volume-fade": ExecutedVolumeFade,
    "favorite-side-follower": FavoriteSideFollower,
    "momentum-follower": MomentumFollower,
    "liquidity-filtered-follower": LiquidityFilteredFollower,
    "resting-depth-follower": RestingDepthFollower,
    "hybrid-score-follower": HybridScoreFollower,
}

def get_experiment(name: str, config: dict = None) -> StrategyExperiment:
    if name not in EXPERIMENT_REGISTRY:
        raise ValueError(f"Unknown experiment: {name}. Available: {list(EXPERIMENT_REGISTRY.keys())}")
    return EXPERIMENT_REGISTRY[name](config or {})
```

---

## Phase 5: Backtesting Infrastructure

> **Cross-ref:** `docs/engines/strategy-system.md` defines performance metrics
> and decision thresholds. The backtesting engine runs all 7 experiments
> against historical Kalshi data.

**Verification:** After building backtesting files, run:
```bash
cd backend && python -c "
from backend.strategies.backtesting.metrics import compute_metrics
print('Backtesting metrics module OK')
"
```

### 5.1 — `backend/strategies/backtesting/__init__.py`

```python
```

### 5.2 — `backend/strategies/backtesting/feature_builder.py`

```python
from datetime import datetime
from typing import Optional
from backend.strategies.base import MarketFeatures

def build_market_features(
    market_ticker: str,
    trades: list,
    candles: list,
    orderbook_snapshot: Optional[dict],
    entry_time: datetime,
    yes_price_at_entry: float,
    no_price_at_entry: float,
    reference_yes_price: Optional[float] = None,
) -> MarketFeatures:
    trades_before = [t for t in trades if t.trade_time < entry_time]
    total_vol = sum(t.count for t in trades_before)
    yes_vol = sum(t.count for t in trades_before if t.taker_side == "YES")
    no_vol = sum(t.count for t in trades_before if t.taker_side == "NO")

    return MarketFeatures(
        market_ticker=market_ticker,
        total_executed_volume=total_vol,
        yes_executed_volume=yes_vol,
        no_executed_volume=no_vol,
        trade_count=len(trades_before),
        yes_price=yes_price_at_entry,
        no_price=no_price_at_entry,
        yes_price_momentum=yes_price_at_entry - reference_yes_price if reference_yes_price else None,
        yes_total_depth=orderbook_snapshot.get("yes_total_depth") if orderbook_snapshot else None,
        no_total_depth=orderbook_snapshot.get("no_total_depth") if orderbook_snapshot else None,
        spread=orderbook_snapshot.get("spread") if orderbook_snapshot else None,
        yes_best_bid=orderbook_snapshot.get("yes_best_bid") if orderbook_snapshot else None,
        no_best_bid=orderbook_snapshot.get("no_best_bid") if orderbook_snapshot else None,
    )
```

### 5.3 — `backend/strategies/backtesting/entry_simulator.py`

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class FillResult:
    filled: bool
    price_cents: float
    fill_quantity: int
    mode: str  # "taker" | "maker"
    slippage_cents: float

def simulate_taker_entry(side: str, price_cents: float, quantity: int, spread_cents: float = 0.0) -> FillResult:
    execution_price = price_cents + (spread_cents if side == "YES" else spread_cents)
    return FillResult(filled=True, price_cents=execution_price, fill_quantity=quantity, mode="taker", slippage_cents=spread_cents)

def simulate_maker_entry(side: str, price_cents: float, quantity: int, best_bid: float, best_ask: float) -> FillResult:
    limit_price = best_bid if side == "YES" else (100 - best_ask)
    return FillResult(filled=True, price_cents=limit_price, fill_quantity=quantity, mode="maker", slippage_cents=0.0)
```

### 5.4 — `backend/strategies/backtesting/exit_simulator.py`

```python
from enum import Enum

class ExitReason(Enum):
    SETTLEMENT = "settlement"
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_STOP = "time_stop"
    EXIT_AT_PROGRESS = "exit_at_progress"

@dataclass
class ExitResult:
    exit_price_cents: float
    exit_reason: ExitReason
    pnl_cents: float
    roi_percent: float

def hold_to_settlement(entry_price: float, side: str, settlement_result: str) -> ExitResult:
    won = (side == settlement_result)
    payout = 100.0 if won else 0.0
    pnl = payout - entry_price
    return ExitResult(exit_price_cents=payout, exit_reason=ExitReason.SETTLEMENT, pnl_cents=pnl, roi_percent=(pnl / entry_price) * 100)
```

### 5.5 — `backend/strategies/backtesting/metrics.py`

```python
from dataclasses import dataclass, field
from typing import Optional
import statistics

@dataclass
class TradeResult:
    experiment_id: str
    threshold: float
    event_ticker: str
    market_ticker: str
    side: str
    entry_price: float
    exit_price: float
    won: bool
    pnl_cents: float
    roi_percent: float
    category: str = ""
    fill_mode: str = "taker"

@dataclass
class StrategyMetrics:
    experiment_id: str
    threshold: float
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_entry_price: float
    breakeven_win_rate: float
    gross_roi: float
    net_roi: float
    profit_factor: float
    max_drawdown: float
    sharpe_like: float
    avg_roi_per_trade: float
    category_rois: dict = field(default_factory=dict)

def compute_metrics(results: list[TradeResult]) -> StrategyMetrics:
    if not results:
        return StrategyMetrics(experiment_id="", threshold=0, total_trades=0, wins=0, losses=0, win_rate=0, avg_entry_price=0, breakeven_win_rate=0, gross_roi=0, net_roi=0, profit_factor=0, max_drawdown=0, sharpe_like=0, avg_roi_per_trade=0)

    wins = [r for r in results if r.won]
    losses_list = [r for r in results if not r.won]
    total_pnl = sum(r.pnl_cents for r in results)
    gross_profit = sum(r.pnl_cents for r in wins)
    gross_loss = abs(sum(r.pnl_cents for r in losses_list))

    entry_prices = [r.entry_price for r in results]
    rois = [r.roi_percent for r in results]

    return StrategyMetrics(
        experiment_id=results[0].experiment_id,
        threshold=results[0].threshold,
        total_trades=len(results),
        wins=len(wins),
        losses=len(losses_list),
        win_rate=len(wins) / len(results) if results else 0,
        avg_entry_price=statistics.mean(entry_prices) if entry_prices else 0,
        breakeven_wr=statistics.mean(entry_prices) / 100 if entry_prices else 0,
        gross_roi=gross_profit / (gross_profit + gross_loss) if (gross_profit + gross_loss) > 0 else 0,
        net_roi=total_pnl / (statistics.mean(entry_prices) * len(results)) if entry_prices else 0,
        profit_factor=gross_profit / gross_loss if gross_loss > 0 else float('inf'),
        max_drawdown=0.0,
        sharpe_like=statistics.mean(rois) / statistics.stdev(rois) if len(rois) > 1 and statistics.stdev(rois) > 0 else 0,
        avg_roi_per_trade=statistics.mean(rois) if rois else 0,
    )
```

### 5.6 — `backend/strategies/backtesting/backtest_engine.py`

```python
from datetime import datetime, timedelta
from typing import Optional
from backend.strategies import get_experiment, EXPERIMENT_REGISTRY
from backend.strategies.base import EventFeatures
from .feature_builder import build_market_features
from .entry_simulator import simulate_taker_entry
from .exit_simulator import hold_to_settlement
from .metrics import compute_metrics, TradeResult

def run_backtest(
    historical_events: list,
    get_trades_fn,
    get_candles_fn,
    thresholds: list[float] = None,
    experiment_names: list[str] = None,
    default_threshold: float = 0.60,
) -> dict:
    if thresholds is None:
        thresholds = [0.50, 0.60, 0.65, 0.75, 0.85]
    if experiment_names is None:
        experiment_names = list(EXPERIMENT_REGISTRY.keys())

    all_results = {}

    for event in historical_events:
        child_markets = event.get("child_markets", [])
        event_start = event["start_time"]
        event_end = event["end_time"]

        for threshold in thresholds:
            entry_time = event_start + (event_end - event_start) * threshold

            market_features_list = []
            for market in child_markets:
                trades = get_trades_fn(market["ticker"], entry_time)
                candles = get_candles_fn(market["ticker"], entry_time)
                mf = build_market_features(
                    market_ticker=market["ticker"],
                    trades=trades,
                    candles=candles,
                    orderbook_snapshot=None,
                    entry_time=entry_time,
                    yes_price_at_entry=market.get("yes_price", 50),
                    no_price_at_entry=market.get("no_price", 50),
                )
                market_features_list.append(mf)

            event_features = EventFeatures(
                event_ticker=event["event_ticker"],
                event_title=event.get("title", ""),
                category=event.get("category", ""),
                event_progress=threshold,
                threshold=threshold,
                entry_time=entry_time,
                child_markets=market_features_list,
            )

            for exp_name in experiment_names:
                experiment = get_experiment(exp_name, {})
                decision = experiment.select_trade(event_features)

                if decision.trade_decision == "SKIP":
                    continue

                fill = simulate_taker_entry(
                    side=decision.selected_side,
                    price_cents=decision.entry_price_cents or 50,
                    quantity=1,
                )

                exit_result = hold_to_settlement(
                    entry_price=fill.price_cents,
                    side=decision.selected_side,
                    settlement_result=event.get("result", "NO"),
                )

                result = TradeResult(
                    experiment_id=decision.experiment_id or exp_name,
                    threshold=threshold,
                    event_ticker=event["event_ticker"],
                    market_ticker=decision.market_ticker,
                    side=decision.selected_side,
                    entry_price=fill.price_cents,
                    exit_price=exit_result.exit_price_cents,
                    won=exit_result.pnl_cents > 0,
                    pnl_cents=exit_result.pnl_cents,
                    roi_percent=exit_result.roi_percent,
                    category=event.get("category", ""),
                )

                key = f"{exp_name}_{int(threshold * 100)}"
                if key not in all_results:
                    all_results[key] = []
                all_results[key].append(result)

    # Compute metrics per experiment × threshold
    metrics = {}
    for key, results in all_results.items():
        exp_name, thresh_str = key.rsplit("_", 1)
        metrics[key] = compute_metrics(results)

    return metrics
```

---

## Phase 6: Trading + Logging + Portfolio

> **Inspired by:** polymarket-arbitrage `core/execution.py`, `core/portfolio.py`, `utils/logging_utils.py`
> Uses signal-queue pattern with async processing loop, dry-run fill simulation,
> separate log files per event type, and full portfolio tracking.

### Files (in creation order)

```
backend/trading/portfolio.py           # Portfolio, PortfolioPosition, PnL tracking
backend/trading/execution_engine.py     # Signal queue, order lifecycle, dry-run sim
backend/trading/trade_executor.py       # Thin facade: validate → execution_engine.submit
backend/logging/csv_logger.py           # CSV per event type (candidates, trades, opportunities)
backend/logging/log_setup.py            # Logging initializer (separate files, rotation, custom levels)
```

**Verification:** After building all files, run:
```bash
cd backend && python -c "
from backend.trading.portfolio import Portfolio, PortfolioPosition, PortfolioStats
from backend.trading.execution_engine import ExecutionEngine, ExecutionConfig
from backend.trading.trade_executor import TradeExecutor
from backend.logging.csv_logger import CSVLogger
print('Trading + portfolio + logging modules import OK')
"
```

### 5.1 — `backend/trading/portfolio.py`

```python
"""
Portfolio tracking — positions, PnL, balance.
Mirrors polymarket-arbitrage core/portfolio.py but simplified for one-sided (most-bet) scanning.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from backend.core.models import TradeRecord

logger = logging.getLogger(__name__)


@dataclass
class PortfolioPosition:
    """A single position in one market (on one side)."""
    event_ticker: str
    market_ticker: str
    side: str                           # "yes" | "no"
    size: float = 0.0                   # Contracts held
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    cost_basis: float = 0.0
    trade_count: int = 0

    def unrealized_pnl(self, current_price: float) -> float:
        if self.size == 0:
            return 0.0
        return self.size * (current_price - self.avg_entry_price)

    @property
    def notional(self) -> float:
        return abs(self.size) * self.avg_entry_price


@dataclass
class PortfolioStats:
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_volume: float = 0.0

    @property
    def total_pnl(self) -> float:
        return self.total_realized_pnl + self.total_unrealized_pnl

    @property
    def win_rate(self) -> float:
        if self.winning_trades + self.losing_trades == 0:
            return 0.0
        return self.winning_trades / (self.winning_trades + self.losing_trades)


class Portfolio:
    """
    Tracks positions and PnL across all markets.
    Used by ExecutionEngine to record fills and by the API to report status.
    """

    def __init__(self, initial_balance: float = 0.0):
        self.initial_balance = initial_balance
        self.cash_balance = initial_balance
        self._positions: dict[str, PortfolioPosition] = {}  # key: f"{market_ticker}:{side}"
        self._trades: list[TradeRecord] = []
        self.stats = PortfolioStats()
        logger.info(f"Portfolio initialized with balance={initial_balance}")

    def record_fill(self, trade: TradeRecord):
        """Update portfolio from a trade fill (real or simulated)."""
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
        new_size = pos.size + trade.size
        total_cost = (pos.avg_entry_price * pos.size) + (trade.price * trade.size)
        pos.avg_entry_price = total_cost / new_size if new_size > 0 else 0
        pos.size = new_size
        pos.trade_count += 1
        self.cash_balance -= trade.price * trade.size

        # Track trade
        self._trades.append(trade)
        self.stats.total_trades += 1
        self.stats.total_volume += trade.price * trade.size

        if trade.price > pos.avg_entry_price:
            self.stats.winning_trades += 1
        else:
            self.stats.losing_trades += 1

    def get_position(self, market_ticker: str, side: str) -> Optional[PortfolioPosition]:
        return self._positions.get(f"{market_ticker}:{side}")

    def get_all_positions(self) -> list[PortfolioPosition]:
        return list(self._positions.values())

    def get_total_exposure(self) -> float:
        return sum(p.notional for p in self._positions.values())

    def get_pnl(self) -> dict:
        return {
            "realized": self.stats.total_realized_pnl,
            "unrealized": self.stats.total_unrealized_pnl,
            "total": self.stats.total_pnl,
        }

    def reset(self, new_balance: float = 0.0):
        self._positions.clear()
        self._trades.clear()
        self.cash_balance = new_balance
        self.stats = PortfolioStats()
```

### 5.2 — `backend/trading/execution_engine.py`

```python
"""
Execution engine with signal queue, async processing loop, order timeout monitoring,
and dry-run fill simulation. Mirrors polymarket-arbitrage core/execution.py.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable

from backend.core.models import (
    ProgressBasedOrderCandidate, ValidatedOrderCandidate,
    TradeRecord, ValidationConfig,
)
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.interfaces import StrategyProfile
from backend.engines.engine7_validation import validate_candidate
from backend.trading.portfolio import Portfolio

logger = logging.getLogger(__name__)


@dataclass
class ExecutionConfig:
    slippage_tolerance: float = 0.02
    order_timeout_seconds: float = 60.0
    dry_run: bool = True
    simulate_fills: bool = True
    fill_probability: float = 0.8


@dataclass
class ExecutionStats:
    orders_placed: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0
    orders_rejected: int = 0
    total_notional: float = 0.0
    signals_processed: int = 0
    slippage_rejections: int = 0


class ExecutionEngine:
    """
    Async order execution engine.
    
    - Consumes signals (validated candidates) via an asyncio.Queue
    - Processes them in a background task loop
    - Monitors order timeouts
    - Simulates fills in dry_run mode (with configurable probability)
    - Tracks open orders and execution stats
    """

    def __init__(
        self,
        adapter: KalshiAdapter,
        strategy: StrategyProfile,
        portfolio: Portfolio,
        mode: str = "dry_run",
        config: Optional[ExecutionConfig] = None,
    ):
        self.adapter = adapter
        self.strategy = strategy
        self.portfolio = portfolio
        self.mode = mode
        self.config = config or ExecutionConfig(dry_run=(mode == "dry_run"))
        self.stats = ExecutionStats()

        # Signal queue
        self._signal_queue: asyncio.Queue[ProgressBasedOrderCandidate] = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._timeout_monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Track open orders
        self._open_orders: dict[str, TradeRecord] = {}
        self._order_timestamps: dict[str, datetime] = {}

        # Shutdown event
        self._stop_event = asyncio.Event()

        logger.info(f"ExecutionEngine initialized (mode={mode}, simulate={self.config.simulate_fills})")

    async def start(self):
        if self._running:
            return
        self._running = True
        self._processing_task = asyncio.create_task(
            self._process_signals(), name="execution_signal_processor"
        )
        self._timeout_monitor_task = asyncio.create_task(
            self._monitor_order_timeouts(), name="execution_timeout_monitor"
        )
        logger.info("ExecutionEngine started")

    async def stop(self):
        self._running = False
        self._stop_event.set()
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        if self._timeout_monitor_task:
            self._timeout_monitor_task.cancel()
            try:
                await self._timeout_monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ExecutionEngine stopped")

    async def submit_signal(self, candidate: ProgressBasedOrderCandidate):
        """Submit a validated candidate for execution."""
        await self._signal_queue.put(candidate)
        self.stats.signals_processed += 1

    async def _process_signals(self):
        while self._running:
            try:
                candidate = await asyncio.wait_for(
                    self._signal_queue.get(), timeout=1.0
                )
                await self._execute_signal(candidate)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Signal processing error: {e}")

    async def _execute_signal(self, candidate: ProgressBasedOrderCandidate):
        """Execute a single signal (validated candidate)."""
        if self.mode == "read_only":
            logger.info(f"[READ-ONLY] Would execute: {candidate.event_ticker}")
            return

        validated = await validate_candidate(
            candidate, self.adapter, self.strategy, ValidationConfig()
        )
        if not validated.can_trade:
            logger.info(f"Signal rejected by validation: {candidate.event_ticker} — {validated.reason}")
            return

        side = validated.confirmed_side or candidate.most_bet_side
        price = candidate.selected_market_stats.best_yes_bid or 0.5
        size = candidate.total_resting_order_quantity

        if self.mode == "dry_run":
            await self._execute_dry_run(candidate, validated, side, price, size)
        else:
            await self._execute_live(candidate, validated, side, price, size)

    async def _execute_dry_run(self, candidate, validated, side, price, size):
        """Simulate execution — conditionally create a filled trade."""
        import random
        trade_id = f"dry_{uuid.uuid4().hex[:12]}"
        is_filled = (
            not self.config.simulate_fills
            or random.random() < self.config.fill_probability
        )
        trade = TradeRecord(
            trade_id=trade_id,
            event_ticker=candidate.event_ticker,
            market_ticker=candidate.selected_market.ticker,
            side=side,
            price=price,
            size=size if is_filled else 0,
            mode="dry_run",
            status="filled" if is_filled else "failed",
            timestamp=validated.validation_timestamp,
            validation_latency_ms=validated.validation_latency_ms,
        )
        self._open_orders[trade_id] = trade
        self._order_timestamps[trade_id] = datetime.utcnow()
        self.stats.orders_placed += 1
        if is_filled:
            self.stats.orders_filled += 1
            self.portfolio.record_fill(trade)
        logger.info(
            f"[DRY-RUN] {'FILLED' if is_filled else 'REJECTED'}: "
            f"{candidate.event_ticker} {side} {size:.2f}x@{price:.4f}"
        )

    async def _execute_live(self, candidate, validated, side, price, size):
        """Place a real order on Kalshi."""
        try:
            result = await self.adapter.place_order(
                ticker=candidate.selected_market.ticker,
                side=side,
                price=price,
                size=size,
            )
            trade_id = result.get("order_id", f"live_{uuid.uuid4().hex[:12]}")
            trade = TradeRecord(
                trade_id=trade_id,
                event_ticker=candidate.event_ticker,
                market_ticker=candidate.selected_market.ticker,
                side=side,
                price=price,
                size=size,
                mode="live",
                status="filled",
                timestamp=validated.validation_timestamp,
                validation_latency_ms=validated.validation_latency_ms,
            )
            self._open_orders[trade_id] = trade
            self._order_timestamps[trade_id] = datetime.utcnow()
            self.stats.orders_placed += 1
            self.stats.orders_filled += 1
            self.portfolio.record_fill(trade)
            logger.info(f"[LIVE] ORDER PLACED: {candidate.event_ticker} {side} {size:.2f}x@{price:.4f}")
        except Exception as e:
            logger.error(f"[LIVE] ORDER FAILED: {candidate.event_ticker} — {e}")
            self.stats.orders_rejected += 1

    async def _monitor_order_timeouts(self):
        """Periodically cancel orders that have been open too long."""
        while self._running:
            try:
                await asyncio.sleep(5.0)
                now = datetime.utcnow()
                expired = [
                    oid for oid, ts in self._order_timestamps.items()
                    if (now - ts).total_seconds() > self.config.order_timeout_seconds
                ]
                for oid in expired:
                    logger.info(f"Order {oid} timed out, cancelling")
                    self._open_orders.pop(oid, None)
                    self._order_timestamps.pop(oid, None)
                    self.stats.orders_cancelled += 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Timeout monitor error: {e}")

    @property
    def open_order_count(self) -> int:
        return len(self._open_orders)

    def get_stats(self) -> dict:
        return {
            "orders_placed": self.stats.orders_placed,
            "orders_filled": self.stats.orders_filled,
            "orders_cancelled": self.stats.orders_cancelled,
            "orders_rejected": self.stats.orders_rejected,
            "signals_processed": self.stats.signals_processed,
            "open_orders": self.open_order_count,
        }
```

### 5.3 — `backend/trading/trade_executor.py`

```python
"""
Thin facade — validates a candidate and submits it to the ExecutionEngine.
Kept for backward compat with the API layer; new code calls ExecutionEngine directly.
"""
from typing import Optional
from backend.core.models import ProgressBasedOrderCandidate
from backend.trading.execution_engine import ExecutionEngine

class TradeExecutor:
    def __init__(self, engine: ExecutionEngine):
        self.engine = engine

    async def execute(self, candidate: ProgressBasedOrderCandidate):
        await self.engine.submit_signal(candidate)
        return None, None  # Results now flow through portfolio + stats
```

### 5.4 — `backend/logging/log_setup.py`

```python
"""
Logging initializer — separate log files per event type, with rotation.
Mirrors polymarket-arbitrage utils/logging_utils.py.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Custom log levels
TRADE = 25      # Between INFO and WARNING
OPPORTUNITY = 26


def setup_logging(
    log_dir: str = "logs",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    main_log_file: str = "scanner.log",
    trades_log_file: str = "trades.log",
    opportunities_log_file: str = "opportunities.log",
    max_size_mb: int = 50,
    backup_count: int = 5,
):
    """Configure logging with per-event-type log files."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Register custom levels
    logging.addLevelName(TRADE, "TRADE")
    logging.addLevelName(OPPORTUNITY, "OPPORTUNITY")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, console_level.upper()))
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # Main log file
    main_handler = RotatingFileHandler(
        log_path / main_log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
    )
    main_handler.setLevel(getattr(logging, file_level.upper()))
    main_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(funcName)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(main_handler)

    # Trades log file (separate logger)
    trades_logger = logging.getLogger("trades")
    trades_handler = RotatingFileHandler(
        log_path / trades_log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
    )
    trades_handler.setLevel(logging.DEBUG)
    trades_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S.%f",
    ))
    trades_logger.addHandler(trades_handler)
    trades_logger.propagate = False

    # Opportunities log file (separate logger)
    opps_logger = logging.getLogger("opportunities")
    opps_handler = RotatingFileHandler(
        log_path / opportunities_log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
    )
    opps_handler.setLevel(logging.DEBUG)
    opps_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S.%f",
    ))
    opps_logger.addHandler(opps_handler)
    opps_logger.propagate = False

    # Reduce noise from libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    logging.info(f"Logging initialized | console={console_level} | file={file_level} | dir={log_dir}")
```

### 5.5 — `backend/logging/csv_logger.py`

```python
"""
CSV logging — one file per event type (candidates, trades, opportunities).
"""
import csv
import os
from datetime import datetime
from backend.core.models import ProgressBasedOrderCandidate, TradeRecord

class CSVLogger:
    """Logs candidates, trades, and opportunities to separate CSV files."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self):
        self._init_csv("candidates.csv", [
            "timestamp", "event_ticker", "market_ticker", "side",
            "progress_pct", "threshold_pct", "total_orders",
            "yes_orders", "no_orders", "actionable", "manual_review", "reasons",
        ])
        self._init_csv("trades.csv", [
            "timestamp", "trade_id", "event_ticker", "market_ticker",
            "side", "price", "size", "mode", "status", "latency_ms", "error",
        ])
        self._init_csv("opportunities.csv", [
            "timestamp", "event_ticker", "market_ticker", "side",
            "progress_pct", "total_orders", "yes_orders", "no_orders", "edge",
        ])

    def _init_csv(self, name: str, headers: list[str]):
        path = os.path.join(self.log_dir, name)
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(headers)

    def log_candidate(self, c: ProgressBasedOrderCandidate):
        path = os.path.join(self.log_dir, "candidates.csv")
        with open(path, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now().isoformat(), c.event_ticker,
                c.selected_market.ticker if c.selected_market else "",
                c.most_bet_side, f"{c.event_progress_percent:.1f}",
                c.threshold_percent, c.total_resting_order_quantity,
                c.yes_order_quantity, c.no_order_quantity,
                c.should_create_order_candidate, c.requires_manual_review,
                "; ".join(c.reasons),
            ])

    def log_trade(self, t: TradeRecord):
        path = os.path.join(self.log_dir, "trades.csv")
        with open(path, "a", newline="") as f:
            csv.writer(f).writerow([
                t.timestamp, t.trade_id, t.event_ticker, t.market_ticker,
                t.side, t.price, t.size, t.mode, t.status,
                f"{t.validation_latency_ms:.1f}", t.error or "",
            ])
```

---

## Phase 6: API Layer (FastAPI)

> **DRY**: Shared response helpers extracted to `api/errors.py` instead of
> being redefined in every route module.
> **Cross-ref:** `docs/api-contract.md` defines every REST endpoint schema.

### Files (in creation order)

```
backend/api/
  __init__.py
  errors.py           # APIResponse, ok(), err() — shared by all routes
  rest.py             # REST endpoints
  websocket_handler.py # WS connections
```

### 6.0 — `backend/api/errors.py` (DRY: shared response helpers)

> Extracted from the inline definitions in rest.py. Now reused by all route modules.

```python
from typing import Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from pydantic import BaseModel

ET = ZoneInfo("America/New_York")


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
    """Standard success response with timestamp."""
    return APIResponse(
        success=True,
        data=data,
        meta={"timestamp": datetime.now(ET).isoformat()},
    )


def err(code: str, message: str, status: int = 400, details: dict = None):
    """Standard error response as HTTP exception."""
    raise HTTPException(
        status_code=status,
        detail=APIError(code=code, message=message, details=details).model_dump(),
    )
```

**Verification:** After building all API files, start the backend and check:
```bash
cd backend && python -c "
from backend.api.errors import ok, err, APIResponse, APIError
resp = ok({'mode': 'dry_run'})
print(f'Response: success={resp.success}')
"
# Then start the server:
cd backend && uvicorn backend.main:app --reload &
sleep 2
curl -s http://localhost:8000/api/v1/scanner/status | python -m json.tool
```

### 6.1 — `backend/main.py`

```python
"""
Main entry point. Uses a TradingBot orchestrator (like polymarket-arbitrage TradingBot)
to initialize all components in order, wire them together, and manage the lifecycle.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import load_settings, Settings
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.scanner_state import ScannerState
from backend.strategies import get_experiment, StrategyExperiment
from backend.trading.portfolio import Portfolio
from backend.trading.execution_engine import ExecutionEngine, ExecutionConfig
from backend.logging.log_setup import setup_logging
from backend.api.rest import router as api_router
from backend.api.websocket_handler import router as ws_router

logger = logging.getLogger(__name__)


class TradingBot:
    """
    Orchestrator — creates all components, wires them, manages lifecycle.
    Mirrors polymarket-arbitrage main.py TradingBot.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._running = False
        self._stop_event = asyncio.Event()

        # Components (initialized in start())
        self.kalshi_client: KalshiClient = None
        self.kalshi_adapter: KalshiAdapter = None
        self.scanner_state = ScannerState()
        self.strategy: StrategyProfile = None
        self.portfolio: Portfolio = None
        self.execution_engine: ExecutionEngine = None
        self.mode: str = settings.scanner.default_mode

        # Background tasks
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        """Initialize all components in order."""
        self._running = True
        logger.info("=" * 60)
        logger.info("Nunu Scanner Bot Starting")
        logger.info("=" * 60)
        logger.info(f"Mode: {self.mode}")

        # 1. API client
        self.kalshi_client = KalshiClient(
            base_url=self.settings.kalshi.base_url,
            api_key=self.settings.kalshi_api_key_id,
            private_key=self.settings.kalshi_private_key,
            rate_limit=self.settings.kalshi.rate_limit,
        )
        await self.kalshi_client.__aenter__()

        # 2. Adapter
        self.kalshi_adapter = KalshiAdapter(self.kalshi_client)

        # 3. Experiment
        active = self.settings.strategy.active_experiment
        self.experiment = get_experiment(
            active,
            self.settings.strategy.experiments.get(active, {}),
        )

        # 4. Portfolio
        initial_balance = 10000.0 if self.mode == "dry_run" else 0.0
        self.portfolio = Portfolio(initial_balance=initial_balance)

        # 5. Execution engine
        self.execution_engine = ExecutionEngine(
            adapter=self.kalshi_adapter,
            strategy=self.strategy,
            portfolio=self.portfolio,
            mode=self.mode,
            config=ExecutionConfig(dry_run=(self.mode == "dry_run")),
        )
        await self.execution_engine.start()

        # 6. Scanner state
        self.scanner_state = ScannerState()

        logger.info("TradingBot started successfully")
        logger.info("-" * 60)

    async def stop(self):
        """Graceful shutdown — reverse order."""
        logger.info("TradingBot shutting down...")
        self._stop_event.set()
        self._running = False

        for task in self._tasks:
            task.cancel()

        await self.execution_engine.stop()
        await self.kalshi_client.__aexit__(None, None, None)
        logger.info("TradingBot stopped")


# ─── Bootstrap ────────────────────────────────────────────────────────────

settings = load_settings()
setup_logging(
    log_dir=settings.logging.csv_path.rsplit("/", 1)[0] if "/" in settings.logging.csv_path else "logs",
    console_level=settings.logging.level,
)

bot = TradingBot(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.start()
    yield
    await bot.stop()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"app": "nunu-scanner", "mode": bot.mode, "status": "running" if bot._running else "stopped"}
```

### 6.2 — `backend/api/rest.py`

FastAPI router with all REST endpoints.

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.main import bot
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
    state = bot.scanner_state
    return ok({
        "mode": bot.mode,
        "is_running": state.is_running,
        "connected_to_kalshi": bot.kalshi_client is not None,
        "markets_tracked": len(state.markets_by_ticker),
        "events_tracked": len(state.ranked_events),
        "active_candidates": sum(1 for c in state.candidates.values() if c.should_create_order_candidate),
        "last_discovery": state.last_discovery,
        "last_progress_check": state.last_progress_check,
    })

@router.post("/scanner/start")
async def start_scanner():
    """Run a one-shot scan."""
    state = bot.scanner_state
    state.is_running = True
    
    result = await run_one_shot(
        adapter=bot.kalshi_adapter,
        strategy=bot.strategy,
        threshold_percent=bot.settings.scanner.default_threshold,
        mode=bot.mode,
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
    events = list(bot.scanner_state.ranked_events.values())
    
    summaries = []
    for e in events:
        candidate = bot.scanner_state.get_candidate(e.event_ticker)
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
    event = bot.scanner_state.get_event(event_ticker)
    if not event:
        err("EVENT_NOT_FOUND", f"Event {event_ticker} not found.", 404)
    
    candidate = bot.scanner_state.get_candidate(event_ticker)
    
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
    candidates = list(bot.scanner_state.candidates.values())
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
    if bot.mode == "read_only":
        err("MODE_READ_ONLY", "Cannot approve in read-only mode.", 403)
    
    candidate = bot.scanner_state.get_candidate(event_ticker)
    if not candidate or not candidate.should_create_order_candidate:
        err("CANDIDATE_NOT_ACTIONABLE", "Candidate is not actionable.", 400)
    
    from backend.trading.trade_executor import TradeExecutor
    executor = TradeExecutor(bot.execution_engine)
    await executor.execute(candidate)
    
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
    if mode == "live" and not bot.settings.kalshi_private_key:
        err("AUTH_REQUIRED", "Kalshi API credentials not configured.", 401)
    
    previous = bot.mode
    bot.mode = mode
    return ok({"previous_mode": previous, "current_mode": mode})

@router.get("/config")
async def get_config():
    from backend.strategies import EXPERIMENT_REGISTRY
    return ok({
        "mode": bot.mode,
        "experiment": {
            "active_experiment": bot.settings.strategy.active_experiment,
        },
        "threshold_percent": bot.settings.scanner.default_threshold,
        "available_experiments": [
            {"name": name, "description": cls({}).description}
            for name, cls in EXPERIMENT_REGISTRY.items()
        ],
        "kalshi_connected": bot.kalshi_client is not None,
        "has_credentials": bool(bot.settings.kalshi_private_key),
    })

@router.put("/config")
async def update_config(experiment: str = None, threshold_percent: int = None):
    if experiment:
        from backend.strategies import get_experiment
        bot.experiment = get_experiment(experiment, {})
        bot.settings.strategy.active_experiment = experiment
    if threshold_percent:
        bot.settings.scanner.default_threshold = threshold_percent
    return await get_config()
```

---

## Phase 7: Frontend lib (Types + API Client)

> **IMPORTANT — implement against `docs/api-contract.md`:** This file is the
> binding contract between backend and frontend. Every TypeScript type below,
> every endpoint path, every request/response shape must match that spec exactly.
> The backend (Phase 6) and frontend implement independently against the same contract.

### Files (in creation order)

```
frontend/src/lib/types.ts          # TypeScript interfaces matching API contract
frontend/src/lib/api.ts             # ScannerAPI class
frontend/src/lib/constants.ts       # Constants
```

**Verification:** After building types and API client:
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -5
# Should show no type errors (or only errors for not-yet-created hook files)
```

### 7.1 — `frontend/src/lib/types.ts`

> **DRY**: This file mirrors `docs/api-contract.md`. The API contract is the
> single source of truth — types.ts is the TypeScript projection.
> Any change to an endpoint first updates the contract doc, then both
> backend (rest.py) and frontend (types.ts) independently.

Full TypeScript types matching the API contract. See `docs/api-contract.md` for the complete list.
Every `interface`, every union type, every field used by the frontend must be defined here.

Key types to define (full schemas in `docs/api-contract.md`):
```typescript
type ScannerMode = 'dry_run' | 'read_only' | 'live';
type CandidateSide = 'yes' | 'no' | 'tie' | 'none';
type TradeStatus = 'filled' | 'partial' | 'failed';

interface ScannerStatus { ... }          // GET /scanner/status response
interface StartResult { ... }            // POST /scanner/start response
interface EventSummary { ... }           // GET /events response item
interface EventDetail { ... }            // GET /events/{ticker} response
interface CandidateResponse { ... }      // GET /candidates response item
interface ValidatedCandidateResponse { ... }
interface ApproveResult { ... }
interface SwitchResult { ... }
interface ScannerConfigResponse { ... }  // GET /config response
```

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

---

## Phase 8: Frontend Hooks

**Verification:** After building all hooks:
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -5
```

### 8.1 — `frontend/src/hooks/useWebSocket.ts`

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

---

## Phase 9: Frontend Pages

### 9.1 — Pages (key pseudocode)

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

---

## Phase 10: Frontend Components

### 10.1 — Key Components

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

## Phase 11: Test Infrastructure

### 11.1 — Test setup

> **DRY**: Shared test factories in `tests/test_utils.py` are reused across
> all engine tests (create_sample_market, create_sample_orderbook, etc.).

```
tests/
  __init__.py
  conftest.py           # pytest fixtures (wires test_utils factories into pytest)
  test_utils.py          # DRY: shared factory functions (create_sample_market, etc.)
  test_engine1_discovery.py
  test_engine2_classification.py
  test_engine3_grouping.py
  test_engine4_orderbook.py
  test_engine5_ranking.py
  test_engine6_progress_gate.py
  test_engine7_validation.py
  test_engine8_orchestrator.py
  test_strategies.py
  test_api.py
  run_simulation.py     # Smoke test: runs pipeline against real Kalshi API
```

### 11.2 — `tests/test_utils.py` (DRY: shared factory functions)

```python
"""
Shared test factories — single source of truth for test data creation.
Used by conftest.py and directly by test modules.
"""
from backend.core.models.market import Market, Orderbook, OrderbookLevel, MarketOrderbookStats
from backend.core.models.classification import MarketClassification


def create_sample_market(
    ticker: str = "TEST-M1",
    event_ticker: str = "TEST",
    status: str = "active",
    yes_bid: str = "0.65",
    yes_ask: str = "0.70",
    no_bid: str = "0.30",
    no_ask: str = "0.35",
    volume_24h: str = "50000",
    total_volume: str = "100000",
) -> Market:
    return Market(
        ticker=ticker, event_ticker=event_ticker, status=status,
        title=f"Test market {ticker}",
        open_time="2026-06-17T00:00:00-04:00",
        close_time="2026-06-18T00:00:00-04:00",
        expected_expiration_time="2026-06-17T18:00:00-04:00",
        latest_expiration_time="2026-06-17T18:00:00-04:00",
        yes_bid=yes_bid, yes_ask=yes_ask, no_bid=no_bid, no_ask=no_ask,
        volume_24h=volume_24h, total_volume=total_volume,
    )


def create_sample_orderbook(
    market_id: str = "TEST-M1",
    yes_bids: list = None,
    no_bids: list = None,
) -> Orderbook:
    if yes_bids is None:
        yes_bids = [(0.65, 1000), (0.64, 500)]
    if no_bids is None:
        no_bids = [(0.35, 800), (0.34, 300)]
    return Orderbook(
        market_id=market_id,
        yes_bids=[OrderbookLevel(price=p, size=s) for p, s in yes_bids],
        no_bids=[OrderbookLevel(price=p, size=s) for p, s in no_bids],
    )


def create_classification(
    ticker: str = "TEST-M1",
    event_ticker: str = "TEST",
    same_day_live: bool = True,
) -> MarketClassification:
    return MarketClassification(
        ticker=ticker, event_ticker=event_ticker,
        live_now=same_day_live, expected_to_resolve_today=same_day_live,
        latest_expiration_today=same_day_live, same_day_live_market=same_day_live,
        reasons=[],
    )
```

### 11.2 — `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests that hit real Kalshi API
```

### 11.3 — `tests/conftest.py` (fixtures + helper functions)

> **DRY**: Helper factories (`create_sample_market`, `create_sample_orderbook`)
> are shared across all test files. Add common test data here.

```python
"""
Test fixtures and helpers — mirrors polymarket-arbitrage test pattern.
DRY: shared factory functions used by all test modules.
"""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from backend.core.models import (
    Market, Orderbook, OrderbookLevel, MarketOrderbookStats,
    MarketClassification, ClassifiedEvent, EventWithTopMarkets, RankedMarket,
    ProgressBasedOrderCandidate, TradeRecord,
)


# ─── Helper factory functions ─────────────────────────────────────────────

def create_sample_market(
    ticker: str = "TEST-M1",
    event_ticker: str = "TEST",
    status: str = "active",
    yes_bid: str = "0.65",
    yes_ask: str = "0.70",
    no_bid: str = "0.30",
    no_ask: str = "0.35",
    volume_24h: str = "50000",
    total_volume: str = "100000",
) -> Market:
    """Create a Market with sensible defaults for testing."""
    return Market(
        ticker=ticker,
        event_ticker=event_ticker,
        status=status,
        title=f"Test market {ticker}",
        open_time="2026-06-17T00:00:00-04:00",
        close_time="2026-06-18T00:00:00-04:00",
        expected_expiration_time="2026-06-17T18:00:00-04:00",
        latest_expiration_time="2026-06-17T18:00:00-04:00",
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        volume_24h=volume_24h,
        total_volume=total_volume,
    )


def create_sample_orderbook(
    market_id: str = "TEST-M1",
    yes_bids: list[tuple[float, float]] = None,
    no_bids: list[tuple[float, float]] = None,
) -> Orderbook:
    """Create an Orderbook with given price levels."""
    if yes_bids is None:
        yes_bids = [(0.65, 1000), (0.64, 500)]
    if no_bids is None:
        no_bids = [(0.35, 800), (0.34, 300)]
    return Orderbook(
        market_id=market_id,
        yes_bids=[OrderbookLevel(price=p, size=s) for p, s in yes_bids],
        no_bids=[OrderbookLevel(price=p, size=s) for p, s in no_bids],
    )


def create_classification(
    ticker: str = "TEST-M1",
    event_ticker: str = "TEST",
    same_day_live: bool = True,
) -> MarketClassification:
    """Create a MarketClassification for testing."""
    return MarketClassification(
        ticker=ticker,
        event_ticker=event_ticker,
        live_now=same_day_live,
        expected_to_resolve_today=same_day_live,
        latest_expiration_today=same_day_live,
        same_day_live_market=same_day_live,
        reasons=[],
    )


# ─── Standard fixtures ────────────────────────────────────────────────────

@pytest.fixture
def sample_market() -> Market:
    return create_sample_market()


@pytest.fixture
def sample_orderbook() -> Orderbook:
    return create_sample_orderbook()


@pytest.fixture
def sample_stats(sample_market, sample_orderbook) -> MarketOrderbookStats:
    from backend.adapters.kalshi.types import calculate_orderbook_stats
    return calculate_orderbook_stats(sample_market, sample_orderbook)


@pytest.fixture
def mock_adapter():
    """Returns an AsyncMock KalshiAdapter with sample data defaults."""
    mock = AsyncMock()
    mock.get_all_open_markets.return_value = [create_sample_market()]
    return mock


@pytest.fixture
def ranked_market(sample_market, sample_stats) -> RankedMarket:
    return RankedMarket(
        market=sample_market,
        classification=create_classification(),
        orderbook_stats=sample_stats,
    )
```

### 11.4 — Running tests

```bash
# Run all unit tests (fast — no API calls)
cd backend && python -m pytest -v -m "not slow"

# Run specific engine test
cd backend && python -m pytest tests/test_engine2_classification.py -v

# Run smoke test (hits real Kalshi API — needs .env configured)
cd backend && python tests/run_simulation.py

# Run full suite including slow tests
cd backend && python -m pytest -v
```

---

## Utility Scripts

### `scripts/test_connection.py` — Quick Kalshi API connectivity test

```python
#!/usr/bin/env python3
"""Quick connectivity test — mirrors polymarket-arbitrage test_connection.py."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.config.settings import load_settings
from backend.adapters.kalshi.client import KalshiClient


async def main():
    settings = load_settings()
    print(f"Testing connection to {settings.kalshi.base_url}")
    print(f"API key ID: {settings.kalshi_api_key_id[:8]}...")
    print(f"Private key configured: {bool(settings.kalshi_private_key)}")

    async with KalshiClient(
        base_url=settings.kalshi.base_url,
        api_key=settings.kalshi_api_key_id,
        private_key=settings.kalshi_private_key,
    ) as client:
        # Test market list
        print("\n1. Fetching open markets...")
        data = await client.list_markets(status="open", limit=5)
        markets = data.get("markets", [])
        print(f"   Got {len(markets)} markets (first 5)")
        if markets:
            m = markets[0]
            print(f"   Sample: {m.get('ticker')} — {m.get('title', '')[:60]}")

        # Test single market
        if markets:
            ticker = markets[0]["ticker"]
            print(f"\n2. Fetching market {ticker}...")
            m_detail = await client.get_market(ticker)
            if m_detail:
                print(f"   Status: {m_detail.get('status')}")
                print(f"   YES bid: {m_detail.get('yes_bid_dollars')}")

        # Test orderbook
        if markets:
            ticker = markets[0]["ticker"]
            print(f"\n3. Fetching orderbook for {ticker}...")
            ob = await client.get_orderbook(ticker)
            ob_fp = ob.get("orderbook_fp", {})
            yes_side = ob_fp.get("yes_dollars", [])
            no_side = ob_fp.get("no_dollars", [])
            print(f"   YES levels: {len(yes_side)}, NO levels: {len(no_side)}")

    print("\n✅ Connection test passed!")


if __name__ == "__main__":
    asyncio.run(main())
```

### `scripts/run_simulation.py` — Full pipeline smoke test

```python
#!/usr/bin/env python3
"""Full pipeline smoke test — mirrors polymarket-arbitrage test_real_data.py."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.config.settings import load_settings
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.strategies import get_experiment
from backend.engines.engine8_orchestrator import run_one_shot


async def main():
    settings = load_settings()
    async with KalshiClient(
        base_url=settings.kalshi.base_url,
        api_key=settings.kalshi_api_key_id,
        private_key=settings.kalshi_private_key,
    ) as client:
        adapter = KalshiAdapter(client)
        experiment = get_experiment(settings.strategy.active_experiment, {})
        result = await run_one_shot(adapter, experiment, mode="dry_run")

        print(f"\n{'='*60}")
        print(f"Scanner Result — {result.timestamp}")
        print(f"{'='*60}")
        print(f"Scanned markets: {result.scanned_market_count}")
        print(f"Same-day-live events: {len(result.events)}")
        print(f"Candidates generated: {len(result.candidates)}")
        print(f"  Actionable: {len(result.actionable)}")
        print(f"  Manual review: {len(result.manual_review)}")
        print(f"Validated: {len(result.validated)}")

        if result.actionable:
            print(f"\nTop 3 actionable:")
            for c in result.actionable[:3]:
                print(f"  {c.event_ticker}: {c.most_bet_side} @ {c.event_progress_percent:.1f}%")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for e in result.errors:
                print(f"  - {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 11.5 — Running the app

```bash
# Backend only (Phase 1)
cd backend && uvicorn backend.main:app --reload --port 8000

# Test connection first
cd backend && python scripts/test_connection.py

# Run full scanner pipeline (dry-run)
cd backend && python scripts/run_simulation.py

# Full stack via run.sh
./run.sh --phase 2
```

---

## Phase 12: Docker + Integration

### 12.1 — `docker-compose.yml`

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

### 12.2 — `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 12.3 — Dev Runner

The project root has a single `run.sh` script that starts everything:

```bash
# Phase 1: Backend only (uvicorn on :8000)
./run.sh

# Phase 2: Backend + Frontend
PHASE=2 ./run.sh

# Phase 3: Docker Compose
PHASE=3 ./run.sh
```

### 12.4 — Testing Script

```bash
# backend/tests/run_simulation.py
# Quick smoke test script to verify the pipeline works

python -c "
import asyncio
from backend.config.settings import load_settings
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.strategies import get_experiment
from backend.engines.engine8_orchestrator import run_one_shot

async def test():
    settings = load_settings()
    async with KalshiClient() as client:
        adapter = KalshiAdapter(client)
        experiment = get_experiment('executed-volume-follower')
        result = await run_one_shot(adapter, experiment, mode='dry_run')
        print(f'Scanned: {result.scanned_market_count} markets')
        print(f'Events: {len(result.events)}')
        print(f'Actionable: {len(result.actionable)}')
        for c in result.actionable[:3]:
            print(f'  {c.event_ticker}: {c.selected_side} @ {c.event_progress_percent:.1f}%')

asyncio.run(test())
"
```

---

## Full Build Execution Order (54 Steps)

Following this exact order ensures each file's dependencies exist before it's created.
Each step maps to the pseudocode in the corresponding phase section above.

```
Step 0:  mkdir -p backend/{config,core/{models,interfaces},utils,adapters/kalshi,engines/live,strategies,trading,logging,api}
         mkdir -p frontend/src/{lib,hooks,pages,components/{Dashboard,Orderbook,Candidates,Trading,Controls,Common},styles}
         mkdir -p config tests logs scripts

# ─── Phase 1: Backend Core (SOLID: split models/, interfaces/, utils/) ──
Step 1:  backend/core/models/market.py              # No deps (pure dataclass)
Step 2:  backend/core/models/classification.py      # Depends on market.py
Step 3:  backend/core/models/trading.py             # Depends on market.py, classification.py
Step 4:  backend/core/models/__init__.py            # Re-exports all model types
Step 5:  backend/core/interfaces/adapter.py         # Depends on models/
Step 6:  backend/core/interfaces/strategy.py        # Depends on models/
Step 7:  backend/core/interfaces/engine.py          # No deps
Step 8:  backend/core/interfaces/__init__.py        # Re-exports all interfaces
Step 9:  backend/core/scanner_state.py              # Depends on models/
Step 10: backend/utils/datetime_utils.py            # No deps (stdlib only)
Step 11: backend/utils/http_utils.py                # No deps (stdlib + httpx)
Step 12: backend/utils/auth_utils.py                # No deps (cryptography)
Step 13: backend/utils/poller.py                    # No deps (stdlib asyncio)
Step 14: backend/utils/__init__.py                  # Package marker
Step 15: backend/config/settings.py                 # No deps
Step 16: backend/config/defaults.py                 # Depends on settings.py

# ─── Phase 2: Kalshi Adapter (SRP: auth/http/client split) ────────────
Step 17: backend/adapters/kalshi/auth.py            # No deps (RSA-PSS signing)
Step 18: backend/adapters/kalshi/http_client.py     # No deps (HTTP transport)
Step 19: backend/adapters/kalshi/types.py           # Depends on core/models/
Step 20: backend/adapters/kalshi/client.py          # Depends on auth.py, http_client.py
Step 21: backend/adapters/kalshi/websocket.py       # Depends on auth.py
Step 22: backend/adapters/kalshi/adapter.py         # Depends on client.py, types.py

# ─── Phase 3: Engines (OCP: implement AbstractEngine) ──────────────────
Step 23: backend/engines/engine1_discovery.py       # Depends on adapter
Step 24: backend/engines/engine2_classification.py  # Depends on utils/datetime_utils.py
Step 25: backend/engines/engine3_grouping.py        # Depends on core/models/
Step 26: backend/engines/engine4_orderbook.py       # Depends on adapter, models
Step 27: backend/engines/engine5_ranking.py         # Depends on types.py, models
Step 28: backend/engines/engine6_progress_gate.py   # Depends on engine2, strategies
Step 29: backend/engines/engine7_validation.py      # Depends on engine2, engine5, strategies
Step 30: backend/engines/engine8_orchestrator.py    # Depends on E1-E7
Step 31: backend/engines/live/discovery_poller.py   # Depends on utils/poller.py
Step 32: backend/engines/live/event_reranker.py     # Depends on E5
Step 33: backend/engines/live/progress_gate_loop.py # Depends on utils/poller.py

# ─── Phase 4: Strategies (implement ISideSelector + IMarketSelector) ───
Step 34: backend/strategies/base.py                 # Depends on core/interfaces/
Step 35: backend/strategies/most_bet.py             # Depends on base.py
Step 36: backend/strategies/highest_volume.py       # Depends on base.py
Step 37: backend/strategies/widest_spread.py        # Depends on base.py
Step 38: backend/strategies/deepest_book.py         # Depends on base.py
Step 39: backend/strategies/momentum_shift.py       # Depends on base.py
Step 40: backend/strategies/custom_threshold.py     # Depends on most_bet.py
Step 41: backend/strategies/__init__.py             # Depends on all strategies

# ─── Phase 5: Trading + Logging + Portfolio ────────────────────────────
Step 42: backend/trading/portfolio.py               # No deps (core dataclasses)
Step 43: backend/trading/execution_engine.py        # Depends on portfolio, adapter, E7
Step 44: backend/trading/trade_executor.py          # Thin facade over execution_engine
Step 45: backend/logging/log_setup.py               # No deps (stdlib logging)
Step 46: backend/logging/csv_logger.py              # Depends on models

# ─── Phase 6: API Layer (DRY: shared errors.py) ────────────────────────
Step 47: backend/api/errors.py                      # No deps
Step 48: backend/api/rest.py                        # Depends on everything above
Step 49: backend/main.py                            # Depends on everything above

# ─── Phase 7-10: Frontend ──────────────────────────────────────────────
Step 50: frontend/src/lib/types.ts                  # No deps (mirrors API contract)
Step 51: frontend/src/lib/api.ts                    # Depends on types.ts
Step 52: frontend/src/hooks/useWebSocket.ts         # No deps
Step 53: frontend/src/hooks/useScanner.ts           # Depends on api.ts
Step 54: frontend/src/hooks/useCandidates.ts        # Depends on api.ts
Step 55: frontend/src/App.tsx                       # Depends on all pages
Step 56-61: frontend/src/pages/*.tsx                # Depends on hooks, api
Step 62-71: frontend/src/components/**/*.tsx        # Depends on types
```

---

## Scaffold Script

```bash
#!/bin/bash
# scripts/scaffold.sh — Create all directories

# SOLID: Separate dirs for models/, interfaces/, utils/ (was flat core/)
mkdir -p backend/{config,core/{models,interfaces},utils,adapters/kalshi,engines/live,strategies,trading,logging,api}
mkdir -p frontend/src/{lib,hooks,pages,components/{Dashboard,Orderbook,Candidates,Trading,Controls,Common},styles}
mkdir -p config tests logs scripts

# Core package (models/, interfaces/, utils/ each have __init__.py below)
touch backend/__init__.py
touch backend/core/__init__.py
touch backend/core/models/__init__.py
touch backend/core/interfaces/__init__.py
touch backend/utils/__init__.py
touch backend/config/__init__.py
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
