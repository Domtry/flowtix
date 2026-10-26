"""Tests for AES-256-GCM encryption."""

import base64
import pytest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from packages.security.src.encryption import SecretEncryptor


@pytest.fixture
def encryptor():
    key = AESGCM.generate_key(bit_length=256)
    return SecretEncryptor(key=key)


def test_encrypt_decrypt(encryptor):
    plaintext = "my-super-secret-password"
    ciphertext = encryptor.encrypt(plaintext)
    assert ciphertext != plaintext.encode()
    assert encryptor.decrypt(ciphertext) == plaintext


def test_different_ciphertexts(encryptor):
    ct1 = encryptor.encrypt("same")
    ct2 = encryptor.encrypt("same")
    assert ct1 != ct2  # random nonce


def test_wrong_key():
    key1 = AESGCM.generate_key(bit_length=256)
    key2 = AESGCM.generate_key(bit_length=256)
    enc = SecretEncryptor(key=key1)
    ct = enc.encrypt("secret")
    dec = SecretEncryptor(key=key2)
    with pytest.raises(Exception):
        dec.decrypt(ct)


def test_invalid_key_size():
    with pytest.raises(ValueError, match="32 bytes"):
        SecretEncryptor(key=b"too-short")


def test_generate_key():
    key_b64 = SecretEncryptor.generate_key()
    key_bytes = base64.b64decode(key_b64)
    assert len(key_bytes) == 32


def test_unicode_content(encryptor):
    text = "Mot de passe: café ☕ 日本語"
    assert encryptor.decrypt(encryptor.encrypt(text)) == text
