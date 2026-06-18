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
