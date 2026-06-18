"""Experiment G: Hybrid Score Follower.

Weighted composite scoring for both market and side selection. The most
sophisticated strategy, combining volume, depth, momentum, and liquidity
signals into a single score.

Full formula (requires Phase 5 FeatureBuilder for all fields):
    market_score = 0.40 * norm_volume + 0.25 * norm_trades + 0.20 * norm_momentum + 0.15 * norm_liquidity
    yes_score = 0.45 * norm_yes_vol + 0.25 * norm_yes_momentum + 0.20 * norm_yes_depth + 0.10 * norm_yes_trades
    no_score  = 0.45 * norm_no_vol  + 0.25 * norm_no_momentum  + 0.20 * norm_no_depth  + 0.10 * norm_no_trades

Runtime fallback: simplified scoring using core fields only.
"""

from backend.core.interfaces.strategy import EventFeatures, MarketFeatures, TradeDecision
from backend.strategies.base import StrategyExperiment


class HybridScoreFollower(StrategyExperiment):
    """Weighted composite scoring: best combined signal across dimensions."""

    name = "hybrid-score-follower"
    description = (
        "Weighted composite score for market and side selection. Combines "
        "volume, depth, momentum, and liquidity into a single ranked score. "
        "Full formula requires Phase 5 FeatureBuilder; simplified at runtime."
    )

    def _compute_market_score(self, m: MarketFeatures, max_vol: int, max_depth: int) -> float:
        """Compute a market-level composite score (0-1)."""
        # Volume component (core)
        vol_score = m.volume / max(max_vol, 1)

        # Depth component (core)
        depth_score = m.total_resting_order_quantity / max(max_depth, 1)

        # Extended: momentum component
        momentum_score = min(abs(m.yes_price_momentum) / 100.0, 1.0) if abs(m.yes_price_momentum) > 0.001 else 0.0

        # Liquidity component: wider spread = less liquid = lower score
        liquidity_score = max(0.0, 1.0 - m.spread_cents / 20.0)

        # Weighted combination
        # At runtime (extended fields = 0): weights shift to vol + depth + liquidity
        has_momentum = abs(m.yes_price_momentum) > 0.001
        if has_momentum:
            return 0.40 * vol_score + 0.20 * momentum_score + 0.25 * depth_score + 0.15 * liquidity_score
        else:
            return 0.50 * vol_score + 0.30 * depth_score + 0.20 * liquidity_score

    def _compute_side_score(
        self, m: MarketFeatures, side: str,
        max_vol: int, max_depth: int,
    ) -> float:
        """Compute a side-level score (0-1) for YES or NO."""
        if side == "yes":
            # Yes side volume (extended if available)
            side_vol = m.yes_executed_volume if m.yes_executed_volume > 0 else m.volume // 2
            # Yes side depth (extended if available)
            side_depth = m.yes_total_depth if m.yes_total_depth > 0 else m.total_resting_order_quantity // 2
            # Yes side momentum
            side_momentum = m.yes_price_momentum if abs(m.yes_price_momentum) > 0.001 else 0.0
            # Bid price signal
            bid_signal = m.yes_bid / 100.0
        else:
            side_vol = m.no_executed_volume if m.no_executed_volume > 0 else m.volume // 2
            side_depth = m.no_total_depth if m.no_total_depth > 0 else m.total_resting_order_quantity // 2
            side_momentum = -m.yes_price_momentum if abs(m.yes_price_momentum) > 0.001 else 0.0
            bid_signal = (100 - m.no_bid) / 100.0

        vol_score = side_vol / max(max_vol, 1)
        depth_score = side_depth / max(max_depth, 1)
        momentum_score = min(max(side_momentum / 100.0, 0.0), 1.0)
        bid_score = bid_signal

        has_full = m.yes_executed_volume > 0 or m.no_executed_volume > 0
        if has_full:
            return 0.45 * vol_score + 0.25 * momentum_score + 0.20 * depth_score + 0.10 * bid_score
        else:
            return 0.50 * bid_score + 0.30 * depth_score + 0.20 * vol_score

    def select_trade(self, features: EventFeatures) -> TradeDecision:
        if not features.child_markets:
            return TradeDecision(
                market_ticker="", side="no", should_trade=False,
                reason="no_child_markets",
            )

        # Pre-compute normalization maxima
        max_vol = max(m.volume for m in features.child_markets) or 1
        max_depth = max(m.total_resting_order_quantity for m in features.child_markets) or 1

        # Score each market
        scored = [
            (m, self._compute_market_score(m, max_vol, max_depth))
            for m in features.child_markets
        ]

        if not scored:
            return TradeDecision(
                market_ticker="", side="no", should_trade=False,
                reason="no_scorable_markets",
            )

        # Pick the highest-scored market
        selected, market_score = max(scored, key=lambda pair: pair[1])

        # Score both sides on the selected market
        yes_score = self._compute_side_score(selected, "yes", max_vol, max_depth)
        no_score = self._compute_side_score(selected, "no", max_vol, max_depth)

        side = "yes" if yes_score > no_score else "no"
        entry_price = selected.yes_bid if side == "yes" else selected.no_bid

        # Confidence from the margin between side scores
        score_margin = abs(yes_score - no_score)
        confidence = min(0.5 + score_margin * 0.5, 0.95)

        return TradeDecision(
            market_ticker=selected.ticker,
            side=side,
            should_trade=True,
            confidence=confidence,
            reason=(
                f"hybrid_score_market_{market_score:.2f}_"
                f"yes_{yes_score:.2f}_no_{no_score:.2f}_side_{side}"
            ),
            entry_price_cents=entry_price,
            max_contracts=100,
        )
