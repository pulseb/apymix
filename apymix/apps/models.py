"""Modèle AppEntry — registre des applications découvertes par PulseApps."""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel

from apymix.db.models import TimestampMixin, _utcnow, _TABLE_PREFIX


class AppStatus(str, Enum):
    """Statuts possibles d'une application."""

    active = "active"
    disabled = "disabled"
    unavailable = "unavailable"


class AppType(str, Enum):
    """Types d'application."""

    api = "api"
    front = "front"


class AppEntry(TimestampMixin, table=True):
    """Table de registre des applications découvertes.

    À chaque démarrage, le système scanne */amx.yaml puis synchronise
    cette table : les nouvelles apps sont insérées en 'active', celles qui
    ont disparu passent en 'unavailable', celles désactivées manuellement
    restent en 'disabled'.
    """

    __tablename__ = f"{_TABLE_PREFIX}apps"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    app_type: str = Field(max_length=10)  # "api" ou "front"
    prefix: str = Field(max_length=100)
    status: str = Field(default=AppStatus.active.value, max_length=20)
    docs_enabled: bool = Field(default=True)
    description: str = Field(default="", max_length=500)
    version: str = Field(default="0.0.0", max_length=20)
    last_seen_at: datetime = Field(default_factory=_utcnow)


class AppEntryRead(SQLModel):
    """Schéma de lecture d'une AppEntry."""

    id: uuid.UUID
    name: str
    app_type: str
    prefix: str
    status: str
    docs_enabled: bool
    description: str
    version: str
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
