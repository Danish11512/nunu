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
class ValidationResult:
    can_trade: bool
    reason: str | None
    details: dict | None = None
```

## Validation Flow

```
1. Receive OrderCandidate from Engine 6
       │
2. Check operating mode
       ├── read_only → return canTrade=False, "Read-only mode"
       ├── dry_run   → proceed to validation, return simulated result
       └── live      → proceed to validation, return real result
       │
3. Re-fetch the market from Kalshi API
       │
4. Re-run SAME_DAY_LIVE_MARKET classification
       ├── FAIL → canTrade=False, "Market no longer same-day live"
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
    """Tunable thresholds for pre-trade validation."""

    # Maximum price movement since candidate was created
    max_price_movement_percent: float = 10.0

    # Maximum acceptable spread width (dollars)
    max_spread_width: float = 0.05

    # Minimum liquidity at best price (dollars)
    min_liquidity: float = 100.0

    # Maximum age of candidate before it must be re-discovered
    max_candidate_age_seconds: float = 30.0

    # Whether to allow partial fills
    allow_partial_fill: bool = True
```

## Implementation

```python
async def validate_candidate(
    candidate: ProgressBasedOrderCandidate,
    mode: str,
    config: ValidationConfig,
    client: KalshiClient,
    strategy: StrategyProfile,
    now: datetime | None = None,
) -> ValidationResult:
    """Pre-trade validation. Re-fetches all data before deciding."""
    if now is None:
        now = datetime.now(ZoneInfo("America/New_York"))

    # Mode check
    if mode == "read_only":
        return ValidationResult(
            can_trade=False,
            reason="Scanner is in read-only mode.",
        )

    if not candidate.should_create_order_candidate or not candidate.selected_market:
        return ValidationResult(
            can_trade=False,
            reason="Candidate is not actionable.",
        )

    market = candidate.selected_market
    ticker = market.ticker

    # Step 3: Re-fetch market
    latest_market = await client.get_market(ticker)
    if not latest_market:
        return ValidationResult(
            can_trade=False,
            reason=f"Market {ticker} not found during re-fetch.",
        )

    # Step 4: Re-classify
    classification = classify_market(latest_market, now)
    if not classification.same_day_live_market:
        return ValidationResult(
            can_trade=False,
            reason="Market no longer passes same-day live classification.",
            details={"classification": asdict(classification)},
        )

    # Step 5: Re-fetch orderbook
    orderbook = await client.get_orderbook(ticker)

    # Step 6: Recalculate stats
    stats = compute_orderbook_stats(latest_market, orderbook)

    # Step 7: Recalculate side
    current_side = strategy.select_side(
        RankedMarket(
            market=latest_market,
            classification=classification,
            orderbook_stats=stats,
        ),
        stats,
    )

    if current_side != candidate.most_bet_side:
        return ValidationResult(
            can_trade=False,
            reason=f"Most-bet side changed: was {candidate.most_bet_side}, now {current_side}.",
            details={
                "previous_side": candidate.most_bet_side,
                "current_side": current_side,
                "stats": asdict(stats),
            },
        )

    # Step 8: Check price movement
    if candidate.selected_market_stats and candidate.selected_market_stats.best_yes_bid:
        original_price = candidate.selected_market_stats.best_yes_bid
        current_price = stats.best_yes_bid or 0
        if original_price > 0:
            movement = abs(current_price - original_price) / original_price * 100
            if movement > config.max_price_movement_percent:
                return ValidationResult(
                    can_trade=False,
                    reason=f"Price moved {movement:.2f}% (max {config.max_price_movement_percent}%).",
                )

    # Step 9: Check liquidity
    if stats.total_resting_order_quantity < config.min_liquidity:
        return ValidationResult(
            can_trade=False,
            reason=f"Insufficient liquidity: {stats.total_resting_order_quantity:.2f} (min {config.min_liquidity}).",
        )

    # All checks passed
    if mode == "dry_run":
        return ValidationResult(
            can_trade=True,
            reason="DRY RUN: Validation passed. No real order placed.",
            details={
                "mode": "dry_run",
                "stats": asdict(stats),
                "side": current_side,
            },
        )

    # Live mode — ready to place
    return ValidationResult(
        can_trade=True,
        reason="Validation passed.",
        details={
            "mode": "live",
            "market": asdict(latest_market),
            "orderbook": asdict(orderbook),
            "stats": asdict(stats),
            "side": current_side,
        },
    )
```

## Mode-Specific Behavior

| Mode | Validation Runs? | Order Placed? | Output |
|------|-----------------|---------------|--------|
| **Dry-Run** | ✅ Full validation | ❌ Simulated | Validation result + simulated fill |
| **Read-Only** | ❌ Skipped | ❌ Never | `canTrade=False, "Read-only mode"` |
| **Live** | ✅ Full validation | ✅ If valid | Real order via Kalshi API |

## What "Stale Data" Means

A candidate is considered stale if:

- `max_candidate_age_seconds` has elapsed since Engine 6 created it (default: 30s)
- The market's status has changed since classification
- The orderbook has 0 resting quantity when it previously had > 0
- The most-bet side has flipped

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Market disappears between E6 and E7 | `canTrade=False`, reason logged |
| Orderbook goes to zero in the gap | `canTrade=False`, insufficient liquidity |
| Side flips from YES to NO | `canTrade=False`, side changed |
| Price moves 15% in 10 seconds | `canTrade=False`, price movement exceeded |
| Network error during re-fetch | Retry once, then fail |
| Kalshi API returns 429 | Backoff, retry once, then fail |

## Dependencies

- `backend/adapters/kalshi/client.py` — `KalshiClient.get_market()`, `get_orderbook()`
- `backend/engines/engine2_classification.py` — `classify_market()`
- `backend/engines/engine5_ranking.py` — `compute_orderbook_stats()`
- `backend/strategies/` — Active strategy for side selection
- `backend/core/models.py` — All data types

## Testing

```python
async def test_live_mode_rejects_changed_side():
    """Side flipped between E6 and E7 → canTrade=False."""
    ...

async def test_live_mode_rejects_expired_market():
    """Market expired between E6 and E7 → canTrade=False."""
    ...

async def test_dry_run_returns_simulated_success():
    """Dry-run validates then returns simulated result."""
    ...

async def test_read_only_skips_validation():
    """Read-only immediately returns canTrade=False."""
    ...

async def test_passes_when_nothing_changed():
    """Market, orderbook, and side unchanged → canTrade=True."""
    ...

async def test_checks_price_movement_threshold():
    """Price moved beyond threshold → blocked."""
    ...
```
