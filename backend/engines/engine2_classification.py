"""
Engine 2: Overtime-aware same-day-live classification.

Returns ClassificationResult (not MarketClassification — that class doesn't exist).
Uses Market model fields: status, create_date, close_date, expiry.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from backend.utils.datetime_utils import parse_date, same_et_day
from backend.core.models.classification import ClassificationResult
from backend.core.models.market import Market

ET = ZoneInfo("America/New_York")


def classify_market(market: Market, now: Optional[datetime] = None) -> ClassificationResult:
    """
    Classify a single market as same-day-live.

    SAME_DAY_LIVE iff:
      - status == "active"
      - create_date <= now
      - close_date > now
      - expiry is today ET

    Uses market.create_date, market.close_date, market.expiry.
    Returns ClassificationResult (NOT MarketClassification).
    """
    if now is None:
        now = datetime.now(ET)

    reason_parts: list[str] = []
    create_dt = parse_date(market.create_date)
    close_dt = parse_date(market.close_date)
    expiry_dt = market.expiry

    live_now = (
        market.status == "active"
        and create_dt is not None
        and close_dt is not None
        and create_dt <= now
        and close_dt > now
    )
    if not live_now:
        reason_parts.append("Market is not currently active/open.")

    expiry_today = (expiry_dt is not None and same_et_day(expiry_dt, now))
    if not expiry_today:
        reason_parts.append("Expiry not today ET.")

    return ClassificationResult(
        market_ticker=market.ticker,
        event_ticker=market.event_ticker,
        is_same_day_live=live_now and expiry_today,
        confidence=1.0 if (live_now and expiry_today) else 0.0,
        reason="; ".join(reason_parts) if reason_parts else "Passed all checks",
    )


def get_same_day_live_markets(
    markets: list[Market],
    now: Optional[datetime] = None,
) -> tuple[list[tuple[Market, ClassificationResult]], list[tuple[Market, ClassificationResult]]]:
    """
    Classify all markets. Returns (all_classified, same_day_live_only).
    Second list is a subset of the first.
    """
    if now is None:
        now = datetime.now(ET)

    all_classified: list[tuple[Market, ClassificationResult]] = []
    live: list[tuple[Market, ClassificationResult]] = []

    for market in markets:
        classification = classify_market(market, now)
        pair = (market, classification)
        all_classified.append(pair)
        if classification.is_same_day_live:
            live.append(pair)

    return all_classified, live
