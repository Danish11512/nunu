"""Experiment A: Executed Volume Follower.

Follows the crowd: selects the market with the highest trading volume,
then bets on the side with the higher bid price (proxy for dominant side).

Alignment: Uses core `MarketFeatures.volume` as the primary signal.
If extended fields `total_executed_volume`/`yes_executed_volume`/`no_executed_volume`
are populated (Phase 5 FeatureBuilder), uses those instead for more precise ranking.
"""

from backend.core.interfaces.strategy import EventFeatures, TradeDecision
from backend.strategies.base import StrategyExperiment


class ExecutedVolumeFollower(StrategyExperiment):
    """Market with highest volume → side with higher bid price."""

    name = "executed-volume-follower"
    description = (
        "Follows the crowd: highest executed trade volume → most-bet side. "
        "Uses volume as primary signal; falls back to bid-price proxy when "
        "extended fields are unavailable."
    )

    def select_trade(self, features: EventFeatures) -> TradeDecision:
        # ── Step 1: Select market ──
        # Prefer total_executed_volume (extended) if available, else volume (core)
        has_extended = any(
            m.total_executed_volume > 0 for m in features.child_markets
        )
        if has_extended:
            valid = [m for m in features.child_markets if m.total_executed_volume > 0]
            if not valid:
                return TradeDecision(
                    market_ticker="", side="no", should_trade=False,
                    reason="no_markets_with_executed_volume",
                )
            selected = max(valid, key=lambda m: m.total_executed_volume)
            # Use extended side-volume data if available
            if selected.yes_executed_volume > 0 or selected.no_executed_volume > 0:
                side = "yes" if selected.yes_executed_volume > selected.no_executed_volume else "no"
                signal_strength = (
                    max(selected.yes_executed_volume, selected.no_executed_volume)
                    / (selected.yes_executed_volume + selected.no_executed_volume)
                    if (selected.yes_executed_volume + selected.no_executed_volume) > 0
                    else 0.0
                )
            else:
                # Fallback to bid-price proxy
                side = "yes" if selected.yes_bid > selected.no_bid else "no"
                signal_strength = 0.0
        else:
            # Core path: use volume + bid-price proxy
            valid = [m for m in features.child_markets if m.volume > 0]
            if not valid:
                return TradeDecision(
                    market_ticker="", side="no", should_trade=False,
                    reason="no_markets_with_volume",
                )
            selected = max(valid, key=lambda m: m.volume)
            side = "yes" if selected.yes_bid > selected.no_bid else "no"
            signal_strength = 0.0

        entry_price = selected.yes_bid if side == "yes" else selected.no_bid

        return TradeDecision(
            market_ticker=selected.ticker,
            side=side,
            should_trade=True,
            confidence=min(signal_strength + 0.5, 1.0) if signal_strength > 0 else 0.6,
            reason=(
                f"highest_volume_{selected.ticker}_side_{side}"
                if not has_extended
                else f"highest_executed_vol_{selected.ticker}_side_{side}"
            ),
            entry_price_cents=entry_price,
            max_contracts=100,
        )
