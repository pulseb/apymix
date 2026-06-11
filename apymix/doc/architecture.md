# Architecture technique — PAPI

## Vue d'ensemble

PAPI suit une architecture **modulaire en couches** avec **découverte automatique** des APIs :

```
┌─────────────────────────────────────────────────────┐
│                   Clients (navigateur)               │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────┐
│              Reverse Proxy (Traefik / Nginx)         │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 FastAPI Main App                     │
│  ┌─────────────┬─────────────┬─────────────────┐    │
│  │ Middleware   │ Auth (JWT)  │ Config           │    │
│  │ CORS, Logs  │             │ (env-based)      │    │
│  └─────────────┴─────────────┴─────────────────┘    │
│                                                      │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ Auto-Discovery ─ ─ ─ ─ ─ ─ ┐  │
│  │ scan apis/ → mount sub-apps → serve fronts/   │  │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘  │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │/api/     │  │/api/     │  │/api/     │  ...     │
│  │ eve      │  │ api-2    │  │ api-n    │          │
│  │ Sub-App  │  │ Sub-App  │  │ Sub-App  │          │
│  │ FastAPI  │  │ FastAPI  │  │ FastAPI  │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
└───────┼──────────────┼──────────────┼───────────────┘
        │              │              │
┌───────▼──────────────▼──────────────▼───────────────┐
│                 SQLModel (async)                      │
│          (SQLAlchemy 2.0 + Pydantic v2)              │
│  ┌─────────────────┐  ┌──────────────────────┐      │
│  │ SQLite (dev)     │  │ PostgreSQL (prod)     │      │
│  │ via aiosqlite    │  │ via asyncpg           │      │
│  └─────────────────┘  └──────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

## Principe fondamental : découplage total

Le module `papi/` est **complètement agnostique** des APIs métier et des frontends :

```
papi/     →  Ne connaît AUCUNE API métier. Zéro import depuis apis/ ou fronts/.
apis/     →  Importe depuis papi/ (auth, db, config). Indépendant des autres APIs.
fronts/   →  Consomme les APIs via HTTP. Aucune dépendance Python vers papi/ ou apis/.
```

> Cela permet de transformer `papi/` en package pip réutilisable pour d'autres projets.

## Routage par préfixes

Le routage utilise des préfixes pour éviter toute collision entre les composants :

| Préfixe | Usage | Exemples |
|---------|-------|----------|
| `/-/` | Routes système PAPI | `/-/docs`, `/-/admin`, `/-/health`, `/-/auth/*` |
| `/api/` | APIs métier | `/api/eve/events`, `/api/eve/events/{slug}/rsvps` |
| `/{name}` | Frontends (StaticFiles) | `/eve` (SPA Vue.js/Quasar) |
| `/` | Root minimaliste | Retourne `{"message": "PulseApps is running"}` (pas d'info sensible) |

> **Le dashboard ASCII art** (liens vers docs, admin, health) est sur `/-/` (non indexé).
> La page `/` est volontairement minimaliste pour ne pas exposer d'informations à un visiteur non autorisé.

### Constantes (dans `app.py`) :
```python
PAPI_PREFIX = "/-"     # Routes système
API_PREFIX = "/api"    # APIs métier
```

## Composants

### 1. Module `papi/` (cœur technique)

Le module technique réutilisable, potentiellement open-sourceable.

| Sous-module | Responsabilité |
|-------------|----------------|
| `app.py` | App factory : crée l'app FastAPI, **découvre et monte** les sub-apps automatiquement, enregistre les middleware |
| `discovery.py` | Scanner de `apis/` et `fronts/` : détecte les sub-apps et les fichiers statiques à monter |
| `apps/` | **Registre d'applications** : modèle `AppEntry` (table `papi_apps`) et logique de synchronisation au démarrage. Permet l'activation/désactivation des apps sans supprimer le code ni les données |
| `auth/` | Authentification JWT + token statique, gestion des tokens, dépendances de protection des routes |
| `admin/` | Back-office SQLAdmin monté sur `/-/admin` (gestion CRUD auto-générée, auth par session). UUIDs raccourcis dans l'affichage (1ère section) |
| `db/` | Session factory, base model SQLModel, gestion du cycle de vie des connexions |
| `config/` | Chargement de la configuration depuis les variables d'environnement (via Pydantic Settings) |
| `middleware/` | CORS, logging structuré, gestion globale des erreurs |
| `utils/` | Utilitaires partagés (pagination, réponses standardisées, etc.) |

### 2. Sub-apps `apis/` — Découverte automatique

Chaque dossier dans `apis/` est une **FastAPI sub-app** indépendante, **découverte et montée automatiquement** par l'app factory.

#### Convention de découverte

L'app factory scanne le dossier `apis/` au démarrage. Pour qu'un dossier soit reconnu comme une API, il doit :

1. Contenir un fichier **`app.py`** exportant une instance FastAPI nommée **`app`**
2. *(Optionnel)* Contenir un fichier **`manifest.yaml`** pour les métadonnées

```
apis/
├── eve/
│   ├── manifest.yaml      # ← Métadonnées (optionnel)
│   ├── app.py              # ← OBLIGATOIRE : exporte `app` (FastAPI)
│   ├── models.py
│   ├── schemas.py
│   ├── routes.py
│   └── services.py
└── another_api/
    ├── app.py              # ← Découverte automatique
    └── ...
```

#### Fichier `manifest.yaml` (optionnel)

Permet de surcharger les métadonnées inférées par convention :

```yaml
# apis/eve/manifest.yaml
name: "Eve"
prefix: "/eve"          # Défaut : nom du dossier (monté sous /api/eve)
description: "API de gestion des événements et RSVP"
version: "1.0.0"
enabled: true               # Permet de désactiver sans supprimer
```

Si absent, les valeurs sont inférées :
- `prefix` → nom du dossier (ex : `apis/eve/` → `/eve`, monté sous `/api/eve`)
- `name` → nom du dossier capitalisé
- `enabled` → `true`

#### Exemple de sub-app

```python
# apis/eve/app.py
from fastapi import FastAPI

app = FastAPI(
    title="Eve API",
    version="1.0.0",
    description="API de gestion des événements et RSVP"
)

from .routes import router
app.include_router(router)
```

### 3. Frontends `fronts/` — Fichiers statiques

Applications frontend indépendantes. Chaque frontend est **buildé** (HTML/CSS/JS statiques) puis servi automatiquement.

#### Comment sont servis les fichiers statiques ?

C'est **Starlette** (la fondation de FastAPI) qui fournit `StaticFiles`, un composant ASGI dédié au service de fichiers statiques. Comme FastAPI **est** Starlette, utiliser `StaticFiles` via FastAPI n'ajoute aucun overhead.

**Stratégie retenue :**

| Environnement | Méthode | Avantage |
|---------------|---------|----------|
| **Dev** | `StaticFiles` ou `DevProxy` (reverse proxy ASGI vers quasar dev) | Simple, tout-en-un, un seul processus |
| **Prod** | Reverse proxy (Traefik/Nginx/Caddy) sert les fichiers statiques, proxy les APIs | Performant, cache, compression, HTTPS |

#### Convention pour les fronts

```
fronts/
├── eve/
│   ├── dist/               # ← Build Quasar (quasar build → dist/)
│   │   ├── index.html
│   │   ├── css/
│   │   └── js/
│   ├── src/                # ← Source Vue.js/Quasar (non servi)
│   ├── package.json
│   └── manifest.yaml       # ← Optionnel : métadonnées
└── another_front/
    └── dist/
```

### 4. Base de données

**Stratégie dual-engine** via SQLModel (basé sur SQLAlchemy 2.0) :

```python
# Déterminé par la configuration
if settings.env == "development":
    DATABASE_URL = "sqlite+aiosqlite:///./dev.db"
else:
    DATABASE_URL = "postgresql+asyncpg://user:pass@host/dbname"
```

- **Modèles unifiés** : déclarés une seule fois via SQLModel (`table=True` pour l'ORM, héritage pour les schémas)
- **Migrations** : Alembic gère les migrations pour les deux moteurs
- **Sessions** : gestion via dependency injection FastAPI (`Depends(get_db)`)

## Flux de données

### Requête API typique

```
Client → Reverse Proxy → FastAPI Main → Middleware (CORS, Auth) → Sub-App Router → Service → DB → Response
```

### Flux de découverte au démarrage

```
1. create_app() configure FastAPI, middleware, auth, admin
2. uvicorn lance le lifespan :
   a. init_db() crée les tables (dev mode)
   b. seed_initial_data() (scripts/db_init.py) :
      - _seed_default_admin() crée admin si table users vide
      - _seed_default_eve() crée événement + RSVPs si table events vide
   c. _sync_registry() :
      - discovery.py scanne apis/ et fronts/ → liste des apps découvertes
      - sync_app_registry() synchronise la table papi_apps
      - Montage des APIs actives sous /api/{name}
      - Montage des fronts actifs sous /{name} si dist/ existe (StaticFiles)
3. Serveur prêt
```

### Flux d'authentification

```
Mode JWT (login interactif) :
1. POST /-/auth/login { email, password }
2. Vérification credentials → Génération JWT (access + refresh)
3. Client stocke le JWT
4. Requêtes suivantes : Header "Authorization: Bearer <jwt>"
5. Middleware vérifie le JWT → injecte l'utilisateur dans le contexte

Mode api_token (intégrations simples) :
1. POST /-/auth/me/token (authentifié) → génère un token statique unique
2. Client stocke le token
3. Requêtes suivantes : Header "Authorization: Bearer <api_token>"
4. Si le Bearer n'est pas un JWT valide, le système cherche un User avec ce api_token
```

> Les deux modes utilisent le même header `Authorization: Bearer`. La détection est automatique.

## Déploiement

### Développement

```bash
uv run uvicorn papi.app:app --reload --port 8000
```

### Production (Docker)

```yaml
# docker-compose.yml
services:
  papi:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - JWT_SECRET=...
      - ENV=production
    depends_on:
      - db

  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=papi
      - POSTGRES_USER=papi
      - POSTGRES_PASSWORD=...

volumes:
  pgdata:
```

## Conventions techniques

- **Async everywhere** : toutes les opérations I/O sont asynchrones
- **Dependency Injection** : via le système `Depends()` de FastAPI
- **Validation** : Pydantic v2 (via SQLModel) pour toutes les entrées/sorties
- **Modèles unifiés** : SQLModel pour ORM + schéma en un seul modèle (voir ADR-002)
- **Découverte automatique** : convention `app.py` + `manifest.yaml` optionnel (voir ADR-003)
- **Registre d'apps** : table `papi_apps` synchronisée à chaque démarrage ; gestion `active` / `disabled` / `unavailable`
- **Monitoring** : endpoint `GET /-/apps` expose le registre (APIs et fronts avec leur statut)
- **Docs** : documentation Swagger accessible sur `/-/docs`
- **Erreurs** : réponses standardisées avec codes HTTP appropriés
- **Logging** : structuré (JSON en prod, lisible en dev)
