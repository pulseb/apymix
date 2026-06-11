"""Routes d'authentification — login, refresh, user info, api_token."""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from apymix.auth.jwt import create_access_token, create_refresh_token, decode_token
from apymix.auth.models import LoginRequest, TokenRefreshRequest, TokenResponse, User, UserAccount, UserRead
from apymix.auth.security import get_current_user, verify_password
from apymix.config import get_settings
from apymix.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_token_data(user: User) -> dict:
    return {"sub": str(user.id), "email": user.email, "roles": user.roles}


async def _get_user_read_with_api_token(user: User, db: AsyncSession) -> UserRead:
    """Construit un UserRead avec le champ api_token renseigné si présent."""
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


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authentification par email + mot de passe → JWT."""
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
            detail="Email ou mot de passe incorrect",
        )

    user = await db.get(User, account.user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé ou supprimé",
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
    """OAuth2 password flow pour Swagger UI — le champ 'username' correspond à l'email."""
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
            detail="Email ou mot de passe incorrect",
        )

    user = await db.get(User, account.user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé ou supprimé",
        )

    settings = get_settings()
    return {
        "access_token": create_access_token(_build_token_data(user)),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    """Renouvellement du token d'accès via refresh token."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token type invalide")
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")

    result = await db.execute(select(User).where(User.email == payload.get("email")))
    user = result.scalar_one_or_none()

    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou désactivé")

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
    """Retourne les informations de l'utilisateur connecté."""
    return await _get_user_read_with_api_token(current_user, db)


@router.post("/me/token", response_model=UserRead)
async def generate_api_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Génère (ou régénère) un api_token statique pour l'utilisateur connecté.

    Ce token peut être utilisé comme Bearer token à la place du JWT
    pour des intégrations simples (scripts, frontends légers).
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
    """Révoque l'api_token de l'utilisateur connecté."""
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
