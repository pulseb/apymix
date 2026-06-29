"""Security — password hashing and FastAPI authentication dependencies."""

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
    """Verifies a plain-text password against a hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """Hashes a password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extracts and verifies the user.

    Supports two Bearer authentication modes:
    1. Standard JWT (access token from /auth/login)
    2. Static token (UserAccount provider="api_token", for simple integrations)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    token = credentials.credentials

    # --- Attempt 1: JWT ---
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
        pass  # Not a valid JWT → try the static token

    # --- Attempt 2: static api_token ---
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
