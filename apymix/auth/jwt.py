"""Gestion des tokens JWT."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from apymix.config import get_settings

# Secret actif — initialisé au démarrage via init_jwt_secret() dans app.py lifespan.
_jwt_secret: str | None = None


def init_jwt_secret(secret: str) -> None:
    """Initialise le secret JWT actif. Appelé une seule fois dans le lifespan."""
    global _jwt_secret
    _jwt_secret = secret


def _get_secret() -> str:
    """Retourne le secret actif initialisé par le lifespan.

    Lève une erreur explicite si appelé avant l'initialisation (ne devrait pas arriver).
    """
    if _jwt_secret is None:
        raise RuntimeError("JWT secret not initialized — get_or_create_jwt_secret() must be called during lifespan")
    return _jwt_secret


def create_access_token(data: dict) -> str:
    """Crée un access token JWT."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, _get_secret(), algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    """Crée un refresh token JWT."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, _get_secret(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Décode et vérifie un token JWT. Lève une exception si invalide."""
    settings = get_settings()
    return jwt.decode(token, _get_secret(), algorithms=[settings.jwt_algorithm])
