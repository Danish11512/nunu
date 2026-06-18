from __future__ import annotations

import base64
import logging
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from backend.utils.auth_utils import _normalise_pem

logger = logging.getLogger(__name__)


class KalshiSigner:
    """RSA-PKCS1v15 request signing for Kalshi WebSocket authentication.

    Uses three headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE,
    KALSHI-ACCESS-TIMESTAMP. PKCS1v15 padding is correct for WebSocket auth.

    NOTE: This signer is WebSocket-only. REST API calls use the RSA-PSS
    signer from ``backend.utils.auth_utils.KalshiSigner`` instead.
    """

    def __init__(self, api_key_id: str = "", private_key_pem: Optional[str] = None):
        if not api_key_id:
            raise ValueError("KalshiSigner: api_key_id is required")
        if not private_key_pem:
            raise ValueError("KalshiSigner: private_key_pem is required")
        self.api_key_id = api_key_id
        self.private_key_pem = private_key_pem

    def sign(self, method: str, path: str, body: str = "") -> tuple[str, str, str]:
        """Sign a Kalshi API request.

        Returns:
            Tuple of (api_key_id, base64_signature, timestamp_ms).

        Raises:
            ValueError: If private key is not configured.
        """
        if not self.private_key_pem:
            raise ValueError("KalshiSigner: private_key_pem not configured — cannot sign")

        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + path + body

        normalised = _normalise_pem(self.private_key_pem)
        key_bytes = (
            normalised.encode("utf-8")
            if isinstance(normalised, str)
            else normalised
        )
        private_key = serialization.load_pem_private_key(key_bytes, password=None)
        signature = private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return self.api_key_id, base64.b64encode(signature).decode(), timestamp

    def get_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        """Convenience: returns dict of KALSHI-ACCESS-* headers."""
        key, sig, ts = self.sign(method, path, body)
        return {
            "KALSHI-ACCESS-KEY": key,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }
