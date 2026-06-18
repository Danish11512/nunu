"""Backtesting infrastructure for strategy experiments.

Provides:
  - feature_builder: enriches MarketFeatures from historical trade data
  - entry_simulator: simulates taker/maker trade entry
  - exit_simulator: simulates settlement and other exit scenarios
  - metrics: computes performance metrics per experiment
  - backtest_engine: orchestrates the full backtest loop
"""
