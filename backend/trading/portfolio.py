"""
Portfolio tracking — positions, PnL, balance.
Mirrors polymarket-arbitrage core/portfolio.py but simplified for one-sided (most-bet) scanning.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from backend.core.models.trading import TradeRecord

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
