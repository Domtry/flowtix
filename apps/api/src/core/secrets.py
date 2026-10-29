"""Encrypt secrets stored in the database (AES-256-GCM via packages.security)."""

import base64
import binascii
import hashlib
import os

from packages.security.src.encryption import KEY_SIZE, SecretEncryptor

_PREFIX = "enc:v1:"


def _key() -> bytes:
    raw = os.environ.get("FLOWTIX_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError("FLOWTIX_ENCRYPTION_KEY n'est pas définie : impossible de chiffrer les secrets")
    try:
        key = base64.b64decode(raw, validate=True)
        if len(key) == KEY_SIZE:
            return key
    except (binascii.Error, ValueError):
        pass
    # not a base64 256-bit key (e.g. a passphrase): derive one
    return hashlib.sha256(raw.encode()).digest()


def encrypt(plaintext: str) -> str:
    token = SecretEncryptor(key=_key()).encrypt(plaintext)
    return _PREFIX + base64.b64encode(token).decode()


def decrypt(value: str) -> str:
    if not value.startswith(_PREFIX):
        raise ValueError("Valeur non chiffrée")
    return SecretEncryptor(key=_key()).decrypt(base64.b64decode(value[len(_PREFIX):]))
