"""Price change tracker — detects, logs, and broadcasts pricing changes.

Three ingestion paths:
1. WebSocket push (orderbook_delta) — real-time, zero rate limit cost
2. HTTP webhook POST — external push notifications
3. Polling fallback — via PriceRefresher (already exists at 5s interval)

Only broadcasts when prices actually change (dedup).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class PriceSnapshot:
    """A single price data point for a market ticker."""

    ticker: str
    yes_bid: int | None
    yes_ask: int | None
    no_bid: int | None
    no_ask: int | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PriceChange:
    """A detected price change (delta != 0)."""

    ticker: str
    field: str  # "yes_bid" | "yes_ask" | "no_bid" | "no_ask"
    old_value: int | None
    new_value: int | None
    delta: int | None  # None if old was None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PriceChangeTracker:
    """Tracks price history per ticker, detects changes, broadcasts.

    Evicts tickers with no updates after ``ttl_seconds`` (default 1 hour)
    to prevent unbounded memory growth. Set to 0 to disable eviction.

    Usage:
        tracker = PriceChangeTracker(on_change=my_broadcast_fn)
        await tracker.ingest("KXLYDYX", yes_bid=65, yes_ask=70, ...)
    """

    def __init__(
        self,
        on_change: Callable[[list[PriceChange]], Awaitable[None]] | None = None,
        max_history: int = 100,
        ttl_seconds: int = 3600,
    ):
        self._latest: dict[str, PriceSnapshot] = {}  # ticker -> latest snapshot
        self._history: dict[str, list[PriceSnapshot]] = {}  # ticker -> snapshots
        self._max_history = max_history
        self._ttl_seconds = ttl_seconds
        self._on_change = on_change
        self._lock = asyncio.Lock()

    async def ingest(
        self,
        ticker: str,
        yes_bid: int | None = None,
        yes_ask: int | None = None,
        no_bid: int | None = None,
        no_ask: int | None = None,
        source: str = "unknown",
    ) -> list[PriceChange]:
        """Ingest a new price data point. Returns list of detected changes.

        Args:
            ticker: Market ticker (e.g. ``"KXLYDYX"``).
            yes_bid: Best yes bid price in cents (or None if unknown).
            yes_ask: Best yes ask price in cents.
            no_bid: Best no bid price in cents.
            no_ask: Best no ask price in cents.
            source: Human-readable source label (``"ws"``, ``"webhook"``, ``"poll"``).

        Returns:
            List of :class:`PriceChange` objects (empty if no changes).
        """
        snapshot = PriceSnapshot(
            ticker=ticker,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=no_bid,
            no_ask=no_ask,
        )

        async with self._lock:
            prev = self._latest.get(ticker)
            changes = self._detect_changes(ticker, prev, snapshot)

            # Update latest
            self._latest[ticker] = snapshot

            # Append to history
            if ticker not in self._history:
                self._history[ticker] = []
            self._history[ticker].append(snapshot)
            if len(self._history[ticker]) > self._max_history:
                self._history[ticker] = self._history[ticker][-self._max_history:]

            # Evict stale tickers periodically (every 100th ingest)
            if self._ttl_seconds > 0 and (len(self._latest) % 100 == 0):
                self._evict_stale()

        # Log + broadcast changes outside lock
        if changes:
            logger.info(
                "Price change [%s] %s: %d changes",
                ticker, source, len(changes),
            )
            for c in changes:
                logger.debug(
                    "  %s: %s -> %s (delta=%s)",
                    c.field, c.old_value, c.new_value, c.delta,
                )

            if self._on_change:
                try:
                    await self._on_change(changes)
                except Exception as e:
                    logger.error("Price change callback failed: %s", e)

        return changes

    def _detect_changes(
        self,
        ticker: str,
        prev: PriceSnapshot | None,
        curr: PriceSnapshot,
    ) -> list[PriceChange]:
        """Compare prev → curr, return list of changes."""
        if prev is None:
            return []  # First snapshot = no delta, just baseline

        changes: list[PriceChange] = []
        for field in ("yes_bid", "yes_ask", "no_bid", "no_ask"):
            old_val = getattr(prev, field)
            new_val = getattr(curr, field)
            if old_val != new_val:
                delta = new_val - old_val if old_val is not None else None
                changes.append(PriceChange(
                    ticker=ticker,
                    field=field,
                    old_value=old_val,
                    new_value=new_val,
                    delta=delta,
                ))
        return changes

    def _evict_stale(self) -> int:
        """Remove tickers with no update within TTL. Returns count evicted."""
        cutoff = datetime.now(timezone.utc).timestamp() - self._ttl_seconds
        stale = [t for t, s in self._latest.items()
                 if s.timestamp.timestamp() < cutoff]
        for t in stale:
            self._latest.pop(t, None)
            self._history.pop(t, None)
        if stale:
            logger.debug("Evicted %d stale tickers (TTL=%ds)", len(stale), self._ttl_seconds)
        return len(stale)

    def get_latest(self, ticker: str) -> PriceSnapshot | None:
        """Get latest snapshot for a ticker."""
        return self._latest.get(ticker)

    def get_history(self, ticker: str, limit: int = 10) -> list[PriceSnapshot]:
        """Get recent price history for a ticker."""
        hist = self._history.get(ticker, [])
        return hist[-limit:]

    def get_all_tickers(self) -> list[str]:
        """Return list of tickers with tracked prices."""
        return list(self._latest.keys())

    @property
    def summary(self) -> dict[str, Any]:
        """Return a summary dict of all tracked prices."""
        return {
            ticker: {
                "yes_bid": s.yes_bid,
                "yes_ask": s.yes_ask,
                "no_bid": s.no_bid,
                "no_ask": s.no_ask,
                "last_updated": s.timestamp.isoformat() if s.timestamp else None,
            }
            for ticker, s in self._latest.items()
        }

    def to_json(self) -> str:
        """Serialize tracker state to JSON."""
        data = {
            ticker: {
                "yes_bid": s.yes_bid,
                "yes_ask": s.yes_ask,
                "no_bid": s.no_bid,
                "no_ask": s.no_ask,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            }
            for ticker, s in self._latest.items()
        }
        return json.dumps(data, indent=2)
