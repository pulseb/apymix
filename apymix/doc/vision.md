# Vision — Apymix (API Python Mix)

## Pitch

**Apymix (API Python Mix)** is a Python technical core that lets you host several micro-APIs under a single infrastructure. It pools cross-cutting concerns (authentication, database, configuration, deployment) so a solo developer can ship new business APIs with zero friction.

## Problem

A developer who needs several small APIs (wedding RSVP, personal management, home automation...) currently has to, for each one:

- Set up a new project
- Wire up authentication
- Configure the database and migrations
- Write a Dockerfile and a CI/CD pipeline
- Manage hosting

**This is a major blocker**: the technical scaffolding ends up taking more time than the business logic itself.

## Solution

Apymix provides:

1. **A reusable technical module** (`apymix/`) — auth, DB, config, middleware — potentially open-sourceable
2. **A sub-app system** — each business API lives in its own folder with its own OpenAPI doc
3. **A single deployment** — one Docker container serves all APIs
4. **A database abstraction** — SQLite in dev, PostgreSQL in prod, same code

## Personas

### 👨‍💻 Developer (Apymix's primary persona)

- **Profile:** Solo developer or small team
- **Need:** Ship micro-APIs quickly without technical overhead
- **Interaction:** Creates sub-apps, uses the `apymix/` module

### 🔧 Administrator

- **Profile:** The developer in their role as platform administrator
- **Need:** Manage users, monitor APIs, control access
- **Interaction:** Admin interface, JWT management, monitoring

## Scope

### In scope

- ✅ Apymix technical core (app factory, JWT auth, DB abstraction, config)
- ✅ Sub-app mounting system with per-API OpenAPI
- ✅ Auto-discovery of APIs and frontends via `amx.yaml`
- ✅ Application registry (`amx_apps`)
- ✅ Docker deployment
- ✅ SQLAdmin back-office

### Out of scope

- ❌ Business logic (each API manages its own)
- ❌ Frontends (each app is autonomous)
- ❌ Multi-tenancy
- ❌ Full CI/CD (will be addressed post-MVP)
- ❌ Advanced monitoring / observability

## Guiding values

1. **Simplicity** — A developer must be able to add an API in under 30 minutes
2. **Isolation** — Each business API is independent; the technical core is reusable
3. **Pragmatism** — No over-engineering; build only what we need
4. **Security** — Personal data is protected from day one (auth, HTTPS, validation)
