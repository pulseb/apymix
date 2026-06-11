# Modèle de données — APYMIX

## Vue d'ensemble

```
┌────────────────┐
│  apymix_apps      │       (apymix/apps — registre des applications)
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
│    User      │       (papi/auth — table partagée)
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

## AppEntry (`papi_apps`)

Registre des applications découvertes. Synchronisé automatiquement au démarrage.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | INTEGER | PK, auto | Identifiant unique |
| `name` | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Nom de l'application (ex : `eve`) |
| `app_type` | VARCHAR(10) | NOT NULL | `api` ou `front` |
| `prefix` | VARCHAR(100) | NOT NULL | Préfixe URL (ex : `/eve`) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active' | `active`, `disabled`, `unavailable` |
| `docs_enabled` | BOOLEAN | NOT NULL, DEFAULT true | Afficher la doc OpenAPI |
| `description` | VARCHAR(500) | DEFAULT '' | Description de l'application |
| `version` | VARCHAR(20) | DEFAULT '0.0.0' | Version de l'application |
| `last_seen_at` | DATETIME | NOT NULL | Dernière découverte au démarrage |
| `created_at` | DATETIME | NOT NULL, auto | Date de création |
| `updated_at` | DATETIME | NOT NULL, auto | Dernière modification |

---

## User (`users`)

Utilisateurs authentifiés (administrateurs). Table partagée entre toutes les APIs.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | UUID | PK, auto | Identifiant unique |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Email de connexion |
| `password_hash` | VARCHAR(255) | NOT NULL | Hash bcrypt du mot de passe |
| `role` | VARCHAR(50) | NOT NULL, DEFAULT 'admin' | Rôle utilisateur |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Compte actif |
| `api_token` | VARCHAR(64) | UNIQUE, NULL, INDEX | Token statique pour intégrations |
| `created_at` | DATETIME | NOT NULL, auto | Date de création |
| `updated_at` | DATETIME | NOT NULL, auto | Dernière modification |

---

## Champs automatiques (TimestampMixin)

Toutes les entités héritent d'un mixin qui fournit `created_at` et `updated_at` :

```python
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BaseUUIDModel(TimestampMixin):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
```

### Exemple de modèle AppEntry

```python
# papi/apps/models.py
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
    __tablename__ = "papi_apps"
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
