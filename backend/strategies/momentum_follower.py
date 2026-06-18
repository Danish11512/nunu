"""Experiment D: Momentum Follower.

Catches trends: selects the market with the strongest price momentum,
then buys in the direction of movement.

Alignment: Primarily uses extended field `yes_price_momentum` (defaults to 0).
At runtime (Engine 6/7), falls back to spread-based proxy since momentum
requires multiple data points from historical trade data. Full functionality
requires Phase 5 FeatureBuilder to populate extended fields.
"""

from backend.core.interfaces.strategy import EventFeatures, TradeDecision
from backend.strategies.base import StrategyExperiment


class MomentumFollower(StrategyExperiment):
    """Largest price move → direction of movement."""

    name = "momentum-follower"
    description = (
        "Catches trends: largest absolute price move → direction of movement. "
        "Uses yes_price_momentum (extended) when available; falls back to "
        "spread-based proxy at runtime."
    )

    def select_trade(self, features: EventFeatures) -> TradeDecision:
        # ── Try extended path: yes_price_momentum populated ──
        with_momentum = [
            m for m in features.child_markets
            if abs(m.yes_price_momentum) > 0.001
        ]
        if with_momentum:
            selected = max(with_momentum, key=lambda m: abs(m.yes_price_momentum))
            side = "yes" if selected.yes_price_momentum > 0 else "no"
            confidence = min(abs(selected.yes_price_momentum) / 100.0, 0.95)
            reason = f"momentum_{side}_move_{selected.yes_price_momentum:+.1f}"
        else:
            # ── Fallback: use spread as rough sentiment proxy ──
            # Wide spread = uncertainty = potential momentum shift
            # Narrow spread = consensus = trend continuation
            with_spread = [
                m for m in features.child_markets if m.spread_cents > 0
            ]
            if not with_spread:
                return TradeDecision(
                    market_ticker="", side="no", should_trade=False,
                    reason="no_momentum_or_spread_data",
                )

            # Narrowest spread = most consensus = momentum toward current favorite
            selected = min(with_spread, key=lambda m: m.spread_cents)
            side = "yes" if selected.yes_bid > 50 else "no"
            # Low confidence — this is a weak proxy
            confidence = max(0.35, 0.5 - selected.spread_cents / 100.0)
            reason = f"momentum_proxy_narrow_spread_{selected.spread_cents}c_side_{side}"

        entry_price = selected.yes_bid if side == "yes" else selected.no_bid

        return TradeDecision(
            market_ticker=selected.ticker,
            side=side,
            should_trade=True,
            confidence=confidence,
            reason=reason,
            entry_price_cents=entry_price,
            max_contracts=100,
        )
