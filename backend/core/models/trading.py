from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RankedMarket:
    """A market with its ranking score and price data."""

    market_ticker: str
    volume: int
    spread_cents: int
    yes_price: int  # Current yes bid or valuation
    no_price: int  # Current no bid or valuation
    rank: int
    score: float  # Composite ranking score


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

    event_ticker: str  # NOT event_id — consistent with Market.event_ticker
    market_ticker: str  # NOT market_id — consistent with Market.ticker
    side: str  # "yes" or "no"
    price: int  # Limit price in cents
    confidence: float = 0.0
    reason: str = ""
    volume: int = 0
    progress_pct: float = 0.0  # 0–100 scale
    created_at: datetime | None = None


@dataclass
class ProgressBasedOrderCandidate(OrderCandidate):
    """Candidate created by Engine 6 (progress gate)."""

    most_bet_side: str = ""  # NOT "selected_side" — see build plan
    threshold_pct: float = 0.0  # The threshold that was met
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
    status: str = "open"  # "open" | "closed" | "cancelled"
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
