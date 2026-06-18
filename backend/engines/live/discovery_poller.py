import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.core.interfaces.adapter import MarketReader
from backend.core.scanner_state import ScannerState
from backend.engines.engine1_discovery import fetch_all_open_markets
from backend.engines.engine2_classification import get_same_day_live_markets
from backend.engines.engine3_grouping import group_by_event_ticker

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


class DiscoveryPoller:
    """Periodically re-discovers markets and updates state.
    Depends on MarketReader interface, not concrete adapter.
    """

    def __init__(self, client: MarketReader, state: ScannerState, interval: int = 30):
        self.client = client
        self.state = state
        self.interval = interval
        self._on_new_events_callbacks = []

    def on_new_events(self, callback):
        self._on_new_events_callbacks.append(callback)

    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                now = datetime.now(ET)
                markets = await fetch_all_open_markets(self.client)
                _, live = get_same_day_live_markets(markets, now)
                events = group_by_event_ticker(live)

                # Diff with current state
                current_tickers = set(self.state.classified_events.keys())
                new_tickers = {e.event_ticker for e in events}

                added = new_tickers - current_tickers
                removed = current_tickers - new_tickers

                for t in removed:
                    self.state.classified_events.pop(t, None)

                for callback in self._on_new_events_callbacks:
                    await callback([e for e in events if e.event_ticker in added])

                self.state.classified_events = {e.event_ticker: e for e in events}
                self.state.last_discovery = now

                logger.info(f"Discovery: {len(live)} live markets, {len(events)} events. +{len(added)} -{len(removed)}")

            except Exception as e:
                logger.error(f"Discovery poller error: {e}")

            await asyncio.sleep(self.interval)
