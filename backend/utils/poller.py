from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AsyncPoller(ABC):
    """Generic async poller that calls a user callback on an interval.

    Usage:
        class MyPoller(AsyncPoller):
            async def on_poll(self) -> None:
                # Do work here
                pass

        poller = MyPoller(interval_seconds=30)
        await poller.start()
        # ... later ...
        await poller.stop()
    """

    def __init__(
        self,
        interval_seconds: float = 30.0,
        name: str = "poller",
        jitter_seconds: float = 0.0,
    ):
        self.interval_seconds = interval_seconds
        self.name = name
        self.jitter_seconds = jitter_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._last_poll_time: datetime | None = None
        self._poll_count: int = 0

    @abstractmethod
    async def on_poll(self) -> None:
        """Called every poll interval. Override to implement work."""
        ...

    async def on_start(self) -> None:
        """Hook called when the poller starts. Override for setup."""
        pass

    async def on_stop(self) -> None:
        """Hook called when the poller stops. Override for cleanup."""
        pass

    async def on_error(self, exc: Exception) -> None:
        """Called when on_poll raises. Override for error handling.

        Default: log error and continue polling.
        """
        logger.error(
            "Poller %s: error in cycle %d: %s",
            self.name,
            self._poll_count,
            exc,
            exc_info=True,
        )

    async def start(self) -> None:
        """Start the poller loop (non-blocking)."""
        if self._task is not None:
            logger.warning("Poller %s: already running", self.name)
            return

        await self.on_start()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("Poller %s: started (interval=%ds)", self.name, self.interval_seconds)

    async def stop(self) -> None:
        """Signal the poller to stop and wait for it."""
        if self._task is None:
            return

        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=self.interval_seconds + 5)
        except asyncio.TimeoutError:
            logger.warning("Poller %s: stop timeout — cancelling task", self.name)
            self._task.cancel()
        except asyncio.CancelledError:
            pass

        self._task = None
        await self.on_stop()
        logger.info("Poller %s: stopped", self.name)

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def last_poll_time(self) -> datetime | None:
        return self._last_poll_time

    @property
    def poll_count(self) -> int:
        return self._poll_count

    async def poll_once(self) -> None:
        """Execute a single poll cycle immediately (bypasses interval)."""
        try:
            await self.on_poll()
            self._poll_count += 1
            self._last_poll_time = datetime.now(timezone.utc)
        except Exception as e:
            await self.on_error(e)

    async def _run(self) -> None:
        """Main poller loop."""
        try:
            while not self._stop_event.is_set():
                await self.poll_once()

                # Wait for interval or stop signal
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval_seconds,
                    )
                    break  # Stop signal received
                except asyncio.TimeoutError:
                    continue  # Interval elapsed, poll again
        except asyncio.CancelledError:
            logger.info("Poller %s: cancelled", self.name)
        except Exception as e:
            logger.error("Poller %s: fatal error in run loop: %s", self.name, e)
            raise
