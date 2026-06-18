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
    # Live tracking
    last_discovery: datetime | None = None
    last_progress_check: datetime | None = None
    # Configuration snapshot for this cycle
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def get_event(self, event_ticker: str) -> EventWithTopMarkets | None:
        """Return the ranked event matching *event_ticker*, or None."""
        for ev in self.ranked_events:
            if ev.event_ticker == event_ticker:
                return ev
        return None

    def get_candidate(self, event_ticker: str) -> ValidatedOrderCandidate | None:
        """Return the candidate matching *event_ticker*, or None."""
        for c in self.candidates:
            if c.original_candidate.event_ticker == event_ticker:
                return c
        return None

    def get_candidates_for_event(self, event_ticker: str) -> list[ValidatedOrderCandidate]:
        """Return all candidates for a given event ticker."""
        return [
            c for c in self.candidates
            if c.original_candidate.event_ticker == event_ticker
        ]

    @property
    def markets_by_ticker(self) -> dict[str, dict[str, Any]]:
        """Build a lookup dict of markets keyed by their ``ticker``."""
        return {
            m.get("ticker", ""): m
            for m in self.markets
            if m.get("ticker")
        }

    @property
    def active_candidates(self) -> list[ValidatedOrderCandidate]:
        """Return only candidates where ``is_valid`` is True."""
        return [c for c in self.candidates if c.is_valid]


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
