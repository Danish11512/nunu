import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.core.interfaces import StrategyProfile
from backend.engines.engine6_progress_gate import create_candidate

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


class ProgressGateLoop:
    """Periodically re-evaluates all ranked events for candidate creation."""

    def __init__(self, ranked_events, strategy: StrategyProfile, threshold: int = 65, interval: int = 10):
        self.ranked_events = ranked_events  # reference to ScannerState.ranked_events
        self.strategy = strategy
        self.threshold = threshold
        self.interval = interval
        self.on_new_candidate = None  # async callback

    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                now = datetime.now(ET)
                for event in self.ranked_events:
                    candidate = create_candidate(event, self.strategy, self.threshold, now)

                    if candidate.side in ("yes", "no") and candidate.confidence > 0:
                        if self.on_new_candidate:
                            await self.on_new_candidate(candidate)

                logger.debug(f"Progress gate: checked {len(self.ranked_events)} events.")

            except Exception as e:
                logger.error(f"Progress gate error: {e}")

            await asyncio.sleep(self.interval)
