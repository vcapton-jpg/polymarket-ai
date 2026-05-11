"""Authentication routes — email/password with JWT tokens."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db_session
from app.db.models import UserLimits, UserProfile

logger = logging.getLogger(__name__)

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
    plan: Literal["free", "pro"] | None = "free"
    # Legal-PR-1 B2 — frontend collected the 18+ checkbox in Signup.tsx but
    # never sent it. Now required; the backend mirrors it into UserLimits
    # so the order-time `age_not_confirmed` gate at OrderForm.tsx actually
    # has a True flag to read.
    age_confirmed_18: bool = False
    # Legal-PR-1 B3 — ISO 3166-1 alpha-2. Required so we can refuse signup
    # from blocklisted jurisdictions (CFTC + sanctions). The endpoint
    # cross-checks against `cf-ipcountry` if present.
    country_residence: str | None = Field(default=None, min_length=2, max_length=2)


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
    email: str | None
    plan: Literal["free", "pro"]
    trial_ends_at: datetime | None = None
    card_attached: bool = False
    stripe_customer_id: str | None = None
    preferences: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    created_at: datetime


def _create_token(user_id: int) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(days=TOKEN_EXPIRE_DAYS),
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


def _normalised_blocked_countries(raw: str) -> set[str]:
    """Split the comma-separated env value into an upper-cased set."""
    return {c.strip().upper() for c in raw.split(",") if c.strip()}


def _enforce_geo_restriction(
    declared_country: str | None,
    request: Request,
) -> str:
    """Validate the user's declared country and, if available, cross-check
    against `cf-ipcountry`. Returns the normalised country code (uppercase
    ISO 3166-1 alpha-2). Raises HTTPException(451) on a blocked country.

    `cf-ipcountry` is set by Cloudflare's edge. If absent we trust the
    declared value alone — that's worse but acceptable for an MVP and we
    log loud so an operator notices when traffic isn't routed through
    Cloudflare yet. A user who declares an allowed country while their
    IP says otherwise is rejected — VPN evasion is a feature only the
    user can claim, not the platform.
    """
    settings = get_settings()
    blocked = _normalised_blocked_countries(settings.signup_blocked_countries)
    if not declared_country:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="country_residence is required at signup",
        )
    declared = declared_country.upper()
    if declared in blocked:
        # 451 Unavailable For Legal Reasons is the textbook code for this.
        raise HTTPException(
            status_code=451,
            detail=f"Sign-up is not available in {declared}",
        )

    cf_country = (request.headers.get("cf-ipcountry") or "").upper()
    if cf_country and cf_country in blocked:
        logger.warning(
            "Geo-block: cf-ipcountry=%s declared=%s — refusing register",
            cf_country, declared,
        )
        raise HTTPException(
            status_code=451,
            detail="Sign-up is not available from your network location",
        )
    if not cf_country:
        # Operator visibility — we want to know when the edge isn't
        # passing the country through. Not a fatal error.
        logger.info(
            "Geo-block: cf-ipcountry header missing; trusting declared=%s",
            declared,
        )

    return declared


@router.post("/register", response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    # Legal-PR-1 B2 — refuse registrations that don't carry the 18+
    # confirmation. Mirrors the explicit checkbox in Signup.tsx so the
    # backend cooloff/age gate at OrderForm.tsx can rely on the
    # UserLimits.age_confirmed_18 flag we set below.
    if not body.age_confirmed_18:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="age_confirmed_18 must be true",
        )

    # Legal-PR-1 B3 — geo gate (declared + cf-ipcountry).
    country = _enforce_geo_restriction(body.country_residence, request)

    result = await db.execute(select(UserProfile).where(UserProfile.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    plan = body.plan or "free"
    trial_ends_at: datetime | None = None
    if plan == "pro":
        # 7-day no-card trial (matches client trial.ts copy). Stripe is
        # wired separately in L6 — until then the user is "pro" for the
        # trial window and auto-downgrades on the first /auth/me call
        # past trial_ends_at.
        trial_ends_at = datetime.now(UTC) + timedelta(days=TRIAL_DAYS)

    user = UserProfile(
        email=body.email,
        password_hash=_hash_password(body.password),
        plan=plan,
        trial_ends_at=trial_ends_at,
        card_attached=False,
        country_residence=country,
    )
    db.add(user)
    await db.flush()  # populates user.id for the FK below

    # Legal-PR-1 B2 — persist age_confirmed_18 on the row that the
    # order-time gate actually reads. Pre-fix we wrote the value nowhere;
    # post-fix the gate has a real authoritative source and the cooloff
    # mechanism in `register_trade_result` is meaningful.
    db.add(UserLimits(user_id=user.id, age_confirmed_18=True))
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
        end = end.replace(tzinfo=UTC)
    if end > datetime.now(UTC):
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

    type: str | None = None
    experience: str | None = None
    reaction: str | None = None
    budget: str | None = None
    suggested_sizing: str | None = None


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

    currency: Literal["USD", "EUR"] | None = None
    language: Literal["fr", "en"] | None = None
    exchange_rate: float | None = None
    notif_email: bool | None = None
    notif_push: bool | None = None
    notif_telegram: bool | None = None


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
        # P2-1: do NOT echo `str(e)` back to the client. Google's
        # `verify_oauth2_token` raises ValueError with the verbatim
        # internal reason (clock skew, kid mismatch, JWK fetch URL,
        # etc.) — useful for an operator log, never for an unauth'd
        # caller. Log loud, return generic.
        logger.warning("Google OAuth token verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Hard-delete the calling user's account (RGPD Art. 17, Legal-PR-1 B7).

    Pre-fix the frontend modal at `ConfirmDeleteAccountModal.tsx` only
    cleared `localStorage` — the row stayed in Postgres and the user's
    "Right to Erasure" was effectively a lie. This endpoint deletes the
    `user_profiles` row; every related table (`portfolios`, `positions`,
    `orders`, `user_limits`, `paper_positions`, `onboarding_progress`,
    `quiz_attempts`, `outcome_views`, `daily_briefs`) declares
    `ondelete=CASCADE`, so the FK fan-out is handled by Postgres in a
    single transaction.

    No "soft-delete" / 30-day grace window: a hard delete is what RGPD
    actually demands. Stripe customers, if any, are out of scope here —
    Stripe billing cleanup happens via the customer-portal flow before
    the user lands on this endpoint.
    """
    await db.delete(user)
    await db.commit()
    # 204 — body intentionally empty; the client should clear its own
    # token/auth state (logout flow) immediately after.
    return None
