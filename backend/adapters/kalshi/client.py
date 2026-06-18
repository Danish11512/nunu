from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from backend.config.settings import KalshiConfig
from backend.utils.auth_utils import KalshiSigner  # RSA-PSS signer for REST

from .http_client import KalshiHttpClient

logger = logging.getLogger(__name__)


class KalshiClient:
    """Kalshi REST API client — endpoint-specific methods only.

    Uses **RSA-PSS** signing (from :mod:`backend.utils.auth_utils`) for REST auth.
    WebSocket auth uses the PKCS1v15 signer from :mod:`.auth` instead.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key_id: str = "",
        private_key: str = "",
        rate_limit: int = 10,
    ):
        self.http = KalshiHttpClient(base_url=base_url, rate_limit=rate_limit)
        self.api_key_id = api_key_id
        # RSA-PSS signer for REST — NOT the PKCS1v15 one from .auth
        self.signer: KalshiSigner | None = None
        if private_key:
            self.signer = KalshiSigner(private_key_pem=private_key)

    async def __aenter__(self) -> KalshiClient:
        await self.http.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.http.__aexit__(*args)

    # ── Auth helpers ──────────────────────────────────────────────────────

    def _sign_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        """Generate KALSHI-ACCESS-* headers using RSA-PSS signer."""
        ts = KalshiSigner.generate_timestamp()
        message = ts + method.upper() + path + body
        sig = self.signer.sign(message)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }

    # ── Market endpoints ──────────────────────────────────────────────────

    async def list_markets(
        self, status: str = "open", limit: int = 1000, cursor: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        headers = self._sign_headers("GET", "/markets")
        return await self.http.request("GET", "/markets", headers=headers, params=params)

    async def get_market(self, ticker: str) -> Optional[dict[str, Any]]:
        path = f"/markets/{ticker}"
        headers = self._sign_headers("GET", path)
        try:
            data = await self.http.request("GET", path, headers=headers)
            return data.get("market")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_event(self, event_ticker: str) -> Optional[dict[str, Any]]:
        """Fetch a single event by ticker (wraps /events/{event_ticker})."""
        path = f"/events/{event_ticker}"
        headers = self._sign_headers("GET", path)
        try:
            data = await self.http.request("GET", path, headers=headers)
            return data.get("event")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def list_events(
        self, status: str = "open", limit: int = 100, cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetch all events (wraps /events)."""
        params: dict[str, Any] = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        headers = self._sign_headers("GET", "/events")
        return await self.http.request("GET", "/events", headers=headers, params=params)

    async def get_orderbook(self, ticker: str, **kwargs: Any) -> dict[str, Any]:
        path = f"/markets/{ticker}/orderbook"
        headers = self._sign_headers("GET", path)
        return await self.http.request("GET", path, headers=headers)

    # ── Trading endpoints ─────────────────────────────────────────────────

    async def place_order(
        self, ticker: str, side: str, price: int, count: int, **kwargs: Any
    ) -> dict[str, Any]:
        """Place a limit order.

        Args:
            ticker: Market ticker (e.g. ``"KXLYDYX"``).
            side: ``"yes"`` or ``"no"`` — mapped to Kalshi V2 API values.
            price: Limit price in **integer cents**.
            count: Number of contracts (integer).
            **kwargs: Additional order params (``time_in_force``, etc.).

        Returns:
            dict with order response (e.g. ``{"order_id": "..."}``).
        """
        body: dict[str, Any] = {
            "ticker": ticker,
            "side": side,
            "type": "limit",
            "price": price,    # integer cents
            "count": count,    # integer contracts
            "time_in_force": kwargs.get("time_in_force", "GTC"),
        }
        payload = json.dumps(body, separators=(",", ":"))
        path = "/portfolio/orders"
        headers = self._sign_headers("POST", path, payload)
        headers["Content-Type"] = "application/json"
        return await self.http.request("POST", path, headers=headers, content=payload)

    async def cancel_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        """Cancel an existing order by ID."""
        path = f"/portfolio/orders/{order_id}"
        headers = self._sign_headers("DELETE", path)
        return await self.http.request("DELETE", path, headers=headers)

    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get current positions."""
        path = "/portfolio/positions"
        headers = self._sign_headers("GET", path)
        data = await self.http.request("GET", path, headers=headers)
        return data.get("positions", [])

    # ── Factory ───────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config: KalshiConfig) -> KalshiClient:
        """Create a client from a KalshiConfig, handling key path vs PEM text."""
        private_key = config.private_key
        if not private_key and config.private_key_path:
            from pathlib import Path
            private_key = Path(config.private_key_path).read_text()
        return cls(
            base_url=config.api_base_url,
            api_key_id=config.key_id,
            private_key=private_key,
            rate_limit=config.rate_limit,
        )

    # ── Pagination ────────────────────────────────────────────────────────

    async def fetch_all_open_markets(self, max_pages: int = 100, **kwargs: Any) -> list[dict[str, Any]]:
        """Paginate through all open markets, deduplicate by ticker.

        Uses a while-loop guard (``max_pages``) as a circuit-breaker.
        Wraps each page fetch in try/except to allow partial results.
        """
        all_markets: list[dict[str, Any]] = []
        cursor: str | None = None
        pages_fetched = 0

        while pages_fetched < max_pages:
            try:
                data = await self.list_markets(cursor=cursor)
                all_markets.extend(data.get("markets", []))
                cursor = data.get("cursor")
                pages_fetched += 1
                if not cursor:
                    break
            except Exception as e:
                logger.warning(
                    "Page %d fetch failed (got %d markets so far): %s",
                    pages_fetched + 1,
                    len(all_markets),
                    e,
                )
                # If the very first page fails, propagate the error
                if pages_fetched == 0:
                    raise
                break

        # Deduplicate by ticker (defensive — Kalshi pagination is stable)
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for m in all_markets:
            ticker = m.get("ticker")
            if ticker and ticker not in seen:
                seen.add(ticker)
                unique.append(m)

        logger.info(
            "Fetched %d markets across %d pages (%d unique).",
            len(all_markets),
            pages_fetched,
            len(unique),
        )
        return unique
