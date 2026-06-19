"""Application entry point — TradingBot + FastAPI bootstrap."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import rest as rest_router
from backend.api import websocket_handler as ws_router
from backend.api.errors import APIResponse
from backend.api.rest import set_bot
from backend.config.settings import load_settings, Settings
from backend.core.scanner_state import ScannerState
from backend.core.interfaces.strategy import StrategyProfile
from backend.strategies import get_experiment

logger = logging.getLogger(__name__)


class TradingBot:
    """Application root — owns all dependencies."""

    def __init__(self):
        self.settings: Settings | None = None
        self.kalshi_client: Any = None
        self.kalshi_adapter: Any = None
        self.scanner_state = ScannerState()
        self.strategy: StrategyProfile | None = None
        self.portfolio: Any = None
        self.execution_engine: Any = None
        self.mode: str = "dry_run"
        self.cycle_mode: str = "live"  # "live" or "one-shot"
        self.price_tracker: Any = None
        self._ws_client: Any = None
        self._ws_subscription_task: asyncio.Task | None = None
        self._ws_listen_task: asyncio.Task | None = None

    async def start(self, config_path: str | None = None) -> None:
        """Initialize all dependencies and start background loops."""
        # Lazy imports to break circular deps
        from backend.adapters.kalshi.client import KalshiClient
        from backend.adapters.kalshi.adapter import KalshiAdapter
        from backend.trading.portfolio import Portfolio
        from backend.trading.execution_engine import ExecutionEngine
        from backend.engines.live.discovery_poller import DiscoveryPoller
        from backend.engines.live.progress_gate_loop import ProgressGateLoop
        from backend.engines.live.price_refresher import PriceRefresher

        self.settings = load_settings(config_path)

        # Map oneshot → dry_run for API mode consistency
        raw_mode = self.settings.scanner.default_mode
        self.mode = "dry_run" if raw_mode == "oneshot" else raw_mode
        self.cycle_mode = self.settings.scanner.default_mode if self.settings.scanner.default_mode in ("live", "one-shot") else "live"

        # ── Kalshi client ──
        kc = self.settings.kalshi
        self.kalshi_client = KalshiClient(
            base_url=kc.api_base_url,
            api_key_id=kc.key_id,
            private_key=kc.private_key,
            rate_limit=kc.rate_limit,
        )
        # Initialize the underlying HTTP client (normally done by __aenter__)
        await self.kalshi_client.http.__aenter__()
        self.kalshi_adapter = KalshiAdapter(self.kalshi_client)

        # ── Strategy ──
        strategy_name = self.settings.strategy.name or self.settings.scanner.default_strategy
        self.strategy = get_experiment(strategy_name, self.settings.strategy.params)

        # ── Portfolio ──
        self.portfolio = Portfolio()

        # ── Execution Engine ──
        self.execution_engine = ExecutionEngine(
            adapter=self.kalshi_adapter,
            strategy=self.strategy,
            portfolio=self.portfolio,
            mode=self.mode,
        )
        await self.execution_engine.start()

        # ── Price Change Tracker ──
        from backend.trading.price_tracker import PriceChangeTracker
        from backend.api.websocket_handler import manager

        async def _broadcast_price_changes(changes):
            """Broadcast price changes via WebSocket ``prices`` channel."""
            for c in changes:
                await manager.broadcast("prices", "price:changed", {
                    "ticker": c.ticker,
                    "field": c.field,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                    "delta": c.delta,
                    "timestamp": c.timestamp.isoformat() if c.timestamp else None,
                })

        self.price_tracker = PriceChangeTracker(on_change=_broadcast_price_changes)

        # ── Kalshi WebSocket (orderbook_delta) ──
        self._ws_client = None
        await self._start_ws_price_feed()

        # ── Live engine background loops ──
        self._stop_live: asyncio.Event | None = None
        self._discovery_poller: DiscoveryPoller | None = None
        self._progress_gate: ProgressGateLoop | None = None
        self._live_tasks: list[asyncio.Task] = []

        if self.cycle_mode == "live":
            await self._start_live_tasks()

        # ── State ──
        self.scanner_state.started_at = datetime.now(timezone.utc)
        self.scanner_state.config_snapshot = {
            "mode": self.mode,
            "strategy": strategy_name,
            "threshold": self.settings.scanner.default_threshold,
        }

        logger.info(f"TradingBot started: mode={self.mode}, cycle_mode={self.cycle_mode}, strategy={strategy_name}")

    async def _start_ws_price_feed(self) -> None:
        """Connect Kalshi WebSocket for real-time orderbook_delta prices."""
        try:
            kc = self.settings.kalshi
            if not kc.key_id or not kc.private_key:
                logger.warning("No Kalshi credentials — WS price feed disabled")
                return

            from backend.adapters.kalshi.websocket import KalshiWebSocket
            self._ws_client = KalshiWebSocket(
                url=kc.ws_base_url,
                api_key_id=kc.key_id,
                private_key=kc.private_key,
            )

            async def _on_ws_message(data: dict) -> None:
                """Handle orderbook_delta WS message → feed into price tracker."""
                msg_type = data.get("type", "")
                if msg_type == "orderbook_delta":
                    ticker = data.get("market_ticker", "")
                    yes_data = data.get("yes", {}) or {}
                    no_data = data.get("no", {}) or {}
                    await self.price_tracker.ingest(
                        ticker=ticker,
                        yes_bid=yes_data.get("bid"),
                        yes_ask=yes_data.get("ask"),
                        no_bid=no_data.get("bid"),
                        no_ask=no_data.get("ask"),
                        source="ws",
                    )

            self._ws_client.on_message(_on_ws_message)
            await self._ws_client.connect()

            # Subscribe to markets that are already discovered
            self._ws_subscription_task = asyncio.create_task(
                self._ws_subscription_loop()
            )

            # Start listen loop as background task
            self._ws_listen_task = asyncio.create_task(
                self._ws_client.listen()
            )

            logger.info("Kalshi WebSocket price feed connected")
        except Exception as e:
            logger.warning(f"Failed to start WS price feed: {e}")
            self._ws_client = None

    async def _ws_subscription_loop(self) -> None:
        """Periodically check for new market tickers and subscribe via WS."""
        if self._ws_client is None:
            return
        while True:
            try:
                # Collect all tracked market tickers from scanner state
                tickers = set()
                for ev in self.scanner_state.ranked_events:
                    for rm in (ev.top_markets or []):
                        tickers.add(rm.market_ticker)

                if tickers and self._ws_client is not None:
                    await self._ws_client.subscribe(list(tickers))
                    logger.info("WS subscribed to %d market tickers", len(tickers))
                    await asyncio.sleep(60)
                else:
                    await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("WS subscription loop error: %s", e)
                await asyncio.sleep(10)

    async def _stop_ws_price_feed(self) -> None:
        """Disconnect Kalshi WebSocket."""
        # Cancel background tasks
        for task_name in ("_ws_subscription_task", "_ws_listen_task"):
            task = getattr(self, task_name, None)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        # Close WS connection
        if self._ws_client:
            try:
                await self._ws_client.close()
            except Exception as e:
                logger.warning(f"WS close error: {e}")
            self._ws_client = None

    async def _start_live_tasks(self) -> None:
        """Start background discovery poller + progress gate + price refresher loops."""
        from backend.engines.live.discovery_poller import DiscoveryPoller
        from backend.engines.live.progress_gate_loop import ProgressGateLoop
        from backend.engines.live.price_refresher import PriceRefresher

        if self._live_tasks:
            await self._stop_live_tasks()

        self._stop_live = asyncio.Event()
        self._discovery_poller = DiscoveryPoller(
            self.kalshi_adapter, self.scanner_state,
            interval=self.settings.scanner.poll_interval_seconds,
        )
        self._progress_gate = ProgressGateLoop(
            self.scanner_state,
            self.strategy,
            threshold=self.settings.scanner.default_threshold,
            interval=self.settings.scanner.progress_check_interval_seconds,
        )
        self._price_refresher = PriceRefresher(
            self.kalshi_adapter, self.scanner_state,
            interval=5,
            price_tracker=self.price_tracker,
        )
        self._live_tasks = [
            asyncio.create_task(self._discovery_poller.run(self._stop_live), name="discovery_poller"),
            asyncio.create_task(self._progress_gate.run(self._stop_live), name="progress_gate"),
            asyncio.create_task(self._price_refresher.run(self._stop_live), name="price_refresher"),
        ]
        logger.info("Live cycle tasks started")

    async def _stop_live_tasks(self) -> None:
        """Stop background discovery poller + progress gate loops."""
        if self._stop_live:
            self._stop_live.set()
        for task in getattr(self, '_live_tasks', []):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._live_tasks = []
        self._stop_live = None
        logger.info("Live cycle tasks stopped")

    async def stop(self) -> None:
        """Shut down all components gracefully."""
        await self._stop_ws_price_feed()
        await self._stop_live_tasks()
        if self.execution_engine:
            await self.execution_engine.stop()
        if self.kalshi_client:
            await self.kalshi_client.http.__aexit__(None, None, None)
        self.scanner_state.is_running = False
        logger.info("TradingBot stopped")


# ── Global bot instance ───────────────────────────────────────────────
bot = TradingBot()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    from backend.logutils.log_setup import setup_logging

    settings = load_settings()
    log_dir = (
        settings.logging.csv_path.rsplit("/", 1)[0]
        if settings.logging and settings.logging.csv_path
        else "logs"
    )
    setup_logging(
        log_dir=log_dir,
        console_level=settings.logging.level if settings.logging else "INFO",
    )
    await bot.start()
    set_bot(bot)
    yield
    await bot.stop()


# ── FastAPI app ────────────────────────────────────────────────────────
app = FastAPI(
    title="Nunu Prediction Market Scanner",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(rest_router.router)
app.include_router(ws_router.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=APIResponse(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(exc)},
        ).model_dump(),
    )
