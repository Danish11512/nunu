from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import logging

from backend.core.interfaces.adapter import MarketReader
from backend.core.interfaces.strategy import StrategyProfile
from backend.core.models.trading import ValidatedOrderCandidate, ValidationConfig
from backend.core.scanner_state import ScannerOutput
from backend.engines.engine1_discovery import fetch_all_open_markets
from backend.engines.engine2_classification import get_same_day_live_markets
from backend.engines.engine3_grouping import group_by_event_ticker
from backend.engines.engine4_orderbook import fetch_orderbooks
from backend.engines.engine5_ranking import rank_all_events
from backend.engines.engine6_progress_gate import process_all_events
from backend.engines.engine7_validation import validate_candidate

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


async def run_one_shot(
    client: MarketReader,
    strategy: StrategyProfile,
    threshold_pct: int = 65,
    mode: str = "dry_run",
    now: Optional[datetime] = None,
) -> ScannerOutput:
    """
    Engine 8: Run all 7 engines once and return results.
    Uses ScannerOutput from core.scanner_state (NOT a custom class).
    Pipeline: E1 \u2192 E2 \u2192 E3 \u2192 E4 \u2192 E5 \u2192 E6 \u2192 E7
    """
    if now is None:
        now = datetime.now(ET)

    # E1: Discovery
    markets = await fetch_all_open_markets(client)
    logger.info(f"E1: Found {len(markets)} open markets.")

    if not markets:
        return ScannerOutput(num_markets_scanned=0, completed_at=now)

    # E2: Classification
    _, live = get_same_day_live_markets(markets, now)
    logger.info(f"E2: {len(live)} same-day-live markets.")

    if not live:
        return ScannerOutput(num_markets_scanned=len(markets), completed_at=now)

    # E3: Grouping
    events = group_by_event_ticker(live)
    logger.info(f"E3: {len(events)} same-day-live events.")

    # E4: Orderbooks
    event_books = await fetch_orderbooks(events, client)
    logger.info("E4: Orderbooks fetched.")

    # E5: Ranking
    ranked_events = rank_all_events(event_books)
    logger.info("E5: Events ranked.")

    # E6: Progress Gate
    candidates, actionable = process_all_events(
        ranked_events, strategy, threshold_pct, now,
    )
    logger.info(f"E6: {len(actionable)} actionable candidates.")

    # E7: Validation (only for actionable candidates in dry_run or live)
    validated: list[ValidatedOrderCandidate] = []
    if mode != "read_only":
        for candidate in actionable:
            vc = await validate_candidate(
                candidate, client, strategy, ValidationConfig(), now,
            )
            validated.append(vc)
        logger.info(f"E7: {len(validated)} validated.")

    return ScannerOutput(
        events=ranked_events,
        trades=validated,
        num_events_scanned=len(ranked_events),
        num_markets_scanned=len(markets),
        num_candidates_found=len(actionable),
        num_trades_executed=sum(1 for v in validated if v.is_valid),
        completed_at=datetime.now(ET),
    )
