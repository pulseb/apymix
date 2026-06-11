"""Tests unitaires pour apymix.auth.jwt — création et validation des tokens JWT."""


import pytest
from jose import JWTError

from apymix.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    init_jwt_secret,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_jwt_secret():
    """Réinitialise le secret avant chaque test."""
    init_jwt_secret("test-secret-for-unit-tests-only")
    yield
    init_jwt_secret("")  # reset pour le suivant


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token({"sub": "user-123", "email": "alice@example.com"})
        assert isinstance(token, str)
        assert len(token) > 50  # JWT typique

        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "alice@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_token_has_correct_type(self):
        token = create_access_token({"sub": "user-1"})
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_invalid_token_raises(self):
        with pytest.raises(JWTError):
            decode_token("this.is.not.a.valid.jwt")

    def test_wrong_secret_raises(self):
        token = create_access_token({"sub": "user-1"})
        # Changer le secret après création → le token devient invalide
        init_jwt_secret("different-secret")
        with pytest.raises(JWTError):
            decode_token(token)


class TestRefreshToken:
    def test_create_and_decode(self):
        token = create_refresh_token({"sub": "user-456"})
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_refresh_token_has_longer_expiry(self):
        """Un refresh token doit vivre plus longtemps qu'un access token (en pratique)."""
        access = create_access_token({"sub": "u"})
        refresh = create_refresh_token({"sub": "u"})

        access_payload = decode_token(access)
        refresh_payload = decode_token(refresh)

        # Comparer les timestamps exp (datetime en secondes)
        assert refresh_payload["exp"] > access_payload["exp"]


class TestSecretNotInitialized:
    def test_raises_before_init(self):
        """Si init_jwt_secret n'a jamais été appelé, on lève une erreur explicite."""
        # Force l'état non initialisé (None) en patchant directement le module.
        # init_jwt_secret("") ne le fait pas car la garde est "is None".
        import apymix.auth.jwt as mod
        original = mod._jwt_secret
        mod._jwt_secret = None
        try:
            with pytest.raises(RuntimeError, match="JWT secret not initialized"):
                create_access_token({"sub": "u"})
        finally:
            mod._jwt_secret = original

    def test_decode_raises_before_init(self):
        """Le même garde-fou s'applique à decode_token."""
        import apymix.auth.jwt as mod
        original = mod._jwt_secret
        mod._jwt_secret = None
        try:
            with pytest.raises(RuntimeError, match="JWT secret not initialized"):
                decode_token("valid.looking.jwt")
        finally:
            mod._jwt_secret = original
