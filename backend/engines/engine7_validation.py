from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from backend.core.interfaces.adapter import MarketReader
from backend.core.models.trading import (
    ProgressBasedOrderCandidate, ValidatedOrderCandidate, ValidationConfig,
)
from backend.core.interfaces.strategy import StrategyProfile, EventFeatures, MarketFeatures
from backend.adapters.kalshi.types import parse_market, calculate_orderbook_stats, parse_orderbook
from backend.engines.engine2_classification import classify_market

ET = ZoneInfo("America/New_York")


async def validate_candidate(
    candidate: ProgressBasedOrderCandidate,
    client: MarketReader,
    strategy: StrategyProfile,
    config: ValidationConfig,
    now: Optional[datetime] = None,
) -> ValidatedOrderCandidate:
    """
    Engine 7: Pre-trade validation.

    1. Check candidate has valid side
    2. Re-fetch market + re-classify
    3. Re-fetch orderbook + recalc stats
    4. Recalculate side via strategy.select_trade()
    5. Check spread + volume thresholds
    """
    if now is None:
        now = datetime.now(ET)

    errors: list[str] = []

    # Must have a valid side
    if candidate.side not in ("yes", "no"):
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=["Candidate has no valid side."],
        )

    ticker = candidate.market_ticker

    # Fetch event (single API call, not paginated) and find our market
    event_raw = await client.fetch_event(candidate.event_ticker)
    market_obj = None
    if event_raw:
        for m in event_raw.get("markets", []):
            if m.get("ticker") == ticker:
                market_obj = parse_market(m)
                break
    if market_obj is None:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=[f"Market {ticker} not found."],
        )

    # Re-classify using parsed Market object
    classification = classify_market(market_obj, now)
    if not classification.is_same_day_live:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=["Market no longer same-day live."],
        )

    # Re-fetch orderbook and compute stats
    orderbook_raw = await client.fetch_orderbook(ticker)
    if not orderbook_raw:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=False,
            validation_errors=[f"Orderbook for {ticker} not available."],
        )
    orderbook = parse_orderbook(orderbook_raw, ticker)
    stats = calculate_orderbook_stats(market_obj, orderbook)

    # Recalculate side via strategy
    event_features = EventFeatures(
        event_ticker=candidate.event_ticker,
        child_markets=[MarketFeatures(
            ticker=ticker,
            volume=candidate.volume,
            spread_cents=stats.spread_cents or 0,
            yes_bid=stats.yes_bid or 0,
            no_bid=stats.no_bid or 0,
        )],
    )
    decision = strategy.select_trade(event_features)

    if decision.side != candidate.side:
        errors.append(f"Side changed: was {candidate.side}, now {decision.side}.")

    # Spread check
    if stats.spread_cents is not None and stats.spread_cents > config.max_spread_cents:
        errors.append(f"Spread {stats.spread_cents}\u00a2 exceeds max {config.max_spread_cents}\u00a2.")

    # Volume check
    if stats.volume < config.min_volume:
        errors.append(f"Insufficient volume: {stats.volume} (min {config.min_volume}).")

    if not errors:
        return ValidatedOrderCandidate(
            original_candidate=candidate,
            is_valid=True,
            estimated_entry_price=candidate.price,
            max_contracts=candidate.volume,
        )

    return ValidatedOrderCandidate(
        original_candidate=candidate,
        is_valid=False,
        validation_errors=errors,
    )
