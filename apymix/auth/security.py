"""Sécurité — hash de mots de passe et dépendances d'authentification FastAPI."""

import uuid

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from apymix.auth.jwt import decode_token
from apymix.auth.models import User, UserAccount
from apymix.db.session import get_db

security_scheme = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe en clair contre un hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """Hashe un mot de passe."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dépendance FastAPI : extrait et vérifie l'utilisateur.

    Supporte deux modes d'authentification Bearer :
    1. JWT classique (access token issu de /auth/login)
    2. Token statique (UserAccount provider="api_token", pour intégrations simples)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
    )
    token = credentials.credentials

    # --- Tentative 1 : JWT ---
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user = await db.get(User, uuid.UUID(user_id))
        if user is not None and user.status == "active":
            return user
        raise credentials_exception
    except JWTError:
        pass  # Ce n'est pas un JWT valide → on essaie le token statique

    # --- Tentative 2 : api_token statique ---
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.provider == "api_token",
            UserAccount.provider_user_id == token,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise credentials_exception

    user = await db.get(User, account.user_id)
    if user is None or user.status != "active":
        raise credentials_exception

    return user
