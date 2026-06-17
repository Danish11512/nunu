# Strategy System Specification

## Overview

The platform ships with **all six strategy profiles implemented** from day one. Only **most-bet** is tested. The user switches between strategies via config.

## Architecture

```
Config (settings.yaml)
    │
    ▼
STRATEGY_REGISTRY ───▶ get_strategy(name, config) ──▶ StrategyProfile instance
    │
    ├── most-bet          ───▶ MostBetStrategy          ✅ tested
    ├── highest-volume    ───▶ HighestVolumeStrategy     ⏸ untested
    ├── widest-spread     ───▶ WidestSpreadStrategy      ⏸ untested
    ├── deepest-book      ───▶ DeepestBookStrategy       ⏸ untested
    ├── momentum-shift    ───▶ MomentumShiftStrategy     ⏸ untested
    └── custom-threshold  ───▶ CustomThresholdStrategy   ⏸ untested
```

## Interface

```python
class StrategyProfile(ABC):
    name: str
    description: str
    config: dict

    @abstractmethod
    def select_market(self, ranked_markets: list[RankedMarket], event: Event) -> Optional[RankedMarket]:
        """Pick the best market from the ranked list."""
        ...

    @abstractmethod
    def select_side(self, market: RankedMarket, stats: MarketOrderbookStats) -> OrderCandidateSide:
        """Pick YES or NO for the selected market."""
        ...
```

## Profile Summary

| Profile | Market Selection | Side Selection | State Needed |
|---------|-----------------|----------------|--------------|
| **most-bet** | Highest `total_resting_order_quantity` | Side with more resting orders | None |
| **highest-volume** | Highest `volume_24h` | Same as most-bet | None |
| **widest-spread** | Biggest \|yes_bid - no_bid\| | Cheaper side (contrarian) | None |
| **deepest-book** | Highest `depth_level_count` | Side with more order depth | None |
| **momentum-shift** | Biggest change in YES/NO bid ratio over window | Side with positive momentum | Historical snapshots |
| **custom-threshold** | Same as most-bet | Same as most-bet | Per-event-type threshold config |

## Files

```
backend/strategies/
├── __init__.py              # STRATEGY_REGISTRY dict + get_strategy() factory
├── base.py                  # StrategyProfile ABC
├── most_bet.py              # ✅ Tested
├── highest_volume.py        # ⏸ Untested
├── widest_spread.py         # ⏸ Untested
├── deepest_book.py          # ⏸ Untested
├── momentum_shift.py        # ⏸ Untested
└── custom_threshold.py      # ⏸ Untested
```

## Config

```yaml
strategy:
  active_profile: most-bet
  profiles:
    most-bet: {}
    highest-volume: {}
    widest-spread: {}
    deepest-book: {}
    momentum-shift:
      lookback_seconds: 300
    custom-threshold:
      per_event_type:
        default: 65
        sports: 50
        politics: 75
```

## Testing

Only `most_bet.py` has tests run. All others have a `# TODO` marker.

```bash
pytest tests/test_strategies/test_most_bet.py -v   # runs
pytest tests/test_strategies/ -v                    # runs most_bet only, skips others
```
