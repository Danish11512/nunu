"""Experiment F: Resting Depth Follower.

Uses orderbook depth as the primary signal. Selects the market with the
highest total resting order quantity, then bets on the side with deeper depth.

Alignment: Uses core `MarketFeatures.total_resting_order_quantity` as the
primary signal (this IS available at runtime from orderbook data). Extended
fields `yes_total_depth`/`no_total_depth` add precision when populated by
Phase 5 FeatureBuilder.
"""

from backend.core.interfaces.strategy import EventFeatures, TradeDecision
from backend.strategies.base import StrategyExperiment


class RestingDepthFollower(StrategyExperiment):
    """Highest total resting depth → deeper side."""

    name = "resting-depth-follower"
    description = (
        "Original most-bet logic: highest resting orderbook depth → deeper side. "
        "Uses total_resting_order_quantity as primary signal; extended depth "
        "fields add precision in backtesting."
    )

    def select_trade(self, features: EventFeatures) -> TradeDecision:
        # ── Step 1: Select market with highest depth ──
        # Prefer extended yes_total_depth + no_total_depth if available
        has_extended_depth = any(
            m.yes_total_depth > 0 or m.no_total_depth > 0
            for m in features.child_markets
        )

        if has_extended_depth:
            valid = [
                m for m in features.child_markets
                if m.yes_total_depth > 0 or m.no_total_depth > 0
            ]
            if not valid:
                return TradeDecision(
                    market_ticker="", side="no", should_trade=False,
                    reason="no_depth_data",
                )
            selected = max(
                valid,
                key=lambda m: (m.yes_total_depth or 0) + (m.no_total_depth or 0),
            )
            # Use extended depth for side selection
            side = (
                "yes"
                if (selected.yes_total_depth or 0) > (selected.no_total_depth or 0)
                else "no"
            )
        else:
            # Core path: use total_resting_order_quantity + bid-price proxy
            with_depth = [
                m for m in features.child_markets
                if m.total_resting_order_quantity > 0
            ]
            if not with_depth:
                return TradeDecision(
                    market_ticker="", side="no", should_trade=False,
                    reason="no_resting_depth",
                )
            selected = max(
                with_depth, key=lambda m: m.total_resting_order_quantity
            )
            # Infer deeper side from bid prices
            side = "yes" if selected.yes_bid > selected.no_bid else "no"

        entry_price = selected.yes_bid if side == "yes" else selected.no_bid

        return TradeDecision(
            market_ticker=selected.ticker,
            side=side,
            should_trade=True,
            confidence=0.65,
            reason=f"highest_depth_{selected.ticker}_side_{side}",
            entry_price_cents=entry_price,
            max_contracts=100,
        )
