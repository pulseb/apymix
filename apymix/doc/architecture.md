# Technical Architecture — Apymix

## Overview

Apymix follows a **layered, modular architecture** with **automatic discovery** of APIs:

```
┌─────────────────────────────────────────────────────┐
│                   Clients (browser)                  │
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
│  │  scan amx.yaml → mount sub-apps + fronts      │  │
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

## Core principle: full decoupling

The `apymix/` module is **completely agnostic** of business APIs and frontends:

```
apymix/   →  Knows NO business API. Zero imports from any API or frontend.
*-api/    →  Imports from apymix/ (auth, db, config). Independent of other APIs.
*-ui/     →  Consumes APIs over HTTP. No Python dependency on apymix/ or APIs.
```

> This makes it possible to turn `apymix/` into a reusable pip package for other projects.

## Routing by prefix

Routing uses prefixes to prevent collisions between components:

| Prefix | Usage | Examples |
|---------|-------|----------|
| `/-/` | Apymix system routes | `/-/docs`, `/-/admin`, `/-/health`, `/-/auth/*` |
| `/api/` | Business APIs | `/api/eve/events`, `/api/eve/events/{slug}/rsvps` |
| `/{name}` | Frontends (StaticFiles) | `/eve` (Vue.js/Quasar SPA) |
| `/` | Minimal root | Returns `{"message": "PulseApps is running"}` (no sensitive info) |

> The **ASCII art dashboard** (links to docs, admin, health) lives at `/-/` (not indexed).
> The `/` page is intentionally minimal so it doesn't leak information to unauthenticated visitors.

### Constants (in `app.py`):
```python
AMX_ROUTES_PREFIX = "/-"     # System routes
API_PREFIX = "/api"    # Business APIs
```

## Components

### 1. The `apymix/` module (technical core)

The reusable technical module, potentially open-sourceable.

| Sub-module | Responsibility |
|-------------|----------------|
| `app.py` | App factory: creates the FastAPI app, **discovers and mounts** sub-apps automatically, registers middleware |
| `discovery.py` | Scanner that walks the workspace for `amx.yaml` files: detects sub-apps and static frontends to mount |
| `apps/` | **Application registry**: `AppEntry` model (`amx_apps` table) and startup sync logic. Lets you enable/disable apps without deleting code or data |
| `auth/` | JWT authentication + static token, token management, route protection dependencies |
| `admin/` | SQLAdmin back-office mounted at `/-/admin` (auto-generated CRUD, session-based auth). Shortened UUIDs in the display (1st section) |
| `db/` | Session factory, SQLModel base model, connection lifecycle management |
| `config.py` | Configuration loading from environment variables (via Pydantic Settings) |
| `middleware/` | CORS, structured logging, global error handling |
| `spa_static.py` | Static file serving for built SPAs |

### 2. Sub-apps — Automatic discovery

Each `amx.yaml` at the workspace root that declares `type: api` is an **independent FastAPI sub-app**, **discovered and mounted automatically** by the app factory.

#### Discovery convention

The app factory walks the workspace at startup. For a project to be recognized as an API, its `amx.yaml` must declare:

```yaml
name: Eve-API
route: /eve
type: api
module: eve_api        # Python module exposing `app: FastAPI`
table_prefix: eve_
version: 1.0.0
enabled: true
```

#### Example sub-app

```python
# eve-api/eve_api/app.py
from fastapi import FastAPI

app = FastAPI(
    title="Eve API",
    version="1.0.0",
    description="API for event management and RSVP"
)

from .routes import router
app.include_router(router)
```

### 3. Frontends — Static files

Independent frontend applications. Each frontend is **built** (static HTML/CSS/JS) then served automatically.

#### How are static files served?

**Starlette** (the foundation of FastAPI) provides `StaticFiles`, an ASGI component dedicated to serving static files. Since FastAPI **is** Starlette, using `StaticFiles` through FastAPI adds no overhead.

**Chosen strategy:**

| Environment | Method | Advantage |
|---------------|---------|----------|
| **Dev** | `StaticFiles` or `DevProxy` (ASGI reverse proxy to `quasar dev`) | Simple, all-in-one, single process |
| **Prod** | Reverse proxy (Traefik/Nginx/Caddy) serves static files, proxies APIs | Performant, cache, compression, HTTPS |

#### Frontend convention

```
eve-ui/
├── amx.yaml            # route, type: static, dist_dir, etc.
├── dist/               # Quasar build output (quasar build → dist/)
│   ├── index.html
│   ├── css/
│   └── js/
├── src/                # Vue.js/Quasar source (not served)
└── package.json
```

### 4. Database

**Dual-engine strategy** via SQLModel (built on SQLAlchemy 2.0):

```python
# Determined by configuration
if settings.env == "development":
    DATABASE_URL = "sqlite+aiosqlite:///./dev.db"
else:
    DATABASE_URL = "postgresql+asyncpg://user:pass@host/dbname"
```

- **Unified models**: declared once via SQLModel (`table=True` for ORM, inheritance for schemas)
- **Migrations**: Alembic handles migrations for both engines
- **Sessions**: managed via FastAPI dependency injection (`Depends(get_db)`)

## Data flow

### Typical API request

```
Client → Reverse Proxy → FastAPI Main → Middleware (CORS, Auth) → Sub-App Router → Service → DB → Response
```

### Discovery flow at startup

```
1. create_app() configures FastAPI, middleware, auth, admin
2. uvicorn runs the lifespan:
   a. init_db() creates the tables (dev mode)
   b. seed_initial_data() (scripts/db_init.py):
      - _seed_default_admin() creates admin if users table is empty
      - _seed_default_eve() creates event + RSVPs if events table is empty
   c. _sync_registry():
      - discovery.py scans the workspace for amx.yaml files → list of discovered apps
      - sync_app_registry() synchronizes the amx_apps table
      - Mounting of active APIs under /api/{name}
      - Mounting of active frontends under /{name} if dist/ exists (StaticFiles)
3. Server ready
```

### Authentication flow

```
JWT mode (interactive login):
1. POST /-/auth/login { email, password }
2. Verify credentials → Generate JWT (access + refresh)
3. Client stores the JWT
4. Subsequent requests: Header "Authorization: Bearer <jwt>"
5. Middleware verifies the JWT → injects the user into the context

api_token mode (simple integrations):
1. POST /-/auth/me/token (authenticated) → generates a unique static token
2. Client stores the token
3. Subsequent requests: Header "Authorization: Bearer <api_token>"
4. If the Bearer is not a valid JWT, the system looks up a User with this api_token
```

> Both modes use the same `Authorization: Bearer` header. Detection is automatic.

## Deployment

### Development

```bash
uv run uvicorn apymix.app:app --reload --port 8000
```

### Production (Docker)

```yaml
# docker-compose.yml
services:
  apymix:
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
      - POSTGRES_DB=apymix
      - POSTGRES_USER=apymix
      - POSTGRES_PASSWORD=...

volumes:
  pgdata:
```

## Technical conventions

- **Async everywhere**: all I/O operations are asynchronous
- **Dependency Injection**: via FastAPI's `Depends()` system
- **Validation**: Pydantic v2 (via SQLModel) for all inputs/outputs
- **Unified models**: SQLModel for ORM + schema in a single model (see ADR-002)
- **Automatic discovery**: `amx.yaml` convention per project at the workspace root
- **App registry**: `amx_apps` table synchronized on every startup; supports `active` / `disabled` / `unavailable` states
- **Monitoring**: `GET /-/apps` endpoint exposes the registry (APIs and fronts with their status)
- **Docs**: Swagger documentation available at `/-/docs`
- **Errors**: standardized responses with appropriate HTTP codes
- **Logging**: structured (JSON in prod, human-readable in dev)
