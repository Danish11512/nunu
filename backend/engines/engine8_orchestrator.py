import asyncio
import logging
import time as time_module
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

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
from backend.models.scanner_progress import PipelineStage, PipelineCycle, set_current_cycle

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

_cycle_counter = 0


async def _broadcast(manager, type_: str, data: dict) -> None:
    """Helper to broadcast with error handling."""
    try:
        await manager.broadcast("scanner", type_, data)
    except Exception:
        logger.warning("Broadcast %s failed", type_, exc_info=True)


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
    Pipeline: E1 -> E2 -> E3 -> E4 -> E5 -> E6 -> E7
    """
    global _cycle_counter

    # Lazy import to avoid circular deps
    from backend.api.websocket_handler import manager

    if now is None:
        now = datetime.now(ET)

    _cycle_counter += 1
    cycle_id = _cycle_counter
    started_at = datetime.now(timezone.utc).isoformat()
    stages: dict[str, PipelineStage] = {}

    # --- HTTP trace queue & flusher ---
    trace_queue: asyncio.Queue = asyncio.Queue()
    if hasattr(client, 'http') and hasattr(client.http, 'on_request'):
        async def _trace_cb(trace) -> None:
            trace_queue.put_nowait(trace)
        client.http.on_request = _trace_cb

    flusher_task: asyncio.Task | None = None

    async def _flush_traces():
        try:
            while True:
                batch: list = []
                try:
                    while len(batch) < 20:
                        trace = await asyncio.wait_for(trace_queue.get(), timeout=0.5)
                        batch.append(trace)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
                if batch:
                    await _broadcast(manager, "scanner:api_batch",
                                     [{"method": t.method, "path": t.path, "status": t.status,
                                       "duration_ms": t.duration_ms, "rate_remaining": t.rate_remaining,
                                       "timestamp": t.timestamp, "error": t.error} for t in batch])
        except asyncio.CancelledError:
            remaining = []
            while not trace_queue.empty():
                try:
                    remaining.append(trace_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            if remaining:
                await _broadcast(manager, "scanner:api_batch",
                                 [{"method": t.method, "path": t.path, "status": t.status,
                                   "duration_ms": t.duration_ms, "rate_remaining": t.rate_remaining,
                                   "timestamp": t.timestamp, "error": t.error} for t in remaining])

    flusher_task = asyncio.create_task(_flush_traces())

    # Broadcast started
    await _broadcast(manager, "scanner:started", {"cycle_id": cycle_id, "started_at": started_at})

    # Set in-memory store immediately so the REST endpoint returns a running cycle
    set_current_cycle(PipelineCycle(
        cycle_id=cycle_id, status="running", stages={},
        started_at=started_at, completed_at=None,
    ))

    try:
        # --- E1: Discovery ---
        t0 = time_module.monotonic()
        markets = await fetch_all_open_markets(client)
        t1 = time_module.monotonic()
        stages["E1"] = PipelineStage(stage="E1", label="Discovery", status="done",
                                      output_count=len(markets), duration_ms=int((t1 - t0) * 1000))
        await _broadcast(manager, "scanner:stage_update", {
            "cycle_id": cycle_id, "stage": "E1", "label": "Discovery",
            "status": "done", "input_count": 0, "output_count": len(markets),
            "duration_ms": int((t1 - t0) * 1000),
        })

        if not markets:
            cycle = PipelineCycle(cycle_id=cycle_id, status="completed", stages=stages,
                                  started_at=started_at, completed_at=datetime.now(timezone.utc).isoformat())
            set_current_cycle(cycle)
            await _broadcast(manager, "scanner:completed", {
                "cycle_id": cycle_id, "total_markets": 0, "total_events": 0, "total_candidates": 0,
            })
            if flusher_task:
                flusher_task.cancel()
                try:
                    await flusher_task
                except asyncio.CancelledError:
                    pass
            return ScannerOutput(num_markets_scanned=0, completed_at=now)

        # --- E2: Classification (returns tuple, handled inline) ---
        t0 = time_module.monotonic()
        _, live = get_same_day_live_markets(markets, now)
        t1 = time_module.monotonic()
        stages["E2"] = PipelineStage(stage="E2", label="Classification", status="done",
                                      input_count=len(markets), output_count=len(live),
                                      duration_ms=int((t1 - t0) * 1000))
        await _broadcast(manager, "scanner:stage_update", {
            "cycle_id": cycle_id, "stage": "E2", "label": "Classification",
            "status": "done", "input_count": len(markets), "output_count": len(live),
            "duration_ms": int((t1 - t0) * 1000),
        })

        if not live:
            cycle = PipelineCycle(cycle_id=cycle_id, status="completed", stages=stages,
                                  started_at=started_at, completed_at=datetime.now(timezone.utc).isoformat(),
                                  total_markets_discovered=len(markets))
            set_current_cycle(cycle)
            await _broadcast(manager, "scanner:completed", {
                "cycle_id": cycle_id, "total_markets": len(markets), "total_events": 0, "total_candidates": 0,
            })
            if flusher_task:
                flusher_task.cancel()
                try:
                    await flusher_task
                except asyncio.CancelledError:
                    pass
            return ScannerOutput(num_markets_scanned=len(markets), completed_at=now)

        # --- E3: Grouping ---
        t0 = time_module.monotonic()
        events = group_by_event_ticker(live)
        t1 = time_module.monotonic()

        stages["E3"] = PipelineStage(stage="E3", label="Grouping", status="done",
                                      input_count=len(live), output_count=len(events),
                                      duration_ms=int((t1 - t0) * 1000))
        await _broadcast(manager, "scanner:stage_update", {
            "cycle_id": cycle_id, "stage": "E3", "label": "Grouping",
            "status": "done", "input_count": len(live), "output_count": len(events),
            "duration_ms": int((t1 - t0) * 1000),
        })

        # --- E4: Orderbook ---
        t0 = time_module.monotonic()
        event_books = await fetch_orderbooks(events, client)
        t1 = time_module.monotonic()
        stages["E4"] = PipelineStage(stage="E4", label="Orderbook", status="done",
                                      input_count=len(events), output_count=len(event_books),
                                      duration_ms=int((t1 - t0) * 1000))
        await _broadcast(manager, "scanner:stage_update", {
            "cycle_id": cycle_id, "stage": "E4", "label": "Orderbook",
            "status": "done", "input_count": len(events), "output_count": len(event_books),
            "duration_ms": int((t1 - t0) * 1000),
        })

        # --- E5: Ranking ---
        t0 = time_module.monotonic()
        ranked_events = rank_all_events(event_books)
        t1 = time_module.monotonic()
        stages["E5"] = PipelineStage(stage="E5", label="Ranking", status="done",
                                      input_count=len(event_books), output_count=len(ranked_events),
                                      duration_ms=int((t1 - t0) * 1000))
        await _broadcast(manager, "scanner:stage_update", {
            "cycle_id": cycle_id, "stage": "E5", "label": "Ranking",
            "status": "done", "input_count": len(event_books), "output_count": len(ranked_events),
            "duration_ms": int((t1 - t0) * 1000),
        })

        # --- E6: Progress Gate ---
        t0 = time_module.monotonic()
        candidates, actionable = process_all_events(
            ranked_events, strategy, threshold_pct, now,
        )
        t1 = time_module.monotonic()
        stages["E6"] = PipelineStage(stage="E6", label="Progress Gate", status="done",
                                      input_count=len(ranked_events), output_count=len(actionable),
                                      duration_ms=int((t1 - t0) * 1000))
        await _broadcast(manager, "scanner:stage_update", {
            "cycle_id": cycle_id, "stage": "E6", "label": "Progress Gate",
            "status": "done", "input_count": len(ranked_events), "output_count": len(actionable),
            "duration_ms": int((t1 - t0) * 1000),
        })

        # --- E7: Validation ---
        validated: list[ValidatedOrderCandidate] = []
        if mode != "read_only":
            t0 = time_module.monotonic()
            for candidate in actionable:
                vc = await validate_candidate(
                    candidate, client, strategy, ValidationConfig(), now,
                )
                validated.append(vc)
            t1 = time_module.monotonic()
            stages["E7"] = PipelineStage(stage="E7", label="Validation", status="done",
                                          input_count=len(actionable), output_count=len(validated),
                                          duration_ms=int((t1 - t0) * 1000))
            await _broadcast(manager, "scanner:stage_update", {
                "cycle_id": cycle_id, "stage": "E7", "label": "Validation",
                "status": "done", "input_count": len(actionable), "output_count": len(validated),
                "duration_ms": int((t1 - t0) * 1000),
            })
        else:
            stages["E7"] = PipelineStage(stage="E7", label="Validation", status="skipped", input_count=0)

    except Exception as e:
        # Mark remaining pending stages as skipped
        all_stages = ["E1", "E2", "E3", "E4", "E5", "E6", "E7"]
        for sid in all_stages:
            if sid not in stages:
                stages[sid] = PipelineStage(stage=sid, label="", status="skipped")
            elif stages[sid].status == "running":
                stages[sid].status = "skipped"

        await _broadcast(manager, "scanner:error", {"cycle_id": cycle_id, "error": str(e)})

        num_markets = len(markets) if 'markets' in locals() else 0
        num_events = len(ranked_events) if 'ranked_events' in locals() else 0
        cycle = PipelineCycle(cycle_id=cycle_id, status="error", stages=stages,
                              started_at=started_at, completed_at=datetime.now(timezone.utc).isoformat(),
                              total_markets_discovered=num_markets,
                              total_events_active=num_events)
        set_current_cycle(cycle)

        if flusher_task:
            flusher_task.cancel()
            try:
                await flusher_task
            except asyncio.CancelledError:
                pass

        return ScannerOutput(
            num_markets_scanned=num_markets,
            completed_at=now,
            errors=[str(e)],
        )

    # --- Success path ---
    if flusher_task:
        flusher_task.cancel()
        try:
            await flusher_task
        except asyncio.CancelledError:
            pass

    cycle = PipelineCycle(
        cycle_id=cycle_id, status="completed", stages=stages,
        started_at=started_at, completed_at=datetime.now(timezone.utc).isoformat(),
        total_markets_discovered=len(markets),
        total_events_active=len(ranked_events),
        total_candidates_found=len(actionable),
    )
    set_current_cycle(cycle)

    await _broadcast(manager, "scanner:completed", {
        "cycle_id": cycle_id, "completed_at": cycle.completed_at,
        "total_duration_ms": sum(s.duration_ms for s in stages.values()),
        "total_markets": len(markets), "total_events": len(ranked_events),
        "total_candidates": len(actionable),
    })

    return ScannerOutput(
        events=ranked_events,
        trades=validated,
        num_events_scanned=len(ranked_events),
        num_markets_scanned=len(markets),
        num_candidates_found=len(actionable),
        num_trades_executed=sum(1 for v in validated if v.is_valid),
        completed_at=datetime.now(ET),
    )
