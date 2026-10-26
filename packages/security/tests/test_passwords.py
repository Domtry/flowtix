"""Tests for password hashing."""

from packages.security.src.passwords import hash_password, verify_password


def test_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)


def test_wrong_password():
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_different_hashes():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
