"""Periodically refreshes live prices for ranked events and broadcasts via WS."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from backend.core.interfaces.adapter import MarketReader
from backend.core.scanner_state import ScannerState
from backend.engines.engine5_ranking import rank_event_markets

logger = logging.getLogger(__name__)


from backend.utils.price_utils import cents_to_dollars


class PriceRefresher:
    """Fetches fresh orderbooks for top markets of active events and updates state + WS.

    Runs independently of the discovery poller. Only refreshes the top N markets
    per event (the ones the dashboard displays) to minimize API calls.
    """

    def __init__(
        self,
        client: MarketReader,
        state: ScannerState,
        interval: int = 5,
        top_n: int = 3,
        price_tracker: Any = None,
    ):
        self.client = client
        self.state = state
        self.interval = interval
        self.top_n = top_n
        self.price_tracker = price_tracker

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._refresh_prices()
            except Exception as e:
                logger.error(f"Price refresher error: {e}")
            await asyncio.sleep(self.interval)

    async def _refresh_prices(self) -> None:
        """Fetch fresh orderbooks for top markets, re-rank, update state & WS."""
        classified = self.state.classified_events
        if not classified:
            return

        # Track which ranked events get updated prices
        tickers_needing_orderbooks: set[str] = set()
        event_ticker_to_classified: dict[str, tuple] = {}

        for ev in self.state.ranked_events:
            cls_ev = classified.get(ev.event_ticker)
            if not cls_ev:
                continue
            # Only refresh prices for the top N markets (the ones shown on dashboard)
            for rm in ev.top_markets[:self.top_n]:
                tickers_needing_orderbooks.add(rm.market_ticker)
            event_ticker_to_classified[ev.event_ticker] = (ev, cls_ev)

        if not tickers_needing_orderbooks:
            return

        # Fetch orderbooks for those market tickers
        semaphore = asyncio.Semaphore(10)

        async def fetch_one(ticker: str):
            async with semaphore:
                from backend.core.models.market import Orderbook
                from backend.adapters.kalshi.types import parse_orderbook
                try:
                    raw = await self.client.fetch_orderbook(ticker)
                    ob = parse_orderbook(raw, ticker)
                    # Feed into price tracker (poll source)
                    if self.price_tracker is not None:
                        yes_bid = ob.yes_side[0].price if ob.yes_side else None
                        yes_ask = ob.yes_side[-1].price if ob.yes_side else None
                        no_bid = ob.no_side[0].price if ob.no_side else None
                        no_ask = ob.no_side[-1].price if ob.no_side else None
                        try:
                            await self.price_tracker.ingest(
                                ticker=ticker,
                                yes_bid=yes_bid,
                                yes_ask=yes_ask,
                                no_bid=no_bid,
                                no_ask=no_ask,
                                source="poll",
                            )
                        except Exception:
                            logger.warning("Price tracker ingest failed for %s", ticker)
                    return ticker, ob
                except Exception as e:
                    logger.warning(f"Price refresh OB fetch failed for {ticker}: {e}")
                    return ticker, Orderbook(market_ticker=ticker)

        tasks = [fetch_one(t) for t in tickers_needing_orderbooks]
        results = await asyncio.gather(*tasks)
        fresh_orderbooks = dict(results)

        # Re-rank each event with fresh orderbooks
        updated_events = []
        for ev in self.state.ranked_events:
            cls_ev = classified.get(ev.event_ticker)
            if not cls_ev:
                updated_events.append(ev)
                continue

            # Only pass orderbooks we actually refreshed
            event_obs = {
                t: fresh_orderbooks[t]
                for t in tickers_needing_orderbooks
                if t in fresh_orderbooks and any(rm.market_ticker == t for rm in ev.top_markets)
            }
            # If no orderbooks were refreshed for this event, keep existing
            if not event_obs:
                updated_events.append(ev)
                continue

            reranked = rank_event_markets(cls_ev, event_obs)
            updated_events.append(reranked)

        # Update state
        self.state.ranked_events = updated_events

        # Broadcast updated event summaries via WS "events" channel
        await self._broadcast_events(updated_events)

    async def _broadcast_events(self, ranked_events) -> None:
        """Build event summary and broadcast each updated event to events WS channel."""
        from backend.api.websocket_handler import manager

        for ev in ranked_events:
            candidate = self.state.get_candidate(ev.event_ticker)
            top_mkts = []
            for rm in ev.top_markets[:self.top_n]:
                top_mkts.append({
                    "ticker": rm.market_ticker,
                    "title": rm.title,
                    "yes_bid": cents_to_dollars(rm.yes_price),
                    "no_bid": cents_to_dollars(rm.no_price),
                    "total_resting_order_quantity": float(max(rm.score, 0)),
                    "yes_order_quantity": 0.0,
                    "no_order_quantity": 0.0,
                    "volume_24h": float(rm.volume),
                })
            progress = rm.score if (rm := ev.top_markets[0] if ev.top_markets else None) else 0.0
            summary = {
                "event_ticker": ev.event_ticker,
                "event_title": ev.event_title,
                "market_count": ev.num_top_markets,
                "live_market_count": ev.num_top_markets,
                "total_resting_order_quantity": float(ev.total_volume),
                "active_orderbook_market_count": ev.num_top_markets,
                "top_markets": top_mkts,
                "event_progress_percent": progress,
                "has_active_candidate": candidate is not None,
                "candidate_side": candidate.original_candidate.side if candidate and candidate.original_candidate.side else None,
            }

            try:
                await manager.broadcast("events", "event:updated", summary)
            except Exception:
                logger.debug("Broadcast failed for %s", ev.event_ticker)
