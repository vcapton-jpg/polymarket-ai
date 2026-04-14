"""Authentication routes — email/password with JWT tokens."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db_session
from app.db.models import UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class UserOut(BaseModel):
    id: int
    email: str | None
    plan: str
    created_at: datetime


def _create_token(user_id: int) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def _user_dict(user: UserProfile) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> UserProfile:
    """Extract and validate JWT, return the authenticated UserProfile."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret_key, algorithms=[ALGORITHM]
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = await db.execute(select(UserProfile).where(UserProfile.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@router.post("/register", response_model=AuthResponse)
async def register(body: AuthRequest, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(UserProfile).where(UserProfile.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = UserProfile(
        email=body.email,
        password_hash=pwd_context.hash(body.password),
        plan="free",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(token=_create_token(user.id), user=_user_dict(user))


@router.post("/login", response_model=AuthResponse)
async def login(body: AuthRequest, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(UserProfile).where(UserProfile.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return AuthResponse(token=_create_token(user.id), user=_user_dict(user))


@router.get("/me", response_model=UserOut)
async def me(user: UserProfile = Depends(get_current_user)):
    return UserOut(
        id=user.id,
        email=user.email,
        plan=user.plan,
        created_at=user.created_at,
    )


@router.post("/logout")
async def logout():
    return {"ok": True}
