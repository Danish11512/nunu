"""Backtest engine — main backtest orchestrator.

Runs all strategy experiments across historical events and progress
thresholds, simulating entry, exit, and computing performance metrics.
"""

import warnings
from datetime import datetime
from typing import Callable, Optional

from backend.core.interfaces.strategy import EventFeatures, MarketFeatures
from backend.core.models.backtesting import HistoricalEvent, OrderbookSnapshot
from backend.strategies import EXPERIMENT_REGISTRY, get_experiment

from .entry_simulator import simulate_taker_entry
from .exit_simulator import hold_to_settlement
from .feature_builder import build_market_features
from .metrics import StrategyMetrics, TradeResult, compute_metrics


def run_backtest(
    historical_events: list[HistoricalEvent],
    get_trades_fn: Callable[[str, datetime], list],
    thresholds: Optional[list[float]] = None,
    experiment_names: Optional[list[str]] = None,
    fee_cents: int = 0,
    slippage_cents: int = 0,
    get_orderbook_fn: Optional[Callable[[str, datetime], Optional[OrderbookSnapshot]]] = None,
    get_yes_price_fn: Optional[Callable[[str], int]] = None,
    get_no_price_fn: Optional[Callable[[str], int]] = None,
) -> dict[str, StrategyMetrics]:
    """Run a full backtest across events, thresholds, and experiments.
    
    Args:
        historical_events: List of HistoricalEvent dataclasses.
        get_trades_fn: Callable(market_ticker, before_time) -> list[HistoricalTrade].
        thresholds: Progress thresholds to test (e.g., [0.50, 0.60, 0.65, 0.75, 0.85]).
        experiment_names: Strategy names to test (default: all registered).
        fee_cents: Per-trade fee in cents (subtracted from PnL).
        slippage_cents: Per-trade slippage in cents (added to entry price).
        get_orderbook_fn: Optional callable returning Optional[OrderbookSnapshot].
        get_yes_price_fn: Optional callable for reference yes price.
        get_no_price_fn: Optional callable for reference no price.
    
    Returns:
        Dict mapping "{experiment_name}_{threshold_pct}" to StrategyMetrics.
    """
    if thresholds is None:
        thresholds = [0.50, 0.60, 0.65, 0.75, 0.85]
    if experiment_names is None:
        experiment_names = list(EXPERIMENT_REGISTRY.keys())

    price_default_warned = False
    all_results: dict[str, list[TradeResult]] = {}

    for event in historical_events:
        event_start = event.start_time
        event_end = event.end_time
        event_duration = (event_end - event_start).total_seconds()

        if event_duration <= 0:
            continue

        # Skip unsupported events early
        if event.settlement_result is None:
            continue

        for threshold in thresholds:
            # Compute entry time at this progress threshold
            entry_time = event_start + (event_end - event_start) * threshold

            # Build MarketFeatures for each child market
            market_features_list: list[MarketFeatures] = []
            for market_ticker in event.child_market_tickers:
                trades = get_trades_fn(market_ticker, entry_time)

                # Determine prices at entry (fetch once, cache for momentum)
                yes_price = 50
                no_price = 50
                ref_yes_price = None
                if (get_yes_price_fn is None or get_no_price_fn is None) and not price_default_warned:
                    warnings.warn(
                        "get_yes_price_fn or get_no_price_fn not provided — defaulting to 50¢ "
                        "for prices. Results may be misleading."
                    )
                    price_default_warned = True
                if get_yes_price_fn is not None:
                    yes_price = get_yes_price_fn(market_ticker)
                    ref_yes_price = yes_price
                if get_no_price_fn is not None:
                    no_price = get_no_price_fn(market_ticker)

                # Optional orderbook snapshot
                orderbook_snap = None
                if get_orderbook_fn is not None:
                    orderbook_snap = get_orderbook_fn(market_ticker, entry_time)

                mf = build_market_features(
                    ticker=market_ticker,
                    trades=trades,
                    orderbook_snapshot=orderbook_snap,
                    entry_time=entry_time,
                    yes_price_at_entry=yes_price,
                    no_price_at_entry=no_price,
                    reference_yes_price=ref_yes_price,
                )
                market_features_list.append(mf)

            # Build EventFeatures (note: NO category, event_progress, threshold, or entry_time fields)
            event_features = EventFeatures(
                event_ticker=event.event_ticker,
                event_title=event.event_title,
                child_markets=market_features_list,
                total_volume=sum(m.volume for m in market_features_list),
                num_markets=len(market_features_list),
            )

            # Run each experiment
            for exp_name in experiment_names:
                experiment = get_experiment(exp_name, {})
                decision = experiment.select_trade(event_features)

                if not decision.should_trade:
                    continue

                # Set experiment_id for tracing
                decision.experiment_id = exp_name

                # Simulate entry (always taker for v1)
                fill = simulate_taker_entry(
                    side=decision.side,
                    price_cents=decision.entry_price_cents if decision.entry_price_cents > 0 else 50,
                    quantity=1,
                    spread_cents=slippage_cents,
                )

                # Simulate exit (settlement only for v1)
                settlement_result = event.settlement_result
                exit_result = hold_to_settlement(
                    entry_price=fill.price_cents,
                    side=decision.side,
                    settlement_result=settlement_result,
                )

                # Apply fee
                fee = fee_cents
                pnl = exit_result.pnl_cents - fee
                roi = (pnl / fill.price_cents) * 100.0 if fill.price_cents > 0 else 0.0

                result = TradeResult(
                    experiment_id=exp_name,
                    threshold=threshold,
                    event_ticker=event.event_ticker,
                    market_ticker=decision.market_ticker,
                    side=decision.side,
                    entry_time=entry_time,
                    entry_price=fill.price_cents,
                    exit_price=exit_result.exit_price_cents,
                    won=pnl > 0,
                    pnl_cents=pnl,
                    roi_percent=roi,
                    fill_mode="taker",
                )

                key = f"{exp_name}_{int(threshold * 100)}"
                if key not in all_results:
                    all_results[key] = []
                all_results[key].append(result)

    # Compute metrics per experiment × threshold
    metrics: dict[str, StrategyMetrics] = {}
    for key, results in all_results.items():
        metrics[key] = compute_metrics(results)

    return metrics
