"""FastAPI authentication dependencies — JWT bearer + RBAC."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.security.src.auth import AuthService, TokenPayload
from packages.security.src.rbac import Permission, require_permission

_bearer = HTTPBearer(auto_error=False)
_auth_service = AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> TokenPayload:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return _auth_service.verify_token(credentials.credentials)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_role(*permissions: Permission):
    async def checker(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        for perm in permissions:
            try:
                require_permission(user.role, perm)
            except PermissionError:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {perm.value}")
        return user
    return checker
