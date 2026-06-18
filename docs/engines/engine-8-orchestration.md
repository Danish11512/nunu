# Engine 8: Orchestration Engine

## Purpose

Run all 7 engines in sequence, manage scanner state, handle live updates, and dispatch results to the API layer and frontend. This is the **conductor** — it doesn't do data work itself, it coordinates the other engines.

## Modes

| Mode | Startup | Runtime Loop | Output |
|------|---------|-------------|--------|
| **Oneshot** | E1→E2→E3→E4→E5→E6→E7 | None (exit) | Print events + candidates |
| **Live Scanner** | E1→E2→E3→E4→E5 | Discovery poller + WS updater + reranker + progress gate | Real-time dashboard |

## Input

```python
@dataclass
class OrchestratorConfig:
    mode: str                              # "oneshot" | "live"
    operating_mode: str                    # "dry_run" | "read_only" | "live"
    strategy_name: str                     # "favorite-side-follower" (default)
    threshold_percent: int                 # 65 (default)
    discovery_poll_interval_seconds: int   # 30-60
    progress_gate_interval_seconds: int    # 5-15
    client: MarketReader
    strategy: StrategyProfile
    validation_config: ValidationConfig
    state: ScannerState
```

## Output

```python
@dataclass
class ScannerOutput:
    """Final output after a complete scanner cycle."""

    cycle: int = 0
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    # Results
    events: list[EventWithTopMarkets] = field(default_factory=list)
    trades: list[ValidatedOrderCandidate] = field(default_factory=list)

    # Summary
    num_events_scanned: int = 0
    num_markets_scanned: int = 0
    num_candidates_found: int = 0
    num_trades_executed: int = 0

    # Error tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

## Pipeline Sequence (One-Shot)

```python
async def run_one_shot(config: OrchestratorConfig) -> ScannerOutput:
    """Run all 8 engines once and return results."""
    now = datetime.now(ZoneInfo("America/New_York"))

    # Engine 1: Discovery
    engine1_output = await fetch_all_open_markets(config.client)

    # Engine 2: Classification
    engine2_output = get_same_day_live_markets(engine1_output.markets, now)

    # Engine 3: Grouping
    engine3_output = group_by_event_ticker(engine2_output.same_day_live_markets)

    if not engine3_output.events:
        return ScannerOutput(
            num_markets_scanned=engine1_output.scanned_market_count,
            num_events_scanned=0,
            completed_at=now,
        )

    # Engine 4: Orderbooks
    engine4_output = await fetch_orderbooks(engine3_output.events, config.client)

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
    validated: list[ValidatedOrderCandidate] = []
    for candidate in engine6_output.actionable_candidates:
        result = await validate_candidate(
            candidate,
            config.operating_mode,
            config.validation_config,
            config.client,
            config.strategy,
            now,
        )
        if result.is_valid:
            validated.append(ValidatedOrderCandidate(
                original_candidate=candidate,
                is_valid=True,
            ))

    return ScannerOutput(
        events=engine5_output.events,
        trades=validated,
        num_events_scanned=len(engine5_output.events),
        num_markets_scanned=engine1_output.scanned_market_count,
        num_candidates_found=len(engine6_output.actionable_candidates),
        num_trades_executed=len(validated),
        completed_at=datetime.now(ZoneInfo("America/New_York")),
        duration_seconds=(datetime.now(ZoneInfo("America/New_York")) - now).total_seconds(),
    )
```

## Live Scanner Loop

```
                    ┌─────────────────────────────────────────────┐
                    │               Scanner State                  │
                    │  markets: list[dict]                         │
                    │  classified_events: dict[str, ClassifiedEvent]│
                    │  ranked_events: list[EventWithTopMarkets]     │
                    │  candidates: list[ValidatedOrderCandidate]    │
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
    config.state.is_running = True

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
            engine1 = await fetch_all_open_markets(config.client)
            engine2 = get_same_day_live_markets(engine1.markets)
            engine3 = group_by_event_ticker(engine2.same_day_live_markets)

            # Diff with previous state (forward-looking: diff_events not yet implemented)
            # added, removed, changed = diff_events(config.state.classified_events, engine3.events)

            # Fetch orderbooks for new markets
            if engine3.events:
                new_books = await fetch_orderbooks(engine3.events, config.client)
                for event in new_books.events:
                    # Re-rank event (forward-looking: rerank_event not yet implemented)
                    pass

            config.state.cycle_started_at = datetime.now()

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
            for event in config.state.ranked_events:
                candidate = create_progress_based_candidate(
                    event, config.strategy, config.threshold_percent, now,
                )

                if candidate.side in ("yes", "no"):
                    # Validate and dispatch
                    result = await validate_candidate(
                        candidate, config.operating_mode,
                        config.validation_config, config.client,
                        config.strategy, now,
                    )
                    if result.is_valid:
                        config.state.candidates.append(ValidatedOrderCandidate(
                            original_candidate=candidate,
                            is_valid=True,
                        ))
                        await broadcast_candidate(config, candidate, result)

        except Exception as e:
            logger.error(f"Progress gate error: {e}")

        await asyncio.sleep(config.progress_gate_interval_seconds)
```

## State Management

```python
@dataclass
class ScannerState:
    """Mutable state for the scanner's current cycle."""

    # Pipeline stages
    is_running: bool = False
    current_cycle: int = 0
    started_at: datetime | None = None
    cycle_started_at: datetime | None = None

    # Data flowing through pipeline
    markets: list[dict[str, Any]] = field(default_factory=list)
    classified_events: dict[str, ClassifiedEvent] = field(default_factory=dict)
    ranked_events: list[EventWithTopMarkets] = field(default_factory=list)
    candidates: list[ValidatedOrderCandidate] = field(default_factory=list)

    # Error tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Configuration snapshot for this cycle
    config_snapshot: dict[str, Any] = field(default_factory=dict)
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
5. **Oneshot is the default** — startup always begins in oneshot mode.

## Dependencies

- All 7 engines
- `backend.core.scanner_state` — `ScannerState`, `ScannerOutput`, `CycleMetrics`
- `backend.core.interfaces.adapter` — `MarketReader`
- `backend.core.interfaces.strategy` — `StrategyProfile`
- `backend.core.models.trading` — `ValidatedOrderCandidate`, `ValidationConfig`
- `backend.core.models.classification` — `ClassifiedEvent`

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
