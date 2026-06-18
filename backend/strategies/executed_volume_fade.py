"""Experiment B: Executed Volume Fade.

Fades the crowd: selects the same market as Exp A (highest trading volume),
but bets AGAINST the dominant side. Hypothesis: the crowd overpays for the
dominant side, creating edge on the cheap side.

Alignment: Uses core `MarketFeatures.volume` as the primary signal.
If extended fields are populated (Phase 5 FeatureBuilder), uses those instead.
"""

from backend.core.interfaces.strategy import EventFeatures, TradeDecision
from backend.strategies.base import StrategyExperiment


class ExecutedVolumeFade(StrategyExperiment):
    """Highest volume market → fade (bet against) the dominant side."""

    name = "executed-volume-fade"
    description = (
        "Fades the crowd: highest volume market → bet against the dominant side. "
        "Hypothesis: crowd overpays for the favorite, creating edge on the opposite side."
    )

    def select_trade(self, features: EventFeatures) -> TradeDecision:
        # ── Step 1: Select market (same as Exp A) ──
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
            # Determine dominant side from extended side-volume data
            if selected.yes_executed_volume > 0 or selected.no_executed_volume > 0:
                dominant = "yes" if selected.yes_executed_volume > selected.no_executed_volume else "no"
            else:
                dominant = "yes" if selected.yes_bid > selected.no_bid else "no"
        else:
            valid = [m for m in features.child_markets if m.volume > 0]
            if not valid:
                return TradeDecision(
                    market_ticker="", side="no", should_trade=False,
                    reason="no_markets_with_volume",
                )
            selected = max(valid, key=lambda m: m.volume)
            dominant = "yes" if selected.yes_bid > selected.no_bid else "no"

        # ── Step 2: Fade the dominant side ──
        fade_side = "no" if dominant == "yes" else "yes"
        entry_price = selected.yes_bid if fade_side == "yes" else selected.no_bid

        return TradeDecision(
            market_ticker=selected.ticker,
            side=fade_side,
            should_trade=True,
            confidence=0.5,  # Fade strategies are inherently less confident
            reason=f"fade_{dominant}_on_{selected.ticker}",
            entry_price_cents=entry_price,
            max_contracts=100,
        )
