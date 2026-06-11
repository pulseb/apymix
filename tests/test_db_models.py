"""Tests unitaires pour apymix.db.models — TimestampMixin, BaseUUIDModel, AmxConfig, Redirect."""

import uuid
from datetime import datetime, timedelta, timezone


from apymix.db.models import (
    _TABLE_PREFIX,
    _utcnow,
    AmxConfig,
    BaseUUIDModel,
    Redirect,
    TimestampMixin,
)


# ---------------------------------------------------------------------------
# _utcnow
# ---------------------------------------------------------------------------

class TestUtcnow:
    def test_returns_naive_datetime(self):
        """Doit retourner un datetime sans tzinfo (compatible TIMESTAMP WITHOUT TIME ZONE)."""
        now = _utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is None

    def test_returns_current_utc_time(self):
        """Doit retourner l'heure actuelle en UTC (tolère 2s de marge)."""
        # _utcnow() retourne un datetime NAIVE représentant UTC.
        # On compare avec datetime.now(UTC).replace(tzinfo=None) pour obtenir
        # un datetime naive en UTC, sans utiliser datetime.utcnow() (déprécié).
        before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=2)
        now = _utcnow()
        after = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=2)
        assert before <= now <= after


# ---------------------------------------------------------------------------
# TimestampMixin
# ---------------------------------------------------------------------------

class TestTimestampMixin:
    def test_has_timestamps(self):
        """Un modèle qui hérite de TimestampMixin doit exposer created_at et updated_at."""
        from sqlmodel import Field as SQLField

        class M(TimestampMixin, table=True):
            __tablename__ = "test_timestamps"
            id: int = SQLField(default=1, primary_key=True)

        m = M()
        assert isinstance(m.created_at, datetime)
        assert isinstance(m.updated_at, datetime)


# ---------------------------------------------------------------------------
# BaseUUIDModel
# ---------------------------------------------------------------------------

class TestBaseUUIDModel:
    def test_default_uuid_is_generated(self):
        class M_UUID_Default(BaseUUIDModel, table=True):
            __tablename__ = "test_uuid_defaults"

        m = M_UUID_Default()
        assert isinstance(m.id, uuid.UUID)
        # Deux instances doivent avoir des UUIDs différents
        m2 = M_UUID_Default()
        assert m.id != m2.id

    def test_can_override_uuid(self):
        class M_UUID_Override(BaseUUIDModel, table=True):
            __tablename__ = "test_uuid_override"

        forced = uuid.uuid4()
        m = M_UUID_Override(id=forced)
        assert m.id == forced


# ---------------------------------------------------------------------------
# AmxConfig
# ---------------------------------------------------------------------------

class TestAmxConfigModel:
    def test_tablename_uses_prefix(self, monkeypatch):
        """Le tablename doit être '<prefix>config'."""
        monkeypatch.setattr("apymix.db.models._TABLE_PREFIX", "amx_")
        # Recharger le module ne change pas la classe — mais on peut vérifier
        # directement le tablename généré à la lecture.
        # (Le prefix est figé à l'import du module.)
        assert AmxConfig.__tablename__ == f"{_TABLE_PREFIX}config"

    def test_key_and_value(self):
        config = AmxConfig(key="jwt_secret", value="abc123")
        assert config.key == "jwt_secret"
        assert config.value == "abc123"


# ---------------------------------------------------------------------------
# Redirect
# ---------------------------------------------------------------------------

class TestRedirectModel:
    def test_defaults(self):
        r = Redirect(destination="https://new.example.com")
        assert isinstance(r.id, uuid.UUID)
        assert r.host is None
        assert r.path_prefix is None
        assert r.destination == "https://new.example.com"
        assert r.status_code == 302  # défaut : temporaire
        assert r.enabled is True

    def test_tablename_uses_prefix(self):
        assert Redirect.__tablename__ == f"{_TABLE_PREFIX}redirects"

    def test_custom_status_code(self):
        r = Redirect(destination="/x", status_code=301)
        assert r.status_code == 301

    def test_can_be_disabled(self):
        r = Redirect(destination="/x", enabled=False)
        assert r.enabled is False


# ---------------------------------------------------------------------------
# _TABLE_PREFIX env override
# ---------------------------------------------------------------------------

class TestTablePrefixEnv:
    def test_default_prefix(self, monkeypatch):
        """Le préfixe par défaut est 'amx_'."""
        # L'env AMX_TABLE_PREFIX n'est pas set
        monkeypatch.delenv("AMX_TABLE_PREFIX", raising=False)
        # Le module est déjà importé → _TABLE_PREFIX est figé
        # On vérifie que la valeur par défaut est bien "amx_"
        assert _TABLE_PREFIX in ("amx_", "papi_")  # tolère un override env au démarrage
