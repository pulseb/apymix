"""Tests unitaires pour apymix.db.config_store — gestion de la config en DB."""

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from apymix.db import config_store
from apymix.db.models import AmxConfig


# ---------------------------------------------------------------------------
# get_or_create_jwt_secret
# ---------------------------------------------------------------------------

class TestGetOrCreateJwtSecret:
    async def test_env_var_takes_precedence(self, monkeypatch):
        """Si JWT_SECRET est défini en env, on l'utilise directement, sans toucher la DB."""
        monkeypatch.setenv("JWT_SECRET", "env-secret-123")

        # Session mockée — ne doit jamais être appelée
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock()

        secret = await config_store.get_or_create_jwt_secret(session)
        assert secret == "env-secret-123"
        # Aucune lecture DB, aucun commit
        session.get.assert_not_called()
        session.add.assert_not_called()
        session.commit.assert_not_called()

    async def test_loads_from_db_when_present(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)

        existing = AmxConfig(key="jwt_secret", value="db-secret-xyz")
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(return_value=existing)

        secret = await config_store.get_or_create_jwt_secret(session)
        assert secret == "db-secret-xyz"
        # On n'a pas généré de nouveau secret
        session.add.assert_not_called()

    async def test_generates_and_persists_when_absent(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)

        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(return_value=None)  # pas de config en DB
        session.add = MagicMock()
        session.commit = AsyncMock()

        secret = await config_store.get_or_create_jwt_secret(session)
        # Nouveau secret : 64 caractères hexadécimaux
        assert len(secret) == 64
        assert all(c in "0123456789abcdef" for c in secret)
        # Le secret a été ajouté à la session et persisté
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, AmxConfig)
        assert added.key == "jwt_secret"
        assert added.value == secret
        session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_verbose_errors
# ---------------------------------------------------------------------------

class TestGetVerboseErrors:
    async def test_returns_false_when_absent(self):
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(return_value=None)
        assert await config_store.get_verbose_errors(session) is False

    async def test_returns_true_when_true_string(self):
        config = AmxConfig(key="verbose_errors", value="true")
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(return_value=config)
        assert await config_store.get_verbose_errors(session) is True

    async def test_returns_false_when_false_string(self):
        config = AmxConfig(key="verbose_errors", value="false")
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(return_value=config)
        assert await config_store.get_verbose_errors(session) is False

    async def test_strips_whitespace(self):
        config = AmxConfig(key="verbose_errors", value="  true  ")
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(return_value=config)
        assert await config_store.get_verbose_errors(session) is True

    async def test_case_insensitive(self):
        config = AmxConfig(key="verbose_errors", value="TRUE")
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(return_value=config)
        assert await config_store.get_verbose_errors(session) is True
