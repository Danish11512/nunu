from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from backend.core.models.trading import EventWithTopMarkets, ProgressBasedOrderCandidate
from backend.core.interfaces import StrategyProfile, EventFeatures, MarketFeatures, TradeDecision
from backend.utils.datetime_utils import calculate_progress, parse_date
from backend.engines.engine2_classification import classify_market

ET = ZoneInfo("America/New_York")


def _build_event_features(
    event: EventWithTopMarkets,
    now: datetime,
) -> EventFeatures:
    """Build EventFeatures from ranked event data for strategy consumption."""
    child_markets = [
        MarketFeatures(
            ticker=rm.market_ticker,
            volume=rm.volume,
            yes_bid=rm.yes_price,
            no_bid=rm.no_price,
            spread_cents=rm.spread_cents,
            total_resting_order_quantity=max(rm.score, 0),
        )
        for rm in event.top_markets
    ]
    return EventFeatures(
        event_ticker=event.event_ticker,
        event_title=event.event_title or "",
        child_markets=child_markets,
        total_volume=event.total_volume,
        num_markets=event.num_top_markets,
        num_markets_live=event.num_top_markets,
    )


def create_candidate(
    event: EventWithTopMarkets,
    strategy: StrategyProfile,
    threshold_pct: int = 65,
    now: Optional[datetime] = None,
) -> ProgressBasedOrderCandidate:
    """
    Engine 6: Create order candidate if event passes progress threshold.

    1. Calculate event progress from first ranked market
    2. Build EventFeatures from ranked event markets
    3. Call strategy.select_trade() for holistic decision
    4. Map TradeDecision to ProgressBasedOrderCandidate
    """
    if now is None:
        now = datetime.now(ET)

    reason_parts: list[str] = []

    # Calculate progress from first top market
    if event.top_markets:
        top_rm = event.top_markets[0]
        progress_pct = min(float(top_rm.volume) / 1000.0 * 100.0, 100.0) if top_rm.volume > 0 else 0.0
    else:
        progress_pct = 0.0

    passes_threshold = progress_pct >= threshold_pct
    if not passes_threshold:
        reason_parts.append(f"Progress {progress_pct:.0f}% < threshold {threshold_pct}%.")

    # Build features and call strategy
    event_features = _build_event_features(event, now)
    decision = strategy.select_trade(event_features)

    if not decision.should_trade:
        reason_parts.append(decision.reason or "Strategy returned no trade.")

    has_side = decision.side in ("yes", "no")
    should_create = passes_threshold and decision.should_trade and has_side

    return ProgressBasedOrderCandidate(
        event_ticker=event.event_ticker,
        market_ticker=decision.market_ticker if should_create else "",
        side=decision.side if should_create else "",
        price=decision.entry_price_cents if should_create else 0,
        confidence=decision.confidence if should_create else 0.0,
        reason="; ".join(reason_parts) if reason_parts else "Candidate created",
        volume=decision.max_contracts if should_create else 0,
        progress_pct=progress_pct,
        most_bet_side=decision.side if decision.side in ("yes", "no") else "",
        threshold_pct=float(threshold_pct),
        is_overtime=False,
    )


def process_all_events(
    events: list[EventWithTopMarkets],
    strategy: StrategyProfile,
    threshold_pct: int = 65,
    now: Optional[datetime] = None,
) -> tuple[list[ProgressBasedOrderCandidate], list[ProgressBasedOrderCandidate]]:
    """
    Run Engine 6 across all events.
    Returns (all_candidates, actionable_candidates).
    Actionable = side in ("yes", "no") and confidence > 0.
    """
    if now is None:
        now = datetime.now(ET)

    candidates = [
        create_candidate(e, strategy, threshold_pct, now)
        for e in events
    ]

    actionable = [c for c in candidates if c.side in ("yes", "no") and c.confidence > 0]

    return candidates, actionable
