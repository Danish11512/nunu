"""
Thin facade — validates a candidate and submits it to the ExecutionEngine.
Kept for backward compat with the API layer; new code calls ExecutionEngine directly.
"""
from backend.core.models.trading import ProgressBasedOrderCandidate
from backend.trading.execution_engine import ExecutionEngine


class TradeExecutor:
    def __init__(self, engine: ExecutionEngine):
        self.engine = engine

    async def execute(self, candidate: ProgressBasedOrderCandidate):
        """Submit a candidate to the execution engine.

        Returns (None, None) — results flow through portfolio + stats.
        """
        await self.engine.submit_signal(candidate)
        return None, None
