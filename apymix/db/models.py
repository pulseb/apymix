import os
import uuid
from datetime import datetime, timezone

from sqlmodel import SQLModel, Field


# Apymix system tables prefix. Configurable via AMX_TABLE_PREFIX.
# Prod with existing papi_* tables: AMX_TABLE_PREFIX=papi_
_TABLE_PREFIX: str = os.environ.get("AMX_TABLE_PREFIX", "amx_")


def _utcnow() -> datetime:
    """Returns naive UTC time (no tzinfo), compatible with TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin(SQLModel):
    """Mixin for automatic date fields."""

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class BaseUUIDModel(TimestampMixin):
    """Base model with UUID and automatic timestamps."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class AmxConfig(SQLModel, table=True):
    """Internal Apymix key/value configuration storage (e.g. jwt_secret)."""

    __tablename__ = f"{_TABLE_PREFIX}config"

    key: str = Field(primary_key=True)
    value: str


class Redirect(SQLModel, table=True):
    """HTTP redirect rules managed via the admin.

    Evaluation priority: host+path > host only > path only.
    If `host` is empty, the rule applies to all hosts.
    If `path_prefix` is empty, the rule applies to all paths on the host.
    """

    __tablename__ = f"{_TABLE_PREFIX}redirects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    host: str | None = Field(default=None, max_length=160, description="Source host (e.g. old.example.com). Empty = all.")
    path_prefix: str | None = Field(default=None, max_length=160, description="Source path prefix (e.g. /old). Empty = all.")
    destination: str = Field(max_length=160, description="Target URL or path (e.g. https://new.example.com or /new-path)")
    status_code: int = Field(default=302, description="HTTP code: 301 (permanent) or 302 (temporary)")
    enabled: bool = Field(default=True)
