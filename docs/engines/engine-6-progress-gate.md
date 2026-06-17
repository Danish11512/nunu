# Engine 6: Event Progress Threshold + Side Selection Engine

## Purpose

Create an order candidate only after a user-configurable percentage of the event has elapsed. This is the **decision engine** — it determines whether to act on a ranked event.

## Input

```python
@dataclass
class Engine6Input:
    events: list[EventWithTopMarkets]    # From Engine 5 (ranked)
    experiment: StrategyExperiment        # Active experiment (configurable)
    threshold_percent: float              # Default: 0.60
    now: datetime                         # Default: system clock
```

## Output

```python
@dataclass
class ProgressBasedOrderCandidate:
    event_ticker: str
    threshold_percent: float
    event_progress_percent: float
    event_passes_progress_threshold: bool
    selected_market: Market | None
    selected_market_stats: MarketOrderbookStats | None
    selected_side: str                    # "YES" | "NO" | "SKIP"
    yes_order_quantity: float
    no_order_quantity: float
    total_executed_volume: float
    should_create_order_candidate: bool
    requires_manual_review: bool
    reasons: list[str]

@dataclass
class Engine6Output:
    threshold_percent: float
    candidates: list[ProgressBasedOrderCandidate]
    actionable_candidates: list[ProgressBasedOrderCandidate]
    manual_review_candidates: list[ProgressBasedOrderCandidate]
```

## Event Progress Calculation

### Formula

```python
def get_end_time(market: Market) -> datetime | None:
    """Fallback chain for event end time."""
    return (
        parse_date(market.expected_expiration_time)
        or parse_date(market.latest_expiration_time)
        or parse_date(market.close_time)
    )

def calculate_event_progress(market: Market, now: datetime) -> float:
    """
    Calculate what percentage of the event has elapsed.

    Returns 0–100, clamped.
    """
    start = parse_date(market.open_time)
    end = get_end_time(market)

    if not start or not end:
        return 0.0

    total_ms = (end - start).total_seconds() * 1000
    elapsed_ms = (now - start).total_seconds() * 1000

    if total_ms <= 0:
        return 100.0

    raw = (elapsed_ms / total_ms) * 100
    return max(0.0, min(100.0, raw))
```

### End Time Fallback

1. `expected_expiration_time` — primary (most accurate)
2. `latest_expiration_time` — secondary (latest possible)
3. `close_time` — last resort (market closing time)

## Side Selection

The active **experiment** handles market and side selection via a single
`select_trade()` call. The default `ExecutedVolumeFollower` uses
**executed trade volume** — not resting orderbook quantity:

```python
def select_trade(self, event_features: EventFeatures) -> TradeDecision:
    valid = [m for m in event_features.child_markets if m.total_executed_volume > 0]
    if not valid:
        return TradeDecision(trade_decision="SKIP", skip_reason="no_markets_with_volume")

    selected = max(valid, key=lambda m: m.total_executed_volume)
    side = "YES" if selected.yes_executed_volume > selected.no_executed_volume else "NO"
    return TradeDecision(trade_decision=f"BUY_{side}", selected_side=side, ...)
```

See the [Strategy System](strategy-system.md) doc for all 7 experiments.

## Order Candidate Creation Rules

Create a candidate **only if ALL** of:

1. Event progress >= user threshold (default 60%)
2. Experiment returns `trade_decision != "SKIP"`
3. Selected market still passes `SAME_DAY_LIVE_MARKET` classification
4. Selected side is `"YES"` or `"NO"`

## Implementation

```python
def create_progress_based_candidate(
    event: EventWithTopMarkets,
    experiment: StrategyExperiment,
    threshold_percent: float,
    now: datetime,
    child_market_features: list[MarketFeatures],
) -> ProgressBasedOrderCandidate:
    reasons: list[str] = []

    # Build EventFeatures for the experiment
    event_features = EventFeatures(
        event_ticker=event.event_ticker,
        event_title=event.event_data.title if event.event_data else "",
        category=event.event_data.category or "",
        event_progress=calculate_event_progress(event.all_same_day_live_markets_ranked[0].market, now),
        threshold=threshold_percent,
        entry_time=now,
        child_markets=child_market_features,
    )

    # Step 1: Experiment selects market + side in a single call
    decision = experiment.select_trade(event_features)

    if decision.trade_decision == "SKIP":
        reasons.append(decision.skip_reason or "Experiment returned SKIP.")
        return empty_candidate(event.event_ticker, threshold_percent, reasons)

    # Step 2: Calculate progress
    progress = calculate_event_progress(event.all_same_day_live_markets_ranked[0].market, now)
    passes_threshold = progress >= threshold_percent
    if not passes_threshold:
        reasons.append(f"Progress {progress:.2f}% < threshold {threshold_percent}%.")

    # Step 3: Re-check classification
    selected_market_data = next(
        (rm for rm in event.all_same_day_live_markets_ranked if rm.market.ticker == decision.market_ticker),
        None,
    )
    classification = classify_market(selected_market_data.market, now) if selected_market_data else None
    if classification and not classification.same_day_live_market:
        reasons.append("Selected market no longer passes same-day live classification.")

    should_create = (
        passes_threshold
        and classification.same_day_live_market
        and decision.trade_decision in ("BUY_YES", "BUY_NO")
    )

    return ProgressBasedOrderCandidate(
        event_ticker=event.event_ticker,
        threshold_percent=threshold_percent,
        event_progress_percent=progress,
        event_passes_progress_threshold=passes_threshold,
        selected_market=selected_market_data.market if selected_market_data else None,
        selected_side=decision.selected_side,
        total_executed_volume=decision.market_signal_strength or 0,
        should_create_order_candidate=should_create,
        requires_manual_review=False,
        reasons=reasons,
    )


def process_all_events(
    events: list[EventWithTopMarkets],
    experiment: StrategyExperiment,
    threshold_percent: float = 0.60,
    now: datetime | None = None,
    feature_builder=None,
) -> Engine6Output:
    if now is None:
        now = datetime.now(ZoneInfo("America/New_York"))

    candidates = []
    for event in events:
        # Build market features for each child market
        child_features = []
        for rm in event.all_same_day_live_markets_ranked:
            mf = feature_builder(rm, now) if feature_builder else MarketFeatures(
                market_ticker=rm.market.ticker,
                total_executed_volume=rm.orderbook_stats.volume_24h,
                yes_price=float(rm.market.yes_ask or 50),
                no_price=float(rm.market.no_ask or 50),
            )
            child_features.append(mf)

        candidate = create_progress_based_candidate(
            event, experiment, threshold_percent, now, child_features,
        )
        candidates.append(candidate)

    return Engine6Output(
        threshold_percent=threshold_percent,
        candidates=candidates,
        actionable_candidates=[c for c in candidates if c.should_create_order_candidate],
        manual_review_candidates=[c for c in candidates if c.requires_manual_review],
    )
```
```

## Strategy Integration

Engine 6 receives the active strategy as a dependency. The pipeline wires it:

```python
# In Engine 8 (orchestrator):
strategy = get_strategy(config.strategy.active_profile, config.strategy.profiles)
engine6 = ProgressGateEngine(strategy=strategy, default_threshold=config.strategy.default_threshold)
output = await engine6.process(engine5_output)
```

Strategy profiles are defined in `backend/strategies/`. See [Strategy System](strategy-system.md) for all profiles.

## Non-Global Threshold

The `CustomThresholdStrategy` allows per-event-type thresholds:

```yaml
strategy:
  active_profile: custom-threshold
  profiles:
    custom-threshold:
      per_event_type:
        default: 65
        sports: 50
        politics: 75
```

When this strategy is active, Engine 6 uses the event-specific threshold instead of the global default.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Event 25% done, threshold 65% | Candidate not created, reason logged |
| Market has YES qty 0, NO qty 0 | `side="none"`, candidate not created |
| YES qty == NO qty (both > 0) | `side="tie"`, requires manual review |
| Market expired between ranking and gate | Re-classify fails, candidate not created |
| Event with 0 markets (shouldn't happen) | Empty candidate with reason |

## Dependencies

- `backend/strategies/` — Active strategy profile
- `backend/core/models.py` — `EventWithTopMarkets`, `ProgressBasedOrderCandidate`
- `backend/engines/engine2_classification.py` — `classify_market()` for re-check

## Testing

```python
async def test_creates_candidate_when_threshold_passed():
    """Progress >= 65% + valid market + valid side → candidate created."""
    ...

async def test_blocks_candidate_below_threshold():
    """Progress < 65% → no candidate, reason logged."""
    ...

async def test_blocks_candidate_when_side_is_tie():
    """YES == NO qty → manual review, no automatic candidate."""
    ...

async def test_blocks_candidate_when_side_is_none():
    """Zero order qty → no candidate."""
    ...

async def test_strategy_plugs_in_correctly():
    """Active strategy's select_market/select_side are called."""
    ...

async def test_custom_threshold_uses_event_type_threshold():
    """CustomThresholdStrategy uses per-event-type threshold."""
    ...
```
