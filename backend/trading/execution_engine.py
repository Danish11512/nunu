"""
Execution engine with signal queue, async processing loop, order timeout monitoring,
and dry-run fill simulation. Mirrors polymarket-arbitrage core/execution.py.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from backend.core.models.trading import (
    ProgressBasedOrderCandidate, ValidatedOrderCandidate,
    TradeRecord, ValidationConfig,
)
from backend.adapters.kalshi.adapter import KalshiAdapter
from backend.core.interfaces.strategy import StrategyProfile
from backend.engines.engine7_validation import validate_candidate
from backend.trading.portfolio import Portfolio

logger = logging.getLogger(__name__)


@dataclass
class ExecutionConfig:
    slippage_tolerance: float = 0.02
    order_timeout_seconds: float = 60.0
    dry_run: bool = True
    simulate_fills: bool = True
    fill_probability: float = 0.8


@dataclass
class ExecutionStats:
    orders_placed: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0
    orders_rejected: int = 0
    total_notional: float = 0.0
    signals_processed: int = 0
    slippage_rejections: int = 0


class ExecutionEngine:
    """
    Async order execution engine.
    
    - Consumes signals (validated candidates) via an asyncio.Queue
    - Processes them in a background task loop
    - Monitors order timeouts
    - Simulates fills in dry_run mode (with configurable probability)
    - Tracks open orders and execution stats
    """

    def __init__(
        self,
        adapter: KalshiAdapter,
        strategy: StrategyProfile,
        portfolio: Portfolio,
        mode: str = "dry_run",
        config: Optional[ExecutionConfig] = None,
    ):
        self.adapter = adapter
        self.strategy = strategy
        self.portfolio = portfolio
        self.mode = mode
        self.config = config or ExecutionConfig(dry_run=(mode != "live"))
        self.stats = ExecutionStats()

        # Signal queue
        self._signal_queue: asyncio.Queue[ProgressBasedOrderCandidate] = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._timeout_monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Track open orders
        self._open_orders: dict[str, TradeRecord] = {}
        self._order_timestamps: dict[str, datetime] = {}

        # Shutdown event
        self._stop_event = asyncio.Event()

        logger.info(f"ExecutionEngine initialized (mode={mode}, simulate={self.config.simulate_fills})")

    async def start(self):
        if self._running:
            return
        self._running = True
        self._processing_task = asyncio.create_task(
            self._process_signals(), name="execution_signal_processor"
        )
        self._timeout_monitor_task = asyncio.create_task(
            self._monitor_order_timeouts(), name="execution_timeout_monitor"
        )
        logger.info("ExecutionEngine started")

    async def stop(self):
        self._running = False
        self._stop_event.set()
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        if self._timeout_monitor_task:
            self._timeout_monitor_task.cancel()
            try:
                await self._timeout_monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ExecutionEngine stopped")

    async def submit_signal(self, candidate: ProgressBasedOrderCandidate):
        """Submit a validated candidate for execution."""
        await self._signal_queue.put(candidate)
        self.stats.signals_processed += 1

    async def _process_signals(self):
        while self._running:
            try:
                candidate = await asyncio.wait_for(
                    self._signal_queue.get(), timeout=1.0
                )
                await self._execute_signal(candidate)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Signal processing error: {e}")

    async def _execute_signal(self, candidate: ProgressBasedOrderCandidate):
        """Execute a single signal (validated candidate)."""
        if self.mode == "read_only":
            logger.info(f"[READ-ONLY] Would execute: {candidate.event_ticker}")
            return

        validated = await validate_candidate(
            candidate, self.adapter, self.strategy, ValidationConfig()
        )
        if not validated.is_valid:
            reasons = "; ".join(validated.validation_errors)
            logger.info(f"Signal rejected by validation: {candidate.event_ticker} — {reasons}")
            return

        side = validated.original_candidate.side
        price = candidate.price
        size = candidate.volume

        if self.mode == "dry_run":
            await self._execute_dry_run(candidate, validated, side, price, size)
        else:
            await self._execute_live(candidate, validated, side, price, size)

    async def _execute_dry_run(self, candidate, validated, side, price, size):
        """Simulate execution — conditionally create a filled trade."""
        import random
        trade_id = f"dry_{uuid.uuid4().hex[:12]}"
        is_filled = (
            not self.config.simulate_fills
            or random.random() < self.config.fill_probability
        )
        trade = TradeRecord(
            trade_id=trade_id,
            event_ticker=candidate.event_ticker,
            market_ticker=candidate.market_ticker,
            side=side,
            entry_price=price,
            quantity=size if is_filled else 0,
            mode=self.mode,
            status="filled" if is_filled else "failed",
            entry_time=datetime.now(timezone.utc),
            validation_latency_ms=0.0,
        )
        self._open_orders[trade_id] = trade
        self._order_timestamps[trade_id] = datetime.now(timezone.utc)
        self.stats.orders_placed += 1
        if is_filled:
            self.stats.orders_filled += 1
            self.portfolio.record_fill(trade)
        logger.info(
            f"[DRY-RUN] {'FILLED' if is_filled else 'REJECTED'}: "
            f"{candidate.event_ticker} {side} {size}x@{price}¢"
        )

    async def _execute_live(self, candidate, validated, side, price, size):
        """Place a real order on Kalshi."""
        try:
            result = await self.adapter.place_order(
                ticker=candidate.market_ticker,
                side=side,
                price=price,
                count=size,
            )
            trade_id = result.get("order_id", f"live_{uuid.uuid4().hex[:12]}")
            trade = TradeRecord(
                trade_id=trade_id,
                event_ticker=candidate.event_ticker,
                market_ticker=candidate.market_ticker,
                side=side,
                entry_price=price,
                quantity=size,
                mode=self.mode,
                status="filled",
                entry_time=datetime.now(timezone.utc),
                validation_latency_ms=0.0,
            )
            self._open_orders[trade_id] = trade
            self._order_timestamps[trade_id] = datetime.now(timezone.utc)
            self.stats.orders_placed += 1
            self.stats.orders_filled += 1
            self.portfolio.record_fill(trade)
            logger.info(f"[LIVE] ORDER PLACED: {candidate.event_ticker} {side} {size}x@{price}¢")
        except Exception as e:
            logger.error(f"[LIVE] ORDER FAILED: {candidate.event_ticker} — {e}")
            self.stats.orders_rejected += 1

    async def _monitor_order_timeouts(self):
        """Periodically cancel orders that have been open too long."""
        while self._running:
            try:
                await asyncio.sleep(5.0)
                now = datetime.now(timezone.utc)
                expired = [
                    oid for oid, ts in self._order_timestamps.items()
                    if (now - ts).total_seconds() > self.config.order_timeout_seconds
                ]
                for oid in expired:
                    logger.info(f"Order {oid} timed out, cancelling")
                    self._open_orders.pop(oid, None)
                    self._order_timestamps.pop(oid, None)
                    self.stats.orders_cancelled += 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Timeout monitor error: {e}")

    @property
    def open_order_count(self) -> int:
        return len(self._open_orders)

    def get_stats(self) -> dict:
        return {
            "orders_placed": self.stats.orders_placed,
            "orders_filled": self.stats.orders_filled,
            "orders_cancelled": self.stats.orders_cancelled,
            "orders_rejected": self.stats.orders_rejected,
            "signals_processed": self.stats.signals_processed,
            "open_orders": self.open_order_count,
        }
