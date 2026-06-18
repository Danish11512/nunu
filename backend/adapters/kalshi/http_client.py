from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from backend.utils.http_utils import RateLimiter

logger = logging.getLogger(__name__)


class KalshiHttpClient:
    """Raw HTTP transport for Kalshi API.

    - Connection pooling via ``httpx.AsyncClient``
    - Rate limiting via :class:`backend.utils.http_utils.RateLimiter`
    - Retry with capped ``retry-after`` header parsing (max 30 s)
    - Auth headers injected at call time (caller provides signer)
    """

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(
        self,
        base_url: str | None = None,
        rate_limit: int = 10,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(max_per_second=rate_limit)
        self.timeout = timeout
        self.max_retries = max_retries

    async def __aenter__(self) -> KalshiHttpClient:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HTTP client not initialized. Use 'async with'.")
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        auth_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Rate-limited request with retry. Auth headers injected by caller."""
        async with self._rate_limiter:
            url = f"{self.base_url}{path}"
            headers = {**(kwargs.pop("headers", {})), **(auth_headers or {})}

            async def _request_with_retry() -> dict[str, Any]:
                for attempt in range(self.max_retries):
                    try:
                        response = await self.client.request(
                            method, url, headers=headers, **kwargs
                        )
                        response.raise_for_status()
                        return response.json()
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            # Rate limited — parse retry-after, cap at 30 s
                            raw = e.response.headers.get("retry-after", "1")
                            try:
                                retry_after = min(int(raw), 30)
                            except (ValueError, TypeError):
                                retry_after = min(2**attempt, 30)
                            logger.warning(
                                "Rate limited (attempt %d/%d). Retrying in %ds.",
                                attempt + 1,
                                self.max_retries,
                                retry_after,
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        # Non-retryable status — propagate immediately
                        raise
                    except (httpx.TimeoutException, httpx.NetworkError) as e:
                        if attempt == self.max_retries - 1:
                            raise
                        delay = min(2**attempt, 10)
                        logger.warning(
                            "Request error (attempt %d/%d): %s. Retrying in %ds.",
                            attempt + 1,
                            self.max_retries,
                            e,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                raise RuntimeError(
                    f"Request failed after {self.max_retries} retries."
                )

            return await _request_with_retry()
