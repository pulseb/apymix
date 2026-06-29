# Technical Enablers — Apymix

---

## ENB-01 : Project Scaffolding & Development Environment

**Type:** DevEx
**Objective:** Set up the file structure, dependencies, and development tooling.
**Dependencies:** None

**Done criteria:**
- [x] `pyproject.toml` configured with dependencies (FastAPI, SQLAlchemy, Alembic, Pydantic, uvicorn, etc.)
- [x] `[dev]` dependency group (pytest, httpx, ruff, mypy)
- [x] Folder structure created (`apymix/`, `apis/`, `fronts/`, `tests/`, `alembic/`)
- [ ] `.gitignore` configured for Python, Node.js, IDE, `.env`
- [ ] `.env.example` with documented variables

---

## ENB-02 : Multi-Engine Database Abstraction

**Type:** Infrastructure
**Objective:** Allow SQLite in development and PostgreSQL in production with the same application code.
**Dependencies:** ENB-01

**Done criteria:**
- [x] SQLAlchemy 2.0 async configured with a session factory
- [x] Engine determined by the `DATABASE_URL` variable
- [x] FastAPI `get_db` dependency injecting a session per request
- [x] Declarative base model with automatic `id`, `created_at`, `updated_at`
- [ ] Tests pass on SQLite (in-memory)

---

## ENB-03 : JWT Authentication & Authorization

**Type:** Security
**Objective:** Secure administration endpoints with JWT authentication and/or a static token.
**Dependencies:** ENB-01, ENB-02

**Done criteria:**
- [x] `User` model with email and hashed password
- [x] `/auth/login` and `/auth/refresh` endpoints
- [x] FastAPI `get_current_user` dependency to protect routes
- [x] Password hashing (bcrypt)
- [x] JWT configuration (secret, lifetime) via environment variables
- [x] Role management (at minimum: admin)
- [x] Static token (`api_token`) as an alternative to JWT for simple integrations

---

## ENB-04 : Docker Containerization

**Type:** Infrastructure
**Objective:** Produce an optimized Docker image for deployment.
**Dependencies:** ENB-01

**Done criteria:**
- [x] Dockerfile (multi-stage, python:3.14, uv builder + slim runtime)
- [x] Image based on Python 3.14-slim
- [x] Non-root user inside the container
- [ ] `docker-compose.yml` with `apymix` + `db` (PostgreSQL) services
- [ ] Healthcheck configured
- [x] `.dockerignore` configured

---

## ENB-05 : Alembic Schema Migrations

**Type:** Infrastructure
**Objective:** Manage database schema evolutions in a versioned way.
**Dependencies:** ENB-02

**Done criteria:**
- [ ] Alembic initialized with async configuration
- [ ] `alembic.ini` and `env.py` configured
- [ ] Support for SQLite and PostgreSQL
- [ ] `alembic revision --autogenerate` working
- [ ] Initial migration created

---

## ENB-06 : Centralized Configuration

**Type:** DevEx
**Objective:** Centralize application configuration via Pydantic Settings.
**Dependencies:** ENB-01

**Done criteria:**
- [x] `Settings` class inheriting from `BaseSettings` (Pydantic)
- [x] Support for `.env` file via `env_file`
- [x] Variables: `ENV`, `DEBUG`, `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRATION`, `CORS_ORIGINS`
- [x] Value validation at startup
- [x] Singleton accessible across the application

---

## ENB-07 : Minimal Observability

**Type:** Observability
**Objective:** Set up structured logging and a healthcheck endpoint.
**Dependencies:** ENB-01

**Done criteria:**
- [ ] Structured logging (JSON in prod, human-readable in dev)
- [ ] Per-request log (method, path, status, duration)
- [ ] `GET /health` endpoint returning the app and DB status
- [ ] Log level configurable via environment variable

---

## ENB-08 : Testing & Code Quality

**Type:** DevEx
**Objective:** Set up the testing infrastructure and code quality tools.
**Dependencies:** ENB-01, ENB-02

**Done criteria:**
- [ ] pytest configured via `pytest.ini` or `pyproject.toml`
- [ ] httpx `AsyncClient` configured for API tests
- [ ] Test fixtures (app, client, in-memory db session)
- [ ] Ruff configured for linting
- [ ] At least one test per MVP endpoint
