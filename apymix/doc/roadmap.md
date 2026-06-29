# Roadmap — Apymix

## Development Plan — Technical Core

> **Objective:** A working technical core for hosting micro-APIs
> **Developer:** Solo

---

## Phase 1 : Foundations

**Objective:** Have a project that starts up and serves an empty sub-app.

| Task | Epic / Enabler | Estimation |
|-------|----------------|------------|
| Project scaffolding (`pyproject.toml`, folder structure) | ENB-01 | 1h |
| Pydantic Settings configuration | ENB-06, US-003 | 1h |
| App factory + sub-app mounting | US-001, US-002 | 1h |
| DB abstraction (SQLAlchemy async + sessions) | ENB-02, US-004 | 2h |
| Alembic setup | ENB-05 | 1h |

**Deliverable:** `uvicorn papi.app:create_app --factory --reload` starts, sub-app docs accessible.

---

## Phase 2 : Auth & Middleware

**Objective:** JWT authentication is functional, middleware is in place.

| Task | Epic / Enabler | Estimation |
|-------|----------------|------------|
| `User` model + migration | ENB-03 | 1h |
| Auth endpoints (login, refresh) | US-005 | 2h |
| `get_current_user` dependency | US-005 | 1h |
| CORS, logging, errors middleware | US-006, ENB-07 | 2h |
| Healthcheck endpoint | ENB-07 | 30min |

**Deliverable:** You can sign in, obtain a JWT, and access a protected endpoint.

---

## Phase 3 : Docker & Infrastructure

**Objective:** The application is deployable.

| Task | Epic / Enabler | Estimation |
|-------|----------------|------------|
| Dockerfile | ENB-04, US-017 | 1h |
| docker-compose.yml (app + PostgreSQL) | ENB-04, US-017 | 1h |
| Admin user seed (script) | ENB-03 | 30min |
| Quickstart documentation | US-016 | 30min |

**Deliverable:** `docker-compose up` launches the full application in production.

---

## Post-MVP (backlog)

| Priority | Feature | Description |
|----------|----------------|-------------|
| 🔥 High | CI/CD GitHub Actions | Lint, tests, Docker build, registry push |
| 🔥 High | HTTPS (Let's Encrypt) | Via Traefik or Caddy as a reverse proxy |
| 🟡 Medium | Infra tests | pytest configured, fixtures, coverage |
| 🟢 Low | Advanced observability | Structured JSON logging, metrics |

---

## Phase 4 : Admin Operations & Quality

**Objective:** Equip backend operations and harden the core with automated tests.

| Task | Epic / US | Estimation |
|-------|----------------|------------|
| Admin route to trigger seed per API | US-019 | ✅ |
| pytest coverage of admin seed routes | US-020 | 1h |

**Deliverable:** An authenticated admin can launch an API seed and the behavior is covered by automated tests.
