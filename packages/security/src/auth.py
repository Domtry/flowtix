"""JWT authentication — token creation and validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()


class TokenPayload(BaseModel):
    sub: str
    role: str = "operator"
    exp: datetime | None = None


class AuthConfig(BaseModel):
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 7


class AuthService:
    def __init__(self, config: AuthConfig | None = None) -> None:
        self._config = config or AuthConfig()

    def create_access_token(self, user_id: str, role: str = "operator", extra: dict[str, Any] | None = None) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self._config.access_token_ttl_minutes)
        payload = {"sub": user_id, "role": role, "exp": expire, "type": "access"}
        if extra:
            payload.update(extra)
        return jwt.encode(payload, self._config.secret_key, algorithm=self._config.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=self._config.refresh_token_ttl_days)
        payload = {"sub": user_id, "exp": expire, "type": "refresh"}
        return jwt.encode(payload, self._config.secret_key, algorithm=self._config.algorithm)

    def verify_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(token, self._config.secret_key, algorithms=[self._config.algorithm])
            return TokenPayload(
                sub=payload["sub"],
                role=payload.get("role", "operator"),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            )
        except JWTError as exc:
            raise PermissionError(f"Invalid token: {exc}") from exc
