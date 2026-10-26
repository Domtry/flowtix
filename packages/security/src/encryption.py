"""AES-256-GCM encryption for secrets — never store secrets in cleartext."""

from __future__ import annotations

import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import structlog

logger = structlog.get_logger()

KEY_SIZE = 32  # 256 bits
NONCE_SIZE = 12


class SecretEncryptor:
    """Encrypts/decrypts secrets using AES-256-GCM.

    The encryption key must be provided externally (env var, vault, etc.).
    Never hardcode or log the key.
    """

    def __init__(self, key: bytes | None = None) -> None:
        if key is None:
            key_b64 = os.environ.get("FLOWTIX_ENCRYPTION_KEY")
            if key_b64:
                key = base64.b64decode(key_b64)
            else:
                key = AESGCM.generate_key(bit_length=256)
                logger.warning("encryption.generated_key", msg="Using generated key — set FLOWTIX_ENCRYPTION_KEY in production")
        if len(key) != KEY_SIZE:
            raise ValueError(f"Encryption key must be {KEY_SIZE} bytes")
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: str) -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + ct

    def decrypt(self, ciphertext: bytes) -> str:
        nonce = ciphertext[:NONCE_SIZE]
        ct = ciphertext[NONCE_SIZE:]
        plaintext = self._aesgcm.decrypt(nonce, ct, None)
        return plaintext.decode("utf-8")

    @staticmethod
    def generate_key() -> str:
        """Generate a new base64-encoded 256-bit key."""
        return base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()
