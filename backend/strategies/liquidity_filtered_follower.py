"""Experiment E: Liquidity Filtered Follower.

Volume follower with liquidity guards. Same core logic as Exp A but filters
out illiquid markets before selection. Protects against bad fills by requiring
minimum volume, maximum spread, and sane price boundaries.

Alignment: Uses core `MarketFeatures` fields for runtime filtering
(volume, spread_cents, yes_bid, no_bid). Extended fields
(total_executed_volume, trade_count) add precision when available.
"""

from backend.core.interfaces.strategy import EventFeatures, MarketFeatures, TradeDecision
from backend.strategies.base import StrategyExperiment


# ── Default filter thresholds ──
# These work with core MarketFeatures fields available at runtime.
_DEFAULT_MIN_VOLUME = 500
_DEFAULT_MAX_SPREAD_CENTS = 5
_DEFAULT_MAX_PRICE = 85
_DEFAULT_MIN_PRICE = 15


class LiquidityFilteredFollower(StrategyExperiment):
    """Volume follower with liquidity filters to avoid bad fills."""

    name = "liquidity-filtered-follower"
    description = (
        "Volume follower with liquidity guards: filters out illiquid markets "
        "before selecting highest-volume market and most-bet side."
    )

    def __init__(
        self,
        name: str = "liquidity-filtered-follower",
        description: str = "",
        min_volume: int = _DEFAULT_MIN_VOLUME,
        max_spread_cents: int = _DEFAULT_MAX_SPREAD_CENTS,
        max_price_cents: int = _DEFAULT_MAX_PRICE,
        min_price_cents: int = _DEFAULT_MIN_PRICE,
    ):
        desc = description or (
            "Volume follower with liquidity guards: filters out illiquid markets "
            "before selecting highest-volume market and most-bet side."
        )
        super().__init__(name=name, description=desc)
        self.min_volume = min_volume
        self.max_spread_cents = max_spread_cents
        self.max_price_cents = max_price_cents
        self.min_price_cents = min_price_cents

    def _passes_filters(self, m: MarketFeatures) -> bool:
        """Check if a market passes all liquidity filters."""
        # Volume filter (core field)
        if m.volume < self.min_volume:
            return False

        # Extended: also check total_executed_volume if available
        if m.total_executed_volume > 0 and m.total_executed_volume < self.min_volume:
            return False

        # Spread filter (core field)
        if m.spread_cents > self.max_spread_cents:
            return False

        # Price sanity filters (core fields)
        yes_price = m.yes_bid
        if yes_price > self.max_price_cents or yes_price < self.min_price_cents:
            return False

        return True

    def select_trade(self, features: EventFeatures) -> TradeDecision:
        filtered = [m for m in features.child_markets if self._passes_filters(m)]
        if not filtered:
            return TradeDecision(
                market_ticker="", side="no", should_trade=False,
                reason=(
                    f"no_markets_pass_filters_"
                    f"min_vol_{self.min_volume}_max_spread_{self.max_spread_cents}"
                ),
            )

        # Select highest-volume market from filtered set
        has_extended = any(m.total_executed_volume > 0 for m in filtered)
        if has_extended:
            selected = max(filtered, key=lambda m: m.total_executed_volume)
        else:
            selected = max(filtered, key=lambda m: m.volume)

        # Determine side
        side = "yes" if selected.yes_bid > selected.no_bid else "no"
        entry_price = selected.yes_bid if side == "yes" else selected.no_bid

        return TradeDecision(
            market_ticker=selected.ticker,
            side=side,
            should_trade=True,
            confidence=0.7,  # Higher confidence due to liquidity filtering
            reason=f"filtered_highest_vol_{selected.ticker}_side_{side}",
            entry_price_cents=entry_price,
            max_contracts=100,
        )
