from __future__ import annotations

import base64
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


def _normalise_pem(pem: str) -> str:
    """Reformat single-line PEM to standard 64-char line breaks.

    ``cryptography``'s ``load_pem_private_key`` requires line breaks every
    64 characters.  Environment variables often store the PEM as a single
    line, so this helper inserts newlines when the body lacks them.
    """
    if "-----BEGIN" not in pem or "-----END" not in pem:
        return pem
    header_end = pem.index("-----END")
    before_end = pem[:header_end]
    if "\n" not in before_end.strip("-----BEGIN ") and len(pem) > 150:
        b64 = (
            pem.replace("-----BEGIN RSA PRIVATE KEY-----", "")
            .replace("-----END RSA PRIVATE KEY-----", "")
            .strip()
        )
        fixed = "-----BEGIN RSA PRIVATE KEY-----\n"
        fixed += "\n".join(b64[i : i + 64] for i in range(0, len(b64), 64))
        fixed += "\n-----END RSA PRIVATE KEY-----"
        return fixed
    return pem


class KalshiSigner:
    """RSA-PSS signer for Kalshi API authentication.

    Uses SHA-256 hashing with MGF1 padding as required by Kalshi's API.
    """

    def __init__(self, private_key_pem: str | bytes):
        """Initialize with PEM-encoded RSA private key.

        Args:
            private_key_pem: PEM-encoded private key string or bytes.
                Can include or exclude the PEM header/footer.
                Single-line PEM (all base64 on one line without newlines)
                is automatically reformatted to 64-char lines.
        """
        if isinstance(private_key_pem, str):
            private_key_pem = private_key_pem.encode("utf-8")

        decoded = private_key_pem.decode("utf-8")
        private_key_pem = _normalise_pem(decoded).encode("utf-8")

        self._private_key: RSAPrivateKey = serialization.load_pem_private_key(
            private_key_pem,
            password=None,
        )  # type: ignore[assignment]

    @classmethod
    def from_key_file(cls, key_path: str) -> KalshiSigner:
        """Load the private key from a PEM file.

        Args:
            key_path: Path to the PEM-encoded private key file.
        """
        with open(key_path, "rb") as f:
            pem_data = f.read()
        return cls(pem_data)

    def sign(self, message: str | bytes) -> str:
        """Sign a message using RSA-PSS and return base64-encoded signature.

        Args:
            message: The message to sign (string or bytes).

        Returns:
            Base64-encoded signature string.
        """
        if isinstance(message, str):
            message = message.encode("utf-8")

        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def get_public_key_pem(self) -> str:
        """Get the public key in PEM format (for debugging/verification)."""
        public_key = self._private_key.public_key()
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    @staticmethod
    def generate_timestamp() -> str:
        """Generate a Kalshi-compatible ISO timestamp for signing.

        Kalshi requires timestamps in ISO 8601 format with millisecond
        precision and Z suffix.
        """
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
