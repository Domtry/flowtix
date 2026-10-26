"""User management routes — registration, login, profile."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from packages.security.src.auth import AuthService
from packages.security.src.passwords import hash_password, verify_password
from packages.security.src.rbac import Permission

from ..core.auth import get_current_user, require_role

router = APIRouter(prefix="/users", tags=["users"])

_auth = AuthService()
# In-memory user store for MVP — replace with DB in production
_users: dict[str, dict] = {}


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str = "operator"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    if req.email in _users:
        raise HTTPException(status_code=409, detail="Email already registered")
    _users[req.email] = {
        "email": req.email,
        "name": req.name,
        "password_hash": hash_password(req.password),
        "role": req.role,
    }
    return {"email": req.email, "name": req.name, "role": req.role}


@router.post("/login")
async def login(req: LoginRequest) -> TokenResponse:
    user = _users.get(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=_auth.create_access_token(user["email"], user["role"]),
        refresh_token=_auth.create_refresh_token(user["email"]),
    )


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return {"sub": user.sub, "role": user.role}


@router.get("/", dependencies=[Depends(require_role(Permission.USER_MANAGE))])
async def list_users():
    return [{"email": u["email"], "name": u["name"], "role": u["role"]} for u in _users.values()]
