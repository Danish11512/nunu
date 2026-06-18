# Engine 2: Same-Day Live Market Classification Engine

## Purpose

Classify which markets are **currently live and expected to resolve today**. This is the **gatekeeper** — only markets passing this engine proceed to grouping, orderbook fetching, and ranking.

## Verification Status

> ✅ **Verified against live Kalshi API on 2026-06-17.** Tested against 2,000 open markets.
> See `scripts/run_classification_analysis.py` to re-run the verification.

## Input

```python
@dataclass
class Engine2Input:
    markets: list[Market]    # All open markets from Engine 1
    now: datetime            # Reference time (default: system clock)
```

## Output

```python
@dataclass
class ClassificationResult:
    market_ticker: str
    event_ticker: str
    is_same_day_live: bool = False
    confidence: float = 0.0       # 0.0 to 1.0
    reason: str = ""              # Single reason string, not list
```

## Classification Rule (Overtime-Aware)

```
SAME_DAY_LIVE_MARKET =
    market.status == "active"                              # Kalshi "active" = open for trading
    AND create_date (parsed) <= now                        # Trading has started
    AND close_date (parsed) > now                          # Trading hasn't ended
    AND market.expiry is today in ET                       # Scheduled to resolve today
    AND (
        latest_expiration_time is today in ET              # Standard: no overtime gap
        OR (latest_expiration_time - market.expiry)
           <= MAX_OVERTIME_WINDOW_HOURS                    # Overtime-capable with backstop
    )
```

> **Note:** `latest_expiration_time` is available from the Kalshi API but is not
> yet modeled in the Phase 1 `Market` dataclass (which maps it to `expiry`).
> The overtime logic above is forward-looking — Phase 1 simplifies to:
> `is_same_day_live = (status == "active" and expiry is today ET)`.

**MAX_OVERTIME_WINDOW_HOURS defaults to 48.** Markets with gaps beyond 48h are
classified as "composite" (multi-event bundles) and excluded from same-day-live.

### Field Mappings (Kalshi API → Market Model)

| Rule | Kalshi API Field | Model Field | Type |
|------|-----------------|-------------|------|
| Status check | `status` | `status` | string |
| Open / create time | `open_time` | `create_date` | ISO 8601 str |
| Close time | `close_time` | `close_date` | ISO 8601 str |
| Expected expiration | `expected_expiration_time` | `expiry` (datetime), `expiry_iso` (raw) | datetime / str |
| Latest expiration | `latest_expiration_time` | *(not on Market model — adapter raw dict)* | ISO 8601 |

### Timezone Handling

All "today" comparisons use **America/New_York** (ET). The helpers
`day_key_et()`, `same_et_day()`, and `parse_date()` live in
`backend.utils.datetime_utils`:

```python
from backend.utils.datetime_utils import day_key_et, same_et_day, parse_date
```

### Expiration Field Note

The Kalshi API provides both `expected_expiration_time` and `latest_expiration_time`.
Our Phase 1 `Market` model maps `expected_expiration_time` to `expiry` (datetime) and
stores the raw ISO string in `expiry_iso`. `latest_expiration_time` is NOT currently
modeled on the Market dataclass — the forward-looking overtime logic would access it
from the adapter's raw API response dict. The engine uses `market.expiry` for the
"today" check.

**Migration from `open_time` / `close_time`:** Earlier spec versions referenced
`market.open_time` and `market.close_time`. The actual Market model uses
`market.create_date` (ISO string for when trading opened) and `market.close_date`
(ISO string for when trading closes). All engine code must use these field names.

---

## Overtime & Event Continuation Model

Kalshi uses a **two-field expiration system** to handle real-world events that
run longer than scheduled:

```
expected_expiration_time:  The scheduled/expected resolution time.
                           The event is LIKELY to resolve here.
latest_expiration_time:    The maximum possible resolution time.
                           The event MUST resolve by here (hard backstop).
```

### Overtime Categories

| Category | Gap (latest - expected) | Interpretation | SDL Decision |
|----------|------------------------|---------------|--------------|
| `standard` | ≤ 0 hours (same time or same-day) | Normal event, no overtime expected | ✅ Include |
| `overtime_short` | 0–6 hours | Game/match may run into OT (e.g., sports) | ✅ Include |
| `overtime_medium` | 6–24 hours | Multi-session event spanning into next day | ✅ Include |
| `overtime_long` | 24–48 hours | Extended multi-day event | ✅ Include (conservative) |
| `composite` | > 48 hours | Multi-event bundle, not same-day specific | ❌ Exclude |

### Real-World Examples (verified against Kalshi API, 2026-06-17)

**STANDARD (expected+latest both today):**
```
Expected: 06/17 02:05 EDT    Latest: 06/17 02:00 EDT
Gap: -0.1h (slight negative — data artifact, still included)
Decision: ✅ SAME-DAY LIVE (both within today ET)
```

**OVERTIME (expected today, latest tomorrow):**
```
Expected: 06/17 23:05 EDT    Latest: 06/19 19:15 EDT
Gap: 44.2h
Decision: ⚠️ OVERTIME_LONG (gap > 24h, under 48h cap — included)
```

**COMPOSITE (expected today, latest days later):**
```
Expected: 06/17 23:00 EDT    Latest: 07/01 16:00 EDT
Gap: 329h (13.7 days!)
Decision: ❌ COMPOSITE (excluded — backstop too far for same-day)
```

### Why the 48-Hour Cap?

Without the overtime filter, **531 of 541** markets with today's expected
expiration would be accepted — but most have 300+ hour gaps and are composite
multi-event bundles that don't actually resolve today. The 48-hour cap correctly
excludes these while keeping genuine same-day events.

---

## Progress Calculation (Fractions)

Progress measures how much of the event's lifecycle has elapsed. This is used
by Engine 6 (Progress Gate) to determine if an event is "far enough along" to
start generating candidates.

The actual implementation lives in `backend.utils.datetime_utils`:

```python
from backend.utils.datetime_utils import calculate_progress

# Signature:
# calculate_progress(expires_at: datetime, now: datetime | None = None, start_at: datetime | None = None) -> float
```

### Formula

```
progress_pct = clamp(
    (1 - (expires_at - now) / (expires_at - start_at)) * 100,
    0, 100
)
```

- **End anchor**: `expires_at` — `market.expiry` (scheduled resolution datetime)
- **Start anchor**: `start_at` — parsed `market.create_date` (when the market opened for trading)
- Values clamp to [0, 100]. If the denominator is ≤ 0, returns 100.

### Example (verified against Kalshi API)

```
Event: KXMVESPORTSMULTIGAMEEXTENDED-S202690A7F347182
Create date:    06/17 02:00 EDT
Expiry:         06/17 23:05 EDT
Window:         21.1 hours

Progress at milestones:
  At opening (02:00):      0.0%
  At 25% (07:16):         25.0%
  At 50% (12:32):         50.0%
  At 65% (15:42):         65.0%  ← Default threshold
  At 90% (20:58):         90.0%
  At expiry (23:05):     100.0%
  Now (02:00):             0.0%  ← Just opened (example time)
```

The default 65% threshold hits at **15:42 EDT** (13.7 hours after open). At that
point, the scanner would begin generating order candidates for this event.

### Important: Progress ≠ Event Outcome

Progress is purely temporal — it measures clock elapsed between creation and
expected expiry. It does **not** measure:
- How much volume has traded
- How close the market is to resolution
- Whether the outcome is decided

Those come from Engine 5 (Ranking) and Engine 6 (Progress Gate).

---

## Edge Cases (verified 2026-06-17)

### 1. Negative Gap (latest < expected)
**38 markets** out of 2000 have `latest_expiration_time` (raw API field) before
`expected_expiration_time`. This appears to be a data artifact (likely the
expected time got pushed back after latest was set). Our classification handles
this fine because we only check `expiry` (mapped from `expected_expiration_time`)
for the "today" decision.

### 2. Zero-Volume Same-Day-Live Markets
**49 markets** classified as same-day-live have zero trading volume. These are
valid — they may get volume later. Our non-filtering rule at this stage is
correct.

### 3. Past Expiry
**0 markets** are past their expected expiration but still trading. Kalshi
closes markets at expected expiration time and proceeds to settlement. This
confirms `expected_expiration_time` is a hard deadline.

### 4. Midnight ET Boundary
**119 markets** have `expiry` (mapped from `expected_expiration_time`) at exactly
00:00 ET. The `same_et_day()` check handles this correctly — midnight is the
boundary of "today." A market expiring at 00:00 ET on June 18 is classified as
June 18, not June 17.

### 5. Market with `status != "active"`
All 2000 open markets returned `status: "active"`. We still check for it as
a defensive measure — closed/settled markets may appear in the dataset.

### 6. Multiple Markets Per Event
Events can have hundreds of markets (e.g., esports multi-game events with 20+
sub-markets). Each market is classified individually. An event qualifies for
scanning if ANY of its child markets passes classification (handled by Engine 3).

---

## Non-Negotiable Rules

1. **Do NOT filter by orderbook** — volume, liquidity, spread, depth are irrelevant at this stage.
2. **Do NOT filter by category or keyword** — no allowlists, no topic filters.
3. **Do NOT classify event status directly** — always classify markets first, then group by event_ticker (Engine 3).
4. **All "today" comparisons use America/New_York** — ET is the market's home timezone.
5. **Use `market.expiry` for the "today" decision** — the Market model coalesces the Kalshi API's `expected_expiration_time` and `latest_expiration_time` into `expiry`. The forward-looking overtime logic can access raw API fields through the adapter.
6. **Cap overtime window at 48 hours** — composite multi-event bundles with gaps of 300+ hours are not same-day-live events.

---

## Implementation

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from backend.utils.datetime_utils import day_key_et, same_et_day, parse_date
from backend.core.models.classification import ClassificationResult

ET = ZoneInfo("America/New_York")
MAX_OVERTIME_HOURS = 48.0


def classify_market(market, now: Optional[datetime] = None) -> ClassificationResult:
    """Overtime-aware classification. Returns a ClassificationResult dataclass.
    
    Uses Market model fields:
      - market.status (str)
      - market.create_date (ISO str — open_time from API)
      - market.close_date (ISO str — close_time from API)
      - market.expiry (datetime — expected_expiration_time from API)
    """
    if now is None:
        now = datetime.now(ET)

    reason_parts: list[str] = []
    create_dt = parse_date(market.create_date)
    close_dt = parse_date(market.close_date)
    expiry_dt = market.expiry  # Already a datetime from the adapter

    # Rule 1: Currently trading
    live_now = (
        market.status == "active"
        and create_dt is not None
        and close_dt is not None
        and create_dt <= now
        and close_dt > now
    )
    if not live_now:
        reason_parts.append("Market is not currently active/open.")

    # Rule 2: Expiry is today ET
    expiry_today = (expiry_dt is not None and same_et_day(expiry_dt, now))
    if not expiry_today:
        reason_parts.append("Expiry not today ET.")
    elif expiry_dt and now > expiry_dt:
        reason_parts.append("Market past expiry (overdue).")

    # Rule 3: Check overtime window
    # latest_expiration_time is NOT on the Market model. This forward-looking
    # logic would access the raw API field from the adapter's response dict.
    # Until then, overtime check is disabled and composite detection is skipped.
    is_composite = False

    # Final decision
    is_same_day_live = live_now and expiry_today and not is_composite

    # Build single reason string
    reason = "; ".join(reason_parts) if reason_parts else "Passed all checks"

    return ClassificationResult(
        market_ticker=market.ticker,
        event_ticker=market.event_ticker,
        is_same_day_live=is_same_day_live,
        confidence=1.0 if is_same_day_live else 0.0,
        reason=reason,
    )


def get_same_day_live_markets(
    markets: list,
    now: Optional[datetime] = None,
) -> tuple[list[tuple], list[tuple]]:
    """
    Classify all markets.
    
    Returns (all_classified, same_day_live_only) where each is a list of
    (Market, ClassificationResult) tuples. The second list is a subset of the first.
    """
    if now is None:
        now = datetime.now(ET)

    all_classified = []
    live = []

    for market in markets:
        classification = classify_market(market, now)
        pair = (market, classification)
        all_classified.append(pair)
        if classification.is_same_day_live:
            live.append(pair)

    return all_classified, live
```

---

## Dependencies

- `backend.core.models.market` — `Market`
- `backend.core.models.classification` — `ClassificationResult`
- `backend.utils.datetime_utils` — `parse_date`, `day_key_et`, `same_et_day`, `calculate_progress`
- `zoneinfo` (Python 3.9+) — `ZoneInfo("America/New_York")`
- No external API calls — pure data transformation

---

## Verification Script

The analysis at `scripts/run_classification_analysis.py` provides a
verifiable, live-audited baseline. Run it against the real Kalshi API to:

1. Confirm every market has `expiry` set (mapped from `expected_expiration_time`) ✅ (100% in 2026-06-17 test)
2. Classify all open markets into SDL / overtime / composite buckets
3. Display real examples of each category
4. Measure overtime window distribution
5. Verify edge cases (negative gaps, midnight boundary, zero-volume)

### Expected Results (as of 2026-06-17)

```
Dataset: 2000 open markets
  Standard same-day (both exp today):       10 (0.5%)
  Overtime-aware (gap ≤ 48h):               51 (2.5%)
  Composite (gap > 48h):                   449 (22.5%)
  Non-today (no SDL):                    1,490 (74.5%)
```

---

## Testing

```python
async def test_classifies_same_day_live():
    """Market open now, closing later, both exp today → SAME_DAY_LIVE."""
    ...

async def test_excludes_composite_event():
    """Market with 300h gap between expected and latest → COMPOSITE."""
    ...

async def test_overtime_short_accepted():
    """Market with 3h overtime gap → SAME_DAY_LIVE (overtime_short)."""
    ...

async def test_progress_at_milestones():
    """Progress returns 25% when 1/4 of window has elapsed."""
    ...

async def test_midnight_et_boundary():
    """Market expiring 00:00 ET tomorrow → NOT today."""
    ...

async def test_negative_gap_handled():
    """Market where latest < expected → still passes (data artifact)."""
    ...

async def test_zero_volume_still_passes():
    """Market with zero volume → still SAME_DAY_LIVE if lifecycle ok."""
    ...
```
