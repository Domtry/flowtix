"""Tests for JWT auth service."""

import pytest
from packages.security.src.auth import AuthConfig, AuthService


@pytest.fixture
def auth():
    return AuthService(AuthConfig(secret_key="test-secret-key-32chars-minimum!"))


def test_create_and_verify_access_token(auth):
    token = auth.create_access_token("user@test.com", "admin")
    payload = auth.verify_token(token)
    assert payload.sub == "user@test.com"
    assert payload.role == "admin"


def test_create_refresh_token(auth):
    token = auth.create_refresh_token("user@test.com")
    payload = auth.verify_token(token)
    assert payload.sub == "user@test.com"


def test_invalid_token(auth):
    with pytest.raises(PermissionError, match="Invalid token"):
        auth.verify_token("invalid.token.here")


def test_wrong_secret():
    auth1 = AuthService(AuthConfig(secret_key="secret-one-32chars-minimum!!!!"))
    auth2 = AuthService(AuthConfig(secret_key="secret-two-32chars-minimum!!!!"))
    token = auth1.create_access_token("user@test.com")
    with pytest.raises(PermissionError):
        auth2.verify_token(token)


def test_extra_claims(auth):
    token = auth.create_access_token("user@test.com", extra={"tenant": "acme"})
    payload = auth.verify_token(token)
    assert payload.sub == "user@test.com"
