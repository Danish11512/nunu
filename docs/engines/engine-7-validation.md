# Engine 7: Pre-Trade Validation Engine

## Purpose

Before any actual order placement, re-validate the candidate against **fresh market data**. Never trade on stale scanner output. This is the **last line of defense** before money moves.

## Input

```python
@dataclass
class Engine7Input:
    candidate: ProgressBasedOrderCandidate    # From Engine 6
    mode: str                                  # "dry_run" | "read_only" | "live"
    validation_config: ValidationConfig
```

## Output

```python
@dataclass
class ValidatedOrderCandidate:
    is_valid: bool
    reason: str | None
    details: dict | None = None
```

## Validation Flow

```
1. Receive OrderCandidate from Engine 6
       │
2. Check operating mode
       ├── read_only → return is_valid=False, "Read-only mode"
       ├── dry_run   → proceed to validation, return simulated result
       └── live      → proceed to validation, return real result
       │
3. Re-fetch the market from Kalshi API
       │
4. Re-run SAME_DAY_LIVE_MARKET classification
       ├── FAIL → is_valid=False, "Market no longer same-day live"
       │
5. Re-fetch the orderbook
       │
6. Recalculate MarketOrderbookStats
       │
7. Recalculate most-bet side using active strategy
       ├── FAIL if side changed from candidate
       │
8. Check spread/price acceptability
       ├── FAIL if price moved > max_price_movement_percent (default 10%)
       │
9. Check size/liquidity
       ├── FAIL if insufficient liquidity at desired size
       │
10. If all pass → return validation passed
```

## Validation Thresholds

```python
@dataclass
class ValidationConfig:
    """Configuration for trade validation (Engine 7)."""

    max_spread_cents: int = 5
    min_volume: int = 100
    max_position_size: int = 1000
    min_confidence: float = 0.6
    allow_overtime: bool = False
```

## Implementation

```python
async def validate_candidate(
    candidate: ProgressBasedOrderCandidate,
    mode: str,
    config: ValidationConfig,
    client: MarketReader,
    strategy: StrategyProfile,
    now: datetime | None = None,
) -> ValidatedOrderCandidate:
    """Pre-trade validation. Re-fetches all data before deciding."""
    if now is None:
        now = datetime.now(ZoneInfo("America/New_York"))

    # Mode check
    if mode == "read_only":
        return ValidatedOrderCandidate(
            is_valid=False,
            reason="Scanner is in read-only mode.",
        )

    if not candidate.side or candidate.side not in ("yes", "no"):
        return ValidatedOrderCandidate(
            is_valid=False,
            reason="Candidate is not actionable (no valid side).",
        )

    ticker = candidate.market_ticker

    # Step 3: Re-fetch market
    # MarketReader doesn't have a single-market fetch method, so fetch all and find ours
    from backend.adapters.kalshi.types import parse_market
    all_markets = await client.fetch_markets()
    latest_market = None
    for m in all_markets:
        if m.get("ticker") == ticker:
            latest_market = parse_market(m)
            break
    if not latest_market:
        return ValidatedOrderCandidate(
            is_valid=False,
            reason=f"Market {ticker} not found during re-fetch.",
        )

    # Step 4: Re-classify
    classification = classify_market(latest_market, now)
    if not classification.is_same_day_live:
        return ValidatedOrderCandidate(
            is_valid=False,
            reason="Market no longer passes same-day live classification.",
            details={"classification": asdict(classification)},
        )

    # Step 5: Re-fetch orderbook
    orderbook = await client.fetch_orderbook(ticker=ticker)

    # Step 6: Recalculate stats
    stats = calculate_orderbook_stats(latest_market, orderbook)

    # Step 7: Recalculate side via strategy
    decision = strategy.select_trade(
        EventFeatures(
            event_ticker=candidate.event_ticker,
            child_markets=[MarketFeatures(
                ticker=ticker,
                volume=candidate.volume,
                spread_cents=stats.spread_cents or 0,
                yes_bid=stats.yes_bid or 0,
                no_bid=stats.no_bid or 0,
            )],
        ),
    )

    if decision.side != candidate.most_bet_side:
        return ValidatedOrderCandidate(
            is_valid=False,
            reason=f"Most-bet side changed: was {candidate.most_bet_side}, now {decision.side}.",
            details={
                "previous_side": candidate.most_bet_side,
                "current_side": decision.side,
                "stats": asdict(stats),
            },
        )

    # Step 8: Check spread
    if stats.spread_cents is not None and stats.spread_cents > config.max_spread_cents:
        return ValidatedOrderCandidate(
            is_valid=False,
            reason=f"Spread {stats.spread_cents}¢ exceeds max {config.max_spread_cents}¢.",
        )

    # Step 9: Check volume / liquidity
    if stats.volume < config.min_volume:
        return ValidatedOrderCandidate(
            is_valid=False,
            reason=f"Insufficient volume: {stats.volume} (min {config.min_volume}).",
        )

    # All checks passed
    if mode == "dry_run":
        return ValidatedOrderCandidate(
            is_valid=True,
            reason="DRY RUN: Validation passed. No real order placed.",
            details={
                "mode": "dry_run",
                "stats": asdict(stats),
                "side": decision.side,
            },
        )

    # Live mode — ready to place
    return ValidatedOrderCandidate(
        is_valid=True,
        reason="Validation passed.",
        details={
            "mode": "live",
            "stats": asdict(stats),
            "side": decision.side,
        },
    )
```

## Mode-Specific Behavior

| Mode | Validation Runs? | Order Placed? | Output |
|------|-----------------|---------------|--------|
| **Dry-Run** | ✅ Full validation | ❌ Simulated | Validation result + simulated fill |
| **Read-Only** | ❌ Skipped | ❌ Never | `is_valid=False, "Read-only mode"` |
| **Live** | ✅ Full validation | ✅ If valid | Real order via Kalshi API |

## What "Stale Data" Means

A candidate is considered stale if:

- The market's status has changed since classification
- The orderbook has 0 resting quantity when it previously had > 0
- The most-bet side has flipped
- The spread exceeds `max_spread_cents`

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Market disappears between E6 and E7 | `is_valid=False`, reason logged |
| Orderbook goes to zero in the gap | `is_valid=False`, insufficient volume |
| Side flips from YES to NO | `is_valid=False`, side changed |
| Spread exceeds `max_spread_cents` | `is_valid=False`, spread too wide |
| Network error during re-fetch | Retry once, then fail |
| Kalshi API returns 429 | Backoff, retry once, then fail |

## Dependencies

- `backend.core.interfaces.adapter` — `MarketReader`
- `backend.core.interfaces.strategy` — `StrategyProfile`, `EventFeatures`, `MarketFeatures`
- `backend.core.models.trading` — `ProgressBasedOrderCandidate`, `ValidatedOrderCandidate`, `ValidationConfig`
- `backend.core.models.market` — `MarketOrderbookStats`
- `backend.core.models.classification` — `ClassificationResult`
- `backend.engines.engine2_classification` — `classify_market()`

## Testing

```python
async def test_live_mode_rejects_changed_side():
    """Side flipped between E6 and E7 → is_valid=False."""
    ...

async def test_live_mode_rejects_expired_market():
    """Market expired between E6 and E7 → is_valid=False."""
    ...

async def test_dry_run_returns_simulated_success():
    """Dry-run validates then returns simulated result."""
    ...

async def test_read_only_skips_validation():
    """Read-only immediately returns is_valid=False."""
    ...

async def test_passes_when_nothing_changed():
    """Market, orderbook, and side unchanged → is_valid=True."""
    ...

async def test_checks_price_movement_threshold():
    """Price moved beyond threshold → blocked."""
    ...
```
