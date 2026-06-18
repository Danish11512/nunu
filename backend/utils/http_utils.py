from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket rate limiter for API requests.

    Limits requests to `max_per_second` calls per second.
    """

    def __init__(self, max_per_second: int = 10):
        self.max_per_second = max_per_second
        self._timestamps: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request slot is available."""
        while True:
            async with self._lock:
                now = datetime.now(timezone.utc)
                # Remove timestamps older than 1 second
                cutoff = now - timedelta(seconds=1)
                while self._timestamps and self._timestamps[0] < cutoff:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_per_second:
                    self._timestamps.append(now)
                    return

            # Wait a bit before retrying
            await asyncio.sleep(0.05)

    async def __aenter__(self) -> RateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


async def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_statuses: set[int] | None = None,
) -> Any:
    """Execute an async callable with exponential backoff retry.

    Args:
        func: Async callable to execute (e.g., lambda: client.get(...))
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds
        retryable_statuses: HTTP status codes that trigger retry.
            Default: {429, 500, 502, 503, 504}

    Returns:
        The result of the callable

    Raises:
        httpx.HTTPStatusError: If non-retryable status or max retries exceeded
        httpx.RequestError: On network errors (retried up to max_retries)
    """
    if retryable_statuses is None:
        retryable_statuses = {429, 500, 502, 503, 504}

    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            last_exception = e
            if e.response.status_code not in retryable_statuses:
                raise
            if attempt >= max_retries:
                raise
            logger.warning(
                "HTTP %d on attempt %d/%d: %s",
                e.response.status_code,
                attempt + 1,
                max_retries,
                e.response.url,
            )
        except httpx.RequestError as e:
            last_exception = e
            if attempt >= max_retries:
                raise
            logger.warning(
                "Request error on attempt %d/%d: %s",
                attempt + 1,
                max_retries,
                e,
            )

        # Exponential backoff with jitter
        delay = min(base_delay * (2 ** attempt), max_delay)
        await asyncio.sleep(delay)

    # Should not reach here, but satisfy type checker
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected: retry loop ended without result or exception")
