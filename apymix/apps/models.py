"""AppEntry model — registry of applications discovered by PulseApps."""

import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from apymix.db.models import TimestampMixin, _utcnow, _TABLE_PREFIX


class AppStatus(str, Enum):
    """Possible application statuses."""

    active = "active"
    disabled = "disabled"
    unavailable = "unavailable"


class AppType(str, Enum):
    """Application types."""

    api = "api"
    front = "front"


class AppEntry(TimestampMixin, table=True):
    """Registry table for discovered applications.

    At every startup, the system scans */amx.yaml and then syncs this table:
    new apps are inserted with status 'active', missing ones are switched
    to 'unavailable', and those manually disabled stay at 'disabled'.
    """

    __tablename__ = f"{_TABLE_PREFIX}apps"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    app_type: str = Field(max_length=10)  # "api" or "front"
    prefix: str = Field(max_length=100)
    status: str = Field(default=AppStatus.active.value, max_length=20)
    docs_enabled: bool = Field(default=True)
    description: str = Field(default="", max_length=500)
    version: str = Field(default="0.0.0", max_length=20)
    last_seen_at: datetime = Field(default_factory=_utcnow)


class AppEntryRead(SQLModel):
    """Read schema for an AppEntry."""

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
