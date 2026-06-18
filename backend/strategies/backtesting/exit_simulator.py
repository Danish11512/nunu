"""Exit simulation for backtesting.

Provides settlement-based exit simulation with placeholders for
profit target, stop loss, and time-based exits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExitReason(Enum):
    """Reason for a trade exit."""
    SETTLEMENT = "settlement"
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_STOP = "time_stop"


@dataclass
class ExitResult:
    """Result of a simulated trade exit."""
    exit_price_cents: int
    exit_reason: ExitReason
    pnl_cents: int
    roi_percent: float


def hold_to_settlement(
    entry_price: int,
    side: str,
    settlement_result: str,
) -> ExitResult:
    """Simulate holding a position until settlement.

    Args:
        entry_price: Entry price in cents paid.
        side: "yes" or "no" — the side that was bought.
        settlement_result: "yes" or "no" — the market settlement outcome.

    Returns:
        ExitResult with payout of 100¢ if the bought side won, 0¢ if lost.
    """
    won = (side == settlement_result)
    payout = 100 if won else 0
    pnl = payout - entry_price
    roi = (pnl / entry_price) * 100.0 if entry_price > 0 else 0.0

    return ExitResult(
        exit_price_cents=payout,
        exit_reason=ExitReason.SETTLEMENT,
        pnl_cents=pnl,
        roi_percent=roi,
    )


def exit_at_profit_target(
    entry_price: int,
    target_price_cents: int,
) -> ExitResult:
    """Simulate exiting when a profit target is hit.

    NOTE: This is a stub for future expansion. The current backtest
    engine only uses hold_to_settlement.
    """
    pnl = target_price_cents - entry_price
    roi = (pnl / entry_price) * 100.0 if entry_price > 0 else 0.0

    return ExitResult(
        exit_price_cents=target_price_cents,
        exit_reason=ExitReason.PROFIT_TARGET,
        pnl_cents=pnl,
        roi_percent=roi,
    )


def exit_at_stop_loss(
    entry_price: int,
    stop_price_cents: int,
) -> ExitResult:
    """Simulate exiting when a stop loss is hit.

    NOTE: This is a stub for future expansion.
    """
    pnl = stop_price_cents - entry_price
    roi = (pnl / entry_price) * 100.0 if entry_price > 0 else 0.0

    return ExitResult(
        exit_price_cents=stop_price_cents,
        exit_reason=ExitReason.STOP_LOSS,
        pnl_cents=pnl,
        roi_percent=roi,
    )
