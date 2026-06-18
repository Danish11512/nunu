"""Application entry point — TradingBot + FastAPI bootstrap."""

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

    async def start(self, config_path: str | None = None) -> None:
        """Initialize all dependencies."""
        # Lazy imports to break circular deps
        from backend.adapters.kalshi.client import KalshiClient
        from backend.adapters.kalshi.adapter import KalshiAdapter
        from backend.trading.portfolio import Portfolio
        from backend.trading.execution_engine import ExecutionEngine

        self.settings = load_settings(config_path)

        # Map oneshot → dry_run for API mode consistency
        raw_mode = self.settings.scanner.default_mode
        self.mode = "dry_run" if raw_mode == "oneshot" else raw_mode

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

        # ── State ──
        self.scanner_state.started_at = datetime.now(timezone.utc)
        self.scanner_state.config_snapshot = {
            "mode": self.mode,
            "strategy": strategy_name,
            "threshold": self.settings.scanner.default_threshold,
        }

        logger.info(f"TradingBot started: mode={self.mode}, strategy={strategy_name}")

    async def stop(self) -> None:
        """Shut down all components gracefully."""
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
