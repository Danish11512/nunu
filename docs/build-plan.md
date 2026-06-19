# Master Build Plan — Nunu Prediction Market Scanner

> **Single source of truth for implementation.** Follow the phases in order.
> Each phase links to detailed specs in other `.md` files when available.

---

## Quick Start (start here)

```bash
# 1. Prerequisites: Python 3.11+

# 2. Create directories
bash scripts/scaffold.sh

# 3. Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 4. Configure environment
cp .env.example .env
# → Edit .env with your Kalshi API credentials

# 5. Start development (backend + frontend)
./run.sh

# 6. Follow phases below — each tells you what to build and how to verify
```

> **⚠️ Implementation status (2026-06-18):** Phases 0–10 are complete.
> 
> > **Phase 11 (Pipeline Diagnostics Panel — spec complete 2026-06-18):**
> > A live diagnostics console in the Settings page that surfaces the scanner pipeline
> > stage-by-stage (E1→E7) and backend HTTP request traces — all pushed in real-time
> > over the existing `scanner` WebSocket channel. Full spec in Phase 11 below.
> > **Not yet implemented** — this is the next build target.
> 
> Phase 12 (Test Infrastructure) — **not yet implemented**.
> Phase 13 (Docker + Integration) — **not yet implemented**.
>
> **Pipeline bugfix — Kalshi API V2 field name alignment (2026-06-19):**
> `parse_market()` in `backend/adapters/kalshi/types.py` was using V1 API field names
> (`create_date`, `close_date`, `yes_ask`, `volume`) which don't exist in the V2 API.
> Fixed to use V2 equivalents (`created_time`, `close_time`, `yes_ask_dollars`,
> `volume_fp`, etc.). Added `_to_int()` helper for `_fp` string-to-int conversion.
> This was the root cause of the "zero same-day-live events" bug.
>
> **Auth resilience — one-line PEM format support (2026-06-19):**
> Added `_normalise_pem()` helper in `backend/utils/auth_utils.py` that reformats
> single-line PEM private keys (common in `.env` files) into the standard
> multi-line format required by `cryptography`. Both REST signer
> (`utils/auth_utils.KalshiSigner`) and WS signer
> (`adapters/kalshi/auth.KalshiSigner`) now use the shared helper.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
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
2. **Copy env template**: `cp .env.example .env`
3. **Fill in `.env`**: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY` (PEM), `KALSHI_FUNDER_ADDRESS`
4. **Create venv**: `python3 -m venv venv && source venv/bin/activate`
5. **Install Python deps**: `pip install -r backend/requirements.txt`
6. **Scaffold dirs**: `bash scripts/scaffold.sh` (creates all empty dirs + `__init__.py` files)
7. **Install frontend deps**: `cd frontend && bun install && cd ..`

---

## Build Execution Order (54 Steps)

Phases build in dependency order. Within each phase, create files in the order listed.
For the full detailed step list with pseudocode references, see the [Full Build Execution Order](#full-build-execution-order-62-steps) section at the end.

**Quick reference:**
```
Phase 0:  Scaffolding (dirs + configs)              — Step 0          ✅
Phase 1:  Backend Core + Utils                      — Steps 1–16      ✅
Phase 2:  Kalshi Adapter (SOLID split)              — Steps 17–22     ✅
Phase 3:  Engines + Live                            — Steps 23–33     ✅
Phase 4:  Strategies + Registry                     — Steps 34–41     ✅
Phase 5:  Backtesting Infrastructure                — Steps 42–46     ✅
Phase 6:  Trading + Logging + Portfolio             — Steps 47–51     ✅
Phase 7:  API Layer (DRY errors.py)                — Steps 52–54     ✅
Phase 8:  Frontend lib (Types + API Client)         — Steps 55–56     ✅
Phase 9:  Frontend Hooks + Pages                    — Steps 57–66     ✅
Phase 10: Frontend Components + API Alignment       — Steps 67–76     ✅
Phase 11: Pipeline Diagnostics Panel                — Steps 77–94     🔄
Phase 12: Test Infrastructure                       — After all steps ⬜
Phase 13: Docker + Integration                      — After all steps ⬜
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
                                            Phase 9: Frontend Hooks + Pages
                                                    │
                                            Phase 10: Frontend Components + API Alignment
                                                    │
                                            Phase 11: Pipeline Diagnostics Panel
                                                    │
                                            Phase 12: Test Infrastructure
                                                    │
                                            Phase 13: Docker + Integration
```

---

## Phase 0: Project Scaffolding

> **Scope**: Only what Phase 1 needs. Frontend (Phases 8–11) and Docker
> (Phase 13) will scaffold their files when those phases begin.

### Files to Create

```
backend/
  requirements.txt
  .env.example
  __init__.py

config/
  settings.yaml

.gitignore

scripts/
  scaffold.sh
```

### 0.1 — `run.sh` (project root)

Already exists at project root. Starts backend + frontend in parallel.
Auto-installs missing Python and JS dependencies.

### 0.2 — `backend/requirements.txt`

> **Phase-scoped**: Only Phase 1 deps listed here. Phase 2+ deps (fastapi,
> websockets, etc.) are added to this file when those phases begin.

```
# Phase 1: Backend Core (models, interfaces, utils, config)
pydantic==2.7.4
pydantic-settings==2.3.4
httpx==0.27.0
pyyaml==6.0.1
cryptography==42.0.8

# Phase 2+: Kalshi Adapter, API, WebSocket
fastapi==0.111.0
uvicorn[standard]==0.30.1
websockets==12.0
python-dateutil==2.9.0
python-dotenv==1.0.1
```

### 0.2 — `.env.example`

```
# Kalshi API
KALSHI_API_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
KALSHI_WS_BASE_URL=wss://api.elections.kalshi.com/trade-api/v2
KALSHI_API_KEY_ID=             # API key ID from Kalshi dashboard
KALSHI_PRIVATE_KEY=            # RSA private key in PEM format (for signing)
KALSHI_MEMBER_ID=              # Kalshi member ID (optional, Phase 6+)
KALSHI_FUNDER_ADDRESS=         # Optional, Phase 6+

# Scanner
SCANNER_DEFAULT_MODE=oneshot
SCANNER_DEFAULT_THRESHOLD=65
SCANNER_DEFAULT_STRATEGY=favorite-side-follower

# Logging
LOG_LEVEL=INFO
CSV_LOG_PATH=logs/scanner.csv
TRADE_HISTORY_PATH=logs/trades.json
```

### 0.3 — `config/settings.yaml`

> **Phase-scoped**: Only `kalshi`, `scanner`, `logging` sections needed for Phase 1.
> `strategy`, `validation`, `risk` sections are added when their phases begin.

```yaml
kalshi:
  base_url: "https://api.elections.kalshi.com/trade-api/v2"
  rate_limit: 10              # requests per second

scanner:
  default_mode: oneshot        # oneshot | live
  default_threshold: 65        # matches settings.py default
  default_strategy: favorite-side-follower
  discovery_poll_interval: 30  # seconds
  progress_gate_interval: 10   # seconds
  max_candidate_age: 30        # seconds

logging:
  level: INFO
  csv_path: "logs/scanner.csv"
  trade_history_path: "logs/trades.json"
```



---

## Phase 1: Backend Core

### SOLID Changes
- **SRP**: Split monolithic `models.py` into domain-specific modules (market, classification, trading)
- **DIP**: Extract abstract `Engine` interface from concrete engines
- **ISP**: Segregated `StrategyProfile` into single-method `select_trade()` interface (per ADR-018)

### Files (in creation order)

```
backend/core/
  __init__.py
  models/
    __init__.py               # Re-exports all models
    market.py                 # Market, Orderbook, OrderbookLevel, MarketOrderbookStats
    classification.py         # ClassificationResult, ClassifiedEvent
    trading.py                # OrderCandidate, TradeRecord, ValidationConfig, RiskConfig
  interfaces/
    __init__.py               # Re-exports all interfaces
    adapter.py                # AbstractMarketAdapter (ISP: read-only vs trading)
    strategy.py               # StrategyProfile with select_trade() (per ADR-018)
    engine.py                 # AbstractEngine (single-method interface)
  scanner_state.py

backend/config/
  __init__.py
  settings.py                  # Pydantic models for YAML + env config

backend/utils/
  __init__.py
  datetime_utils.py           # parse_date, day_key_et, same_et_day, calculate_progress
  http_utils.py               # RateLimiter, RetryHandler
  auth_utils.py               # RSA-PSS signer (extracted from client)
  poller.py                   # Generic async poller loop (used by live/ modules)
```

> **Note:** `config/defaults.py` and `utils/logging_utils.py` removed — their responsibilities
> are covered by `config/settings.py` (pydantic defaults) and `backend/logging/log_setup.py` (Phase 6).

**Verification:**
```bash
cd backend && python -c "
from backend.core.models import Market, OrderCandidate, ClassificationResult
from backend.core.interfaces import AbstractMarketAdapter, StrategyProfile, AbstractEngine
from backend.utils.datetime_utils import parse_date, calculate_progress
from backend.utils.http_utils import RateLimiter
from backend.utils.auth_utils import KalshiSigner
print('Phase 1: Core + Utils import OK')
"
```

### 1.1 — `backend/core/models/market.py`

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Market:
    """A single Kalshi prediction market contract."""

    ticker: str                    # e.g. "KXLYDYX"
    event_ticker: str              # e.g. "PRESIDENTS-DAY-24H"
    title: str
    status: str                    # "open" | "active" | "closed" | "settled"
    yes_ask: int | None            # Price in cents
    yes_bid: int | None
    no_ask: int | None
    no_bid: int | None
    volume: int                    # Total contracts traded
    open_interest: int
    expiry: datetime | None        # expected_expiration_time from API
    expiry_iso: str | None         # Raw ISO string for serialization
    create_date: str | None        # ISO date
    settlement_date: str | None
    close_date: str | None
    result: str | None             # "yes" | "no" | None (before settlement)
    rules_primary: str | None      # The main "Yes/No" rule
    rule_key: str | None
    volume_24h: int | None = None
    volume_24h_adjusted: int | None = None


@dataclass
class OrderbookLevel:
    """A single price level in the orderbook."""

    price: int          # In cents
    count: int          # Number of contracts at this level


@dataclass
class Orderbook:
    """Orderbook snapshot for a single market."""

    market_ticker: str
    yes_side: list[OrderbookLevel] = field(default_factory=list)
    no_side: list[OrderbookLevel] = field(default_factory=list)
    fetch_time: datetime | None = None


@dataclass
class MarketOrderbookStats:
    """Derived orderbook statistics for a market."""

    market_ticker: str               # NOT market_id — consistent with Market.ticker
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

### 1.2 — `backend/core/models/classification.py`

```python
from dataclasses import dataclass, field

from backend.core.models.market import Market


@dataclass
class ClassificationResult:
    """Result of running a classifier on a market."""

    market_ticker: str
    event_ticker: str
    is_same_day_live: bool = False
    confidence: float = 0.0        # 0.0 to 1.0
    reason: str = ""


@dataclass
class ClassifiedEvent:
    """A grouped event with classified markets."""

    event_ticker: str
    event_title: str
    event_start_date: str | None = None
    event_end_date: str | None = None
    event_description: str | None = None
    markets: list[Market] = field(default_factory=list)
    classification: ClassificationResult | None = None
    num_markets: int = 0
    total_volume: int = 0
```

### 1.3 — `backend/core/models/trading.py`

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RankedMarket:
    """A market with its ranking score and price data."""

    market_ticker: str
    volume: int
    spread_cents: int
    yes_price: int               # Current yes bid or valuation
    no_price: int                # Current no bid or valuation
    rank: int
    score: float                 # Composite ranking score


@dataclass
class EventWithTopMarkets:
    """An event with its top ranked markets."""

    event_ticker: str
    event_title: str
    top_markets: list[RankedMarket] = field(default_factory=list)
    total_volume: int = 0
    num_top_markets: int = 0


@dataclass
class OrderCandidate:
    """A potential trade order before validation."""

    event_ticker: str              # NOT event_id — consistent with Market.event_ticker
    market_ticker: str             # NOT market_id — consistent with Market.ticker
    side: str                      # "yes" or "no"
    price: int                     # Limit price in cents
    confidence: float = 0.0
    reason: str = ""
    volume: int = 0
    progress_pct: float = 0.0     # 0–100 scale
    created_at: datetime | None = None


@dataclass
class ProgressBasedOrderCandidate(OrderCandidate):
    """Candidate created by Engine 6 (progress gate)."""

    most_bet_side: str = ""        # NOT "selected_side" — see build plan
    threshold_pct: float = 0.0    # The threshold that was met
    is_overtime: bool = False
    # Note: progress_pct inherited from OrderCandidate (default 0.0)


@dataclass
class ValidatedOrderCandidate:
    """Candidate after Engine 7 validation."""

    original_candidate: OrderCandidate
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    estimated_entry_price: int = 0
    estimated_exit_price: int = 0
    max_contracts: int = 0


@dataclass
class TradeRecord:
    """A completed trade record."""

    market_ticker: str
    event_ticker: str
    side: str
    entry_price: int
    exit_price: int | None = None
    quantity: int = 0
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    pnl: float = 0.0
    status: str = "open"           # "open" | "closed" | "cancelled"
    trade_id: str = ""


@dataclass
class ValidationConfig:
    """Configuration for trade validation (Engine 7)."""

    max_spread_cents: int = 5
    min_volume: int = 100
    max_position_size: int = 1000
    min_confidence: float = 0.6
    allow_overtime: bool = False


@dataclass
class RiskConfig:
    """Risk management configuration."""

    max_position_size_per_market: int = 500
    max_position_size_per_event: int = 1000
    max_total_positions: int = 20
    max_daily_trades: int = 50
    stop_loss_cents: int = 20
    take_profit_cents: int = 40
```

### 1.4 — `backend/core/models/__init__.py`

```python
from backend.core.models.market import Market, OrderbookLevel, Orderbook, MarketOrderbookStats
from backend.core.models.classification import ClassificationResult, ClassifiedEvent
from backend.core.models.trading import (
    RankedMarket,
    EventWithTopMarkets,
    OrderCandidate,
    ProgressBasedOrderCandidate,
    ValidatedOrderCandidate,
    TradeRecord,
    ValidationConfig,
    RiskConfig,
)
```

### 1.5 — `backend/core/interfaces/` (SOLID: segregated interfaces)

> **ISP**: Instead of one monolithic `StrategyProfile`, we split into two single-method interfaces.
> **DIP**: Engines depend on `AbstractMarketAdapter`, not `KalshiAdapter`.
> **OCP**: Add new adapters by implementing `AbstractMarketAdapter` — no existing code changes.

#### `backend/core/interfaces/adapter.py`

```python
from abc import ABC, abstractmethod
from typing import Any


class MarketReader(ABC):
    """Read-only market data access."""

    @abstractmethod
    async def fetch_markets(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch all available markets."""
        ...

    @abstractmethod
    async def fetch_orderbook(self, ticker: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch orderbook for a single market by ticker."""
        ...

    @abstractmethod
    async def fetch_event(self, event_ticker: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch a single event by ticker."""
        ...

    @abstractmethod
    async def fetch_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch all events."""
        ...


class Trader(ABC):
    """Write-only trading operations."""

    @abstractmethod
    async def place_order(self, ticker: str, side: str, price: int, count: int, **kwargs: Any) -> dict[str, Any]:
        """Place a limit order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        """Cancel an existing order."""
        ...

    @abstractmethod
    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get current positions."""
        ...


class AbstractMarketAdapter(MarketReader, Trader, ABC):
    """Combined interface for full market access (read + write).

    Properties that adapters should provide:
    - name: str — adapter identifier
    - timezone: str — exchange timezone
    - supports_trading: bool — whether trading operations are available
    - supports_websocket: bool — whether websocket streaming is available
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""
        ...

    @property
    @abstractmethod
    def timezone(self) -> str:
        """Exchange timezone string (e.g. 'US/Eastern')."""
        ...

    @property
    @abstractmethod
    def supports_trading(self) -> bool:
        """Whether this adapter supports placing orders."""
        ...

    @property
    @abstractmethod
    def supports_websocket(self) -> bool:
        """Whether this adapter supports websocket streaming."""
        ...
```

#### `backend/core/interfaces/strategy.py` (single `select_trade()` per ADR-018)

> **ADR-018**: Single `select_trade()` replaces separate `select_market()` + `select_side()`.
> Strategies receive all pre-computed child market features and return a complete
> BUY_YES / BUY_NO / SKIP decision. The old split interfaces are removed.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MarketFeatures:
    """Features for a single market within an event."""
    ticker: str
    volume: int = 0
    volume_24h: int = 0
    yes_bid: int = 0
    yes_ask: int = 0
    no_bid: int = 0
    no_ask: int = 0
    spread_cents: int = 0
    last_price: int = 0
    open_interest: int = 0
    total_resting_order_quantity: int = 0
    progress_pct: float = 0.0


@dataclass
class EventFeatures:
    """Features computed for an event passed to the strategy."""
    event_ticker: str
    event_title: str = ""
    child_markets: list[MarketFeatures] = field(default_factory=list)
    total_volume: int = 0
    num_markets: int = 0
    num_markets_live: int = 0
    max_progress_pct: float = 0.0
    min_progress_pct: float = 0.0
    has_overtime: bool = False


@dataclass
class TradeDecision:
    """The decision returned by a strategy."""
    market_ticker: str
    side: str                              # "yes" or "no"
    confidence: float = 0.0
    reason: str = ""
    entry_price_cents: int = 0
    max_contracts: int = 0
    should_trade: bool = False


class StrategyProfile(ABC):
    """Base class for all trading strategies.

    Each strategy receives pre-computed EventFeatures with ALL child markets
    and returns a TradeDecision for a single market. The strategy gets full
    context to make the most informed decision.
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def select_trade(self, features: EventFeatures) -> TradeDecision:
        """Analyze event features and return a trade decision.

        The strategy receives ALL child markets in EventFeatures.child_markets
        and must choose the best one (or none) to trade.
        """
        ...

    def __repr__(self) -> str:
        return f"StrategyProfile(name={self.name!r})"
```

#### `backend/core/interfaces/engine.py` (OCP: new engines via implementation)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar


TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


@dataclass
class EngineContext:
    """Shared context passed through the engine pipeline."""
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class AbstractEngine(ABC, Generic[TInput, TOutput]):
    """Base class for all processing engines in the pipeline."""

    def __init__(self, name: str, context: EngineContext | None = None):
        self.name = name
        self.context = context or EngineContext()

    @abstractmethod
    async def process(self, data: TInput) -> TOutput:
        """Process input data and return transformed output.

        Args:
            data: Input data of type TInput

        Returns:
            Processed output of type TOutput
        """
        ...

    @abstractmethod
    async def validate(self, data: TInput) -> bool:
        """Validate whether the input can be processed.

        Args:
            data: Input data to validate

        Returns:
            True if input is valid and can be processed
        """
        ...

    async def __call__(self, data: TInput) -> TOutput:
        """Convenience: call the engine directly."""
        if not await self.validate(data):
            raise ValueError(f"Engine {self.name}: input validation failed")
        return await self.process(data)

    def __repr__(self) -> str:
        return f"AbstractEngine(name={self.name!r})"
```

#### `backend/core/interfaces/__init__.py`

```python
from backend.core.interfaces.adapter import MarketReader, Trader, AbstractMarketAdapter
from backend.core.interfaces.strategy import StrategyProfile, EventFeatures, MarketFeatures, TradeDecision
from backend.core.interfaces.engine import AbstractEngine, EngineContext
```

### 1.6 — `backend/core/scanner_state.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.core.models.classification import ClassifiedEvent
from backend.core.models.trading import EventWithTopMarkets, ValidatedOrderCandidate


@dataclass
class ScannerState:
    """Mutable state for the scanner's current cycle."""

    # Pipeline stages
    is_running: bool = False
    current_cycle: int = 0
    started_at: datetime | None = None
    cycle_started_at: datetime | None = None

    # Data flowing through pipeline
    markets: list[dict[str, Any]] = field(default_factory=list)
    classified_events: dict[str, ClassifiedEvent] = field(default_factory=dict)
    ranked_events: list[EventWithTopMarkets] = field(default_factory=list)
    candidates: list[ValidatedOrderCandidate] = field(default_factory=list)

    # Error tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Configuration snapshot for this cycle
    config_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScannerOutput:
    """Final output after a complete scanner cycle."""

    cycle: int = 0
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    # Results
    events: list[EventWithTopMarkets] = field(default_factory=list)
    trades: list[ValidatedOrderCandidate] = field(default_factory=list)

    # Summary
    num_events_scanned: int = 0
    num_markets_scanned: int = 0
    num_candidates_found: int = 0
    num_trades_executed: int = 0

    # Error tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CycleMetrics:
    """Metrics collected during a single scanner cycle."""

    cycle: int = 0
    duration_seconds: float = 0.0
    markets_fetched: int = 0
    events_classified: int = 0
    events_ranked: int = 0
    candidates_generated: int = 0
    candidates_validated: int = 0
    trades_placed: int = 0
    errors_encountered: int = 0
```

### 1.7 — `backend/utils/` (DRY: shared utilities extracted from engines and client)

#### `backend/utils/datetime_utils.py`

> **DRY**: Extracted from Engine 2 (parse_date, day_key_et, same_et_day) and
> Engine 6 (calculate_progress). Single source of truth for time handling.

```python
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# US Eastern timezone
ET = ZoneInfo("US/Eastern")
UTC = timezone.utc


def parse_date(date_str: str | None) -> datetime | None:
    """Parse ISO 8601 string to datetime. Handles 'Z' suffix and None."""
    if date_str is None:
        return None
    if date_str.endswith("Z") or date_str.endswith("z"):
        date_str = date_str[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def day_key_et(dt: datetime | None = None) -> str:
    """YYYY-MM-DD in America/New_York. Defaults to current ET time."""
    if dt is None or dt.tzinfo is None:
        dt = datetime.now(ET)
    return dt.astimezone(ET).strftime("%Y-%m-%d")


def same_et_day(dt1: datetime, dt2: datetime) -> bool:
    """True if both datetimes fall on the same calendar day in ET."""
    return day_key_et(dt1) == day_key_et(dt2)


def calculate_progress(
    expires_at: datetime,
    now: datetime | None = None,
    start_at: datetime | None = None,
) -> float:
    """
    0–100: time elapsed between start and expiry.
    
    If start_at is None, uses the midpoint between now and expires_at
    as the start (assumes the event started before now).
    Clamps to [0.0, 100.0].
    """
    if now is None:
        now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    total_seconds = (expires_at - (start_at or now)).total_seconds()
    elapsed_seconds = (expires_at - now).total_seconds()
    if total_seconds <= 0:
        return 100.0
    progress = (1.0 - (elapsed_seconds / total_seconds)) * 100.0
    return max(0.0, min(100.0, progress))
```

#### `backend/utils/http_utils.py`

> **DRY**: Extracted from client.py — rate limiter and retry handler reused
> across all HTTP-calling modules.

```python
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket rate limiter for API requests.

    Limits requests to `max_per_second` calls per second.
    """

    def __init__(self, max_per_second: int = 10):
        self.max_per_second = max_per_second
        self._timestamps: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request slot is available."""
        while True:
            async with self._lock:
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(seconds=1)
                while self._timestamps and self._timestamps[0] < cutoff:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.max_per_second:
                    self._timestamps.append(now)
                    return
            await asyncio.sleep(0.05)

    async def __aenter__(self) -> RateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


async def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_statuses: set[int] | None = None,
) -> Any:
    """Execute an async callable with exponential backoff retry.

    Args:
        func: Async callable to execute (e.g., lambda: client.get(...))
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds (caps exponential growth)
        retryable_statuses: HTTP status codes that trigger retry.
            Default: {429, 500, 502, 503, 504}

    Returns:
        The result of the callable

    Raises:
        httpx.HTTPStatusError: If non-retryable status or max retries exceeded
        httpx.RequestError: On network errors (retried up to max_retries)
    """
    if retryable_statuses is None:
        retryable_statuses = {429, 500, 502, 503, 504}

    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            last_exception = e
            if e.response.status_code not in retryable_statuses:
                raise
            if attempt >= max_retries:
                raise
            logger.warning(
                "HTTP %d on attempt %d/%d: %s",
                e.response.status_code,
                attempt + 1,
                max_retries,
                e.response.url,
            )
        except httpx.RequestError as e:
            last_exception = e
            if attempt >= max_retries:
                raise
            logger.warning(
                "Request error on attempt %d/%d: %s",
                attempt + 1,
                max_retries,
                e,
            )

        # Exponential backoff with jitter
        delay = min(base_delay * (2 ** attempt), max_delay)
        await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected: retry loop ended without result or exception")
```

#### `backend/utils/auth_utils.py`

> **SRP**: RSA-PSS signing extracted from KalshiClient. Single responsibility.

```python
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

logger = logging.getLogger(__name__)


class KalshiSigner:
    """RSA-PSS signer for Kalshi API authentication.

    Uses SHA-256 hashing with MGF1 padding (PSS) as required by Kalshi's API.
    """

    def __init__(self, private_key_pem: str | bytes):
        """Initialize with PEM-encoded RSA private key."""
        if isinstance(private_key_pem, str):
            private_key_pem = private_key_pem.encode("utf-8")
        self._private_key: RSAPrivateKey = serialization.load_pem_private_key(
            private_key_pem, password=None,
        )  # type: ignore[assignment]

    @classmethod
    def from_key_file(cls, key_path: str) -> KalshiSigner:
        """Load the private key from a PEM file."""
        with open(key_path, "rb") as f:
            pem_data = f.read()
        return cls(pem_data)

    def sign(self, message: str | bytes) -> str:
        """Sign a message using RSA-PSS and return base64-encoded signature.

        Args:
            message: The message to sign (string or bytes).

        Returns:
            Base64-encoded signature string.
        """
        if isinstance(message, str):
            message = message.encode("utf-8")
        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def generate_timestamp() -> str:
        """Generate a Kalshi-compatible ISO timestamp for signing."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
```

#### `backend/utils/poller.py` (DRY: generic async poller)

> **DRY**: The live/ modules (discovery_poller, progress_gate_loop) both follow
> the same poll-sleep pattern. Extracted into a reusable ABC poller.

```python
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class AsyncPoller(ABC):
    """Generic async poller — subclass and implement on_poll().

    Usage:
        class MyPoller(AsyncPoller):
            async def on_poll(self) -> None:
                # Do work here
                pass

        poller = MyPoller(interval_seconds=30)
        await poller.start()
        # ... later ...
        await poller.stop()
    """

    def __init__(
        self,
        interval_seconds: float = 30.0,
        name: str = "poller",
        jitter_seconds: float = 0.0,
    ):
        self.interval_seconds = interval_seconds
        self.name = name
        self.jitter_seconds = jitter_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._last_poll_time: datetime | None = None
        self._poll_count: int = 0

    @abstractmethod
    async def on_poll(self) -> None:
        """Called every poll interval. Override to implement work."""
        ...

    async def on_start(self) -> None:
        """Hook called when the poller starts. Override for setup."""
        pass

    async def on_stop(self) -> None:
        """Hook called when the poller stops. Override for cleanup."""
        pass

    async def on_error(self, exc: Exception) -> None:
        """Called when on_poll raises. Override for error handling."""
        logger.error(
            "Poller %s: error in cycle %d: %s",
            self.name, self._poll_count, exc, exc_info=True,
        )

    async def start(self) -> None:
        """Start the poller loop (non-blocking)."""
        if self._task is not None:
            logger.warning("Poller %s: already running", self.name)
            return
        await self.on_start()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("Poller %s: started (interval=%ds)", self.name, self.interval_seconds)

    async def stop(self) -> None:
        """Signal the poller to stop and wait for it."""
        if self._task is None:
            return
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=self.interval_seconds + 5)
        except asyncio.TimeoutError:
            logger.warning("Poller %s: stop timeout — cancelling task", self.name)
            self._task.cancel()
        except asyncio.CancelledError:
            pass
        self._task = None
        await self.on_stop()
        logger.info("Poller %s: stopped", self.name)

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def last_poll_time(self) -> datetime | None:
        return self._last_poll_time

    @property
    def poll_count(self) -> int:
        return self._poll_count

    async def poll_once(self) -> None:
        """Execute a single poll cycle immediately (bypasses interval)."""
        try:
            await self.on_poll()
            self._poll_count += 1
            self._last_poll_time = datetime.now(timezone.utc)
        except Exception as e:
            await self.on_error(e)

    async def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                await self.poll_once()
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.interval_seconds,
                    )
                    break
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("Poller %s: cancelled", self.name)
        except Exception as e:
            logger.error("Poller %s: fatal error in run loop: %s", self.name, e)
            raise
```

#### `backend/config/settings.py`

(Content unchanged — pydantic-settings loader. See full listing below.)

### 1.4 — `backend/config/settings.py`

Pydantic-settings loader with YAML + env support. Uses a YAML key map for
translation between snake_case YAML keys and pydantic field names.

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class KalshiConfig(BaseSettings):
    """Kalshi API connection configuration."""

    model_config = {"populate_by_name": True}

    api_base_url: str = Field(
        default="https://api.elections.kalshi.com/trade-api/v2",
        alias="KALSHI_API_BASE_URL",
    )
    ws_base_url: str = Field(
        default="wss://api.elections.kalshi.com/trade-api/v2",
        alias="KALSHI_WS_BASE_URL",
    )
    key_id: str = Field(default="", alias="KALSHI_API_KEY_ID")
    private_key_path: str = Field(default="", description="Path to RSA private key PEM file")
    private_key: str = Field(default="", alias="KALSHI_PRIVATE_KEY")
    member_id: str = Field(default="", alias="KALSHI_MEMBER_ID")
    funder_address: str = Field(default="", alias="KALSHI_FUNDER_ADDRESS")
    rate_limit: int = Field(default=10)
    max_retries: int = Field(default=3)
    timeout_seconds: int = Field(default=30)
    max_connections: int = Field(default=20)


class ScannerConfig(BaseSettings):
    """Scanner behavior configuration."""

    model_config = {"populate_by_name": True}

    default_mode: str = Field(default="oneshot", alias="SCANNER_DEFAULT_MODE")
    default_threshold: int = Field(default=65, alias="SCANNER_DEFAULT_THRESHOLD")
    default_strategy: str = Field(default="favorite-side-follower", alias="SCANNER_DEFAULT_STRATEGY")
    min_markets_per_event: int = Field(default=3)
    min_volume_before_entry: int = Field(default=100)
    min_side_signal_strength: float = Field(default=0.50)
    max_candidates_per_cycle: int = Field(default=10)
    poll_interval_seconds: int = Field(default=30)
    progress_check_interval_seconds: int = Field(default=10)
    max_event_expiry_hours: int = Field(default=48)
    exclude_expired: bool = Field(default=True)
    out_dir: str = Field(default="./kalshi_out")


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = {"populate_by_name": True}

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    format: str = Field(default="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    file: str = Field(default="")
    csv_path: str = Field(default="", alias="CSV_LOG_PATH")
    trade_history_path: str = Field(default="", alias="TRADE_HISTORY_PATH")


class StrategyConfig(BaseSettings):
    """Strategy configuration (forward-looking for Phase 4+)."""

    model_config = {"populate_by_name": True}

    name: str = Field(default="")
    params: dict[str, Any] = Field(default_factory=dict)


class ValidationConfigSection(BaseSettings):
    """Validation rules (forward-looking for Phase 6+)."""

    model_config = {"populate_by_name": True}

    max_spread_cents: int = Field(default=5)
    min_volume: int = Field(default=100)
    max_position_size: int = Field(default=1000)
    min_confidence: float = Field(default=0.6)
    allow_overtime: bool = Field(default=False)


class RiskConfigSection(BaseSettings):
    """Risk management limits (forward-looking for Phase 6+)."""

    model_config = {"populate_by_name": True}

    max_position_size_per_market: int = Field(default=500)
    max_position_size_per_event: int = Field(default=1000)
    max_total_positions: int = Field(default=20)
    max_daily_trades: int = Field(default=50)
    stop_loss_cents: int = Field(default=20)
    take_profit_cents: int = Field(default=40)


class Settings(BaseSettings):
    """Root settings aggregating all sub-configs."""

    kalshi: KalshiConfig = Field(default_factory=KalshiConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    validation: ValidationConfigSection = Field(default_factory=ValidationConfigSection)
    risk: RiskConfigSection = Field(default_factory=RiskConfigSection)

    model_config = {"env_nested_delimiter": "__", "populate_by_name": True}


def load_settings(config_path: str | None = None) -> Settings:
    """Load settings from YAML file, overlaying env vars."""
    if config_path is None:
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            candidate = parent / "config" / "settings.yaml"
            if candidate.exists():
                config_path = str(candidate)
                break
        if config_path is None:
            config_path = "config/settings.yaml"

    settings = Settings()
    if os.path.exists(config_path):
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f) or {}
        # Apply YAML sections using field name mapping
        _YAML_KEY_MAP = {
            "kalshi": {"base_url": "api_base_url"},
            "scanner": {
                "discovery_poll_interval": "poll_interval_seconds",
                "progress_gate_interval": "progress_check_interval_seconds",
            },
        }
        for section, mapping in _YAML_KEY_MAP.items():
            if section in yaml_config:
                raw = yaml_config[section]
                translated = {mapping.get(k, k): v for k, v in raw.items()}
                setattr(settings, section, type(getattr(settings, section))(**translated))
    return settings
```

---

## Phase 2: Kalshi Adapter (SOLID refactored)

> **SRP**: Split monolithic `client.py` into single-responsibility modules.
> **DIP**: `KalshiAdapter` implements `AbstractMarketAdapter` from `core/interfaces/`.
> **Auth split**: REST uses RSA-PSS `KalshiSigner` from `backend.utils.auth_utils`;
> WebSocket uses PKCS1v15 `KalshiSigner` from `.auth`.
> **Cross-ref:** `docs/adapters/adapter-contract.md`.

### Files (in creation order)

```
backend/adapters/kalshi/
  __init__.py           # Exports public API
  auth.py               # PKCS1v15 signing — WebSocket ONLY
  http_client.py        # Raw HTTP + rate limiting + retry (uses utils.RateLimiter)
  client.py             # Kalshi REST methods (uses utils.auth_utils KalshiSigner for RSA-PSS)
  types.py              # Parsers + stats calculators
  websocket.py          # WS client (uses auth.py for PKCS1v15 connect signing)
  adapter.py            # Facade: implements AbstractMarketAdapter fully
```

**Verification:**
```bash
cd backend && python -c "
from backend.adapters.kalshi.auth import KalshiSigner as WsSigner
from backend.adapters.kalshi.http_client import KalshiHttpClient
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.types import parse_market, parse_orderbook, calculate_orderbook_stats
from backend.adapters.kalshi.websocket import KalshiWebSocket
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.adapters.kalshi import KalshiAdapter as ExportedAdapter
from backend.core.interfaces import AbstractMarketAdapter

print('Kalshi adapter classes import OK')
assert issubclass(KalshiAdapter, AbstractMarketAdapter), 'KalshiAdapter must implement AbstractMarketAdapter'

# Verify all ABC methods are implemented
import inspect
missing = [m for m in ('fetch_markets', 'fetch_orderbook', 'fetch_event', 'fetch_events',
                        'place_order', 'cancel_order', 'get_positions')
           if not hasattr(KalshiAdapter, m) or not inspect.iscoroutinefunction(getattr(KalshiAdapter, m))]
assert not missing, f'Missing ABC methods: {missing}'

# Verify convenience methods
for m in ('get_all_open_markets', 'get_market', 'get_orderbook', 'get_orderbook_stats'):
    assert hasattr(KalshiAdapter, m), f'Missing convenience method: {m}'

# Verify properties
k = KalshiAdapter.__new__(KalshiAdapter)
assert k.name == 'kalshi'
assert k.timezone == 'US/Eastern'
assert k.supports_trading is True
assert k.supports_websocket is True

print('All Phase 2 interface contracts verified ✓')
"
```

### 2.1 — `backend/adapters/kalshi/auth.py`

> **SRP**: Single responsibility — RSA-PKCS1v15 request signing. Used ONLY by
> WebSocket (`websocket.py`). REST calls use the RSA-PSS signer from
> `backend.utils.auth_utils` instead.
> Raises immediately if credentials are missing — no silent fallback.

```python
from __future__ import annotations

import base64
import logging
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)


class KalshiSigner:
    """RSA-PKCS1v15 request signing for Kalshi WebSocket authentication.

    Uses three headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE,
    KALSHI-ACCESS-TIMESTAMP. PKCS1v15 padding is correct for WebSocket auth.

    NOTE: This signer is WebSocket-only. REST API calls use the RSA-PSS
    signer from `backend.utils.auth_utils.KalshiSigner`.
    """

    def __init__(self, api_key_id: str = "", private_key_pem: Optional[str] = None):
        if not api_key_id:
            raise ValueError("KalshiSigner: api_key_id is required")
        if not private_key_pem:
            raise ValueError("KalshiSigner: private_key_pem is required")
        self.api_key_id = api_key_id
        self.private_key_pem = private_key_pem

    def sign(self, method: str, path: str, body: str = "") -> tuple[str, str, str]:
        """Sign a Kalshi API request.

        Returns (api_key_id, signature_b64, timestamp_ms).
        Raises ValueError if private key is not configured.
        """
        if not self.private_key_pem:
            raise ValueError("KalshiSigner: private_key_pem not configured — cannot sign")

        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + path + body

        private_key = serialization.load_pem_private_key(
            self.private_key_pem.encode("utf-8") if isinstance(self.private_key_pem, str) else self.private_key_pem,
            password=None,
        )
        signature = private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return self.api_key_id, base64.b64encode(signature).decode(), timestamp

    def get_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        """Convenience: returns dict of KALSHI-ACCESS-* headers."""
        key, sig, ts = self.sign(method, path, body)
        return {
            "KALSHI-ACCESS-KEY": key,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }
```

### 2.2 — `backend/adapters/kalshi/http_client.py`

> **SRP**: Single responsibility — raw HTTP transport with rate limiting and
> retry logic. No knowledge of Kalshi endpoints or auth.
> Uses `RateLimiter` from `backend.utils.http_utils` instead of inline semaphore.

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from backend.utils.http_utils import RateLimiter, retry_with_backoff

logger = logging.getLogger(__name__)


class KalshiHttpClient:
    """Raw HTTP transport for Kalshi API.

    - Connection pooling via httpx.AsyncClient
    - Rate limiting via backend.utils.http_utils.RateLimiter
    - Retry with exponential backoff via backend.utils.http_utils.retry_with_backoff
    - Auth headers injected at call time (caller provides signer)
    """

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(
        self,
        base_url: str | None = None,
        rate_limit: int = 10,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(max_per_second=rate_limit)
        self.timeout = timeout
        self.max_retries = max_retries

    async def __aenter__(self) -> KalshiHttpClient:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HTTP client not initialized. Use 'async with'.")
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        auth_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Rate-limited request with retry. Auth headers injected by caller."""
        async with self._rate_limiter:
            url = f"{self.base_url}{path}"
            headers = {**(kwargs.pop("headers", {})), **(auth_headers or {})}

            async def _do_request() -> dict[str, Any]:
                response = await self.client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()

            async def _request_with_retry() -> dict[str, Any]:
                for attempt in range(self.max_retries):
                    try:
                        return await _do_request()
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            # Rate limited — parse retry-after, cap at 30s
                            raw = e.response.headers.get("retry-after", "1")
                            try:
                                retry_after = min(int(raw), 30)
                            except (ValueError, TypeError):
                                retry_after = min(2**attempt, 30)
                            logger.warning(
                                "Rate limited (attempt %d/%d). Retrying in %ds.",
                                attempt + 1, self.max_retries, retry_after,
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        # Non-retryable status — propagate immediately
                        raise
                    except (httpx.TimeoutException, httpx.NetworkError) as e:
                        if attempt == self.max_retries - 1:
                            raise
                        delay = min(2**attempt, 10)
                        logger.warning(
                            "Request error (attempt %d/%d): %s. Retrying in %ds.",
                            attempt + 1, self.max_retries, e, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                raise RuntimeError(f"Request failed after {self.max_retries} retries.")

            return await _request_with_retry()
```

### 2.3 — `backend/adapters/kalshi/client.py`

> **SRP**: Kalshi-specific REST methods only. Uses the **RSA-PSS** `KalshiSigner`
> from `backend.utils.auth_utils` for REST auth headers (NOT `auth.py`, which is
> PKCS1v15 for WebSocket only). Delegates transport to `KalshiHttpClient`.
> Thin — delegates signing and HTTP to components.

```python
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from backend.utils.auth_utils import KalshiSigner  # RSA-PSS signer for REST

from .http_client import KalshiHttpClient

logger = logging.getLogger(__name__)


class KalshiClient:
    """Kalshi REST API client — endpoint-specific methods only.

    Uses RSA-PSS signing (from backend.utils.auth_utils) for REST auth.
    WebSocket auth uses the PKCS1v15 signer from `.auth` instead.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key_id: str = "",
        private_key: str = "",
        rate_limit: int = 10,
    ):
        self.http = KalshiHttpClient(base_url=base_url, rate_limit=rate_limit)
        # RSA-PSS signer for REST — NOT the PKCS1v15 one from .auth
        self.signer = KalshiSigner(private_key_pem=private_key)
        self.api_key_id = api_key_id

    async def __aenter__(self) -> KalshiClient:
        await self.http.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.http.__aexit__(*args)

    # ── Auth helpers ──────────────────────────────────────────────

    def _sign_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        """Generate KALSHI-ACCESS-* headers using RSA-PSS signer."""
        ts = KalshiSigner.generate_timestamp()
        message = ts + method.upper() + path + body
        sig = self.signer.sign(message)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }

    # ── Market endpoints ──────────────────────────────────────────

    async def list_markets(
        self, status: str = "open", limit: int = 1000, cursor: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        headers = self._sign_headers("GET", "/markets")
        return await self.http.request("GET", "/markets", headers=headers, params=params)

    async def get_market(self, ticker: str) -> Optional[dict[str, Any]]:
        path = f"/markets/{ticker}"
        headers = self._sign_headers("GET", path)
        try:
            data = await self.http.request("GET", path, headers=headers)
            return data.get("market")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_event(self, event_ticker: str) -> Optional[dict[str, Any]]:
        """Fetch a single event by ticker (wraps /events/{event_ticker})."""
        path = f"/events/{event_ticker}"
        headers = self._sign_headers("GET", path)
        try:
            data = await self.http.request("GET", path, headers=headers)
            return data.get("event")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def list_events(
        self, status: str = "open", limit: int = 100, cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetch all events (wraps /events)."""
        params: dict[str, Any] = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        headers = self._sign_headers("GET", "/events")
        return await self.http.request("GET", "/events", headers=headers, params=params)

    async def get_orderbook(self, ticker: str) -> dict[str, Any]:
        path = f"/markets/{ticker}/orderbook"
        headers = self._sign_headers("GET", path)
        return await self.http.request("GET", path, headers=headers)

    # ── Trading endpoints ─────────────────────────────────────────

    async def place_order(
        self, ticker: str, side: str, price: int, count: int, **kwargs: Any
    ) -> dict[str, Any]:
        """Place a limit order.

        Args:
            ticker: Market ticker (e.g. "KXLYDYX").
            side: "yes" or "no" — mapped to Kalshi V2 API values.
            price: Limit price in integer cents.
            count: Number of contracts (integer).
            **kwargs: Additional order params (time_in_force, etc.).

        Returns:
            dict with order response (e.g. {"order_id": "..."}).
        """
        body: dict[str, Any] = {
            "ticker": ticker,
            "side": side,  # Kalshi V2 uses "yes"/"no"
            "type": "limit",
            "price": price,       # integer cents
            "count": count,       # integer contracts
            "time_in_force": kwargs.get("time_in_force", "GTC"),
        }
        payload = json.dumps(body, separators=(",", ":"))
        path = "/portfolio/orders"
        headers = self._sign_headers("POST", path, payload)
        headers["Content-Type"] = "application/json"
        return await self.http.request("POST", path, headers=headers, content=payload)

    async def cancel_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        """Cancel an existing order by ID."""
        path = f"/portfolio/orders/{order_id}"
        headers = self._sign_headers("DELETE", path)
        return await self.http.request("DELETE", path, headers=headers)

    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get current positions."""
        path = "/portfolio/positions"
        headers = self._sign_headers("GET", path)
        data = await self.http.request("GET", path, headers=headers)
        return data.get("positions", [])

    # ── Pagination ────────────────────────────────────────────────

    async def fetch_all_open_markets(self, max_pages: int = 100) -> list[dict[str, Any]]:
        """Paginate through all open markets, deduplicate by ticker.

        Uses a while-loop guard (max_pages) as a circuit-breaker.
        Wraps each page fetch in try/except to allow partial results.
        """
        all_markets: list[dict[str, Any]] = []
        cursor: str | None = None
        pages_fetched = 0

        while pages_fetched < max_pages:
            try:
                data = await self.list_markets(cursor=cursor)
                all_markets.extend(data.get("markets", []))
                cursor = data.get("cursor")
                pages_fetched += 1
                if not cursor:
                    break
            except Exception as e:
                logger.warning(
                    "Page %d fetch failed (got %d markets so far): %s",
                    pages_fetched + 1, len(all_markets), e,
                )
                # Partial result — break out if this was the first page and it failed
                if pages_fetched == 0:
                    raise
                break

        # Deduplicate by ticker (defensive — Kalshi pagination is stable)
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for m in all_markets:
            ticker = m.get("ticker")
            if ticker and ticker not in seen:
                seen.add(ticker)
                unique.append(m)

        logger.info(
            "Fetched %d markets across %d pages (%d unique).",
            len(all_markets), pages_fetched, len(unique),
        )
        return unique
```

### 2.4 — `backend/adapters/kalshi/types.py`

> **SRP**: Pure parsing functions — no I/O, no state. Maps Kalshi API raw dicts
> to domain model dataclasses. All functions are synchronous and stateless.

```python
from __future__ import annotations

from typing import Any

from backend.core.models.market import (
    Market,
    MarketOrderbookStats,
    Orderbook,
    OrderbookLevel,
)
from backend.utils.datetime_utils import parse_date


def parse_market(raw: dict[str, Any]) -> Market:
    """Map Kalshi API market dict → Market dataclass.

    Known Kalshi API field → model field mappings:
      ticker                    → ticker
      event_ticker              → event_ticker
      title                     → title
      status                    → status
      yes_ask                   → yes_ask (int cents, multiply by 100 if float)
      yes_bid                   → yes_bid
      no_ask                    → no_ask
      no_bid                    → no_bid
      volume                    → volume
      open_interest             → open_interest
      expected_expiration_time  → expiry (parsed via parse_date)
      create_date               → create_date (raw ISO string)
      settlement_date           → settlement_date
      close_date                → close_date
      result                    → result
      rules_primary             → rules_primary
      rule_key                  → rule_key
      volume_24h                → volume_24h
      volume_24h_adjusted       → volume_24h_adjusted
    """
    def _to_int_cents(val: Any) -> int | None:
        """Normalize price to int cents. Handles float dollars or string."""
        if val is None:
            return None
        if isinstance(val, str):
            val = float(val)
        if isinstance(val, float):
            # If it looks like dollars (e.g. 0.65), multiply by 100
            if val < 100:
                return int(round(val * 100))
            return int(val)
        if isinstance(val, int):
            return val
        return None

    return Market(
        ticker=raw.get("ticker", ""),
        event_ticker=raw.get("event_ticker", ""),
        title=raw.get("title", ""),
        status=raw.get("status", ""),
        yes_ask=_to_int_cents(raw.get("yes_ask")),
        yes_bid=_to_int_cents(raw.get("yes_bid")),
        no_ask=_to_int_cents(raw.get("no_ask")),
        no_bid=_to_int_cents(raw.get("no_bid")),
        volume=int(raw.get("volume", 0)),
        open_interest=int(raw.get("open_interest", 0)),
        expiry=parse_date(raw.get("expected_expiration_time")),
        expiry_iso=raw.get("expected_expiration_time"),
        create_date=raw.get("create_date"),
        settlement_date=raw.get("settlement_date"),
        close_date=raw.get("close_date"),
        result=raw.get("result"),
        rules_primary=raw.get("rules_primary"),
        rule_key=raw.get("rule_key"),
        volume_24h=_to_int_cents(raw.get("volume_24h")),
        volume_24h_adjusted=_to_int_cents(raw.get("volume_24h_adjusted")),
    )


def parse_orderbook(raw: dict[str, Any], ticker: str) -> Orderbook:
    """Map Kalshi API orderbook dict → Orderbook dataclass.

    The Kalshi API returns:
      {"yes": [{"price": 65, "count": 1000}, ...],
       "no":  [{"price": 35, "count": 2000}, ...]}
    """
    def _parse_levels(levels: list[dict[str, Any]] | None) -> list[OrderbookLevel]:
        if not levels:
            return []
        result: list[OrderbookLevel] = []
        for level in levels:
            try:
                result.append(
                    OrderbookLevel(
                        price=int(level.get("price", 0)),
                        count=int(level.get("count", 0)),
                    )
                )
            except (ValueError, TypeError):
                continue
        # Sort by price ascending
        result.sort(key=lambda l: l.price)
        return result

    return Orderbook(
        market_ticker=ticker,
        yes_side=_parse_levels(raw.get("yes")),
        no_side=_parse_levels(raw.get("no")),
        fetch_time=parse_date(raw.get("fetch_time")),
    )


def calculate_orderbook_stats(
    market: Market,
    orderbook: Orderbook,
) -> MarketOrderbookStats:
    """Derive statistics from a market + its orderbook.

    Computes:
      - spread_cents: best yes_ask - best yes_bid (None if either missing)
      - total_resting_order_quantity: sum of all counts across both sides
      - Best bid/ask prices from orderbook levels
    """
    # Best bid/ask from orderbook levels (first level = best price)
    yes_bid = orderbook.yes_side[0].price if orderbook.yes_side else market.yes_bid
    yes_ask = orderbook.yes_side[-1].price if orderbook.yes_side else market.yes_ask
    no_bid = orderbook.no_side[0].price if orderbook.no_side else market.no_bid
    no_ask = orderbook.no_side[-1].price if orderbook.no_side else market.no_ask

    # Spread: difference between best yes_ask and best yes_bid
    spread: int | None = None
    if yes_bid is not None and yes_ask is not None:
        spread = abs(yes_ask - yes_bid)

    # Total resting quantity across both sides
    total_resting = sum(
        level.count for level in orderbook.yes_side
    ) + sum(
        level.count for level in orderbook.no_side
    )

    return MarketOrderbookStats(
        market_ticker=market.ticker,
        event_ticker=market.event_ticker,
        spread_cents=spread,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        last_price=(yes_bid or 0),  # approximate
        volume=market.volume,
        open_interest=market.open_interest,
        volume_24h=market.volume_24h,
        total_resting_order_quantity=total_resting,
    )
```

### 2.5 — `backend/adapters/kalshi/websocket.py`

> **SRP**: WebSocket client for real-time orderbook updates. Uses `.auth.KalshiSigner`
> (PKCS1v15) for connect authentication — NOT the RSA-PSS signer used by REST.
> Adds callback isolation (try/except per dispatch) and reconnect with re-subscribe.

```python
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

import websockets

from .auth import KalshiSigner  # PKCS1v15 signer — correct for WS auth

logger = logging.getLogger(__name__)


class KalshiWebSocket:
    """WebSocket client for Kalshi real-time updates (PKCS1v15 auth).

    Uses .auth.KalshiSigner for connect authentication headers.
    Each callback is wrapped in try/except so one bad handler doesn't
    break the listen loop. On reconnect, subscribed tickers are re-sent
    and the subscription acknowledgment is verified.
    """

    def __init__(
        self,
        url: str = "wss://api.elections.kalshi.com/trade-api/ws/v2",
        api_key_id: str = "",
        private_key: str = "",
    ):
        self.url = url
        self._signer = KalshiSigner(api_key_id=api_key_id, private_key_pem=private_key)
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._callbacks: list[Callable[[dict[str, Any]], Awaitable[None]]] = []
        self._subscribed_tickers: list[str] = []

    def on_message(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Register a callback invoked on each decoded message."""
        self._callbacks.append(callback)

    async def connect(self) -> None:
        """Connect with PKCS1v15 API key auth via headers."""
        headers = self._signer.get_headers("GET", "/trade-api/ws/v2")
        self._ws = await websockets.connect(self.url, additional_headers=headers)
        logger.info("WebSocket connected to %s", self.url)

    async def subscribe(self, tickers: list[str]) -> None:
        """Subscribe to orderbook_delta channel for given tickers.

        Kalshi WS uses 'id' for request tracking and 'params' for subscription config.
        Stores tickers so they can be re-subscribed on reconnect.
        """
        self._subscribed_tickers = list(tickers)
        message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": tickers,
            },
        }
        await self._ws.send(json.dumps(message))
        logger.info("Subscribed to %d tickers.", len(tickers))

    async def listen(self) -> None:
        """Listen loop with callback isolation, reconnect, and re-subscribe."""
        self._running = True
        while self._running:
            try:
                raw = await self._ws.recv()
                data = json.loads(raw)

                # Dispatch each callback in isolation
                for cb in self._callbacks:
                    try:
                        await cb(data)
                    except Exception as exc:
                        logger.error("WebSocket callback error: %s", exc, exc_info=True)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket disconnected. Reconnecting in 5s...")
                await asyncio.sleep(5)
                if not self._running:
                    break
                await self._reconnect()

            except Exception as exc:
                logger.error("WebSocket listen error: %s", exc, exc_info=True)
                await asyncio.sleep(1)

    async def _reconnect(self) -> None:
        """Reconnect and re-subscribe previously subscribed tickers."""
        try:
            await self.connect()
            if self._subscribed_tickers:
                await self.subscribe(self._subscribed_tickers)
                logger.info("Re-subscribed to %d tickers after reconnect.", len(self._subscribed_tickers))
        except Exception as exc:
            logger.error("WebSocket reconnect failed: %s", exc, exc_info=True)

    async def close(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
```

### 2.6 — `backend/adapters/kalshi/adapter.py`

> **DIP**: Implements `AbstractMarketAdapter` from `core/interfaces/adapter.py`.
> Engines depend on the abstract interface, not this concrete class.
> Implements ALL 4 properties + ALL MarketReader + ALL Trader methods.
> Convenience methods (`get_all_open_markets`, `get_market`, etc.) wrap the
> ABC methods with domain model parsing.

```python
from __future__ import annotations

from typing import Any, Optional

from backend.core.interfaces.adapter import AbstractMarketAdapter
from backend.core.models.market import Market, MarketOrderbookStats, Orderbook

from .client import KalshiClient
from .types import calculate_orderbook_stats, parse_market, parse_orderbook


class KalshiAdapter(AbstractMarketAdapter):
    """Kalshi platform adapter implementing the abstract adapter contract.

    Properties (from AbstractMarketAdapter):
      - name → "kalshi"
      - timezone → "US/Eastern"
      - supports_trading → True
      - supports_websocket → True

    MarketReader methods delegate to KalshiClient and return raw dicts
    (as required by the ABC contract). Convenience methods wrap them
    with domain model parsing.
    """

    def __init__(self, client: KalshiClient):
        self.client = client

    # ── Properties ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "kalshi"

    @property
    def timezone(self) -> str:
        return "US/Eastern"

    @property
    def supports_trading(self) -> bool:
        return True

    @property
    def supports_websocket(self) -> bool:
        return True

    # ── MarketReader implementation (raw dicts per ABC contract) ──

    async def fetch_markets(self, **kwargs: Any) -> list[dict[str, Any]]:
        """ABC: return raw market dicts."""
        return await self.client.fetch_all_open_markets(**kwargs)

    async def fetch_orderbook(self, ticker: str, **kwargs: Any) -> dict[str, Any]:
        """ABC: return raw orderbook dict."""
        return await self.client.get_orderbook(ticker, **kwargs)

    async def fetch_event(self, event_ticker: str, **kwargs: Any) -> dict[str, Any]:
        """ABC: return raw event dict."""
        raw = await self.client.get_event(event_ticker, **kwargs)
        return raw or {}

    async def fetch_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        """ABC: return raw event dicts."""
        data = await self.client.list_events(**kwargs)
        return data.get("events", [])

    # ── Trader implementation ─────────────────────────────────────

    async def place_order(
        self, ticker: str, side: str, price: int, count: int, **kwargs: Any
    ) -> dict[str, Any]:
        """ABC: place a limit order. price=int cents, count=int contracts."""
        return await self.client.place_order(
            ticker=ticker, side=side, price=price, count=count, **kwargs
        )

    async def cancel_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        """ABC: cancel an existing order."""
        return await self.client.cancel_order(order_id=order_id, **kwargs)

    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        """ABC: get current positions."""
        return await self.client.get_positions(**kwargs)

    # ── Convenience methods (domain model wrappers) ───────────────

    async def get_all_open_markets(self) -> list[Market]:
        raw_markets = await self.fetch_markets()
        return [parse_market(m) for m in raw_markets]

    async def get_market(self, ticker: str) -> Optional[Market]:
        raw = await self.client.get_market(ticker)
        return parse_market(raw) if raw else None

    async def get_orderbook(self, ticker: str) -> Orderbook:
        raw = await self.fetch_orderbook(ticker)
        return parse_orderbook(raw, ticker)

    async def get_orderbook_stats(
        self, ticker: str
    ) -> Optional[MarketOrderbookStats]:
        market = await self.get_market(ticker)
        if not market:
            return None
        orderbook = await self.get_orderbook(ticker)
        return calculate_orderbook_stats(market, orderbook)
```

---

### 2.7 — `backend/adapters/kalshi/__init__.py`

Exports the public API surface of the adapter package.

```python
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.adapters.kalshi.auth import KalshiSigner as KalshiWsSigner  # PKCS1v15 (WebSocket)
from backend.adapters.kalshi.client import KalshiClient
from backend.adapters.kalshi.types import (
    calculate_orderbook_stats,
    parse_market,
    parse_orderbook,
)
from backend.adapters.kalshi.websocket import KalshiWebSocket

# Re-export public API
__all__ = [
    "KalshiAdapter",
    "KalshiClient",
    "KalshiWebSocket",
    "KalshiWsSigner",
    "parse_market",
    "parse_orderbook",
    "calculate_orderbook_stats",
]
```

### 2.8 — `backend/requirements.txt` — Add `websockets>=12.0`

In `backend/requirements.txt`, ensure the `websockets==12.0` line is uncommented:

```txt
# Phase 2+: Kalshi Adapter, API, WebSocket
fastapi==0.111.0
uvicorn[standard]==0.30.1
websockets==12.0
python-dateutil==2.9.0
python-dotenv==1.0.1
```

---

## Phase 3: Engines

> **OCP**: Every engine implements `AbstractEngine` from `core/interfaces/`.
> Add new engines by implementing the interface — no orchestrator changes needed.
> **DRY**: Engines use shared utilities from `backend/utils/datetime_utils.py`
> (parse_date, calculate_progress) instead of defining their own.
> **Cross-ref:** Each engine has a detailed spec doc in `docs/engines/`.

> **⚠️ WARNING — Build plan pseudocode known errors have been corrected below.**
> The pseudocode for Engines 1, 4, 5, 6, and 7 originally contained bugs (wrong API keys, fictional dataclass fields, undefined variables). These have been fixed in the code blocks below. If you see discrepancies with the engine spec docs in `docs/engines/`, the spec docs are authoritative for algorithm logic. The actual codebase models (`core/models/*`, `core/interfaces/*`) are authoritative for field names and types.

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

> **DIP**: Engines depend on `MarketReader` interface, not `KalshiAdapter`.
> The actual adapter implementation (Phase 2) will provide a convenience
> method that wraps `fetch_markets()` and returns parsed `list[Market]`.

```python
import logging

from backend.core.interfaces.adapter import MarketReader
from backend.core.models.market import Market

logger = logging.getLogger(__name__)

async def fetch_all_open_markets(client: MarketReader) -> list[Market]:
    """
    Engine 1: Fetch all currently open markets from Kalshi.
    
    Uses the MarketReader interface (not KalshiAdapter directly).
    The adapter handles pagination + dedup internally.
    
    Returns deduplicated list of all open Markets, or empty list on failure.
    """
    try:
        from backend.adapters.kalshi.types import parse_market
        raw_markets = await client.fetch_markets(status="open", limit=1000)
        return [parse_market(m) for m in raw_markets] if raw_markets else []
    except Exception as e:
        logger.error(f"Engine 1 failed: {e}")
        return []
```

### 3.2 — `backend/engines/engine2_classification.py`

> **See `docs/engines/engine-2-classification.md` for full spec.**
>
> **CRITICAL — Use the actual model field names:**
> - `Market.create_date` (NOT `open_time`)
> - `Market.close_date` (NOT `close_time`)
> - `Market.expiry` (NOT `expected_expiration_time`)
> - `ClassificationResult` (NOT `MarketClassification`)
>
> Import shared utilities from `backend.utils.datetime_utils` (parse_date,
> same_et_day, day_key_et, calculate_progress) instead of defining inline.

```python
"""
Engine 2: Overtime-aware same-day-live classification.

Returns ClassificationResult (not MarketClassification — that class doesn't exist).
Uses Market model fields: status, create_date, close_date, expiry.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from backend.utils.datetime_utils import parse_date, same_et_day
from backend.core.models.classification import ClassificationResult
from backend.core.models.market import Market

ET = ZoneInfo("America/New_York")


def classify_market(market: Market, now: Optional[datetime] = None) -> ClassificationResult:
    """
    Classify a single market as same-day-live.

    SAME_DAY_LIVE iff:
      - status == "active"
      - create_date <= now
      - close_date > now
      - expiry is today ET

    Uses market.create_date, market.close_date, market.expiry.
    Returns ClassificationResult (NOT MarketClassification).
    """
    if now is None:
        now = datetime.now(ET)

    reason_parts: list[str] = []
    create_dt = parse_date(market.create_date)
    close_dt = parse_date(market.close_date)
    expiry_dt = market.expiry

    live_now = (
        market.status == "active"
        and create_dt is not None
        and close_dt is not None
        and create_dt <= now
        and close_dt > now
    )
    if not live_now:
        reason_parts.append("Market is not currently active/open.")

    expiry_today = (expiry_dt is not None and same_et_day(expiry_dt, now))
    if not expiry_today:
        reason_parts.append("Expiry not today ET.")

    return ClassificationResult(
        market_ticker=market.ticker,
        event_ticker=market.event_ticker,
        is_same_day_live=live_now and expiry_today,
        confidence=1.0 if (live_now and expiry_today) else 0.0,
        reason="; ".join(reason_parts) if reason_parts else "Passed all checks",
    )


def get_same_day_live_markets(
    markets: list[Market],
    now: Optional[datetime] = None,
) -> tuple[list[tuple[Market, ClassificationResult]], list[tuple[Market, ClassificationResult]]]:
    """
    Classify all markets. Returns (all_classified, same_day_live_only).
    Second list is a subset of the first.
    """
    if now is None:
        now = datetime.now(ET)

    all_classified: list[tuple[Market, ClassificationResult]] = []
    live: list[tuple[Market, ClassificationResult]] = []

    for market in markets:
        classification = classify_market(market, now)
        pair = (market, classification)
        all_classified.append(pair)
        if classification.is_same_day_live:
            live.append(pair)

    return all_classified, live
```

### 3.3 — `backend/engines/engine3_grouping.py`

> **CRITICAL — Use actual model field names:**
> - `ClassificationResult` (NOT `MarketClassification`)
> - `ClassifiedEvent.num_markets` (NOT `market_count`)
> - `ClassifiedEvent.markets` (NOT `same_day_live_markets`)

```python
from backend.core.models.classification import ClassificationResult, ClassifiedEvent
from backend.core.models.market import Market


def group_by_event_ticker(
    same_day_live_markets: list[tuple[Market, ClassificationResult]]
) -> list[ClassifiedEvent]:
    """
    Engine 3: Group same-day-live markets by event_ticker.
    
    An event qualifies if ANY child market passes SAME_DAY_LIVE_MARKET.
    Events are sorted by event_ticker for deterministic output.
    """
    by_event: dict[str, list[tuple[Market, ClassificationResult]]] = {}
    
    for market, classification in same_day_live_markets:
        ticker = market.event_ticker
        if ticker not in by_event:
            by_event[ticker] = []
        by_event[ticker].append((market, classification))
    
    events = []
    for ticker, markets in by_event.items():
        classifs = [c for _, c in markets]
        best_c = max(classifs, key=lambda c: c.confidence)
        total_volume = sum(m.volume for m, _ in markets if isinstance(m.volume, int))
        
        events.append(ClassifiedEvent(
            event_ticker=ticker,
            event_title=markets[0][0].title if markets else "",
            markets=[m for m, _ in markets],
            classification=best_c,
            num_markets=len(markets),
            total_volume=total_volume,
        ))
    
    events.sort(key=lambda e: e.event_ticker)
    return events
```

### 3.4 — `backend/engines/engine4_orderbook.py`

> **CRITICAL — Use actual model field names:**
> - Use `MarketReader` interface (NOT `KalshiAdapter`)
> - `Orderbook(market_ticker=...)` (NOT `Orderbook(market_id=...)`)
> - `event.markets` (NOT `event.same_day_live_markets`)

```python
import asyncio
import logging
from backend.core.interfaces.adapter import MarketReader
from backend.core.models import (
    ClassifiedEvent, Orderbook,
)

logger = logging.getLogger(__name__)

async def fetch_orderbooks(
    events: list[ClassifiedEvent],
    client: MarketReader,
    concurrency: int = 10,
) -> list[tuple[ClassifiedEvent, dict[str, Orderbook]]]:
    """
    Engine 4: Fetch orderbooks for all markets across all qualified events.
    Markets with no orderbook data still get an empty Orderbook.
    Uses bounded concurrency via asyncio.Semaphore.
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def fetch_one(ticker: str) -> tuple[str, Orderbook]:
        async with semaphore:
            try:
                raw = await client.fetch_orderbook(ticker)
                ob = parse_orderbook_response(raw, ticker)
                return ticker, ob
            except Exception as e:
                logger.warning(f"Orderbook fetch failed for {ticker}: {e}")
                return ticker, Orderbook(market_ticker=ticker)
    
    result: list[tuple[ClassifiedEvent, dict[str, Orderbook]]] = []
    
    for event in events:
        tickers = [m.ticker for m in event.markets]
        tasks = [fetch_one(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        orderbooks = dict(results)
        result.append((event, orderbooks))
    
    return result


def parse_orderbook_response(raw: dict, ticker: str) -> Orderbook:
    """Parse Kalshi API orderbook response into Orderbook model.

    The API returns {"yes": [{"price": 65, "count": 1000}, ...],
    "no": [{"price": 35, "count": 800}, ...]} with int cents and int contracts.
    """
    from backend.core.models.market import OrderbookLevel
    yes_raw = raw.get("yes", [])
    no_raw = raw.get("no", [])

    def parse_levels(levels: list) -> list:
        if not levels:
            return []
        return [
            OrderbookLevel(price=level["price"], count=level["count"])
            for level in levels
        ]

    return Orderbook(
        market_ticker=ticker,
        yes_side=parse_levels(yes_raw),
        no_side=parse_levels(no_raw),
        fetch_time=datetime.now(),
    )
```

### 3.5 — `backend/engines/engine5_ranking.py`

> **CRITICAL — Use actual model fields:**
> - `RankedMarket` has scalar fields only: `market_ticker`, `volume`, `spread_cents`,
>   `yes_price`, `no_price`, `rank`, `score` (NO nested `market` or `orderbook_stats`)
> - `EventWithTopMarkets` fields: `event_ticker`, `event_title`, `top_markets`,
>   `total_volume`, `num_top_markets` (NO `market_count`, `same_day_live_market_count`,
>   `total_event_resting_order_quantity`, `active_orderbook_market_count`, etc.)
> - Use `event.markets` (NOT `event.same_day_live_markets`)
> - Use `ClassificationResult` (NOT `MarketClassification`)

```python
import logging
from backend.core.models.classification import ClassificationResult, ClassifiedEvent
from backend.core.models.market import Market, Orderbook, MarketOrderbookStats
from backend.core.models.trading import RankedMarket, EventWithTopMarkets

logger = logging.getLogger(__name__)


def compute_orderbook_stats(market: Market, orderbook: Orderbook) -> MarketOrderbookStats:
    """Derive orderbook statistics for ranking."""
    yes_qty = sum(level.count for level in orderbook.yes_side)
    no_qty = sum(level.count for level in orderbook.no_side)
    spread_cents = None
    if orderbook.yes_side and orderbook.no_side:
        spread_cents = abs(orderbook.yes_side[0].price - orderbook.no_side[0].price)
    return MarketOrderbookStats(
        market_ticker=market.ticker,
        event_ticker=market.event_ticker,
        spread_cents=spread_cents,
        total_resting_order_quantity=yes_qty + no_qty,
        yes_bid=orderbook.yes_side[0].price if orderbook.yes_side else None,
        no_bid=orderbook.no_side[0].price if orderbook.no_side else None,
        volume_24h=market.volume_24h or 0,
    )


def rank_event_markets(
    event: ClassifiedEvent,
    orderbooks: dict[str, Orderbook],
) -> EventWithTopMarkets:
    """
    Rank markets inside an event by resting order activity.
    Sort: total_resting_order_quantity DESC → volume_24h DESC.
    Returns EventWithTopMarkets with top_markets list.
    """
    ranked: list[RankedMarket] = []
    
    for market in event.markets:
        ob = orderbooks.get(market.ticker, Orderbook(market_ticker=market.ticker))
        stats = compute_orderbook_stats(market, ob)
        ranked.append(RankedMarket(
            market_ticker=market.ticker,
            volume=market.volume,
            spread_cents=stats.spread_cents or 0,
            yes_price=market.yes_bid or 0,
            no_price=market.no_bid or 0,
            rank=0,
            score=float(stats.total_resting_order_quantity),
        ))
    
    ranked.sort(
        key=lambda r: (-r.volume, r.spread_cents, -r.score),
    )
    for i, rm in enumerate(ranked):
        rm.rank = i + 1
    
    return EventWithTopMarkets(
        event_ticker=event.event_ticker,
        event_title=event.event_title or "",
        top_markets=ranked,
        total_volume=sum(r.volume for r in ranked),
        num_top_markets=len(ranked),
    )


def rank_all_events(
    event_books: list[tuple[ClassifiedEvent, dict[str, Orderbook]]]
) -> list[EventWithTopMarkets]:
    """Run ranking across all events."""
    return [rank_event_markets(e, ob) for e, ob in event_books]
```

### 3.6 — `backend/engines/engine6_progress_gate.py`

> **CRITICAL — Use actual model fields:**
> - `TradeDecision.should_trade` (bool, NOT `trade_decision` str)
> - `TradeDecision.side` (NOT `selected_side`)
> - `TradeDecision.reason` (NOT `skip_reason`)
> - `EventFeatures` has: `event_ticker`, `child_markets`, `total_volume`, `num_markets`,
>   `num_markets_live`, `max_progress_pct`, `min_progress_pct`, `has_overtime`
> - `MarketFeatures` uses `ticker` (NOT `market_ticker`)
> - `ProgressBasedOrderCandidate` fields: `event_ticker`, `market_ticker`, `side`,
>   `price`, `confidence`, `reason`, `volume`, `progress_pct`, `most_bet_side`,
>   `threshold_pct`, `is_overtime`
> - Import `calculate_progress`, `parse_date` from `backend.utils.datetime_utils`

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from backend.core.models.trading import EventWithTopMarkets, ProgressBasedOrderCandidate
from backend.core.models.classification import ClassificationResult
from backend.core.interfaces import StrategyProfile, EventFeatures, MarketFeatures, TradeDecision
from backend.utils.datetime_utils import calculate_progress, parse_date
from backend.engines.engine2_classification import classify_market

ET = ZoneInfo("America/New_York")


def _build_event_features(
    event: EventWithTopMarkets,
    now: datetime,
) -> EventFeatures:
    """Build EventFeatures from ranked event data for strategy consumption."""
    child_markets = [
        MarketFeatures(
            ticker=rm.market_ticker,
            volume=rm.volume,
            yes_bid=rm.yes_price,
            no_bid=rm.no_price,
            spread_cents=rm.spread_cents,
            total_resting_order_quantity=max(rm.score, 0),
        )
        for rm in event.top_markets
    ]
    return EventFeatures(
        event_ticker=event.event_ticker,
        event_title=event.event_title or "",
        child_markets=child_markets,
        total_volume=event.total_volume,
        num_markets=event.num_top_markets,
        num_markets_live=event.num_top_markets,
    )


def create_candidate(
    event: EventWithTopMarkets,
    strategy: StrategyProfile,
    threshold_pct: int = 65,
    now: Optional[datetime] = None,
) -> ProgressBasedOrderCandidate:
    """
    Engine 6: Create order candidate if event passes progress threshold.
    
    1. Calculate event progress from first ranked market
    2. Build EventFeatures from ranked event markets
    3. Call strategy.select_trade() for holistic decision
    4. Map TradeDecision to ProgressBasedOrderCandidate
    """
    if now is None:
        now = datetime.now(ET)
    
    reason_parts: list[str] = []
    
    # Calculate progress from first top market
    # NOTE: Proper temporal progress requires market expiry data (carried through
    # ClassifiedEvent.markets). Engine 6 receives EventWithTopMarkets which lacks
    # Market objects. Once the pipeline is extended, use:
    #   progress_pct = calculate_progress(market.expiry, now, market.create_date)
    # For now, use a volume-based proxy (0-100 scale).
    if event.top_markets:
        top_rm = event.top_markets[0]
        progress_pct = min(float(top_rm.volume) / 1000.0 * 100.0, 100.0) if top_rm.volume > 0 else 0.0
    else:
        progress_pct = 0.0
    
    passes_threshold = progress_pct >= threshold_pct
    if not passes_threshold:
        reason_parts.append(f"Progress {progress_pct:.0f}% < threshold {threshold_pct}%.")
    
    # Build features and call strategy
    event_features = _build_event_features(event, now)
    decision = strategy.select_trade(event_features)
    
    if not decision.should_trade:
        reason_parts.append(decision.reason or "Strategy returned no trade.")
    
    has_side = decision.side in ("yes", "no")
    should_create = passes_threshold and decision.should_trade and has_side
    
    return ProgressBasedOrderCandidate(
        event_ticker=event.event_ticker,
        market_ticker=decision.market_ticker if should_create else "",
        side=decision.side if should_create else "",
        price=decision.entry_price_cents if should_create else 0,
        confidence=decision.confidence if should_create else 0.0,
        reason="; ".join(reason_parts) if reason_parts else "Candidate created",
        volume=decision.max_contracts if should_create else 0,
        progress_pct=progress_pct,
        most_bet_side=decision.side if decision.side in ("yes", "no") else "",
        threshold_pct=float(threshold_pct),
        is_overtime=False,
    )


def process_all_events(
    events: list[EventWithTopMarkets],
    strategy: StrategyProfile,
    threshold_pct: int = 65,
    now: Optional[datetime] = None,
) -> tuple[list[ProgressBasedOrderCandidate], list[ProgressBasedOrderCandidate]]:
    """
    Run Engine 6 across all events.
    Returns (all_candidates, actionable_candidates).
    Actionable = side in ("yes", "no") and confidence > 0.
    """
    if now is None:
        now = datetime.now(ET)
    
    candidates = [
        create_candidate(e, strategy, threshold_pct, now)
        for e in events
    ]
    
    actionable = [c for c in candidates if c.side in ("yes", "no") and c.confidence > 0]
    
    return candidates, actionable
```

### 3.7 — `backend/engines/engine7_validation.py`

> **CRITICAL — Use actual model fields:**
> - `ValidatedOrderCandidate` has: `original_candidate`, `is_valid`, `validation_errors`,
>   `risk_score`, `estimated_entry_price`, `estimated_exit_price`, `max_contracts`
>   (NOT `can_trade`, `candidate`, `reason`, `validation_timestamp`, `latest_market`, etc.)
> - Use `MarketReader` interface (NOT `KalshiAdapter`) for API calls
> - `TradeDecision.side` (NOT `selected_side`)
> - `EventFeatures` and `MarketFeatures` use actual fields from core/interfaces

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from backend.core.interfaces.adapter import MarketReader
from backend.core.models.trading import (
    ProgressBasedOrderCandidate, ValidatedOrderCandidate, ValidationConfig,
)
from backend.core.interfaces import StrategyProfile, EventFeatures, MarketFeatures
from backend.engines.engine2_classification import classify_market

ET = ZoneInfo("America/New_York")


async def validate_candidate(
    candidate: ProgressBasedOrderCandidate,
    client: MarketReader,
    strategy: StrategyProfile,
    config: ValidationConfig,
    now: Optional[datetime] = None,
) -> ValidatedOrderCandidate:
    """
    Engine 7: Pre-trade validation.
    
    1. Check candidate has valid side
    2. Re-fetch market + re-classify
    3. Re-fetch orderbook + recalc stats
    4. Recalculate side via strategy.select_trade()
    5. Check spread + volume thresholds
    """
    if now is None:
        now = datetime.now(ET)

    errors: list[str] = []

    # Must have a valid side
    if candidate.side not in ("yes", "no"):
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=["Candidate has no valid side."],
        )

    ticker = candidate.market_ticker

    # Re-fetch market
    from backend.adapters.kalshi.types import parse_market
    from backend.adapters.kalshi.client import KalshiClient
    markets_raw = await client.fetch_markets()
    market_obj = None
    for m in markets_raw:
        if m.get("ticker") == ticker:
            market_obj = parse_market(m)
            break
    if market_obj is None:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=[f"Market {ticker} not found."],
        )

    # Re-classify using parsed Market object
    classification = classify_market(market_obj, now)
    if not classification.is_same_day_live:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=["Market no longer same-day live."],
        )

    # Re-fetch orderbook and parse
    from backend.adapters.kalshi.types import parse_orderbook, calculate_orderbook_stats
    orderbook_raw = await client.fetch_orderbook(ticker)
    if not orderbook_raw:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=[f"Orderbook for {ticker} not available."],
        )
    orderbook = parse_orderbook(orderbook_raw, ticker)
    stats = calculate_orderbook_stats(market_obj, orderbook)

    # Recalculate side via strategy
    event_features = EventFeatures(
        event_ticker=candidate.event_ticker,
        child_markets=[MarketFeatures(ticker=ticker)],
    )
    decision = strategy.select_trade(event_features)

    if decision.side != candidate.side:
        errors.append(f"Side changed: was {candidate.side}, now {decision.side}.")

    # Spread check
    if stats.spread_cents is not None and stats.spread_cents > config.max_spread_cents:
        errors.append(f"Spread {stats.spread_cents}¢ exceeds max {config.max_spread_cents}¢.")

    # Volume check
    if stats.volume < config.min_volume:
        errors.append(f"Insufficient volume: {stats.volume} (min {config.min_volume}).")

    if not errors:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=True,
            estimated_entry_price=candidate.price,
            max_contracts=candidate.volume,
        )

    return ValidatedOrderCandidate(
        original_candidate=candidate,
        is_valid=False,
        validation_errors=errors,
    )
```

### 3.8 — `backend/engines/engine8_orchestrator.py`

> **CRITICAL — Use existing `ScannerOutput` from `core/scanner_state.py`**
> (NOT a custom `ScannerResult` class). Engines depend on `MarketReader` interface,
> not `KalshiAdapter`.

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import logging

from backend.core.interfaces.adapter import MarketReader
from backend.core.interfaces import StrategyProfile
from backend.core.models.trading import ValidatedOrderCandidate, ValidationConfig
from backend.core.scanner_state import ScannerOutput
from backend.engines.engine1_discovery import fetch_all_open_markets
from backend.engines.engine2_classification import get_same_day_live_markets
from backend.engines.engine3_grouping import group_by_event_ticker
from backend.engines.engine4_orderbook import fetch_orderbooks
from backend.engines.engine5_ranking import rank_all_events
from backend.engines.engine6_progress_gate import process_all_events
from backend.engines.engine7_validation import validate_candidate

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


async def run_one_shot(
    client: MarketReader,
    strategy: StrategyProfile,
    threshold_pct: int = 65,
    mode: str = "dry_run",
    now: Optional[datetime] = None,
) -> ScannerOutput:
    """
    Engine 8: Run all 7 engines once and return results.
    Uses ScannerOutput from core.scanner_state (NOT a custom class).
    Pipeline: E1 → E2 → E3 → E4 → E5 → E6 → E7
    """
    if now is None:
        now = datetime.now(ET)

    # E1: Discovery
    markets = await fetch_all_open_markets(client)
    logger.info(f"E1: Found {len(markets)} open markets.")

    if not markets:
        return ScannerOutput(num_markets_scanned=0, completed_at=now)

    # E2: Classification
    _, live = get_same_day_live_markets(markets, now)
    logger.info(f"E2: {len(live)} same-day-live markets.")

    if not live:
        return ScannerOutput(num_markets_scanned=len(markets), completed_at=now)

    # E3: Grouping
    events = group_by_event_ticker(live)
    logger.info(f"E3: {len(events)} same-day-live events.")

    # E4: Orderbooks
    event_books = await fetch_orderbooks(events, client)
    logger.info("E4: Orderbooks fetched.")

    # E5: Ranking
    ranked_events = rank_all_events(event_books)
    logger.info("E5: Events ranked.")

    # E6: Progress Gate
    candidates, actionable = process_all_events(
        ranked_events, strategy, threshold_pct, now,
    )
    logger.info(f"E6: {len(actionable)} actionable candidates.")

    # E7: Validation (only for actionable candidates in dry_run or live)
    validated: list[ValidatedOrderCandidate] = []
    if mode != "read_only":
        for candidate in actionable:
            vc = await validate_candidate(
                candidate, client, strategy, ValidationConfig(), now,
            )
            validated.append(vc)
        logger.info(f"E7: {len(validated)} validated.")

    return ScannerOutput(
        events=ranked_events,
        trades=validated,
        num_events_scanned=len(ranked_events),
        num_markets_scanned=len(markets),
        num_candidates_found=len(actionable),
        num_trades_executed=sum(1 for v in validated if v.is_valid),
        completed_at=datetime.now(ET),
    )
```

### 3.9 — Live update modules (`backend/engines/live/`)

These are poller/updater classes for the live scanner loop. Each runs as an asyncio task.

> **CRITICAL — Use `MarketReader` interface** (NOT `KalshiAdapter`).
> The `ScannerState` has these fields: `markets`, `classified_events` (dict[str, ClassifiedEvent]),
> `ranked_events` (list[EventWithTopMarkets]), `candidates` (list[ValidatedOrderCandidate]),
> `is_running`, `cycle_started_at`.

```python
# backend/engines/live/discovery_poller.py
# Periodically re-runs E1→E2→E3, diffs with previous state, triggers rerank

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.core.interfaces.adapter import MarketReader
from backend.core.scanner_state import ScannerState
from backend.engines.engine1_discovery import fetch_all_open_markets
from backend.engines.engine2_classification import get_same_day_live_markets
from backend.engines.engine3_grouping import group_by_event_ticker

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

class DiscoveryPoller:
    """Periodically re-discovers markets and updates state.
    Depends on MarketReader interface, not concrete adapter.
    """
    
    def __init__(self, client: MarketReader, state: ScannerState, interval: int = 30):
        self.client = client
        self.state = state
        self.interval = interval
        self._on_new_events_callbacks = []
    
    def on_new_events(self, callback):
        self._on_new_events_callbacks.append(callback)
    
    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                now = datetime.now(ET)
                markets = await fetch_all_open_markets(self.client)
                _, live = get_same_day_live_markets(markets, now)
                events = group_by_event_ticker(live)
                
                # Diff with current state
                current_tickers = set(self.state.classified_events.keys())
                new_tickers = {e.event_ticker for e in events}
                
                added = new_tickers - current_tickers
                removed = current_tickers - new_tickers
                
                for t in removed:
                    self.state.classified_events.pop(t, None)
                
                for callback in self._on_new_events_callbacks:
                    await callback([e for e in events if e.event_ticker in added])
                
                self.state.classified_events = {e.event_ticker: e for e in events}
                self.state.cycle_started_at = now
                
                logger.info(f"Discovery: {len(live)} live markets, {len(events)} events. +{len(added)} -{len(removed)}")
            
            except Exception as e:
                logger.error(f"Discovery poller error: {e}")
            
            await asyncio.sleep(self.interval)
```

```python
# backend/engines/live/event_reranker.py
# Re-ranks a single event when its markets change

from backend.core.models.classification import ClassifiedEvent
from backend.core.models.market import Orderbook
from backend.core.models.trading import EventWithTopMarkets
from backend.engines.engine5_ranking import rank_event_markets

def rerank_event(event: ClassifiedEvent, orderbooks: dict[str, Orderbook]) -> EventWithTopMarkets:
    """Re-rank a single event when its orderbooks change."""
    return rank_event_markets(event, orderbooks)
```

```python
# backend/engines/live/progress_gate_loop.py
# Periodically re-runs Engine 6 for all ranked events

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from backend.core.interfaces import StrategyProfile
from backend.engines.engine6_progress_gate import create_candidate

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

class ProgressGateLoop:
    """Periodically re-evaluates all ranked events for candidate creation."""
    
    def __init__(self, ranked_events, strategy: StrategyProfile, threshold: int = 65, interval: int = 10):
        self.ranked_events = ranked_events  # reference to ScannerState.ranked_events
        self.strategy = strategy
        self.threshold = threshold
        self.interval = interval
        self.on_new_candidate = None  # async callback
    
    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                now = datetime.now(ET)
                for event in self.ranked_events:
                    candidate = create_candidate(event, self.strategy, self.threshold, now)
                    
                    if candidate.side in ("yes", "no") and candidate.confidence > 0:
                        if self.on_new_candidate:
                            await self.on_new_candidate(candidate)
                
                logger.debug(f"Progress gate: checked {len(self.ranked_events)} events.")
            
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
from backend.engines.engine8_orchestrator import run_one_shot
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

> `StrategyExperiment` extends `StrategyProfile` from `core/interfaces/strategy.py`.
> Data classes (`MarketFeatures`, `EventFeatures`, `TradeDecision`) are defined in
> `interfaces/strategy.py` and imported here to avoid duplication.

```python
from backend.core.interfaces.strategy import (
    StrategyProfile, MarketFeatures, EventFeatures, TradeDecision,
)


class StrategyExperiment(StrategyProfile):
    """
    Base class for all 7 strategy experiments.
    
    Extends StrategyProfile from core/interfaces, which defines:
    - name, description, config fields
    - abstract select_trade(event_features) -> TradeDecision
    
    Each experiment overrides select_trade() with its specific logic.
    """
    pass
```

### 4.2–4.9 — Strategy Experiment Implementations

> **⚠️ CRITICAL — Use actual `TradeDecision` fields from `core/interfaces/strategy.py`:**
> ```python
> @dataclass
> class TradeDecision:
>     market_ticker: str
>     side: str              # "yes" or "no"
>     confidence: float = 0.0
>     reason: str = ""       # why SKIP or the trade rationale
>     entry_price_cents: int = 0
>     max_contracts: int = 0
>     should_trade: bool = False
> ```
>
> **Do NOT use these non-existent fields:** `trade_decision`, `skip_reason`,
> `selected_side`, `experiment_id`, `selected_market_reason`, `selected_side_reason`,
> `entry_threshold`, `event_progress_at_entry`, `estimated_fee_cents`,
> `max_acceptable_price_cents`.
>
> **`MarketFeatures` actual fields:** `ticker` (NOT `market_ticker`), `volume`,
> `volume_24h`, `yes_bid`, `yes_ask`, `no_bid`, `no_ask`, `spread_cents`,
> `last_price`, `open_interest`, `total_resting_order_quantity`, `progress_pct`.
> No `yes_executed_volume`, `no_executed_volume`, `trade_count`, `yes_price_momentum`,
> `yes_total_depth`, `no_total_depth`, `market_title`, `status`.
>
> **`EventFeatures` actual fields:** `event_ticker`, `event_title`, `child_markets`,
> `total_volume`, `num_markets`, `num_markets_live`, `max_progress_pct`,
> `min_progress_pct`, `has_overtime`. No `event_progress`, `threshold`, `entry_time`,
> `category`.
>
> See `docs/engines/strategy-system.md` for the full spec.
>
> **The pseudocode below is illustrative.** The actual `MarketFeatures` model does
> NOT have backtesting-specific fields like `total_executed_volume` or
> `yes_price_momentum`. Those exist in the `strategy-system.md` extended data models
> (`HistoricalTrade`, `Candlestick`, `OrderbookSnapshot`) which are separate from
> the core `MarketFeatures` interface. When implementing Phase 4, either extend
> `MarketFeatures` or build a separate feature-extraction layer.

```python
# ── ExecutedVolumeFollower ──
# Market with highest volume → side with higher yes/no bid

def select_trade(self, event_features: EventFeatures) -> TradeDecision:
    valid = [m for m in event_features.child_markets if m.volume > 0]
    if not valid:
        return TradeDecision(market_ticker="", side="no", should_trade=False, reason="no_volume")
    selected = max(valid, key=lambda m: m.volume)
    side = "yes" if selected.yes_bid > selected.no_bid else "no"
    return TradeDecision(
        market_ticker=selected.ticker, side=side, should_trade=True,
        reason=f"highest_volume_{selected.ticker}_side_{side}",
        entry_price_cents=selected.yes_bid if side == "yes" else selected.no_bid,
    )

# ── ExecutedVolumeFade ──
# Same market selection → fade the dominant side

def select_trade(self, event_features: EventFeatures) -> TradeDecision:
    valid = [m for m in event_features.child_markets if m.volume > 0]
    if not valid:
        return TradeDecision(market_ticker="", side="no", should_trade=False, reason="no_volume")
    selected = max(valid, key=lambda m: m.volume)
    dominant = "yes" if selected.yes_bid > selected.no_bid else "no"
    fade = "no" if dominant == "yes" else "yes"
    return TradeDecision(
        market_ticker=selected.ticker, side=fade, should_trade=True,
        reason=f"fade_{dominant}_on_{selected.ticker}",
        entry_price_cents=selected.yes_bid if fade == "yes" else selected.no_bid,
    )

# ── FavoriteSideFollower ──
# Highest volume market → buy the favorite (price > 50¢ = YES)

def select_trade(self, event_features: EventFeatures) -> TradeDecision:
    valid = [m for m in event_features.child_markets if m.volume > 0]
    if not valid:
        return TradeDecision(market_ticker="", side="no", should_trade=False, reason="no_volume")
    selected = max(valid, key=lambda m: m.volume)
    side = "yes" if selected.yes_bid > 50 else "no"
    return TradeDecision(
        market_ticker=selected.ticker, side=side, should_trade=True,
        reason=f"favorite_side_{side}_price_{selected.yes_bid if side == 'yes' else selected.no_bid}",
        entry_price_cents=selected.yes_bid if side == "yes" else selected.no_bid,
    )

# ── MomentumFollower ──
# Largest price move → direction of movement
# NOTE: MarketFeatures does not have yes_price_momentum.
# This strategy requires extended features from a FeatureBuilder (Phase 5).

# ── LiquidityFilteredFollower ──
# Volume follower with liquidity guards
# NOTE: MarketFeatures does not have trade_count.
# This strategy requires extended features.

# ── RestingDepthFollower ──
# Highest total resting depth → deeper side
# Uses total_resting_order_quantity which IS available on MarketFeatures.

def select_trade(self, event_features: EventFeatures) -> TradeDecision:
    with_depth = [m for m in event_features.child_markets if m.total_resting_order_quantity > 0]
    if not with_depth:
        return TradeDecision(market_ticker="", side="no", should_trade=False, reason="no_depth")
    selected = max(with_depth, key=lambda m: m.total_resting_order_quantity)
    # Infer side from yes/no bid depth
    side = "yes" if selected.yes_bid > selected.no_bid else "no"
    return TradeDecision(
        market_ticker=selected.ticker, side=side, should_trade=True,
        reason=f"highest_depth_{selected.ticker}",
        entry_price_cents=selected.yes_bid if side == "yes" else selected.no_bid,
    )

# ── HybridScoreFollower ──
# Weighted combination — requires extended features for full implementation.

# ── __init__.py (registry) ──
# EXPERIMENT_REGISTRY and get_experiment() as shown in the strategy-system.md doc.
# Actual implementation lives in backend/strategies/__init__.py
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
    size: int = 0                       # Contracts held
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
        new_size = pos.size + trade.quantity
        total_cost = (pos.avg_entry_price * pos.size) + (trade.entry_price * trade.quantity)
        pos.avg_entry_price = total_cost / new_size if new_size > 0 else 0
        pos.size = new_size
        pos.trade_count += 1
        self.cash_balance -= trade.entry_price * trade.quantity

        # Track trade
        self._trades.append(trade)
        self.stats.total_trades += 1
        self.stats.total_volume += trade.entry_price * trade.quantity

        # TODO: Track win/loss on exit (position close), not on individual fills.
        # Comparing entry prices against a running average is misleading.

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
from datetime import datetime, timedelta, timezone
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
        if not validated.is_valid:
            reasons = "; ".join(validated.validation_errors)
            logger.info(f"Signal rejected by validation: {candidate.event_ticker} — {reasons}")
            return

        side = validated.original_candidate.side
        price = candidate.price
        size = candidate.volume

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
            market_ticker=candidate.market_ticker,
            side=side,
            entry_price=price,
            quantity=size if is_filled else 0,
            mode=self.mode,
            status="filled" if is_filled else "failed",
            entry_time=datetime.now(timezone.utc),
            validation_latency_ms=0.0,
        )
        self._open_orders[trade_id] = trade
        self._order_timestamps[trade_id] = datetime.now(timezone.utc)
        self.stats.orders_placed += 1
        if is_filled:
            self.stats.orders_filled += 1
            self.portfolio.record_fill(trade)
        logger.info(
            f"[DRY-RUN] {'FILLED' if is_filled else 'REJECTED'}: "
            f"{candidate.event_ticker} {side} {size}x@{price}¢"
        )

    async def _execute_live(self, candidate, validated, side, price, size):
        """Place a real order on Kalshi."""
        try:
            result = await self.adapter.place_order(
                ticker=candidate.market_ticker,
                side=side,
                price=price,
                count=size,
            )
            trade_id = result.get("order_id", f"live_{uuid.uuid4().hex[:12]}")
            trade = TradeRecord(
                trade_id=trade_id,
                event_ticker=candidate.event_ticker,
                market_ticker=candidate.market_ticker,
                side=side,
                entry_price=price,
                quantity=size,
                mode=self.mode,
                status="filled",
                entry_time=datetime.now(timezone.utc),
                validation_latency_ms=0.0,
            )
            self._open_orders[trade_id] = trade
            self._order_timestamps[trade_id] = datetime.now(timezone.utc)
            self.stats.orders_placed += 1
            self.stats.orders_filled += 1
            self.portfolio.record_fill(trade)
            logger.info(f"[LIVE] ORDER PLACED: {candidate.event_ticker} {side} {size}x@{price}¢")
        except Exception as e:
            logger.error(f"[LIVE] ORDER FAILED: {candidate.event_ticker} — {e}")
            self.stats.orders_rejected += 1

    async def _monitor_order_timeouts(self):
        """Periodically cancel orders that have been open too long."""
        while self._running:
            try:
                await asyncio.sleep(5.0)
                now = datetime.now(timezone.utc)
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
        """Submit a candidate to the execution engine.

        Returns (None, None) — results flow through portfolio + stats.
        """
        await self.engine.submit_signal(candidate)
        return None, None
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
            "progress_pct", "threshold_pct", "total_orders", "reasons",
        ])
        self._init_csv("trades.csv", [
            "entry_time", "trade_id", "event_ticker", "market_ticker",
            "side", "entry_price", "quantity", "mode", "status", "latency_ms", "error",
        ])
        self._init_csv("opportunities.csv", [
            "timestamp", "event_ticker", "market_ticker", "side",
            "progress_pct", "total_orders", "edge",
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
                c.market_ticker,
                c.most_bet_side, f"{c.progress_pct:.1f}",
                c.threshold_pct, c.volume,
                c.reason,
            ])

    def log_trade(self, t: TradeRecord):
        path = os.path.join(self.log_dir, "trades.csv")
        with open(path, "a", newline="") as f:
            csv.writer(f).writerow([
                t.entry_time.isoformat() if t.entry_time else "", t.trade_id,
                t.event_ticker, t.market_ticker,
                t.side, t.entry_price, t.quantity, t.mode, t.status,
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
from backend.strategies import get_experiment
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

        # 3. Strategy experiment
        active = self.settings.strategy.active_experiment
        self.strategy = get_experiment(active, self.settings.strategy.experiments.get(active, {}))

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

## Phase 8: Frontend Scaffolding + Types + API Client

> **⚠️ No `frontend/` directory exists yet.** Before implementing hooks, create the
> frontend project:
> ```bash
> cd /Users/pastry/Projects/nunu
> bun create vite frontend --template react-ts
> cd frontend && bun add @tanstack/react-query tailwindcss
> ```
> This creates `frontend/package.json`, `tsconfig.json`, `vite.config.ts`, `src/`, etc.
> Then implement `src/lib/types.ts` and `src/lib/api.ts` per the API contract.
>
> Frontend Routes (from `docs/plans/generic-prediction-market-scanner-platform.md`):
> | Route | Page | Purpose |
> |-------|------|---------|
> | `/` | Dashboard | Live events, top markets, scanner status |
> | `/events` | Events | Searchable event list |
> | `/events/[id]` | EventDetail | Orderbook, markets, progress |
> | `/candidates` | Candidates | Approve/reject candidates |
> | `/trades` | Trades | Trade history |
> | `/settings` | Settings | Threshold, mode, strategy |

## Phase 8: Frontend Hooks (continued)

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

## Phase 9: Frontend Pages (✅ Complete)

**Commit:** `5b848d0`

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

## Phase 10: Frontend Components + API Contract Alignment (✅ Complete)

**Commit:** `ad25701` (Components) + `28e42ba` (API alignment + WS store)

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

### 10.2 — What was actually built (Phase 10 real scope)

Beyond the components above, Phase 10 included critical integration work:

**Vite proxy config** — `frontend/vite.config.ts` added `/api` → `http://localhost:8000` proxy with `ws: true`, so the frontend dev server forwards all API + WS calls to the backend. Single URL for both.

**Zustand WebSocket store** — `frontend/src/stores/wsStore.ts` manages all WS connections at the **app level** (not per-hook):
- Module-level maps hold WebSocket instances, listeners, and reconnect timers
- `initialize()` in `main.tsx` pre-connects all 4 channels: `scanner`, `events`, `candidates`, `trades`
- `connect()` / `disconnect()` / `scheduleReconnect()` manage connection lifecycle
- `ensurePing()` fires a `{ type: "ping" }` every 30s; backend replies with `{ type: "pong" }`
- Reactive status via Zustand `useWSStore` — components subscribe to `connectedChannels`

**`useWebSocket` simplified** — hooks only register/unregister listeners; they no longer create or manage WS connections. This eliminates mount/unmount reconnect storms.

**Backend `websocket_handler.py` DRYed** — all 4 WS endpoints share a single `_ping_loop()` that handles ping/pong, error recovery, and disconnect.

**API contract alignment** — `frontend/src/lib/types.ts` refactored to match actual backend response shapes:
- `EventSummary` / `EventDetail` / `CandidateResponse` / `TradeRecord` / `ScannerConfigResponse` all aligned with backend Pydantic dataclasses
- Removed incorrect enum types (`Side`, `CandidateSide`, `MarketStatus`, `TradeStatus` values)
- Added `RankedMarket`, `TradesResponse` (wraps `trades` + `total` + `limit` + `offset`)

---

## Phase 11: Pipeline Diagnostics Panel (📋 Spec Complete — Not Yet Implemented)

**Commit:** _TBD_

**Goal:** A live diagnostics console in the Settings page that surfaces the scanner pipeline stage-by-stage (E1→E7) and backend HTTP request traces — all pushed in real-time over the existing `scanner` WebSocket channel. This makes the backend's internal workflow observable from the frontend.

### 11.1 — Backend: Pipeline progress broadcast model

Create `backend/models/scanner_progress.py` with:

```python
@dataclass
class PipelineStage:
    stage: str          # "E1" through "E7"
    label: str          # "Discovery", "Classification", "Grouping", "Orderbook", "Ranking", "Progress Gate", "Validation"
    status: str         # "pending" | "running" | "done" | "error" | "skipped" (never ran because pipeline exited early)
    input_count: int = 0
    output_count: int = 0
    duration_ms: int = 0
    error: str | None = None

@dataclass
class PipelineCycle:
    cycle_id: int
    status: str         # "running" | "completed" | "error"
    stages: dict[str, PipelineStage]
    started_at: str | None = None
    completed_at: str | None = None
    total_markets_discovered: int = 0
    total_events_active: int = 0
    total_candidates_found: int = 0

@dataclass
class ApiTrace:
    method: str
    path: str
    status: int
    duration_ms: int
    rate_remaining: int
    timestamp: str
    error: str | None = None
```

### 11.2 — Wire WS broadcasts into E8 orchestrator

In `backend/engines/engine8_orchestrator.py`:

- Import `manager` from `backend.api.websocket_handler` (lazy import inside `run_one_shot` to avoid circular imports)
- Before E1: broadcast `scanner:started`
- After each E-stage: broadcast `scanner:stage_update` with stage counts + timing
- On completion: broadcast `scanner:completed` with `StopResult`-style summary
- On error: broadcast `scanner:error`

**WS message types on the `scanner` channel:**
```
scanner:started       → { cycle_id, started_at }
scanner:stage_update  → { cycle_id, stage, label, status, input_count, output_count, duration_ms, error? }
scanner:completed     → { cycle_id, completed_at, total_duration_ms, total_markets, total_events, total_candidates }
scanner:error         → { cycle_id, stage, error }
```

### 11.3 — Add HTTP request tracing to KalshiHttpClient

In `backend/adapters/kalshi/http_client.py`:

- Add optional `on_request: Callable[[ApiTrace], Awaitable[None]] | None = None` to `KalshiHttpClient` (**must be async** — see bugfix below)
- After each `response = await self.client.request(...)` (successful or retry-exhausted), build an `ApiTrace` and `await self.on_request(trace)`
- After a retry-exhausted failure, build an `ApiTrace` with extracted response info + `error` field
- Only includes: method, path, status, duration_ms, rate_remaining from headers, timestamp
- Never logs: request body, response body, auth headers, signing material
- Wrap the `await self.on_request(trace)` call in `try/except logger.warning(...)` so a failing callback doesn't crash the API call
- Probe rate limit headers: check `x-rate-limit-remaining`, `x-kalshi-rate-limit-remaining`, `ratelimit-remaining` (in order); `rate_remaining = None` if none found

**🐛 Bugfix — Async callback + batching using `asyncio.Queue`:**

Initial spec had `on_request` as sync (`Callable`) but `manager.broadcast()` is async. Sync callback can't await. If we fire-and-forget with `asyncio.create_task`, exceptions vanish and broadcasts become unpredictable.

**Fix:** Use an `asyncio.Queue` shared between `run_one_shot()` and the HTTP client:

In `engine8_orchestrator.py`, inside `run_one_shot()`:

```python
trace_queue: asyncio.Queue[ApiTrace] = asyncio.Queue()
client.on_request = lambda t: trace_queue.put_nowait(t)

# Background flusher task
async def _flush_traces():
    try:
        while True:
            batch: list[ApiTrace] = []
            try:
                while len(batch) < 20:
                    trace = await asyncio.wait_for(trace_queue.get(), timeout=0.5)
                    batch.append(trace)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            if batch:
                try:
                    await manager.broadcast("scanner", "scanner:api_batch", batch)
                except Exception:
                    logger.warning("Failed to broadcast trace batch", exc_info=True)
    except asyncio.CancelledError:
        # Final flush on cancellation
        remaining = []
        while not trace_queue.empty():
            try:
                remaining.append(trace_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if remaining:
            await manager.broadcast("scanner", "scanner:api_batch", remaining)

flusher = asyncio.create_task(_flush_traces())
```

The flusher task is cancelled when the pipeline completes or errors:

```python
flusher.cancel()
try:
    await flusher
except asyncio.CancelledError:
    pass  # flusher does final flush in CancelledError handler
```

### 11.4 — Wire live pollers

In `backend/engines/live/discovery_poller.py`:

- Broadcast `scanner:discovery_cycle` with event count diff after each poll loop

In `backend/engines/live/progress_gate_loop.py`:

- Broadcast `scanner:progress_cycle` with candidate count after each loop

### 11.5 — Add `GET /api/v1/scanner/progress` REST fallback

In `backend/api/rest.py`:

```python
@router.get("/scanner/progress")
async def get_scanner_progress():
    """Return current pipeline cycle state (for initial mount before WS messages arrive)."""
```

Returns the current `PipelineCycle` snapshot from a lightweight in-memory store (updated each time the orchestrator broadcasts).

### 11.6 — Frontend: Add types to `lib/types.ts`

> **🐛 Bugfix — snake_case alignment:** Backend Pydantic models serialize with `model_dump_json()` using snake_case field names (`input_count`, `output_count`). TypeScript types must match exactly — the frontend receives JSON property names as-is from the backend.

```typescript
export interface PipelineStage {
  stage: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped';
  input_count: number;
  output_count: number;
  duration_ms: number;
  error?: string;
}

export interface PipelineCycle {
  cycle_id: number;
  status: 'running' | 'completed' | 'error';
  stages: Record<string, PipelineStage>;
  started_at: string | null;
  completed_at: string | null;
  total_markets_discovered: number;
  total_events_active: number;
  total_candidates_found: number;
}

export interface ApiTrace {
  method: string;
  path: string;
  status: number;
  duration_ms: number;
  rate_remaining: number | null;  // null if Kalshi didn't send rate-limit headers
  timestamp: string;
  error?: string;
}

export type DiagnosticLogEntry =
  | { kind: 'pipeline-stage'; stage: PipelineStage }
  | { kind: 'api-trace'; trace: ApiTrace }
  | { kind: 'cycle-event'; type: 'started' | 'completed' | 'error'; cycle_id: number };
```

### 11.7 — Create `useDiagnostics` hook

Create `frontend/src/hooks/useDiagnostics.ts`:

- Subscribes to `scanner` WS channel via `useWebSocket`
- Accumulates `PipelineCycle` state (current active cycle)
- Accumulates `ApiTrace[]` ring buffer (last 200 entries)
- Tracks `completedCycles: PipelineCycle[]` — last 3 completed cycles (to preserve visibility if a new cycle starts mid-pipeline)
- Derives `DiagnosticLogEntry[]` from both — each entry gets a timestamp
- Returns: `{ currentCycle, completedCycles, apiTraces, logEntries, clear, paused, setPaused }`
- Uses `useRef` to avoid stale closure issues
- Batches React state updates with a render throttle (~3fps via a simple `setTimeout` gate)

**Key behaviors:**
- `scanner:started` → creates a new `currentCycle`, pushes previous completed one to `completedCycles`
- `scanner:stage_update` → updates the stage inside `currentCycle`
- `scanner:completed` / `scanner:error` → marks all remaining `pending` stages as `skipped` (prevents "waiting forever" in summary strip)
- `scanner:api_batch` → appends to apiTraces ring buffer (capped at 200), derives log entries
- `clear` → resets everything
- `paused` → stops appending new entries (but still accepts and discards)

### 11.8 — Create `DiagnosticsPanel` component

Create `frontend/src/components/DiagnosticsPanel.tsx`:

**🐛 Bugfix — Auto-scroll vs user scroll-up conflict:**
The component tracks scroll position. Only auto-scrolls to bottom when the user is already near the bottom (within 40px). If the user scrolls up to read historical logs, new entries don't steal their position. A "Jump to bottom" button appears when scrolled up.

**🐛 Bugfix — Re-render cascade from parent:**
Wrapped in `React.memo()` so config changes in Settings.tsx don't force unnecessary re-renders of the panel.

Create `frontend/src/components/DiagnosticsPanel.tsx`:

**Layout:**
```
┌─ Diagnostics ─────────────────────────────────── [Pipeline] [HTTP] [All] ● Live [Clear] [Pause] ─┐
│ E1 ✅  E2 ✅  E3 ✅  E4 🔄 3/8  E5 ⏳  E6 ⏳  E7 ⏳           ← pipeline summary strip           │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 19:42:03  🔄 Scanner cycle #42 started                                                           │
│ 19:42:04  ✅ E1 Discovery        12,450 markets                                                  │
│ 19:42:05  ✅ E2 Classification   148 → 11 same-day-live                                          │
│ 19:42:05  🌐 GET /markets?limit=100 → 200 (1.2s)  rate_remaining=42                             │
│ 19:42:06  🌐 GET /markets?limit=100&cursor=xxx → 200 (0.4s)                                     │
│ 19:42:07  🔄 E4 Orderbook        3/8 markets                                                     │
│ 19:42:08  ❌ E4 Orderbook        HTTP 429 rate-limited — retrying...                             │
│ 19:42:11  ✅ E6 Progress Gate    3 candidates found                                              │
│ 19:42:12  ✅ Scanner cycle #42 complete (9.2s)  3 candidates                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Features:**
- **Collapsible** — toggle `▼/▲` header to show/hide
- **Auto-scroll** — scrolls to bottom on new entry unless user has scrolled up
- **Filter pills** — `[Pipeline]` `[HTTP]` `[All]` toggle which log entry kinds appear
- **Live indicator** — green dot + "Live" when WS connected, gray "Disconnected" when not
- **Clear** — empties all log entries
- **Pause/Resume** — stops incoming entries from appending (useful to freeze for reading)
- **Pipeline summary strip** — shows E1-E7 in a single row with ✅/🔄/⏳ status per stage
- **Scrollable log area** — fixed max-height (`max-h-96`), dark code-like background (`bg-gray-950`), monospace font
- **Color coding**: green for completed stages, yellow for running, blue for HTTP traces, red for errors
- **Smart auto-scroll** (🐛 bugfix): tracks `isUserAtBottom` via `onScroll` handler (within 40px of bottom). Only auto-scrolls when user is at the bottom. Shows a floating "↓ Jump to bottom" button when scrolled up.
- **React.memo wrapper** (🐛 bugfix): prevents re-renders when parent Settings page updates config state

### 11.9 — Integrate into Settings.tsx

Add below the Save button:

```tsx
<section className="mt-8 border-t border-gray-700 pt-8">
  <DiagnosticsPanel />
</section>
```

### 11.10 — WS listener conflict mitigation

Update `frontend/src/stores/wsStore.ts` — change `registerListener` from `Map<string, cb>` to `Map<string, Set<cb>>` so multiple components can listen on the same `scanner` channel without silently replacing each other.

**🐛 Bugfix — Backward-compatible `unregisterListener`:**

Existing callers (`useWebSocket` cleanup) call `unregisterListener(channel)` without passing a specific callback — they expect the whole channel to be cleared. New multi-listener callers need to pass the callback to remove just that one.

Both patterns supported via optional `cb` parameter:

```typescript
const listeners = new Map<string, Set<(msg: WSMessage) => void>>();

export function registerListener(channel: string, cb: (msg: WSMessage) => void): void {
  if (!listeners.has(channel)) listeners.set(channel, new Set());
  listeners.get(channel)!.add(cb);
}

export function unregisterListener(channel: string, cb?: (msg: WSMessage) => void): void {
  if (cb) {
    listeners.get(channel)?.delete(cb);
  } else {
    listeners.delete(channel);  // clear all — backward compat for existing callers
  }
}
```

Update `wsStore.ts` `onmessage` handler to iterate the Set:

```typescript
ws.onmessage = (event) => {
  const msg: WSMessage = JSON.parse(event.data);
  if (msg.type === 'pong') return;
  const channelListeners = listeners.get(channel);
  if (channelListeners) {
    for (const cb of channelListeners) {
      cb(msg);
    }
  }
};
```

### 11.11 — Theoretical QA: Bugs Found & Fixes Applied

A systematic end-to-end trace of every data path revealed **10 bugs** in the initial spec. Each is documented below with the fix baked into the plan above.

#### 🐛 CRITICAL: Async/sync mismatch in HTTP tracing callback

**Problem:** `KalshiHttpClient.request()` is async. The `on_request` callback is called after each response. But `manager.broadcast()` is also async — you can't `await` from a sync callback. If we use `asyncio.create_task()` from a sync callback, unhandled exceptions silently disappear and the task may survive beyond the pipeline lifecycle.

**Fix:**
```python
# In http_client.py — on_request is an async callable:
on_request: Callable[[ApiTrace], Awaitable[None]] | None = None

# Inside request(), after the response:
if self.on_request:
    try:
        await self.on_request(trace)
    except Exception:
        logger.warning("HTTP trace callback failed", exc_info=True)
```

This adds ~1ms per request (the `await` is near-instant). For E1's ~120 paginated requests, that's ~120ms total overhead — acceptable.

#### 🐛 CRITICAL: Snake_case / camelCase mismatch

**Problem:** Backend Pydantic models serialize with `model_dump_json()` → snake_case field names (`input_count`, `output_count`). The TypeScript types in the initial spec used camelCase (`inputCount`, `outputCount`). The frontend would receive snake_case JSON but access camelCase properties → all values `undefined`.

**Fix:** All TypeScript types use snake_case field names, matching the backend's Pydantic serialization:

```typescript
export interface PipelineStage {
  stage: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped';
  input_count: number;
  output_count: number;
  duration_ms: number;
  error?: string;
}
// ... same pattern for all types
```

#### 🐛 HIGH: Broadcast exceptions crash the pipeline

**Problem:** Each `await manager.broadcast(...)` could raise (e.g., WS connection drops mid-send). Without try/except, the exception propagates up `run_one_shot()` and aborts the entire pipeline mid-scan.

**Fix:** Every `manager.broadcast()` call in the orchestrator is wrapped:

```python
try:
    await manager.broadcast("scanner", "scanner:stage_update", stage)
except Exception:
    logger.warning("Failed to broadcast stage update", exc_info=True)
```

Same pattern for live poller broadcasts.

#### 🐛 HIGH: HTTP trace batching architecture was undefined

**Problem:** The spec said "buffer and flush every 500ms" but didn't define *how*. The `on_request` callback fires inside `KalshiHttpClient.request()`, which is called deep inside E1's pagination loop (`fetch_all_open_markets()` → `list_markets()` → `http.request()`). The orchestrator has no control over when callbacks fire mid-stage.

**Fix:** Use an `asyncio.Queue` shared between `run_one_shot()` and the HTTP client:

1. `run_one_shot()` accepts an optional `trace_queue: asyncio.Queue[ApiTrace]`
2. When set, `KalshiHttpClient.on_request = lambda t: trace_queue.put_nowait(t)`
3. `run_one_shot()` spawns a background `asyncio.Task` that does:
   ```python
   async def _flush_traces():
       while True:
           batch = []
           try:
               while len(batch) < 20:
                   trace = await asyncio.wait_for(trace_queue.get(), timeout=0.5)
                   batch.append(trace)
           except (asyncio.TimeoutError, asyncio.CancelledError):
               pass
           if batch:
               await manager.broadcast("scanner", "scanner:api_batch", batch)
   ```
4. On error or completion, the task is cancelled and flushed one final time

This keeps tracing zero-overhead on the critical path (the `put_nowait` is O(1)) and batches the broadcasts at ~2 batches/second max.

#### 🐛 HIGH: Auto-scroll UX steals user's position

**Problem:** New log entries cause auto-scroll to bottom. If the user scrolls up to read a historical entry, the next WS message snatches them back to the bottom — infuriating.

**Fix:** Track scroll position in `DiagnosticsPanel`:

```typescript
const [isUserAtBottom, setIsUserAtBottom] = useState(true);
const logEndRef = useRef<HTMLDivElement>(null);

const handleScroll = useCallback(() => {
  const el = logEndRef.current?.parentElement;
  if (!el) return;
  const threshold = 40; // px from bottom
  setIsUserAtBottom(el.scrollTop + el.clientHeight >= el.scrollHeight - threshold);
}, []);

// Only auto-scroll when user hasn't scrolled up:
useEffect(() => {
  if (isUserAtBottom) {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }
}, [logEntries, isUserAtBottom]);
```

#### 🐛 HIGH: Pipeline summary shows ⏳ for stages that never ran

**Problem:** If E1 finds 0 same-day-live markets, E3-E7 never execute. Their status stays "⏳ waiting" forever in the pipeline summary strip.

**Fix:** When the pipeline completes (or errors), auto-mark all remaining `pending` stages as `skipped`:

```typescript
// On scanner:completed or scanner:error
if (msg.type === 'scanner:completed' || msg.type === 'scanner:error') {
  setPipelineCycle(prev => {
    if (!prev) return prev;
    const updated = { ...prev };
    for (const stage of Object.values(updated.stages)) {
      if (stage.status === 'pending') stage.status = 'skipped';
    }
    return updated;
  });
}
```

Also: a stage with 0 input and 0 output that was never called shows as `skipped` (not `pending`).

#### 🐛 MEDIUM: Rate limit header name is unknown

**Problem:** The spec assumed Kalshi returns a `rate_remaining` header on 200 responses. In practice, the Kalshi V2 API may not provide standard rate-limit headers. `KalshiHttpClient` only reads `retry-after` on 429 responses.

**Fix:** Probe for multiple possible header names; `null` if none found:

```python
rate_remaining = None
for header in ("x-rate-limit-remaining", "x-kalshi-rate-limit-remaining", "ratelimit-remaining"):
    if header in response.headers:
        try:
            rate_remaining = int(response.headers[header])
        except (ValueError, TypeError):
            pass
        break
```

The frontend TypeScript type makes `rate_remaining: number | null` explicit. The UI shows "?" when `null`.

#### 🐛 MEDIUM: Multiple pipeline cycles race

**Problem:** If a user triggers `POST /scanner/start` while the live poller is also running, two concurrent cycles broadcast interleaved messages. The frontend replaces `pipelineCycle` state on each `scanner:started`, losing visibility into the first cycle.

**Fix:** Track a short history of recent cycles:

```typescript
interface UseDiagnosticsReturn {
  currentCycle: PipelineCycle | null;      // actively running or last completed
  completedCycles: PipelineCycle[];         // last 3 completed cycles
  // ... rest
}
```

Completed cycles (with `scanner:completed` or `scanner:error`) are appended to `completedCycles` (capped at 3), then `currentCycle` is reset to allow the next `scanner:started` to create a new one.

#### 🐛 MEDIUM: `unregisterListener` API breakage

**Problem:** Changing `registerListener` from `Map<string, cb>` to `Map<string, Set<cb>>` requires unregistration to specify *which* callback to remove. But existing callers (`useWebSocket` cleanup) call `unregisterListener(channel)` without a callback, intending to clear all listeners for that channel.

**Fix:** Support both signatures:

```typescript
export function registerListener(channel: string, cb: (msg: WSMessage) => void): void {
  if (!listeners.has(channel)) listeners.set(channel, new Set());
  listeners.get(channel)!.add(cb);
}

export function unregisterListener(channel: string, cb?: (msg: WSMessage) => void): void {
  if (cb) {
    listeners.get(channel)?.delete(cb);
  } else {
    listeners.delete(channel); // clear all for this channel
  }
}
```

Existing callers pass no callback → channel is fully cleared. New multi-listener callers pass the specific callback → only that listener is removed.

#### 🐛 LOW: `DiagnosticsPanel` re-renders on every config change

**Problem:** `Settings.tsx` re-renders whenever config queries or mutations update. These re-renders cascade into `DiagnosticsPanel`, causing unnecessary DOM diffing.

**Fix:** Wrap `DiagnosticsPanel` in `React.memo()`:

```typescript
const DiagnosticsPanel = React.memo(function DiagnosticsPanel() {
  // ... component body
});
```

Since the panel only depends on WS messages (not props), memoization prevents re-renders from parent state changes.

---

### Risk Mitigations Summary (updated)

| # | Risk | Mitigation Applied |
|---|------|--------------------|
| 1 | Circular import — engines importing `manager` | Lazy `import` inside function bodies |
| 2 | WS flood from E1 pagination (~120 API calls) | HTTP traces buffered via `asyncio.Queue`, flushed every 500ms as batches of ≤20 |
| 3 | Single listener per channel replaced silently | `registerListener` → `Map<string, Set<cb>>`; `unregisterListener` has backward-compat overload |
| 4 | Memory leak — log entries accumulate forever | Ring buffer capped at 200 API traces; `[Clear]` button; completed cycles capped at 3 |
| 5 | Settings page cramped | Diagnostics panel is collapsible with `max-h-96` scrollable log area |
| 6 | Sensitive data in HTTP traces | Only method, path, status, timing logged — never body, headers, or auth material |
| 7 | WS messages arrive before component mounts | `GET /api/v1/scanner/progress` REST endpoint provides initial state snapshot |
| 8 | Stale closures in WS listener | `useWebSocket` uses `useRef`; `useDiagnostics` uses `useRef` for accumulation + render throttle |
| 9 | Broadcast exceptions crash pipeline | Every `manager.broadcast()` wrapped in `try/except logger.warning` |
| 10 | Auto-scroll steals user's position | `isUserAtBottom` scroll-detection; only auto-scroll when user is at the bottom |
| 11 | Snake_case/camelCase type mismatch | TypeScript types use snake_case to match Pydantic `model_dump_json()` |
| 12 | Async/sync callback mismatch | `on_request` is `Callable[[ApiTrace], Awaitable[None]]`; `await`-ed inside `request()` |
| 13 | Rate limit header unknown | Probes multiple header names; `rate_remaining: number \| null` in types |
| 14 | Multiple cycles race | Track `currentCycle` + `completedCycles[]` (last 3) |
| 15 | Stages never ran show as "waiting" forever | `scanner:completed`/`scanner:error` marks remaining `pending` stages as `skipped` |
| 16 | Re-render cascade on config changes | `DiagnosticsPanel` wrapped in `React.memo()` |

### 11.12 — Multi-column pipeline visual redesign

Refactor `DiagnosticsPanel` from a single log list to a 4-column grid layout, one column per engine/endpoint, each showing its own live feed.

#### Column layout

```
┌─ 🔧 Pipeline Diagnostics ────────────────────────────────────────────────── [▼] ─┐
├───────────────┬───────────────────┬────────────────┬─────────────────────────────┤
│ 🔍 DISCOVERY  │ ⚙️ PIPELINE E1-E7 │ 🎯 PROGRESS    │ ↗ API CALLS                 │
│ ● Live        │ ● Idle            │ GATE ● Checking│ 142 total · 3 err           │
├───────────────┼───────────────────┼────────────────┼─────────────────────────────┤
│ [scrolling    │ [scrolling feed]  │ [scrolling     │ [scrolling feed]            │
│  feed]        │                   │  feed]         │                             │
│               │ ── #3 ──          │                │ ↗ GET /markets              │
│ 14:02:01      │ ✅ Discovery      │ 14:01:30       │   200 · 43ms                │
│ 🔍 120 mkts   │   200→120 (43ms)  │ ⏱ Checked 12  │ ──────────────────────      │
│   8 events    │ ✅ Classify       │   events       │ ↗ POST /orderbook           │
│   +2 / -0     │   120→8 (12ms)    │ ─────────────  │   201 · 120ms               │
│ ────────────  │ ✅ Grouping       │ 14:00:15       │ ──────────────────────      │
│ 14:00:08      │   8→8 (2ms)      │ ⏱ Checked 8   │ ↗ GET /markets              │
│ 🔍 115 mkts   │ ✅ Orderbook      │   events       │   200 · 38ms                │
│   7 events    │   8→8 (215ms)    │                │                             │
│   +1 / -0     │ ✅ Ranking        │                │                             │
│               │   8→8 (3ms)      │                │                             │
│               │ ✅ Progress Gate  │                │                             │
│               │   8→3 (8ms)      │                │                             │
│               │ ✅ Validation     │                │                             │
│               │   3→2 (67ms)     │                │                             │
│               │                  │                │                             │
│               │ ── #2 (error) ── │                │                             │
│               │ ❌ Discovery      │                │                             │
│               │   error: timeout  │                │                             │
└───────────────┴───────────────────┴────────────────┴─────────────────────────────┘
```

#### Component architecture

All new files in `frontend/src/components/pipeline/`:

| Sub-component | File | Data Source | Memo strategy |
|---|---|---|---|
| `DiscoveryColumn` | `pipeline/DiscoveryColumn.tsx` | `diagnostics.discoveryFeed` — ring buffer of `scanner:discovery_cycle` events | `React.memo`, auto-scroll via `useRef`, stable keys per event |
| `PipelineColumn` | `pipeline/PipelineColumn.tsx` | `diagnostics.currentCycle` + `diagnostics.completedCycles` | `React.memo`, stage sorting with `useMemo` (stable E1→E7 order), `useCallback` for inline handlers |
| `ProgressGateColumn` | `pipeline/ProgressGateColumn.tsx` | `diagnostics.progressGateFeed` — ring buffer of `scanner:progress_cycle` events | `React.memo`, auto-scroll via `useRef` |
| `ApiTracesColumn` | `pipeline/ApiTracesColumn.tsx` | `diagnostics.apiTraces` | `React.memo`, path truncation with `useMemo`, color coding with `useMemo` |

#### Phase 1 — Refactor `useDiagnostics` hook

**File:** `frontend/src/hooks/useDiagnostics.ts`

- Add `discoveryFeed: DiscoveryEvent[]` state (ring buffer, last 100 entries).
- Add `progressGateFeed: ProgressGateEvent[]` state (ring buffer, last 100 entries).
- Each entry: `{ timestamp, data }` where data is the raw WS payload.
- New types:
  ```typescript
  export interface DiscoveryEvent { timestamp: string; data: { total_markets: number; total_events: number; added: number; removed: number } }
  export interface ProgressGateEvent { timestamp: string; data: { events_checked: number } }
  ```
- Mount-only `useEffect` populates the new feeds from existing WS listeners (no new WS subscriptions).
- Keep existing `addLog` callback via `useCallback` for downward compatibility.
- Return: `{ ..., discoveryFeed, progressGateFeed }`.

#### Phase 2 — Column sub-components

Each component:
- Receives only the data it needs (no store reference — just arrays of events).
- Uses `React.memo` wrapper.
- Has a header bar with status dot + column title.
- Has a fixed-height scrollable feed (`h-64 overflow-y-auto`).
- Implements auto-scroll: tracks `isUserAtBottom` via `onScroll`, scrolls to bottom on new entries only when user is at bottom.
- Uses stable keys (e.g. `discovery-${index}` for ring buffer index, `trace-${method}-${timestamp}`).
- No inline functions or objects in JSX props — uses `useCallback`/`useMemo`.

**DiscoveryColumn details:**
```tsx
interface DiscoveryColumnProps {
  events: DiscoveryEvent[];
  isRunning: boolean;
}
```
- Shows "● Live" when `isRunning` is true AND events have been received recently (< 60s ago), else "○ Idle".
- Each row: gray timestamp, 🔍 icon, `N markets, N events, +added/-removed`.

**PipelineColumn details:**
```tsx
interface PipelineColumnProps {
  currentCycle: PipelineCycleInfo | null;
  completedCycles: PipelineCycleInfo[];
  isRunning: boolean;
}
```
- Top card = current (running) cycle with E1→E7 stages.
- Below: completed cycles as smaller collapsed cards.
- Stage row format: status badge (`✅`/`▶️`/`❌`/`⏭️`), `label: input→output (Nms)`.
- Empty state: "No pipeline runs yet."

**ProgressGateColumn details:**
```tsx
interface ProgressGateColumnProps {
  events: ProgressGateEvent[];
  isRunning: boolean;
}
```
- Shows "● Checking" when `isRunning` && recent events, else "○ Idle".
- Each row: timestamp, ⏱ icon, `Checked N events`.

**ApiTracesColumn details:**
```tsx
interface ApiTracesColumnProps {
  traces: ApiTraceInfo[];
  isRunning: boolean;
}
```
- Summary bar: `N total · M errors` with yellow highlight if errors > 0.
- Each row: status icon (↗️/⚠️), `METHOD /short-path → status (Nms)`.
- Long paths truncated with ellipsis via `useMemo`.

#### Phase 3 — Rewrite `DiagnosticsPanel.tsx`

**File:** `frontend/src/components/DiagnosticsPanel.tsx` (rewrite)

- Imports all 4 column sub-components.
- Uses `useDiagnostics()` hook for all data.
- Collapsible header (same `div[role="button"]` pattern, no nested `<button>`).
- Grid layout: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4`.
- Each column rendered in its own `<div>`.
- "Clear" button resets all column data via `diagnostics.reset()`.
- Below the grid: collapsed "Raw Log" accordion that shows the original text log viewer for debugging.
- Maintains `React.memo` wrapper.

#### Phase 4 — Performance guarantees

| Item | How |
|------|-----|
| Column re-renders | `React.memo` on each column — only re-renders when its prop reference changes |
| Ring buffers | Arrays capped at 100 entries — React never diffs 1000-element lists |
| Stable keys | `discovery-${idx}`, `stage-${stage.stage}`, `gate-${timestamp}`, `trace-${method}-${ts}` — not array index |
| Auto-scroll | Each column maintains its own `useRef` + `onScroll` handler — no shared state |
| No inline props | All handlers wrapped in `useCallback` at the hook level |
| Settings page | `DiagnosticsPanel` already `React.lazy` loaded with `<Suspense>` — the 4 column components are imported normally inside the panel (not lazy individually, to avoid waterfall) |

#### Phase 5 — Status header bar (pills above columns)

Add a status bar row above the grid with individual pills showing system health at a glance.

**Data sources:**
- **Mode pill** — from `GET /api/v1/scanner/status` → `.mode` (dry_run / read_only / live) fetched on mount + polled every 30s via `useEffect` interval. Color: green=live, yellow=read_only, gray=dry_run.
- **Uptime pill** — from scanner status `.uptime_seconds`, formatted as `Xh Ym` via `useMemo`.
- **Market count pill** — from `.markets_tracked`, live-updated from `scanner:discovery_cycle` WS events.
- **Rate limit % pill** — from `ApiTraceInfo.rate_remaining` (last known value). Shown as `N remaining` with color: green > 50%, yellow > 10%, red ≤ 10%.
- **WS status pill** — from `wsStore.connectedChannels` Zustand store. Shows `● Connected` / `○ Disconnected` for the `scanner` channel. Subscribes via Zustand `useWSStore(s => s.connectedChannels.scanner)`.

**Implementation:**
- New sub-component: `StatusBar` in `frontend/src/components/pipeline/StatusBar.tsx`
- Props: `{ mode: ScannerMode; uptimeSeconds: number; marketCount: number; rateLimitRemaining: number | null; wsConnected: boolean }`
- `React.memo` wrapper.
- Layout: `<div className="flex flex-wrap gap-2 mb-4">` with pill `<span>` elements.
- Each pill: rounded-full, small text, colored dot, label.
- Fetched scanner status via a small `useScannerStatus()` hook or inline in `DiagnosticsPanel.tsx`:
  ```typescript
  const [status, setStatus] = useState<ScannerStatus | null>(null);
  useEffect(() => {
    fetch(`${API_BASE}/scanner/status`).then(r => r.json()).then(d => setStatus(d.data));
    const timer = setInterval(() => {...}, 30000);
    return () => clearInterval(timer);
  }, []);
  ```
- Rate limit: track the latest `rate_remaining` from `apiTraces[apiTraces.length - 1]?.rate_remaining` via `useMemo`.

**Memoization:**
- `StatusBar` wrapped in `React.memo` — only re-renders when status data actually changes.
- Status fetch uses a mount-only `useEffect` with interval cleanup.

#### Phase 6 — Additional columns (medium-value)

Expand the grid to include 3 more columns from the "medium-value" diagnostics data. The grid becomes `grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5`, with the original 4 columns on the left and the new ones pushed to additional rows on smaller screens.

##### Column 5: Error Feed (`pipeline/ErrorFeed.tsx`)

- **Data source:** Derived from `logs.filter(l => l.type === 'cycle_error' || (l.type === 'trace' && l.detail?.status >= 400))` + any errors from `completedCycles` (iterate `.stages` and collect stage entries where `.status === 'error'`).
- **Display:** Vertical feed of error entries only — red-highlighted, timestamped.
- Each row: ❌ icon + message + timestamp.
- Counter badge in header: `❌ Errors (N)`.
- **Scrolling:** Respects user scroll position (same pattern as other columns — `isUserAtBottom` + auto-scroll only when at bottom). Not "always auto-scroll" — that would steal position.
- **🐛 Bugfix — `completedCycles` error extraction:** Use a `useMemo` to flatten all stage errors:
  ```typescript
  const cycleErrors = useMemo(() => {
    return completedCycles.flatMap(c =>
      Object.values(c.stages).filter(s => s.status === 'error').map(s => ({ cycle_id: c.cycle_id, ...s }))
    );
  }, [completedCycles]);
  ```
- **🐛 Bugfix — API trace error severity:** 4xx errors (client errors, e.g., 429 rate limit) and 5xx errors (server errors) shown with different icons: ⚠️ for 4xx, ❌ for 5xx.
- `React.memo` wrapper.

##### Column 6: Candidate Queue (`pipeline/CandidateQueue.tsx`)

- **Data source:** `GET /api/v1/candidates` fetched on mount + polled every 15s.
- **🐛 Bugfix — No overlapping polls:** Use recursive `setTimeout` instead of `setInterval`. If the fetch takes >15s, the next poll waits 15s after the previous one completes, not on an overlapping schedule:
  ```typescript
  const POLL_MS = 15_000;
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const resp = await fetch(`${API_BASE}/candidates`);
        const json = await resp.json();
        if (!cancelled) setData(json.data ?? []);
      } catch { /* ignore */ }
      if (!cancelled) setTimeout(poll, POLL_MS);
    };
    poll();
    return () => { cancelled = true; };
  }, []);
  ```
- **Display:**
  - Pending count (blue badge)
  - Approved count (green badge)
  - Rejected count (red badge)
  - Total count
- Each candidate shown if available: `event_ticker → side $price` with status badge.
- Links to event detail if available.
- **🐛 Bugfix — Auth/empty responses:** If the endpoint returns a 401 or `success: false`, show `"Auth required"` or `"No candidates yet"` empty state instead of crashing.
- **Memoization:** `React.memo`, data fetch via mount-only `useEffect` with cancelled flag cleanup.

##### Column 7: Live Event Metrics (`pipeline/LiveEventMetrics.tsx`)

- **Data source:** Derived from `scanner:discovery_cycle` WS events over time + current scanner status.
- **Display:** Delta-based metrics:
  - Markets tracked (current count + delta from last cycle)
  - Events tracked (current count + delta)
  - Active candidates
  - Time since last discovery
- Each metric as a small labeled stat with trend arrow (↑ ↓ →).
- **🐛 Bugfix — First-event delta:** When only one discovery event exists, there's nothing to diff against. Show `—` instead of a delta value:
  ```typescript
  const delta = useMemo(() => {
    if (events.length < 2) return null;
    const prev = events[events.length - 2];
    const curr = events[events.length - 1];
    return { markets: curr.data.total_markets - prev.data.total_markets, events: ... };
  }, [events]);
  ```
- **🐛 Bugfix — "Time since last discovery" ticker:** Without a periodic timer, the display freezes at the value set when the event arrived. Add a `useEffect` that updates every 60s:
  ```typescript
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);
  const lastDiscovery = events.length > 0 ? events[events.length - 1].timestamp : null;
  const timeSince = lastDiscovery ? Math.floor((now - new Date(lastDiscovery).getTime()) / 1000) : null;
  ```
- **🐛 Bugfix — Double data source:** WS discovery events and REST scanner status both report market/event counts. If they diverge (WS delayed vs REST fresh), numbers would flicker. Fix: prefer WS data when available; only fall back to REST when `events.length === 0` (before first discovery cycle).
- **Memoization:** `React.memo`, delta calculations via `useMemo` comparing last two discovery events.

#### Layout update for Phase 6

The grid expands to accommodate all columns. On wide screens all 7 columns are visible; on narrower layouts columns wrap to the next row:

```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
  {/* Row 1: core columns */}
  <DiscoveryColumn ... />        {/* col 1 */}
  <PipelineColumn ... />         {/* col 2 */}
  <ProgressGateColumn ... />     {/* col 3 */}
  <ApiTracesColumn ... />        {/* col 4 */}
  {/* Row 2: additional columns */}
  <ErrorFeed ... />              {/* col 5 */}
  <CandidateQueue ... />         {/* col 6 */}
  <LiveEventMetrics ... />       {/* col 7 */}
</div>
```

### Theoretical QA: Bugs Found & Fixes Applied

A systematic playthrough of every component's data path found the following bugs. All are fixed in the plan above.

| # | Component | Bug | Fix |
|---|-----------|-----|-----|
| 1 | StatusBar | `setInterval` polls can overlap if fetch takes >30s | Recursive `setTimeout` instead of `setInterval` — next poll starts after previous completes |
| 2 | StatusBar | `setState` after unmount if user navigates away | `AbortController` + cancelled flag in cleanup |
| 3 | StatusBar | `useWSStore(s => s.connectedChannels.scanner)` returns `undefined` on first render | `?? false` fallback |
| 4 | DiscoveryColumn + ProgressGateColumn | `React.memo` prevents re-render when no new events arrive, so "Live" → "Idle" transition never happens | Internal `useEffect` with 60s interval that updates a `lastEventTime` ref; staleness check compares against `Date.now()` on each interval tick |
| 5 | All columns | Ring buffer uses array index as React key; when old entries drop off, indices shift causing React to think all items changed | Monotonically incrementing ID counter (`useRef(0)`) in `useDiagnostics`, assigned to each event on insertion |
| 6 | ApiTracesColumn | Long URL paths overflow beyond column width | CSS `overflow-hidden text-ellipsis` on path span; `useMemo` truncates path to ~40 chars |
| 7 | ApiTracesColumn | 4xx (client) and 5xx (server) errors shown identically | Different icons: ⚠️ for 4xx, ❌ for 5xx |
| 8 | ErrorFeed | Extracting errors from `completedCycles` requires nested iteration of `.stages` | Flatten via `useMemo`: `Object.values(c.stages).filter(s => s.status === 'error').map(...)` |
| 9 | ErrorFeed | "Always auto-scroll" conflicts with user reading historical errors | Same `isUserAtBottom` scroll-lock pattern as other columns |
| 10 | CandidateQueue | `setInterval` causes overlapping requests if fetch takes >15s | Recursive `setTimeout` with cancelled flag |
| 11 | CandidateQueue | 401 / `success: false` responses crash the component | `"Auth required"` / `"No candidates yet"` empty states |
| 12 | LiveEventMetrics | With only one discovery event, there's no previous value to diff against | Ternery: `delta === null ? "—" : formattedDelta` |
| 13 | LiveEventMetrics | "Time since last discovery" freezes after event arrives | 60s `setInterval` ticker updating `Date.now()` |
| 14 | LiveEventMetrics | WS discovery data and REST scanner status report conflicting counts | Prefer WS data; fall back to REST only when `events.length === 0` |
| 15 | `useDiagnostics` | All WS handlers assume `data` fields exist; malformed messages crash | Optional chaining (`data?.field`) + default values on all field accesses |

#### Risk Register Additions

| # | Risk | Mitigation |
|---|------|------------|
| 17 | Columns are empty on initial mount (late-join) | `useDiagnostics` discovery/progress feeds initialized empty; data flows in from WS within seconds |
| 18 | Discovery column shows stale "Live" after engine stops | "Recent" heuristic: check if last event timestamp is within 60s; fall back to "Idle" |
| 19 | 7 columns on mobile too cramped | Responsive grid: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5` — columns wrap to next row on smaller screens |
| 20 | Pipeline column has too many cycle cards | `completedCycles` already capped at 3 by `useDiagnostics` |
| 21 | Status bar data stale after navigating away | Poll interval refetches every 30s; WS discovery events update market count instantly |
| 22 | Rate limit pill shows stale value | Uses last known `ApiTrace.rate_remaining` — resets to null if no API calls in last 60s |
| 23 | Candidate Queue shows no data on initial mount | Unauthenticated / no-candidates responses handled gracefully with "No candidates" empty state |
| 24 | 7 columns too wide on small screens | Responsive grid: 1→2→3→5 columns as screen size increases; each column has min-width |

---

## Phase 12: Test Infrastructure (⬜ Not Yet Implemented)

### 12.1 — Test setup

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

### 12.2 — `tests/test_utils.py` (DRY: shared factory functions)

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

### 12.3 — `pytest.ini`

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

### 12.4 — `tests/conftest.py` (fixtures + helper functions)

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

### 12.5 — Running tests

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

### 12.6 — Running the app

```bash
# Backend only (Phase 1)
cd backend && uvicorn backend.main:app --reload --port 8000

# Test connection first
cd backend && python scripts/test_connection.py

# Run full scanner pipeline (dry-run)
cd backend && python scripts/run_simulation.py

# Full stack via run.sh
./run.sh
```

---

## Phase 13: Docker + Integration (⬜ Not Yet Implemented)

### 13.1 — `docker-compose.yml`

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
      - ./.env
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

### 13.2 — `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 13.3 — Dev Runner

The project root has a single `run.sh` script that starts everything:

```bash
# Default: backend + frontend
./run.sh

# Include Docker Compose
./run.sh --docker
```

### 13.4 — Testing Script

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

## Full Build Execution Order (62 Steps)

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
Step 15: backend/config/settings.py                 # No deps (pydantic-settings loader)

# ─── Phase 2: Kalshi Adapter (SRP: auth/http/client split) ────────────
Step 16: backend/adapters/kalshi/auth.py            # No deps (RSA-PSS signing)
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

# ─── Phase 4: Strategies (7 experiments, single select_trade() per ADR-018) ──
Step 34: backend/strategies/base.py                              # Depends on core/interfaces/
Step 35: backend/strategies/executed_volume_follower.py          # Depends on base.py
Step 36: backend/strategies/executed_volume_fade.py              # Depends on base.py
Step 37: backend/strategies/favorite_side_follower.py            # Depends on base.py
Step 38: backend/strategies/momentum_follower.py                 # Depends on base.py
Step 39: backend/strategies/liquidity_filtered_follower.py       # Depends on base.py
Step 40: backend/strategies/resting_depth_follower.py            # Depends on base.py
Step 41: backend/strategies/hybrid_score_follower.py             # Depends on base.py
Step 42: backend/strategies/__init__.py                          # Depends on all experiments

# ─── Phase 5: Backtesting Infrastructure ────────────────────────────────
Step 43: backend/strategies/backtesting/__init__.py
Step 44: backend/strategies/backtesting/feature_builder.py     # Depends on base.py
Step 45: backend/strategies/backtesting/entry_simulator.py     # Depends on base.py
Step 46: backend/strategies/backtesting/exit_simulator.py      # Depends on base.py
Step 47: backend/strategies/backtesting/metrics.py             # Depends on base.py
Step 48: backend/strategies/backtesting/backtest_engine.py     # Depends on all above

# ─── Phase 6: Trading + Logging + Portfolio ────────────────────────────
Step 49: backend/trading/portfolio.py               # No deps (core dataclasses)
Step 50: backend/trading/execution_engine.py        # Depends on portfolio, adapter, E7
Step 51: backend/trading/trade_executor.py          # Thin facade over execution_engine
Step 52: backend/logging/log_setup.py               # No deps (stdlib logging)
Step 53: backend/logging/csv_logger.py              # Depends on models

# ─── Phase 7: API Layer (DRY: shared errors.py) ────────────────────────
Step 54: backend/api/errors.py                      # No deps
Step 55: backend/api/rest.py                        # Depends on everything above
Step 56: backend/main.py                            # Depends on everything above

# ─── Phase 8+: Frontend scaffolding & pages ─────────────────────────
# (Phases 8-10 steps defined in their respective phase sections above)

# ─── Phase 11: Pipeline Diagnostics Panel ────────────────────────────
Step 77: backend/models/scanner_progress.py          # Pipeline stage + cycle + API trace dataclasses
Step 78: backend/engines/engine8_orchestrator.py      # Add WS broadcasts after each E-stage
Step 79: backend/adapters/kalshi/http_client.py        # Add on_request callback for HTTP tracing
Step 80: backend/api/rest.py                          # Add GET /scanner/progress endpoint
Step 81: frontend/src/lib/types.ts                     # Add PipelineStage, PipelineCycle, ApiTrace, DiagnosticLogEntry
Step 82: frontend/src/hooks/useDiagnostics.ts         # New hook — WS listener + ring buffer + render throttle
Step 83: frontend/src/components/DiagnosticsPanel.tsx # New component — collapsible live log + pipeline summary
Step 84: frontend/src/stores/wsStore.ts               # Multi-listener support (Map → Map<string, Set>)
Step 85: frontend/src/hooks/useDiagnostics.ts         # Add discoveryFeed + progressGateFeed ring buffers + types
Step 86: frontend/src/components/pipeline/DiscoveryColumn.tsx    # New — memoized discovery feed column
Step 87: frontend/src/components/pipeline/PipelineColumn.tsx     # New — memoized E1-E7 stage column
Step 88: frontend/src/components/pipeline/ProgressGateColumn.tsx # New — memoized progress gate column
Step 89: frontend/src/components/pipeline/ApiTracesColumn.tsx    # New — memoized API trace column
Step 90: frontend/src/components/DiagnosticsPanel.tsx            # Rewrite to multi-column grid layout
Step 91: frontend/src/components/pipeline/StatusBar.tsx          # New — status pills bar (mode, uptime, markets, rate limit, WS)
Step 92: frontend/src/hooks/useDiagnostics.ts                    # Add error feed derivation + scanner status fetch
Step 93: frontend/src/components/pipeline/CandidateQueue.tsx     # New — candidate queue polling column
Step 94: frontend/src/components/pipeline/LiveEventMetrics.tsx   # New — live event delta metrics column
```

---

## Scaffold Script

```bash
#!/bin/bash
# scripts/scaffold.sh — Create all directories

mkdir -p backend/{config,core/{models,interfaces},utils,adapters/kalshi,engines/live,strategies,trading,logging,api}
mkdir -p config tests scripts

# Note: frontend/ and logs/ scaffolded in Phases 8 and 6 respectively

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
find config tests -type d 2>/dev/null | sort
```
