"""REST API router — 13 endpoints for scanner management."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.api.errors import ok, err
from backend.engines.engine8_orchestrator import run_one_shot
from backend.strategies import get_experiment, EXPERIMENT_REGISTRY
from backend.adapters.kalshi.types import parse_orderbook
from backend.trading.trade_executor import TradeExecutor
from backend.core.models.trading import ProgressBasedOrderCandidate

router = APIRouter(prefix="/api/v1")

# ── Dependency injection ───────────────────────────────────────────────

_BOT: Any = None


def get_bot() -> Any:
    if _BOT is None:
        raise RuntimeError("TradingBot not initialized")
    return _BOT


def set_bot(bot: Any) -> None:
    global _BOT
    _BOT = bot


# ── Request models ─────────────────────────────────────────────────────


class StartScannerRequest(BaseModel):
    mode: str = "live"
    strategy: str | None = None
    threshold_percent: int | None = None


class ApproveCandidateRequest(BaseModel):
    max_price: float | None = None       # In dollars
    size_override: int | None = None     # Number of contracts


class RejectCandidateRequest(BaseModel):
    reason: str = ""


class UpdateConfigRequest(BaseModel):
    strategy: str | None = None
    threshold_percent: int | None = None


class SwitchModeRequest(BaseModel):
    mode: str
    confirm: bool = False


# ── Helpers ────────────────────────────────────────────────────────────

from backend.utils.price_utils import cents_to_dollars


def _cents_or_none(val: int | None) -> float | None:
    return cents_to_dollars(val)


def _serialize_ranked_market(rm: Any) -> dict:
    return {
        "market_ticker": rm.market_ticker,
        "volume": rm.volume,
        "spread_cents": rm.spread_cents,
        "yes_price_cents": rm.yes_price,
        "no_price_cents": rm.no_price,
        "yes_price": cents_to_dollars(rm.yes_price),
        "no_price": cents_to_dollars(rm.no_price),
        "rank": rm.rank,
        "score": rm.score,
    }


def _serialize_candidate(c: Any) -> dict:
    oc = c.original_candidate
    return {
        "event_ticker": oc.event_ticker,
        "market_ticker": oc.market_ticker,
        "side": oc.side,
        "price_cents": oc.price,
        "price": cents_to_dollars(oc.price),
        "confidence": oc.confidence,
        "volume": oc.volume,
        "progress_pct": oc.progress_pct,
        "is_valid": c.is_valid,
        "validation_errors": c.validation_errors,
        "risk_score": c.risk_score,
        "estimated_entry_price_cents": c.estimated_entry_price,
        "estimated_entry_price": cents_to_dollars(c.estimated_entry_price),
        "estimated_exit_price_cents": c.estimated_exit_price,
        "estimated_exit_price": cents_to_dollars(c.estimated_exit_price),
        "max_contracts": c.max_contracts,
    }


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/scanner/status")
async def get_scanner_status(bot: Any = Depends(get_bot)):
    """1. Return current scanner status and metrics."""
    state = bot.scanner_state
    uptime: float | None = None
    if state.started_at:
        uptime = (datetime.now(timezone.utc) - state.started_at).total_seconds()

    has_creds = bot.kalshi_client.signer is not None if hasattr(bot, "kalshi_client") else False
    return ok({
        "mode": bot.mode,
        "cycle_mode": bot.cycle_mode,
        "is_running": state.is_running,
        "connected_to_kalshi": has_creds,
        "uptime_seconds": uptime,
        "markets_tracked": len(state.markets),
        "events_tracked": len(state.ranked_events),
        "active_candidates": len(state.active_candidates),
        "last_discovery": state.last_discovery.isoformat() if state.last_discovery else None,
        "last_progress_check": state.last_progress_check.isoformat() if state.last_progress_check else None,
    })


@router.post("/scanner/start")
async def start_scanner(body: StartScannerRequest, bot: Any = Depends(get_bot)):
    """2. Run a full scanner cycle (one-shot)."""
    if bot.scanner_state.is_running:
        return err("ALREADY_RUNNING", "Scanner is already running.", status_code=409)

    mode = body.mode or bot.mode
    strategy_name = (
        body.strategy
        or (bot.strategy.name if bot.strategy else None)
        or bot.settings.scanner.default_strategy
    )
    threshold = body.threshold_percent or bot.settings.scanner.default_threshold

    if strategy_name not in EXPERIMENT_REGISTRY:
        return err(
            "INVALID_STRATEGY",
            f"Unknown strategy: {strategy_name}. Available: {list(EXPERIMENT_REGISTRY)}",
            status_code=400,
        )

    strategy = get_experiment(strategy_name, bot.settings.strategy.params)

    state = bot.scanner_state
    state.is_running = True
    try:
        output = await run_one_shot(
            client=bot.kalshi_adapter,
            strategy=strategy,
            threshold_pct=threshold,
            mode=mode,
        )
    except Exception as e:
        return err("SCAN_FAILED", str(e), status_code=502)
    finally:
        state.is_running = False
    state.current_cycle += 1
    state.ranked_events = output.events
    state.candidates = output.trades
    state.config_snapshot = {
        "mode": mode,
        "strategy": strategy_name,
        "threshold": threshold,
    }
    state.started_at = datetime.now(timezone.utc)

    scanner_id = f"scan_{state.current_cycle}"
    return ok({
        "scanner_id": scanner_id,
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "events_processed": output.num_events_scanned,
        "candidates_generated": output.num_candidates_found,
        "trades_executed": output.num_trades_executed,
    })


@router.post("/scanner/stop")
async def stop_scanner(bot: Any = Depends(get_bot)):
    """3. Stop the current scanner cycle."""
    state = bot.scanner_state
    if not state.is_running:
        return err("NOT_RUNNING", "Scanner is not running.", status_code=400)

    state.is_running = False
    now = datetime.now(timezone.utc)
    duration: float | None = None
    if state.started_at:
        duration = (now - state.started_at).total_seconds()

    return ok({
        "stopped_at": now.isoformat(),
        "scan_duration_seconds": duration,
        "events_processed": len(state.ranked_events),
        "candidates_generated": len(state.candidates),
    })


@router.get("/events")
async def list_events(
    min_progress: float | None = Query(None, description="Minimum progress percentage (0–100)"),
    has_candidate: bool | None = Query(None, description="Filter by candidate presence"),
    sort_by: str | None = Query(None, description="Sort field: progress, volume, score"),
    bot: Any = Depends(get_bot),
):
    """4. List all tracked events with top markets, filtering and sorting."""
    state = bot.scanner_state
    events = list(state.ranked_events)

    # Filter by minimum progress (using score as proxy for progress)
    if min_progress is not None:
        events = [
            e for e in events
            if e.top_markets
            and ((e.top_markets[0].score or 0.0) * 100.0 >= min_progress)
        ]

    # Filter by candidate presence
    if has_candidate is not None:
        events = [
            e for e in events
            if (len(state.get_candidates_for_event(e.event_ticker)) > 0) == has_candidate
        ]

    # Sort
    if sort_by == "progress":
        events.sort(key=lambda e: e.top_markets[0].score if e.top_markets else 0.0, reverse=True)
    elif sort_by == "market_count":
        events.sort(key=lambda e: e.num_top_markets, reverse=True)
    elif sort_by in ("volume", "score", "total_orders"):
        events.sort(key=lambda e: e.total_volume, reverse=True)

    # Build price-timestamp lookup from price tracker
    tracker = getattr(bot, "price_tracker", None)
    price_timestamps: dict[str, str] = {}
    if tracker:
        for ticker, info in tracker.summary.items():
            ts = info.get("last_updated")
            if ts:
                price_timestamps[ticker] = ts

    result = []
    for ev in events:
        progress = ev.top_markets[0].score if ev.top_markets else 0.0
        candidate = state.get_candidate(ev.event_ticker)
        top_mkts = []
        for rm in (ev.top_markets or [])[:3]:
            top_mkts.append({
                "ticker": rm.market_ticker,
                "title": rm.title,
                "yes_bid": cents_to_dollars(rm.yes_price),
                "no_bid": cents_to_dollars(rm.no_price),
                "total_resting_order_quantity": float(max(rm.score, 0)),
                "yes_order_quantity": 0.0,
                "no_order_quantity": 0.0,
                "volume_24h": float(rm.volume),
                "last_price_update": price_timestamps.get(rm.market_ticker),
            })
        result.append({
            "event_ticker": ev.event_ticker,
            "event_title": ev.event_title,
            "event_sub_title": ev.event_sub_title,
            "market_count": ev.num_top_markets,
            "live_market_count": ev.num_top_markets,
            "total_resting_order_quantity": float(ev.total_volume),
            "active_orderbook_market_count": ev.num_top_markets,
            "top_markets": top_mkts,
            "event_progress_percent": progress,
            "has_active_candidate": candidate is not None,
            "candidate_side": candidate.original_candidate.side if candidate and candidate.original_candidate.side else None,
        })

    return ok(result)


@router.get("/events/{event_ticker}")
async def get_event_detail(event_ticker: str, bot: Any = Depends(get_bot)):
    """5. Return single event detail with all markets and candidate info."""
    state = bot.scanner_state
    ev = state.get_event(event_ticker)
    if ev is None:
        return err("NOT_FOUND", f"Event {event_ticker!r} not found.", status_code=404)

    candidate = state.get_candidate(event_ticker)
    candidate_info = _serialize_candidate(candidate) if candidate else None

    return ok({
        "event_ticker": ev.event_ticker,
        "event_title": ev.event_title,
        "top_markets": [_serialize_ranked_market(rm) for rm in (ev.top_markets or [])],
        "total_volume": ev.total_volume,
        "num_top_markets": ev.num_top_markets,
        "candidate": candidate_info,
    })


@router.get("/events/{event_ticker}/orderbook")
async def get_event_orderbook(
    event_ticker: str,
    market_ticker: str = Query(..., description="Market ticker to fetch orderbook for"),
    max_levels: int = Query(10, description="Max depth levels per side"),
    bot: Any = Depends(get_bot),
):
    """6. Fetch live orderbook for a specific market within an event."""
    if bot.kalshi_adapter is None:
        return err("ADAPTER_UNAVAILABLE", "Kalshi adapter not initialized.", status_code=503)

    try:
        raw = await bot.kalshi_adapter.fetch_orderbook(market_ticker)
    except Exception as e:
        return err("ORDERBOOK_FETCH_FAILED", str(e), status_code=502)

    orderbook = parse_orderbook(raw, market_ticker)

    yes_bids = [
        {"price": cents_to_dollars(l.price), "price_cents": l.price, "count": l.count}
        for l in orderbook.yes_side[:max_levels]
    ]
    no_bids = [
        {"price": cents_to_dollars(l.price), "price_cents": l.price, "count": l.count}
        for l in orderbook.no_side[:max_levels]
    ]

    return ok({
        "market_ticker": market_ticker,
        "event_ticker": event_ticker,
        "yes_bids": yes_bids,
        "no_bids": no_bids,
        "fetch_time": orderbook.fetch_time.isoformat() if orderbook.fetch_time else None,
    })


@router.get("/candidates")
async def list_candidates(
    status: str = Query("all", description="Filter: all, actionable, manual_review"),
    event_ticker: str | None = Query(None, description="Filter by event ticker"),
    bot: Any = Depends(get_bot),
):
    """7. List all candidates with validation info."""
    state = bot.scanner_state
    candidates = list(state.candidates)

    if event_ticker:
        candidates = [c for c in candidates if c.original_candidate.event_ticker == event_ticker]

    if status == "actionable":
        candidates = [c for c in candidates if c.is_valid]
    elif status == "manual_review":
        candidates = [c for c in candidates if not c.is_valid]

    return ok([_serialize_candidate(c) for c in candidates])


@router.post("/candidates/{event_ticker}/approve")
async def approve_candidate(
    event_ticker: str,
    body: ApproveCandidateRequest,
    bot: Any = Depends(get_bot),
):
    """8. Approve a candidate and execute the trade."""
    if bot.mode == "read_only":
        return err("READ_ONLY", "Cannot approve candidates in read_only mode.", status_code=403)

    state = bot.scanner_state
    candidate = state.get_candidate(event_ticker)
    if candidate is None:
        return err("NOT_FOUND", f"No candidate for event {event_ticker!r}.", status_code=404)

    if not candidate.is_valid:
        return err(
            "INVALID_CANDIDATE",
            f"Candidate validation failed: {'; '.join(candidate.validation_errors)}",
            status_code=400,
        )

    oc = candidate.original_candidate

    # Build a ProgressBasedOrderCandidate for execution
    exec_candidate = ProgressBasedOrderCandidate(
        event_ticker=oc.event_ticker,
        market_ticker=oc.market_ticker,
        side=oc.side,
        price=oc.price,
        confidence=oc.confidence,
        reason=oc.reason,
        volume=body.size_override or oc.volume,
        progress_pct=oc.progress_pct,
        most_bet_side=oc.side,
        threshold_pct=oc.progress_pct,
        is_overtime=False,
    )

    # Apply max_price override (dollars → cents)
    if body.max_price is not None:
        exec_candidate.price = int(round(body.max_price * 100))

    # Execute via TradeExecutor
    executor = TradeExecutor(bot.execution_engine)
    await executor.execute(exec_candidate)

    return ok({
        "event_ticker": event_ticker,
        "market_ticker": exec_candidate.market_ticker,
        "side": exec_candidate.side,
        "price_cents": exec_candidate.price,
        "price": cents_to_dollars(exec_candidate.price),
        "volume": exec_candidate.volume,
        "approved": True,
    })


@router.post("/candidates/{event_ticker}/reject")
async def reject_candidate(
    event_ticker: str,
    body: RejectCandidateRequest,
    bot: Any = Depends(get_bot),
):
    """9. Reject a candidate and remove it from the state."""
    state = bot.scanner_state
    candidate = state.get_candidate(event_ticker)
    if candidate is None:
        return err("NOT_FOUND", f"No candidate for event {event_ticker!r}.", status_code=404)

    # Remove from candidates list
    state.candidates = [
        c for c in state.candidates
        if c.original_candidate.event_ticker != event_ticker
    ]

    return ok(None)


@router.get("/trades")
async def list_trades(
    mode: str = Query("all", description="Filter: all, dry_run, live"),
    limit: int = Query(50, description="Max trades to return"),
    offset: int = Query(0, description="Offset for pagination"),
    bot: Any = Depends(get_bot),
):
    """10. List trades with pagination and mode filtering."""
    trades = list(bot.portfolio._trades)

    if mode != "all":
        trades = [t for t in trades if t.mode == mode]

    # Newest first
    trades.sort(key=lambda t: t.entry_time or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    total = len(trades)
    page = trades[offset:offset + limit]

    result = []
    for t in page:
        result.append({
            "trade_id": t.trade_id,
            "event_ticker": t.event_ticker,
            "market_ticker": t.market_ticker,
            "side": t.side,
            "entry_price_cents": t.entry_price,
            "entry_price": cents_to_dollars(t.entry_price),
            "exit_price_cents": t.exit_price,
            "exit_price": cents_to_dollars(t.exit_price),
            "quantity": t.quantity,
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "pnl": t.pnl,
            "status": t.status,
            "mode": t.mode,
            "error": t.error,
        })

    return ok({
        "trades": result,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/config")
async def get_config(bot: Any = Depends(get_bot)):
    """11. Return current configuration."""
    settings = bot.settings
    return ok({
        "mode": bot.mode,
        "cycle_mode": bot.cycle_mode,
        "strategy": {
            "name": bot.strategy.name if bot.strategy else None,
            "params": settings.strategy.params,
        },
        "available_strategies": list(EXPERIMENT_REGISTRY.keys()),
        "threshold_percent": settings.scanner.default_threshold,
        "kalshi": {
            "connected": bot.kalshi_adapter is not None,
            "base_url": settings.kalshi.api_base_url,
            "rate_limit": settings.kalshi.rate_limit,
        },
        "scanner": {
            "min_markets_per_event": settings.scanner.min_markets_per_event,
            "min_volume_before_entry": settings.scanner.min_volume_before_entry,
            "min_side_signal_strength": settings.scanner.min_side_signal_strength,
            "poll_interval_seconds": settings.scanner.poll_interval_seconds,
        },
        "risk": {
            "max_position_size_per_market": settings.risk.max_position_size_per_market,
            "max_total_positions": settings.risk.max_total_positions,
            "max_daily_trades": settings.risk.max_daily_trades,
        },
    })


@router.put("/config")
async def update_config(body: UpdateConfigRequest, bot: Any = Depends(get_bot)):
    """12. Update strategy or threshold configuration."""
    settings = bot.settings
    updated = False

    if body.strategy is not None:
        if body.strategy not in EXPERIMENT_REGISTRY:
            return err(
                "INVALID_STRATEGY",
                f"Unknown strategy: {body.strategy}. Available: {list(EXPERIMENT_REGISTRY)}",
                status_code=400,
            )
        settings.strategy.name = body.strategy
        bot.strategy = get_experiment(body.strategy, settings.strategy.params)
        updated = True

    if body.threshold_percent is not None:
        if not (0 <= body.threshold_percent <= 100):
            return err("INVALID_THRESHOLD", "Threshold must be between 0 and 100.", status_code=400)
        settings.scanner.default_threshold = body.threshold_percent
        updated = True

    if not updated:
        return err("NO_CHANGES", "No valid fields provided to update.", status_code=400)

    # Return full config after update
    return await get_config(bot=bot)


@router.post("/mode")
async def switch_mode(body: SwitchModeRequest, bot: Any = Depends(get_bot)):
    """13. Switch between dry_run, read_only, and live modes."""
    valid_modes = {"dry_run", "read_only", "live"}
    if body.mode not in valid_modes:
        return err("INVALID_MODE", f"Mode must be one of: {sorted(valid_modes)}", status_code=400)

    if body.mode == "live" and not body.confirm:
        return err("CONFIRMATION_REQUIRED", "Switching to live mode requires confirm=true.", status_code=400)

    old_mode = bot.mode
    bot.mode = body.mode

    if bot.execution_engine:
        bot.execution_engine.mode = body.mode
        # dry_run = True for non-live modes (dry_run and read_only)
        bot.execution_engine.config.dry_run = (body.mode != "live")

    return ok({
        "previous_mode": old_mode,
        "current_mode": body.mode,
        "switched_at": datetime.now(timezone.utc).isoformat(),
        "requires_auth": body.mode == "live" and not bot.settings.kalshi.private_key,
        "auth_configured": bool(bot.settings.kalshi.private_key),
    })


class PriceWebhookRequest(BaseModel):
    """Inbound price update from external webhook."""
    ticker: str
    yes_bid: int | None = None
    yes_ask: int | None = None
    no_bid: int | None = None
    no_ask: int | None = None
    source: str = "webhook"


class CycleModeRequest(BaseModel):
    """Request body for /scanner/cycle-mode."""
    cycle_mode: str  # "live" or "one-shot"


@router.post("/scanner/cycle-mode")
async def set_cycle_mode(body: CycleModeRequest, bot: Any = Depends(get_bot)):
    """14. Switch between live-cycle and one-shot scanner modes."""
    valid_modes = {"live", "one-shot"}
    if body.cycle_mode not in valid_modes:
        return err("INVALID_CYCLE_MODE", f"Cycle mode must be one of: {sorted(valid_modes)}", status_code=400)

    if body.cycle_mode == bot.cycle_mode:
        return ok({"cycle_mode": bot.cycle_mode, "message": "Already in this mode."})

    old_mode = bot.cycle_mode
    bot.cycle_mode = body.cycle_mode

    if body.cycle_mode == "live":
        await bot._start_live_tasks()
    else:
        await bot._stop_live_tasks()

    return ok({
        "previous_mode": old_mode,
        "current_mode": body.cycle_mode,
        "switched_at": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/webhooks/price-update")
async def webhook_price_update(body: PriceWebhookRequest, bot: Any = Depends(get_bot)):
    """15. Webhook endpoint for external price update notifications.

    Accepts price changes from external sources (or Kalshi callback),
    feeds them through the PriceChangeTracker, and broadcasts via WS.
    """
    tracker = getattr(bot, "price_tracker", None)
    if tracker is None:
        return err("TRACKER_UNAVAILABLE", "Price tracker not initialized.", status_code=503)

    changes = await tracker.ingest(
        ticker=body.ticker,
        yes_bid=body.yes_bid,
        yes_ask=body.yes_ask,
        no_bid=body.no_bid,
        no_ask=body.no_ask,
        source=body.source,
    )

    return ok({
        "ticker": body.ticker,
        "changes_detected": len(changes),
        "changes": [
            {
                "field": c.field,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "delta": c.delta,
            }
            for c in changes
        ],
    })


@router.get("/prices")
async def list_prices(
    ticker: str | None = Query(None, description="Filter by market ticker"),
    bot: Any = Depends(get_bot),
):
    """16. Return latest tracked prices for all (or one) tickers."""
    tracker = getattr(bot, "price_tracker", None)
    if tracker is None:
        return err("TRACKER_UNAVAILABLE", "Price tracker not initialized.", status_code=503)

    if ticker:
        snap = tracker.get_latest(ticker)
        if snap is None:
            return err("NOT_FOUND", f"No prices for ticker {ticker!r}.", status_code=404)
        return ok({
            "ticker": snap.ticker,
            "yes_bid": snap.yes_bid,
            "yes_ask": snap.yes_ask,
            "no_bid": snap.no_bid,
            "no_ask": snap.no_ask,
            "timestamp": snap.timestamp.isoformat() if snap.timestamp else None,
        })

    return ok(tracker.summary)


@router.get("/prices/{ticker}/history")
async def get_price_history(
    ticker: str,
    limit: int = Query(10, description="Max history entries"),
    bot: Any = Depends(get_bot),
):
    """17. Return price history for a specific ticker."""
    tracker = getattr(bot, "price_tracker", None)
    if tracker is None:
        return err("TRACKER_UNAVAILABLE", "Price tracker not initialized.", status_code=503)

    hist = tracker.get_history(ticker, limit=limit)
    if not hist:
        return err("NOT_FOUND", f"No history for ticker {ticker!r}.", status_code=404)

    return ok([
        {
            "ticker": s.ticker,
            "yes_bid": s.yes_bid,
            "yes_ask": s.yes_ask,
            "no_bid": s.no_bid,
            "no_ask": s.no_ask,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        }
        for s in hist
    ])


@router.get("/scanner/progress")
async def get_scanner_progress():
    """Return current pipeline cycle state (for initial mount before WS messages arrive)."""
    from backend.models.scanner_progress import get_current_cycle

    cycle = get_current_cycle()
    if cycle is None:
        return ok(None)
    return ok({
        "cycle_id": cycle.cycle_id,
        "status": cycle.status,
        "stages": {
            sid: {
                "stage": s.stage, "label": s.label, "status": s.status,
                "input_count": s.input_count, "output_count": s.output_count,
                "duration_ms": s.duration_ms, "error": s.error,
            }
            for sid, s in cycle.stages.items()
        },
        "started_at": cycle.started_at,
        "completed_at": cycle.completed_at,
        "total_markets_discovered": cycle.total_markets_discovered,
        "total_events_active": cycle.total_events_active,
        "total_candidates_found": cycle.total_candidates_found,
    })
