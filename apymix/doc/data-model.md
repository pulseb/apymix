# Data Model — APYMIX

## Overview

```
┌────────────────┐
│  amx_apps      │       (apymix/apps — application registry)
│────────────────│
│ id (PK, int)    │
│ name (unique)   │
│ app_type         │       "api" | "front"
│ prefix           │
│ status           │       "active" | "disabled" | "unavailable"
│ docs_enabled     │       true | false
│ description      │
│ version          │
│ last_seen_at     │
│ created_at       │
│ updated_at       │
└────────────────┘

┌─────────────┐
│    User      │       (apymix/auth — shared table)
│─────────────│
│ id (PK, UUID)│
│ email (unique)│
│ password_hash │
│ role          │
│ is_active     │
│ api_token     │       (unique, nullable)
│ created_at    │
│ updated_at    │
└─────────────┘
```

---

## AppEntry (`amx_apps`)

Registry of discovered applications. Synchronized automatically at startup.

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| `id` | INTEGER | PK, auto | Unique identifier |
| `name` | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Application name (e.g. `eve`) |
| `app_type` | VARCHAR(10) | NOT NULL | `api` or `front` |
| `prefix` | VARCHAR(100) | NOT NULL | URL prefix (e.g. `/eve`) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active' | `active`, `disabled`, `unavailable` |
| `docs_enabled` | BOOLEAN | NOT NULL, DEFAULT true | Show OpenAPI doc |
| `description` | VARCHAR(500) | DEFAULT '' | Application description |
| `version` | VARCHAR(20) | DEFAULT '0.0.0' | Application version |
| `last_seen_at` | DATETIME | NOT NULL | Last discovery at startup |
| `created_at` | DATETIME | NOT NULL, auto | Creation date |
| `updated_at` | DATETIME | NOT NULL, auto | Last modified |

---

## User (`users`)

Authenticated users (administrators). Table shared across all APIs.

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| `id` | UUID | PK, auto | Unique identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Login email |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt hash of the password |
| `role` | VARCHAR(50) | NOT NULL, DEFAULT 'admin' | User role |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Account active |
| `api_token` | VARCHAR(64) | UNIQUE, NULL, INDEX | Static token for integrations |
| `created_at` | DATETIME | NOT NULL, auto | Creation date |
| `updated_at` | DATETIME | NOT NULL, auto | Last modified |

---

## Automatic fields (TimestampMixin)

All entities inherit from a mixin that provides `created_at` and `updated_at`:

```python
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BaseUUIDModel(TimestampMixin):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
```

### Example AppEntry model

```python
# apymix/apps/models.py
from enum import Enum
from sqlmodel import SQLModel, Field

class AppStatus(str, Enum):
    active = "active"
    disabled = "disabled"
    unavailable = "unavailable"

class AppType(str, Enum):
    api = "api"
    front = "front"

class AppEntry(TimestampMixin, table=True):
    __tablename__ = "amx_apps"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    app_type: str = Field(max_length=10)
    prefix: str = Field(max_length=100)
    status: str = Field(default=AppStatus.active.value, max_length=20)
    docs_enabled: bool = Field(default=True)
    description: str = Field(default="", max_length=500)
    version: str = Field(default="0.0.0", max_length=20)
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```
