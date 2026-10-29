"""User management routes — registration, login, profile (DB-backed)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.security.src.auth import AuthService
from packages.security.src.passwords import hash_password, verify_password
from packages.security.src.rbac import Permission

from ..core.auth import get_current_user, require_role
from ..core.database import get_db
from ..models.process import User
from ..schemas.process import LoginRequest, TokenResponse, UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])

_auth = AuthService()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(req: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=req.email,
        name=req.name,
        password_hash=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=_auth.create_access_token(user.email, user.role),
        refresh_token=_auth.create_refresh_token(user.email),
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def me(token=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == token.sub))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/", response_model=list[UserRead], dependencies=[Depends(require_role(Permission.USER_MANAGE))])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())
