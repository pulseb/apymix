"""JWT token management."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from apymix.config import get_settings

# Active secret — initialized at startup via init_jwt_secret() in app.py lifespan.
_jwt_secret: str | None = None


def init_jwt_secret(secret: str) -> None:
    """Initializes the active JWT secret. Called once during the lifespan."""
    global _jwt_secret
    _jwt_secret = secret


def _get_secret() -> str:
    """Returns the active secret initialized by the lifespan.

    Raises an explicit error if called before initialization (should not happen).
    """
    if _jwt_secret is None:
        raise RuntimeError("JWT secret not initialized — get_or_create_jwt_secret() must be called during lifespan")
    return _jwt_secret


def create_access_token(data: dict) -> str:
    """Creates a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, _get_secret(), algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    """Creates a JWT refresh token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, _get_secret(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decodes and verifies a JWT token. Raises an exception if invalid."""
    settings = get_settings()
    return jwt.decode(token, _get_secret(), algorithms=[settings.jwt_algorithm])
