# Strategy System Specification

## Overview

The platform ships with **seven strategy experiments** from day one. Only **Experiment A (executed-volume-follower)** is the primary tested target. The user switches between experiments via config.

**Critical correction from earlier logic:** The original "most-bet" strategy used **resting orderbook quantity** as a proxy for "most bet." That is not the same thing as actual betting volume. Resting orders can be market-maker liquidity, spoof-like behavior, stale quotes, or unfilled intent. The new default signal is **executed trade volume** from historical trades.

| Signal | What it means | Problem |
|--------|---------------|---------|
| Resting orderbook quantity | Orders currently sitting on the book | Can be market-maker liquidity, spoof-like behavior, stale quotes, or unfilled intent. |
| **Executed trade volume** | Trades that actually happened | Better signal for "people actually bet," but can be delayed or noisy. |
| Price/favorite side | Current market-implied probability | Often efficient; high win rate may not mean positive ROI. |
| Hybrid | Combines volume, price, and liquidity | More robust, but more complex. |

---

## Architecture

```
Config (settings.yaml)
    │
    ▼
EXPERIMENT_REGISTRY ───▶ get_experiment(name, config) ──▶ StrategyExperiment instance
    │
    ├── executed-volume-follower     ───▶ ExecutedVolumeFollower      ✅ primary target
    ├── executed-volume-fade         ───▶ ExecutedVolumeFade           ⏸ untested
    ├── favorite-side-follower       ───▶ FavoriteSideFollower         ⏸ untested
    ├── momentum-follower            ───▶ MomentumFollower             ⏸ untested
    ├── liquidity-filtered-follower  ───▶ LiquidityFilteredFollower    ⏸ untested
    ├── resting-depth-follower       ───▶ RestingDepthFollower         ⏸ untested
    └── hybrid-score-follower        ───▶ HybridScoreFollower          ⏸ untested
```

---

## Required Data Sources

### Historical Trades (core data for Experiments A, B, E, G)

```python
@dataclass
class HistoricalTrade:
    market_ticker: str
    trade_time: datetime
    yes_price: float       # cents
    no_price: float        # cents
    count: int             # contract count
    taker_side: Optional[str]  # "YES" | "NO" | None
    is_block_trade: bool = False
```

### Candlesticks (core data for Experiments C, D, G)

```python
@dataclass
class Candlestick:
    market_ticker: str
    bucket_start: datetime
    open_yes_price: float
    high_yes_price: float
    low_yes_price: float
    close_yes_price: float
    volume: float = 0.0
```

### Orderbook Snapshots (core data for Experiment F, supplementary for G)

```python
@dataclass
class OrderbookSnapshot:
    market_ticker: str
    snapshot_time: datetime
    yes_bid_price: float
    yes_bid_quantity: float
    no_bid_price: float
    no_bid_quantity: float
    yes_total_depth: float
    no_total_depth: float
    spread: float
```

---

## Interface

```python
class StrategyExperiment(ABC):
    name: str
    description: str
    config: dict

    @abstractmethod
    def select_trade(
        self,
        event_features: EventFeatures,
    ) -> TradeDecision:
        """Evaluate all child markets for an event and return a trade decision."""
        ...


@dataclass
class EventFeatures:
    """Pre-computed features for one event at a given threshold."""
    event_ticker: str
    event_title: str
    category: str
    event_progress: float
    threshold: float
    entry_time: datetime
    child_markets: list[MarketFeatures]


@dataclass
class MarketFeatures:
    """Pre-computed features for one child market at entry time."""
    market_ticker: str
    market_title: str
    result: Optional[str]          # settlement outcome (YES/NO) — for backtesting
    status: str
    total_executed_volume: float
    yes_executed_volume: float
    no_executed_volume: float
    trade_count: int
    yes_price: float
    no_price: float
    yes_best_bid: Optional[float]
    no_best_bid: Optional[float]
    yes_total_depth: Optional[float]
    no_total_depth: Optional[float]
    spread: Optional[float]
    yes_price_momentum: Optional[float]  # price change from reference
    open_interest: Optional[float]


@dataclass
class TradeDecision:
    """Unified output for every strategy experiment."""
    event_ticker: str
    market_ticker: str
    selected_side: str                    # "YES" | "NO"
    trade_decision: str                   # "BUY_YES" | "BUY_NO" | "SKIP"
    skip_reason: Optional[str] = None
    entry_price_cents: Optional[float] = None
    entry_threshold: Optional[float] = None
    event_progress_at_entry: Optional[float] = None
    side_signal_strength: Optional[float] = None
    market_signal_strength: Optional[float] = None
    selected_market_reason: Optional[str] = None
    selected_side_reason: Optional[str] = None
    experiment_id: Optional[str] = None
    estimated_fee_cents: float = 1.0
    max_acceptable_price_cents: float = 85.0
```

---

## Experiment Summary

| ID | Experiment | Market Selection | Side Selection | Primary Data | Exit |
|----|------------|-----------------|----------------|-------------|------|
| **A** | Executed-volume follower | Highest executed volume | Side with more executed volume | Historical trades | Settlement |
| **B** | Executed-volume fade | Highest executed volume | Opposite of dominant side | Historical trades | Settlement |
| **C** | Favorite-side follower | Highest executed volume | Higher priced side (price > 50 → YES) | Candlesticks | Settlement |
| **D** | Momentum follower | Largest price move (reference → threshold) | Direction of movement | Candlesticks | Settlement |
| **E** | Liquidity-filtered follower | Highest executed volume (with liquidity filters) | Side with more executed volume | Trades + filters | Settlement |
| **F** | Resting-depth follower | Highest total resting depth | Side with more resting depth | Orderbook snapshots | Settlement |
| **G** | Hybrid score follower | Highest weighted hybrid score | Higher YES/NO hybrid score | All sources | Settlement |

---

## Experiment Profiles

### Experiment A — Executed-Volume Follower (Default)

```python
class ExecutedVolumeFollower(StrategyExperiment):
    """
    Market with the highest executed volume before threshold.
    Side with more inferred executed volume (YES or NO).
    """
    name = "executed-volume-follower"
    description = "Follows the crowd: highest executed trade volume → most-bet side"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        # Step 1: Select market with highest executed volume
        valid = [m for m in event_features.child_markets if m.total_executed_volume > 0]
        if not valid:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker="",
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_markets_with_volume",
                experiment_id=f"EXP_A_{int(event_features.threshold * 100)}",
            )

        selected = max(valid, key=lambda m: m.total_executed_volume)
        market_signal_strength = selected.total_executed_volume / max(
            m.total_executed_volume for m in valid
        ) if valid else 0.0

        # Step 2: Select side with more executed volume
        yes_vol = selected.yes_executed_volume
        no_vol = selected.no_executed_volume

        if yes_vol == 0 and no_vol == 0:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker=selected.market_ticker,
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_side_volume",
                market_signal_strength=market_signal_strength,
                experiment_id=f"EXP_A_{int(event_features.threshold * 100)}",
            )

        side = "YES" if yes_vol > no_vol else "NO"
        side_strength = max(yes_vol, no_vol) / (yes_vol + no_vol) if (yes_vol + no_vol) > 0 else 0.0

        return TradeDecision(
            event_ticker=event_features.event_ticker,
            market_ticker=selected.market_ticker,
            selected_side=side,
            trade_decision=f"BUY_{side}",
            entry_price_cents=selected.yes_price if side == "YES" else selected.no_price,
            entry_threshold=event_features.threshold,
            event_progress_at_entry=event_features.event_progress,
            side_signal_strength=side_strength,
            market_signal_strength=market_signal_strength,
            selected_market_reason="highest_executed_volume",
            selected_side_reason=f"{side.lower()}_executed_volume_gt_opposite",
            experiment_id=f"EXP_A_{int(event_features.threshold * 100)}",
        )
```

---

### Experiment B — Executed-Volume Fade

```python
class ExecutedVolumeFade(StrategyExperiment):
    """
    Same market selection as Experiment A, but fades the dominant side.
    Hypothesis: the crowd may overpay for the dominant side.
    """
    name = "executed-volume-fade"
    description = "Fades the crowd: highest volume market → bet against dominant side"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        valid = [m for m in event_features.child_markets if m.total_executed_volume > 0]
        if not valid:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker="",
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_markets_with_volume",
                experiment_id=f"EXP_B_{int(event_features.threshold * 100)}",
            )

        selected = max(valid, key=lambda m: m.total_executed_volume)
        yes_vol = selected.yes_executed_volume
        no_vol = selected.no_executed_volume

        if yes_vol == 0 and no_vol == 0:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker=selected.market_ticker,
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_side_volume",
                experiment_id=f"EXP_B_{int(event_features.threshold * 100)}",
            )

        dominant_side = "YES" if yes_vol > no_vol else "NO"
        fade_side = "NO" if dominant_side == "YES" else "YES"
        side_strength = min(yes_vol, no_vol) / (yes_vol + no_vol) if (yes_vol + no_vol) > 0 else 0.0

        return TradeDecision(
            event_ticker=event_features.event_ticker,
            market_ticker=selected.market_ticker,
            selected_side=fade_side,
            trade_decision=f"BUY_{fade_side}",
            entry_price_cents=selected.yes_price if fade_side == "YES" else selected.no_price,
            entry_threshold=event_features.threshold,
            event_progress_at_entry=event_features.event_progress,
            side_signal_strength=side_strength,
            selected_market_reason="highest_executed_volume",
            selected_side_reason=f"fade_dominant_{dominant_side.lower()}",
            experiment_id=f"EXP_B_{int(event_features.threshold * 100)}",
        )
```

---

### Experiment C — Favorite-Side Follower

```python
class FavoriteSideFollower(StrategyExperiment):
    """
    The current price contains the best signal. Buy the favorite.
    Market: highest executed volume.
    Side: YES if yes_price > 50 else NO.
    """
    name = "favorite-side-follower"
    description = "Follows the price: highest volume market → buy the favorite"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        valid = [m for m in event_features.child_markets if m.total_executed_volume > 0]
        if not valid:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker="",
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_markets_with_volume",
                experiment_id=f"EXP_C_{int(event_features.threshold * 100)}",
            )

        selected = max(valid, key=lambda m: m.total_executed_volume)
        side = "YES" if selected.yes_price > 50 else "NO"

        return TradeDecision(
            event_ticker=event_features.event_ticker,
            market_ticker=selected.market_ticker,
            selected_side=side,
            trade_decision=f"BUY_{side}",
            entry_price_cents=selected.yes_price if side == "YES" else selected.no_price,
            entry_threshold=event_features.threshold,
            event_progress_at_entry=event_features.event_progress,
            selected_market_reason="highest_executed_volume",
            selected_side_reason=(
                f"favorite_side_{side.lower()}_price_gt_50"
                if side == "YES"
                else f"favorite_side_{side.lower()}_price_lt_50"
            ),
            experiment_id=f"EXP_C_{int(event_features.threshold * 100)}",
        )
```

---

### Experiment D — Momentum Follower

```python
class MomentumFollower(StrategyExperiment):
    """
    Markets that move strongly toward YES or NO between early and mid event
    may continue in that direction.
    """
    name = "momentum-follower"
    description = "Catches trends: largest price move → direction of movement"

    def __init__(self, config: dict):
        super().__init__(config)
        self.early_reference = config.get("early_reference_progress", 0.40)

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        with_momentum = [
            m for m in event_features.child_markets
            if m.yes_price_momentum is not None
        ]
        if not with_momentum:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker="",
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_momentum_data",
                experiment_id=f"EXP_D_{int(event_features.threshold * 100)}",
            )

        selected = max(with_momentum, key=lambda m: abs(m.yes_price_momentum))
        side = "YES" if selected.yes_price_momentum > 0 else "NO"

        return TradeDecision(
            event_ticker=event_features.event_ticker,
            market_ticker=selected.market_ticker,
            selected_side=side,
            trade_decision=f"BUY_{side}",
            entry_price_cents=selected.yes_price if side == "YES" else selected.no_price,
            entry_threshold=event_features.threshold,
            event_progress_at_entry=event_features.event_progress,
            selected_market_reason="largest_absolute_price_move",
            selected_side_reason=f"momentum_toward_{side.lower()}",
            experiment_id=f"EXP_D_{int(event_features.threshold * 100)}",
        )
```

---

### Experiment E — Liquidity-Filtered Executed-Volume Follower

Same as Experiment A, but with additional liquidity filters applied before selection.

**Filters:**

| Filter | Default |
|--------|---------|
| Minimum total executed volume before entry | 500 contracts |
| Minimum trades before entry | 20 trades |
| Maximum spread | 5 cents |
| Maximum entry price | 85 cents |
| Minimum entry price | 15 cents |
| Exclude block trades | true |
| Exclude stale markets | true |
| Max one trade per event | true |

```python
class LiquidityFilteredFollower(StrategyExperiment):
    """
    Experiment A with liquidity filters to avoid bad fills.
    """
    name = "liquidity-filtered-follower"
    description = "Volume follower with liquidity guards: filters out illiquid markets"

    def __init__(self, config: dict):
        super().__init__(config)
        self.min_volume = config.get("min_total_executed_volume", 500)
        self.min_trades = config.get("min_trade_count", 20)
        self.max_spread = config.get("max_spread_cents", 5)
        self.max_price = config.get("max_entry_price_cents", 85)
        self.min_price = config.get("min_entry_price_cents", 15)
        self.exclude_block_trades = config.get("exclude_block_trades", True)

    def _passes_filters(self, m: MarketFeatures) -> bool:
        if m.total_executed_volume < self.min_volume:
            return False
        if m.trade_count < self.min_trades:
            return False
        if m.spread is not None and m.spread > self.max_spread:
            return False
        if m.yes_price > self.max_price or m.yes_price < self.min_price:
            return False
        return True

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        filtered = [m for m in event_features.child_markets if self._passes_filters(m)]
        if not filtered:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker="",
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_markets_pass_filters",
                experiment_id=f"EXP_E_{int(event_features.threshold * 100)}",
            )
        # Same side selection as Experiment A on filtered set
        selected = max(filtered, key=lambda m: m.total_executed_volume)
        side = "YES" if selected.yes_executed_volume > selected.no_executed_volume else "NO"

        return TradeDecision(
            event_ticker=event_features.event_ticker,
            market_ticker=selected.market_ticker,
            selected_side=side,
            trade_decision=f"BUY_{side}",
            entry_price_cents=selected.yes_price if side == "YES" else selected.no_price,
            entry_threshold=event_features.threshold,
            event_progress_at_entry=event_features.event_progress,
            selected_market_reason="highest_executed_volume_with_filters",
            selected_side_reason=f"{side.lower()}_executed_volume_gt_opposite",
            experiment_id=f"EXP_E_{int(event_features.threshold * 100)}",
        )
```

---

### Experiment F — Resting-Depth Follower

Closest to the original "most-bet" logic. Requires historical orderbook snapshots for honest backtesting.

```python
class RestingDepthFollower(StrategyExperiment):
    """
    Market with highest total resting orderbook depth.
    Side with more resting depth.
    Requires historical orderbook snapshots for honest backtesting.
    """
    name = "resting-depth-follower"
    description = "Original most-bet logic: highest resting depth → deeper side"

    def select_trade(self, event_features: EventFeatures) -> TradeDecision:
        with_depth = [
            m for m in event_features.child_markets
            if m.yes_total_depth is not None and m.no_total_depth is not None
        ]
        if not with_depth:
            return TradeDecision(
                event_ticker=event_features.event_ticker,
                market_ticker="",
                selected_side="",
                trade_decision="SKIP",
                skip_reason="no_depth_data",
                experiment_id=f"EXP_F_{int(event_features.threshold * 100)}",
            )

        selected = max(
            with_depth,
            key=lambda m: (m.yes_total_depth or 0) + (m.no_total_depth or 0),
        )
        side = "YES" if (selected.yes_total_depth or 0) > (selected.no_total_depth or 0) else "NO"

        return TradeDecision(
            event_ticker=event_features.event_ticker,
            market_ticker=selected.market_ticker,
            selected_side=side,
            trade_decision=f"BUY_{side}",
            entry_price_cents=selected.yes_price if side == "YES" else selected.no_price,
            entry_threshold=event_features.threshold,
            event_progress_at_entry=event_features.event_progress,
            selected_market_reason="highest_total_resting_depth",
            selected_side_reason=f"{side.lower()}_higher_resting_depth",
            experiment_id=f"EXP_F_{int(event_features.threshold * 100)}",
        )
```

---

### Experiment G — Hybrid Score Follower

A weighted combination of executed volume, price movement, liquidity, and spread.

**Market score:**

```python
market_score = (
    0.40 * normalized_executed_volume
    + 0.25 * normalized_trade_count
    + 0.20 * normalized_absolute_price_momentum
    + 0.15 * normalized_liquidity_score
)
```

**Side score:**

```python
yes_score = (
    0.45 * normalized_yes_executed_volume
    + 0.25 * normalized_yes_price_momentum
    + 0.20 * normalized_yes_depth
    + 0.10 * normalized_yes_recent_trade_count
)

no_score = (
    0.45 * normalized_no_executed_volume
    + 0.25 * normalized_no_price_momentum
    + 0.20 * normalized_no_depth
    + 0.10 * normalized_no_recent_trade_count
)
```

Select: `selected_side = YES if yes_score > no_score else NO`

---

## Experiment Registry

```python
EXPERIMENT_REGISTRY: dict[str, type[StrategyExperiment]] = {
    "executed-volume-follower": ExecutedVolumeFollower,
    "executed-volume-fade": ExecutedVolumeFade,
    "favorite-side-follower": FavoriteSideFollower,
    "momentum-follower": MomentumFollower,
    "liquidity-filtered-follower": LiquidityFilteredFollower,
    "resting-depth-follower": RestingDepthFollower,
    "hybrid-score-follower": HybridScoreFollower,
}

def get_experiment(name: str, config: dict) -> StrategyExperiment:
    if name not in EXPERIMENT_REGISTRY:
        raise ValueError(
            f"Unknown experiment: {name}. "
            f"Available: {list(EXPERIMENT_REGISTRY.keys())}"
        )
    return EXPERIMENT_REGISTRY[name](config)
```

---

## Config

```yaml
# config/settings.yaml
strategy:
  active_experiment: executed-volume-follower   # switch here
  default_threshold: 0.60

  experiments:
    executed-volume-follower: {}
    executed-volume-fade: {}
    favorite-side-follower: {}
    momentum-follower:
      early_reference_progress: 0.40
    liquidity-filtered-follower:
      min_total_executed_volume: 500
      min_trade_count: 20
      max_spread_cents: 5
      max_entry_price_cents: 85
      min_entry_price_cents: 15
      exclude_block_trades: true
    resting-depth-follower: {}
    hybrid-score-follower: {}

  execution:
    mode: taker          # taker | maker
    hold_to_settlement: true

  liquidity_filters:
    min_total_executed_volume: 500
    min_trade_count: 20
    exclude_block_trades: true
    max_one_trade_per_event: true

  risk:
    position_size_dollars: 10
    max_daily_loss_dollars: 100
    max_open_positions: 10
    max_positions_per_event: 1
```

---

## Decision Thresholds for Auto-Trading

Do not build auto-trading unless the backtest shows:

| Requirement | Minimum |
|-------------|--------:|
| Sample size | 500+ trades |
| Preferred sample size | 2,000+ trades |
| Net ROI after fees/slippage | 5%+ |
| Profit factor | 1.15+ |
| Max drawdown | Less than 20% |
| Positive months | At least 3 separate months |
| Positive categories | More than one event category |
| Threshold robustness | Positive at multiple thresholds |
| Stress test | Positive after conservative slippage |

---

## Backend Files

```
backend/strategies/
├── __init__.py              # EXPERIMENT_REGISTRY dict + get_experiment() factory
├── base.py                  # StrategyExperiment ABC + data models
├── executed_volume_follower.py      # ✅ Primary target
├── executed_volume_fade.py          # ⏸ Untested
├── favorite_side_follower.py        # ⏸ Untested
├── momentum_follower.py             # ⏸ Untested
├── liquidity_filtered_follower.py   # ⏸ Untested
├── resting_depth_follower.py        # ⏸ Untested
├── hybrid_score_follower.py         # ⏸ Untested
└── backtesting/
    ├── __init__.py
    ├── backtest_engine.py           # Backtest loop
    ├── feature_builder.py           # Feature calculations
    ├── entry_simulator.py           # Taker/maker fill simulation
    ├── exit_simulator.py            # Exit logic (settlement, profit target, etc.)
    └── metrics.py                   # Performance metrics
```

---

## Testing

Only `executed_volume_follower.py` is the primary target for testing initially.

```bash
pytest tests/test_strategies/test_executed_volume_follower.py -v   # runs
pytest tests/test_strategies/ -v                                    # runs primary only, skips others
```

---

## Performance Metrics

| Metric | Formula | Why it matters |
|--------|---------|---------------|
| Win rate | wins / trades | Directional accuracy |
| Avg entry price | mean(entry price) | Determines breakeven |
| Breakeven win rate | avg entry price + fees | Checks if win rate is enough |
| Gross ROI | gross profit / capital deployed | Before costs |
| Net ROI | net profit / capital deployed | Main metric |
| Profit factor | gross profits / gross losses | Robustness |
| Max drawdown | largest peak-to-trough decline | Risk |
| Sharpe-like score | avg return / std return | Stability |
| Fill rate | filled orders / attempted orders | Important for maker tests |
| Skip rate | skipped / candidates | Filter strictness |
| Category ROI | ROI by category | Detects where edge exists |
| Threshold ROI | ROI by threshold | Detects timing sensitivity |

---

## Research Questions

| Question | Why it matters |
|----------|---------------|
| Does the most-volume child market outperform random child-market selection? | Tests if market selection has value. |
| Does following the dominant side outperform fading it? | Tests directionality. |
| Does 60% progress outperform 50%, 65%, 75%, or 85%? | Tests timing. |
| Does win rate exceed breakeven entry price? | Prevents false confidence. |
| Are returns positive after fees and slippage? | Main business viability question. |
| Are returns concentrated in one category? | Detects overfitting. |
| Does maker execution outperform taker execution after fill-rate adjustment? | Execution model decision. |
| Do filters improve or destroy the signal? | Determines production rules. |
| Does the edge persist in forward paper trading? | Final validation before real capital. |
