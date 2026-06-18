"""
CSV logging — one file per event type (candidates, trades, opportunities).
"""
import csv
import os
from datetime import datetime
from backend.core.models.trading import ProgressBasedOrderCandidate, TradeRecord


class CSVLogger:
    """Logs candidates, trades, and opportunities to separate CSV files."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self):
        self._init_csv("candidates.csv", [
            "timestamp", "event_ticker", "market_ticker", "side",
            "progress_pct", "threshold_pct", "total_orders", "reasons",
        ])
        self._init_csv("trades.csv", [
            "entry_time", "trade_id", "event_ticker", "market_ticker",
            "side", "entry_price", "quantity", "mode", "status", "latency_ms", "error",
        ])
        self._init_csv("opportunities.csv", [
            "timestamp", "event_ticker", "market_ticker", "side",
            "progress_pct", "total_orders", "edge",
        ])

    def _init_csv(self, name: str, headers: list[str]):
        path = os.path.join(self.log_dir, name)
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(headers)

    def log_candidate(self, c: ProgressBasedOrderCandidate):
        path = os.path.join(self.log_dir, "candidates.csv")
        with open(path, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now().isoformat(), c.event_ticker,
                c.market_ticker,
                c.most_bet_side, f"{c.progress_pct:.1f}",
                c.threshold_pct, c.volume,
                c.reason,
            ])

    def log_trade(self, t: TradeRecord):
        path = os.path.join(self.log_dir, "trades.csv")
        with open(path, "a", newline="") as f:
            csv.writer(f).writerow([
                t.entry_time.isoformat() if t.entry_time else "", t.trade_id,
                t.event_ticker, t.market_ticker,
                t.side, t.entry_price, t.quantity, t.mode, t.status,
                f"{t.validation_latency_ms:.1f}", t.error or "",
            ])

    def log_opportunity(self, c: ProgressBasedOrderCandidate):
        path = os.path.join(self.log_dir, "opportunities.csv")
        with open(path, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now().isoformat(),
                c.event_ticker,
                c.market_ticker,
                c.most_bet_side,
                f"{c.progress_pct:.1f}",
                c.volume,
                "",  # edge — no edge metric yet
            ])
