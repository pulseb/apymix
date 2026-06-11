import os
import uuid
from datetime import datetime, timezone

from sqlmodel import SQLModel, Field


# Préfixe des tables système d'Apymix. Configurable via AMX_TABLE_PREFIX.
# Prod avec tables existantes papi_* : AMX_TABLE_PREFIX=papi_
_TABLE_PREFIX: str = os.environ.get("AMX_TABLE_PREFIX", "amx_")


def _utcnow() -> datetime:
    """Retourne l'heure UTC naive (sans tzinfo), compatible TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin(SQLModel):
    """Mixin pour les champs de date automatiques."""

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class BaseUUIDModel(TimestampMixin):
    """Base model avec UUID et timestamps automatiques."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class AmxConfig(SQLModel, table=True):
    """Stockage clé/valeur de configuration interne Apymix (ex : jwt_secret)."""

    __tablename__ = f"{_TABLE_PREFIX}config"

    key: str = Field(primary_key=True)
    value: str


class Redirect(SQLModel, table=True):
    """Règles de redirection HTTP gérées via l'admin.

    Priorité d'évaluation : host+path > host seul > path seul.
    Si `host` est vide, la règle s'applique à tous les hosts.
    Si `path_prefix` est vide, la règle s'applique à tous les chemins du host.
    """

    __tablename__ = f"{_TABLE_PREFIX}redirects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    host: str | None = Field(default=None, max_length=160, description="Host source (ex: old.example.com). Vide = tous.")
    path_prefix: str | None = Field(default=None, max_length=160, description="Préfixe de chemin source (ex: /old). Vide = tous.")
    destination: str = Field(max_length=160, description="URL ou chemin cible (ex: https://new.example.com ou /new-path)")
    status_code: int = Field(default=302, description="Code HTTP : 301 (permanent) ou 302 (temporaire)")
    enabled: bool = Field(default=True)
