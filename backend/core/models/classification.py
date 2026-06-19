from dataclasses import dataclass, field

from backend.core.models.market import Market


@dataclass
class ClassificationResult:
    """Result of running a classifier on a market."""

    market_ticker: str
    event_ticker: str
    is_same_day_live: bool = False
    confidence: float = 0.0  # 0.0 to 1.0
    reason: str = ""


@dataclass
class ClassifiedEvent:
    """A grouped event with classified markets."""

    event_ticker: str
    event_title: str
    event_sub_title: str = ""  # Shortened title from Kalshi events API
    event_start_date: str | None = None
    event_end_date: str | None = None
    event_description: str | None = None
    markets: list[Market] = field(default_factory=list)
    classification: ClassificationResult | None = None
    num_markets: int = 0
    total_volume: int = 0
