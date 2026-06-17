# Engine 8: Orchestration Engine

## Purpose

Run all 7 engines in sequence, manage scanner state, handle live updates, and dispatch results to the API layer and frontend. This is the **conductor** — it doesn't do data work itself, it coordinates the other engines.

## Modes

| Mode | Startup | Runtime Loop | Output |
|------|---------|-------------|--------|
| **One-shot** | E1→E2→E3→E4→E5→E6→E7 | None (exit) | Print events + candidates |
| **Live Scanner** | E1→E2→E3→E4→E5 | Discovery poller + WS updater + reranker + progress gate | Real-time dashboard |

## Input

```python
@dataclass
class OrchestratorConfig:
    mode: str                              # "one-shot" | "live"
    operating_mode: str                    # "dry_run" | "read_only" | "live"
    strategy_name: str                     # "most-bet" (default)
    threshold_percent: int                 # 65 (default)
    discovery_poll_interval_seconds: int   # 30-60
    progress_gate_interval_seconds: int    # 5-15
    kalshi_client: KalshiClient
    strategy: StrategyProfile
    state: ScannerState
```

## Output

```python
@dataclass
class ScannerOutput:
    scanned_market_count: int
    same_day_live_event_count: int
    same_day_live_events: list[EventWithTopMarkets]
    progress_based_order_candidates: Engine6Output
    validated_candidates: list[ValidatedOrderCandidate]
    scan_timestamp: str
    mode: str
```

## Pipeline Sequence (One-Shot)

```python
async def run_one_shot(config: OrchestratorConfig) -> ScannerOutput:
    """Run all 8 engines once and return results."""
    now = datetime.now(ZoneInfo("America/New_York"))

    # Engine 1: Discovery
    engine1_output = await fetch_all_open_markets(config.kalshi_client)

    # Engine 2: Classification
    engine2_output = get_same_day_live_markets(engine1_output.markets, now)

    # Engine 3: Grouping
    engine3_output = group_by_event_ticker(engine2_output.same_day_live_markets)

    if not engine3_output.events:
        return ScannerOutput(
            scanned_market_count=engine1_output.scanned_market_count,
            same_day_live_event_count=0,
            same_day_live_events=[],
            progress_based_order_candidates=empty_candidates(config.threshold_percent),
            validated_candidates=[],
            scan_timestamp=now.isoformat(),
            mode=config.operating_mode,
        )

    # Engine 4: Orderbooks
    engine4_output = await fetch_orderbooks(engine3_output.events, config.kalshi_client)

    # Engine 5: Ranking
    engine5_output = rank_events(engine4_output)

    # Engine 6: Progress Gate
    engine6_output = process_all_events(
        engine5_output.events,
        config.strategy,
        config.threshold_percent,
        now,
    )

    # Engine 7: Validate each actionable candidate
    validated = []
    for candidate in engine6_output.actionable_candidates:
        result = await validate_candidate(
            candidate,
            config.operating_mode,
            config.validation_config,
            config.kalshi_client,
            config.strategy,
            now,
        )
        if result.can_trade:
            validated.append(result)

    return ScannerOutput(
        scanned_market_count=engine1_output.scanned_market_count,
        same_day_live_event_count=len(engine5_output.events),
        same_day_live_events=engine5_output.events,
        progress_based_order_candidates=engine6_output,
        validated_candidates=validated,
        scan_timestamp=now.isoformat(),
        mode=config.operating_mode,
    )
```

## Live Scanner Loop

```
                    ┌─────────────────────────────────────────────┐
                    │               Scanner State                  │
                    │  markets_by_ticker: dict                     │
                    │  orderbook_stats_by_ticker: dict             │
                    │  ranked_events: dict[str, EventWithTopMarkets]│
                    │  candidates: dict[str, OrderCandidate]       │
                    └──────┬──────────┬──────────┬────────────────┘
                           │          │          │
              ┌────────────▼──┐  ┌────▼────┐  ┌─▼──────────────┐
              │ Discovery     │  │ WS Live │  │ Progress Gate  │
              │ Poller (30s)  │  │ Updater │  │ Loop (10s)     │
              └───────┬───────┘  └────┬─────┘  └──────┬────────┘
                      │               │               │
                      └───────┬───────┘               │
                              │                       │
                     ┌────────▼────────┐     ┌────────▼────────┐
                     │ Event Reranker  │     │ Validate &      │
                     │ (per event)     │     │ Dispatch        │
                     └────────┬────────┘     └────────┬────────┘
                              │                       │
                              ▼                       ▼
                     Updated ranked_events     Candidates → API/WS
```

```python
async def run_live_scanner(config: OrchestratorConfig, stop_event: asyncio.Event):
    """Run the live scanner with polling + WebSocket updates."""

    # ---- Startup: full pipeline once ----
    output = await run_one_shot(config)
    await config.state.initialize(output)

    # ---- Background tasks ----
    async with asyncio.TaskGroup() as tg:
        tg.create_task(discovery_poller_loop(config, stop_event))
        tg.create_task(websocket_update_loop(config, stop_event))
        tg.create_task(progress_gate_loop(config, stop_event))
        tg.create_task(broadcast_state_loop(config, stop_event))
```

### Background Task: Discovery Poller

```python
async def discovery_poller_loop(config: OrchestratorConfig, stop_event: asyncio.Event):
    """Periodically re-fetch markets and re-classify."""
    while not stop_event.is_set():
        try:
            engine1 = await fetch_all_open_markets(config.kalshi_client)
            engine2 = get_same_day_live_markets(engine1.markets)
            engine3 = group_by_event_ticker(engine2.same_day_live_markets)

            # Diff with previous state
            added, removed, changed = diff_events(config.state.events, engine3.events)

            # Fetch orderbooks for new markets
            if added:
                new_books = await fetch_orderbooks(
                    [e for e in engine3.events if e.event_ticker in added],
                    config.kalshi_client,
                )
                for event in new_books.events:
                    rerank_event(config.state, event)

            # Remove dead events
            for event_id in removed:
                config.state.remove_event(event_id)

            config.state.last_discovery = datetime.now()

        except Exception as e:
            logger.error(f"Discovery poller error: {e}")

        await asyncio.sleep(config.discovery_poll_interval_seconds)
```

### Background Task: Progress Gate Loop

```python
async def progress_gate_loop(config: OrchestratorConfig, stop_event: asyncio.Event):
    """Periodically re-check progress for all events."""
    while not stop_event.is_set():
        try:
            now = datetime.now(ZoneInfo("America/New_York"))
            for event in config.state.ranked_events.values():
                candidate = create_progress_based_candidate(
                    event, config.strategy, config.threshold_percent, now,
                )
                config.state.candidates[event.event_ticker] = candidate

                if candidate.should_create_order_candidate:
                    # Validate and dispatch
                    result = await validate_candidate(
                        candidate, config.operating_mode,
                        config.validation_config, config.kalshi_client,
                        config.strategy, now,
                    )
                    if result.can_trade:
                        await broadcast_candidate(config, candidate, result)

        except Exception as e:
            logger.error(f"Progress gate error: {e}")

        await asyncio.sleep(config.progress_gate_interval_seconds)
```

## State Management

```python
@dataclass
class ScannerState:
    """Central runtime state for the live scanner."""
    markets_by_ticker: dict[str, Market] = field(default_factory=dict)
    events: dict[str, ClassifiedEvent] = field(default_factory=dict)
    orderbook_stats: dict[str, MarketOrderbookStats] = field(default_factory=dict)
    ranked_events: dict[str, EventWithTopMarkets] = field(default_factory=dict)
    candidates: dict[str, ProgressBasedOrderCandidate] = field(default_factory=dict)
    last_discovery: datetime | None = None
    last_progress_check: datetime | None = None
    is_running: bool = False
```

## API Dispatch

Engine 8 outputs are pushed to the FastAPI layer:

```python
async def broadcast_candidate(config, candidate, validation):
    """Push a validated candidate to WebSocket subscribers."""
    await config.ws_broadcaster.send({
        "type": "candidate",
        "data": asdict(candidate),
        "validation": asdict(validation) if validation else None,
    })

async def broadcast_event_update(config, event):
    """Push an event update (after rerank) to WebSocket subscribers."""
    await config.ws_broadcaster.send({
        "type": "event_update",
        "data": asdict(event),
    })
```

## Error Handling & Recovery

| Scenario | Behavior |
|----------|----------|
| Engine 1 fails (API down) | Retry 3x, then stop with error |
| Engine 4 partial failure (some orderbooks fail) | Log warning, continue with partial data |
| WS disconnection (live mode) | Auto-reconnect, re-subscribe, re-snapshot orderbooks |
| State corruption | Re-run full pipeline from Engine 1 |
| Rate limit exceeded | Backoff all engines, resume after window |

## Non-Negotiable Rules

1. **Engines run in order** — E1 must complete before E2, etc. No reordering.
2. **State is the source of truth** — the live scanner reads and writes state, engines are stateless.
3. **Never block on a single engine failure** — partial data is better than no data.
4. **Broadcast after every meaningful state change** — the frontend drives from events.
5. **Dry-run is the default** — startup always begins in dry-run mode.

## Dependencies

- All 7 engines
- `backend/trading/trade_executor.py` — For live mode order placement
- `backend/api/websocket_handler.py` — For broadcasting to frontend
- `backend/core/scanner_state.py` — State management

## Testing

```python
async def test_one_shot_returns_all_stages():
    """One-shot run produces output from all 8 engines."""
    ...

async def test_live_scanner_starts_and_stops():
    """Live scanner can be started and cleanly stopped."""
    ...

async def test_discovery_poller_detects_new_markets():
    """New markets appear in state after poller runs."""
    ...

async def test_progress_gate_loop_creates_candidates():
    """Candidates are created when threshold is passed."""
    ...

async def test_empty_market_set_returns_graceful_output():
    """No open markets → empty results, no crash."""
    ...
```
