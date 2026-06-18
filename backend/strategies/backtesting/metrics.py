"""Performance metrics for backtesting.

Computes win rate, ROI, profit factor, drawdown, and Sharpe-like ratio
for each experiment x threshold combination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import statistics


@dataclass
class TradeResult:
    """Result of a single backtested trade."""
    experiment_id: str
    threshold: float
    event_ticker: str
    market_ticker: str
    side: str                # "yes" | "no"
    entry_price: int         # cents
    exit_price: int          # cents
    won: bool
    pnl_cents: int
    roi_percent: float
    entry_time: Optional[datetime] = None
    category: str = ""
    fill_mode: str = "taker"


@dataclass
class StrategyMetrics:
    """Aggregated performance metrics for one experiment x threshold."""
    experiment_id: str
    threshold: float
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_entry_price: float
    breakeven_win_rate: float
    gross_roi: float
    net_roi: float
    profit_factor: float
    max_drawdown: float
    sharpe_like: float
    avg_roi_per_trade: float
    category_rois: dict = field(default_factory=dict)
    threshold_rois: dict = field(default_factory=dict)


def compute_metrics(results: list[TradeResult]) -> StrategyMetrics:
    """Compute aggregate metrics from a list of TradeResults.

    NOTE: Some formulas have known limitations documented in the
    Phase 5 alignment doc:
      - gross_roi is computed as profit ratio, not true ROI
      - net_roi uses average entry price (approximation)
      - max_drawdown is computed as peak-to-trough of cumulative PnL
      - breakeven_win_rate = avg_entry_price / 100
    """
    if not results:
        return StrategyMetrics(
            experiment_id="",
            threshold=0.0,
            total_trades=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            avg_entry_price=0.0,
            breakeven_win_rate=0.0,
            gross_roi=0.0,
            net_roi=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe_like=0.0,
            avg_roi_per_trade=0.0,
        )

    wins = [r for r in results if r.won]
    losses = [r for r in results if not r.won]
    total_pnl = sum(r.pnl_cents for r in results)
    gross_profit = sum(r.pnl_cents for r in wins)
    gross_loss = abs(sum(r.pnl_cents for r in losses))

    entry_prices = [r.entry_price for r in results]
    rois = [r.roi_percent for r in results]
    avg_entry = statistics.mean(entry_prices) if entry_prices else 0.0

    # Profit factor: gross profit / gross loss
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown: peak-to-trough of cumulative PnL
    if all(r.entry_time is not None for r in results):
        dd_results = sorted(results, key=lambda r: r.entry_time)
    else:
        dd_results = results
    md = _compute_max_drawdown([r.pnl_cents for r in dd_results])

    # Sharpe-like: avg(roi) / stdev(roi)
    if len(rois) > 1 and statistics.stdev(rois) > 1e-9:
        sharpe = statistics.mean(rois) / statistics.stdev(rois)
    else:
        sharpe = 0.0

    # Category ROIs
    cat_rois = _compute_category_rois(results)

    # Threshold ROIs (if multiple thresholds present)
    thresh_rois = _compute_threshold_rois(results)

    return StrategyMetrics(
        experiment_id=results[0].experiment_id,
        threshold=results[0].threshold,
        total_trades=len(results),
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / len(results) if results else 0.0,
        avg_entry_price=avg_entry,
        breakeven_win_rate=avg_entry / 100.0 if avg_entry > 0 else 0.0,
        gross_roi=gross_profit / (gross_profit + gross_loss) if (gross_profit + gross_loss) > 0 else 0.0,
        net_roi=total_pnl / (avg_entry * len(results)) if avg_entry > 0 and results else 0.0,
        profit_factor=pf,
        max_drawdown=md,
        sharpe_like=sharpe,
        avg_roi_per_trade=statistics.mean(rois) if rois else 0.0,
        category_rois=cat_rois,
        threshold_rois=thresh_rois,
    )


def _compute_max_drawdown(pnls: list[int]) -> float:
    """Compute maximum drawdown from a sequence of PnLs.

    Tracks cumulative PnL and measures the largest peak-to-trough decline
    as a fraction of the peak cumulative value.
    """
    if not pnls:
        return 0.0

    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0

    for pnl in pnls:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        if peak > 0:
            dd = (peak - cumulative) / peak
            max_dd = max(max_dd, dd)

    return max_dd


def _compute_category_rois(results: list[TradeResult]) -> dict[str, float]:
    """Compute ROI per event category."""
    categories: dict[str, list[float]] = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = []
        categories[r.category].append(r.roi_percent)

    return {
        cat: statistics.mean(rois) if rois else 0.0
        for cat, rois in categories.items()
    }


def _compute_threshold_rois(results: list[TradeResult]) -> dict[str, float]:
    """Compute ROI per progress threshold."""
    thresholds: dict[float, list[float]] = {}
    for r in results:
        if r.threshold not in thresholds:
            thresholds[r.threshold] = []
        thresholds[r.threshold].append(r.roi_percent)

    return {
        str(th): statistics.mean(rois) if rois else 0.0
        for th, rois in sorted(thresholds.items())
    }
