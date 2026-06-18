"""Entry simulation for backtesting.

Provides taker and maker fill simulation with configurable slippage.
All prices are in integer cents.
"""

from dataclasses import dataclass


@dataclass
class FillResult:
    """Result of a simulated trade entry."""
    filled: bool
    price_cents: int
    fill_quantity: int
    mode: str          # "taker" | "maker"
    slippage_cents: int


def simulate_taker_entry(
    side: str,
    price_cents: int,
    quantity: int,
    spread_cents: int = 0,
) -> FillResult:
    """Simulate a taker fill by crossing the spread.

    Execution price is symmetric: price_cents + spread_cents.
    Side-specific spread crossing (bid/ask) is reserved for future use.

    Args:
        side: "yes" or "no"
        price_cents: Limit price in cents
        quantity: Number of contracts
        spread_cents: Additional spread to cross (slippage)

    Returns:
        FillResult with execution at price_cents + spread_cents.
    """
    execution_price = price_cents + spread_cents
    return FillResult(
        filled=True,
        price_cents=execution_price,
        fill_quantity=quantity,
        mode="taker",
        slippage_cents=spread_cents,
    )


def simulate_maker_entry(
    side: str,
    quantity: int,
    best_bid: int,
    best_ask: int,
) -> FillResult:
    """Simulate a maker fill by providing liquidity.

    For yes side, fills at best_bid.
    For no side, the implied no price is (100 - best_ask).

    Args:
        side: "yes" or "no"
        quantity: Number of contracts
        best_bid: Current best bid price in cents
        best_ask: Current best ask price in cents

    Returns:
        FillResult with execution at the maker price.
    """
    if side == "yes":
        limit_price = best_bid
    else:
        limit_price = 100 - best_ask

    return FillResult(
        filled=True,
        price_cents=limit_price,
        fill_quantity=quantity,
        mode="maker",
        slippage_cents=0,
    )
