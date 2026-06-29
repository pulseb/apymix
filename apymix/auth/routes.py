"""Authentication routes — login, refresh, user info, api_token."""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from apymix.auth.jwt import create_access_token, create_refresh_token, decode_token
from apymix.auth.models import (
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
    User,
    UserAccount,
    UserRead,
)
from apymix.auth.security import get_current_user, get_password_hash, verify_password
from apymix.config import get_settings
from apymix.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_token_data(user: User) -> dict:
    return {"sub": str(user.id), "email": user.email, "roles": user.roles}


async def _get_user_read_with_api_token(user: User, db: AsyncSession) -> UserRead:
    """Builds a UserRead with the api_token field populated when present."""
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == user.id,
            UserAccount.provider == "api_token",
        )
    )
    account = result.scalar_one_or_none()
    data = UserRead.model_validate(user, from_attributes=True)
    data.api_token = account.provider_user_id if account else None
    return data


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Public registration: create a user with a password account, then auto-login."""
    email = body.email.strip().lower()

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(email=email, display_name=body.display_name, status="active")
    db.add(user)
    await db.flush()  # obtain user.id

    account = UserAccount(
        user_id=user.id,
        provider="password",
        provider_user_id=email,
        password_hash=get_password_hash(body.password),
    )
    db.add(account)
    await db.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(_build_token_data(user)),
        refresh_token=create_refresh_token(_build_token_data(user)),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Email + password authentication → JWT."""
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.provider == "password",
            UserAccount.provider_user_id == body.email,
        )
    )
    account = result.scalar_one_or_none()

    if account is None or not verify_password(body.password, account.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user = await db.get(User, account.user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled or deleted",
        )

    user.last_login_at = _utcnow()
    db.add(user)
    await db.commit()

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(_build_token_data(user)),
        refresh_token=create_refresh_token(_build_token_data(user)),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/token", include_in_schema=False)
async def login_oauth2_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 password flow for Swagger UI — the 'username' field corresponds to the email."""
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.provider == "password",
            UserAccount.provider_user_id == form.username,
        )
    )
    account = result.scalar_one_or_none()

    if account is None or not verify_password(form.password, account.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user = await db.get(User, account.user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled or deleted",
        )

    settings = get_settings()  # noqa: F841 — used via dict spread below
    return {
        "access_token": create_access_token(_build_token_data(user)),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh of the access token via a refresh token."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token invalid or expired")

    result = await db.execute(select(User).where(User.email == payload.get("email")))
    user = result.scalar_one_or_none()

    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="User not found or disabled")

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(_build_token_data(user)),
        refresh_token=create_refresh_token(_build_token_data(user)),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns the information of the logged-in user."""
    return await _get_user_read_with_api_token(current_user, db)


@router.post("/me/token", response_model=UserRead)
async def generate_api_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generates (or regenerates) a static api_token for the logged-in user.

    This token can be used as a Bearer token instead of a JWT
    for simple integrations (scripts, lightweight frontends).
    """
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == current_user.id,
            UserAccount.provider == "api_token",
        )
    )
    account = result.scalar_one_or_none()
    token = secrets.token_urlsafe(48)

    if account is None:
        account = UserAccount(
            user_id=current_user.id,
            provider="api_token",
            provider_user_id=token,
        )
        db.add(account)
    else:
        account.provider_user_id = token
        db.add(account)

    await db.commit()
    data = UserRead.model_validate(current_user, from_attributes=True)
    data.api_token = token
    return data


@router.delete("/me/token", response_model=UserRead)
async def revoke_api_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revokes the api_token of the logged-in user."""
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == current_user.id,
            UserAccount.provider == "api_token",
        )
    )
    account = result.scalar_one_or_none()
    if account:
        await db.delete(account)
        await db.commit()

    data = UserRead.model_validate(current_user, from_attributes=True)
    data.api_token = None
    return data
