"""Authentication routes — email/password with JWT tokens."""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db_session
from app.db.models import UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()
# Optional bearer (for /me which we want to accept unauth'd with 401 that
# the client can treat as "logged out" without a raw scheme error).
bearer_optional = HTTPBearer(auto_error=False)

TRIAL_DAYS = 7


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    plan: Optional[Literal["free", "pro"]] = "free"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user: dict


class MeResponse(BaseModel):
    """Rich user blob consumed by useAuth() / AuthState on the client.

    Shape intentionally matches `frontend/src/lib/trial.ts AuthState` plus
    the preferences/profile blobs used by Settings and Welcome, so the
    client can hydrate everything from one round-trip.
    """

    id: int
    email: Optional[str]
    plan: Literal["free", "pro"]
    trial_ends_at: Optional[datetime] = None
    card_attached: bool = False
    stripe_customer_id: Optional[str] = None
    preferences: Optional[dict[str, Any]] = None
    profile: Optional[dict[str, Any]] = None
    created_at: datetime


def _create_token(user_id: int) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def _user_dict(user: UserProfile) -> dict:
    """Compact user payload embedded in /auth/{register,login,google} responses.

    Matches the fields the client needs to build its initial AuthState blob.
    Prefer /auth/me for fully-hydrated reads.
    """
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        "card_attached": bool(user.card_attached),
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
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(UserProfile).where(UserProfile.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    plan = body.plan or "free"
    trial_ends_at: Optional[datetime] = None
    if plan == "pro":
        # 7-day no-card trial (matches client trial.ts copy). Stripe is
        # wired separately in L6 — until then the user is "pro" for the
        # trial window and auto-downgrades on the first /auth/me call
        # past trial_ends_at.
        trial_ends_at = datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)

    user = UserProfile(
        email=body.email,
        password_hash=_hash_password(body.password),
        plan=plan,
        trial_ends_at=trial_ends_at,
        card_attached=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(token=_create_token(user.id), user=_user_dict(user))


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(UserProfile).where(UserProfile.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return AuthResponse(token=_create_token(user.id), user=_user_dict(user))


async def _maybe_auto_downgrade(
    user: UserProfile, db: AsyncSession
) -> UserProfile:
    """If the user is on a Pro trial that has expired without a card,
    downgrade them to Free on this very request. Single source of truth
    for the trial lifecycle (matches client trial.ts semantics).
    """
    if user.plan != "pro":
        return user
    if user.card_attached:
        return user
    if not user.trial_ends_at:
        return user
    end = user.trial_ends_at
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end > datetime.now(timezone.utc):
        return user
    user.plan = "free"
    user.trial_ends_at = None
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=MeResponse)
async def me(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    user = await _maybe_auto_downgrade(user, db)
    return MeResponse(
        id=user.id,
        email=user.email,
        plan=user.plan if user.plan in ("free", "pro") else "free",
        trial_ends_at=user.trial_ends_at,
        card_attached=bool(user.card_attached),
        stripe_customer_id=user.stripe_customer_id,
        preferences=user.preferences,
        profile=user.profile,
        created_at=user.created_at,
    )


class ProfileUpdate(BaseModel):
    """Shape written by Welcome.tsx on onboarding completion.

    All fields optional so partial updates (Settings profile edits) work.
    """

    type: Optional[str] = None
    experience: Optional[str] = None
    reaction: Optional[str] = None
    budget: Optional[str] = None
    suggested_sizing: Optional[str] = None


@router.put("/me/profile", response_model=MeResponse)
async def update_profile(
    body: ProfileUpdate,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    patch = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    current = user.profile or {}
    user.profile = {**current, **patch}
    await db.commit()
    await db.refresh(user)
    return MeResponse(
        id=user.id,
        email=user.email,
        plan=user.plan if user.plan in ("free", "pro") else "free",
        trial_ends_at=user.trial_ends_at,
        card_attached=bool(user.card_attached),
        stripe_customer_id=user.stripe_customer_id,
        preferences=user.preferences,
        profile=user.profile,
        created_at=user.created_at,
    )


class PreferencesUpdate(BaseModel):
    """Written by Settings.tsx — currency, language, notif toggles, etc."""

    currency: Optional[Literal["USD", "EUR"]] = None
    language: Optional[Literal["fr", "en"]] = None
    exchange_rate: Optional[float] = None
    notif_email: Optional[bool] = None
    notif_push: Optional[bool] = None
    notif_telegram: Optional[bool] = None


@router.put("/me/preferences", response_model=MeResponse)
async def update_preferences(
    body: PreferencesUpdate,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    patch = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    current = user.preferences or {}
    user.preferences = {**current, **patch}
    await db.commit()
    await db.refresh(user)
    return MeResponse(
        id=user.id,
        email=user.email,
        plan=user.plan if user.plan in ("free", "pro") else "free",
        trial_ends_at=user.trial_ends_at,
        card_attached=bool(user.card_attached),
        stripe_customer_id=user.stripe_customer_id,
        preferences=user.preferences,
        profile=user.profile,
        created_at=user.created_at,
    )


class GoogleTokenRequest(BaseModel):
    """Google Identity Services credential (JWT) from the client."""

    credential: str = Field(min_length=100, max_length=12000)


@router.post("/google", response_model=AuthResponse)
async def login_google(body: GoogleTokenRequest, db: AsyncSession = Depends(get_db_session)):
    """Verify Google ID token and issue app JWT (create user if new)."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        idinfo = google_id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {e!s}",
        ) from e

    if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")

    email = idinfo.get("email")
    if not email or not isinstance(email, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return an email",
        )
    if not idinfo.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google email is not verified",
        )

    email_norm = email.strip().lower()
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.email.isnot(None),
            func.lower(UserProfile.email) == email_norm,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = UserProfile(
            email=email_norm,
            password_hash=None,
            plan="free",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Same email as existing account (password or prior OAuth) — issue token
        pass

    return AuthResponse(token=_create_token(user.id), user=_user_dict(user))


@router.post("/logout")
async def logout():
    return {"ok": True}
