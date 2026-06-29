# User Stories — Apymix

---

## EPIC-01 : Apymix Technical Core

### US-001 : App factory and sub-app mounting

**As a** developer,
**I want** the main application to automatically mount registered sub-apps,
**so that** I have a single entry point for all APIs.

**Acceptance criteria:**
- [ ] The app factory creates a main FastAPI instance
- [ ] Sub-apps are mounted under configurable prefixes (e.g. `/wedding`)
- [ ] The server starts without error with `uvicorn papi.app:create_app --factory`

**Estimation:** S
**Epic:** EPIC-01

---

### US-002 : Per-sub-app OpenAPI

**As a** developer,
**I want** each sub-app to expose its own OpenAPI schema,
**so that** each API is documented independently.

**Acceptance criteria:**
- [ ] Each sub-app has an accessible Swagger UI page (e.g. `/wedding/docs`)
- [ ] Each sub-app has its own `/openapi.json` endpoint
- [ ] The schema includes the API's title, version, and description

**Estimation:** XS
**Epic:** EPIC-01

---

### US-003 : Environment-based configuration

**As a** developer,
**I want** to load configuration from environment variables,
**so that** I can adapt behavior between dev and prod without changing the code.

**Acceptance criteria:**
- [ ] Configuration is managed via Pydantic Settings (`BaseSettings`)
- [ ] A `.env` file is supported for local development
- [ ] Key settings are configurable: `DATABASE_URL`, `JWT_SECRET`, `ENV`, `DEBUG`

**Estimation:** S
**Epic:** EPIC-01

---

### US-004 : Database abstraction

**As a** developer,
**I want** to use SQLite in development and PostgreSQL in production with the same code,
**so that** local development stays simple.

**Acceptance criteria:**
- [ ] SQLAlchemy 2.0 async is configured with a session factory
- [ ] The database engine is determined by `DATABASE_URL`
- [ ] A FastAPI `get_db` dependency provides a session per request
- [ ] SQLAlchemy models work on both engines

**Estimation:** M
**Epic:** EPIC-01

---

### US-005 : JWT authentication

**As an** administrator,
**I want** to authenticate via JWT,
**so that** I can access administration features securely.

**Acceptance criteria:**
- [ ] A `POST /auth/login` endpoint accepts email + password and returns a JWT
- [ ] A `POST /auth/refresh` endpoint renews the token
- [ ] Protected routes verify the JWT via middleware / dependency
- [ ] Passwords are hashed (bcrypt or argon2)
- [ ] The JWT has a configurable lifetime

**Estimation:** M
**Epic:** EPIC-01

---

### US-006 : Shared middleware

**As a** developer,
**I want** CORS, logging, and error handling middleware to be applied globally,
**so that** I don't have to reconfigure them for each API.

**Acceptance criteria:**
- [ ] CORS is configured on the main app (configurable allowed origins)
- [ ] Requests are logged with method, path, status, and duration
- [ ] Unhandled exceptions return a standardized JSON response
- [ ] Pydantic validation errors return a consistent format

**Estimation:** S
**Epic:** EPIC-01

---

## EPIC-04 : Deployment & Infrastructure

### US-016 : One-command local launch

**As a** developer,
**I want** to launch the application with a single command,
**so that** I can develop quickly.

**Acceptance criteria:**
- [ ] `uvicorn papi.app:create_app --factory --reload` starts the app with SQLite
- [ ] A `.env.example` file documents the required variables
- [ ] The `README.md` contains quickstart instructions

**Estimation:** S
**Epic:** EPIC-04

---

### US-017 : Docker deployment

**As a** developer,
**I want** to deploy via Docker / docker-compose,
**so that** production rollout is straightforward.

**Acceptance criteria:**
- [ ] A multi-stage `Dockerfile` produces an optimized image
- [ ] A `docker-compose.yml` launches the app + PostgreSQL
- [ ] Environment variables are documented
- [ ] The image weighs less than 200 MB

**Estimation:** M
**Epic:** EPIC-04

---

### US-018 : Database migrations

**As a** developer,
**I want** schema migrations to be managed automatically,
**so that** the data model can evolve without manual intervention.

**Acceptance criteria:**
- [ ] Alembic is configured and works with both SQLite and PostgreSQL
- [ ] `alembic upgrade head` applies all migrations
- [ ] `alembic revision --autogenerate` detects model changes
- [ ] Migrations are versioned in the Git repository

**Estimation:** M
**Epic:** EPIC-04

---

## EPIC-05 : Admin Operations & Quality

### US-019 : Trigger an API seed from the admin backend

**As an** administrator,
**I want** to manually launch the seed of a business application,
**so that** I can quickly reset an API's demo data without a manual script.

**Acceptance criteria:**
- [ ] A `GET /-/admin/seed` endpoint lists seedable APIs
- [ ] A `POST /-/admin/seed/{api_name}` endpoint triggers the targeted seed
- [ ] Access is restricted to authenticated admin sessions
- [ ] The response indicates whether data was actually inserted (`seeded: true/false`)

**Estimation:** S
**Epic:** EPIC-05

---

### US-020 : pytest coverage for critical system routes

**As a** developer,
**I want** `pytest` tests for sensitive system routes,
**so that** backend evolutions stay safe.

**Acceptance criteria:**
- [ ] Admin seed routes are tested (auth, 404, success)
- [ ] Tests run locally via `uv run pytest`
- [ ] Tests do not write to the development database by default

**Estimation:** S
**Epic:** EPIC-05

---

## EPIC-06 : Federated Authentication (OIDC)

### US-021 : Admin sign-in via Google OIDC

**As an** administrator,
**I want** to sign in with my Google account,
**so that** I can access the back-office without managing an extra local password.

**Acceptance criteria:**
- [ ] An OIDC redirect endpoint is available (`/-/auth/oidc/google/login`)
- [ ] An OIDC callback validates the identity and creates/updates the local user
- [ ] The connected user receives an internal Apymix JWT for protected routes
- [ ] Admin access still depends on the `admin` role on the Apymix side

**Estimation:** M
**Epic:** EPIC-06

---

### US-022 : Add GitHub as a secondary OIDC provider

**As a** developer,
**I want** to add GitHub as a second OIDC provider,
**so that** I can offer a sign-in alternative without changing the auth architecture.

**Acceptance criteria:**
- [ ] The GitHub provider is toggleable via configuration (feature flag/env)
- [ ] The login/callback flow reuses the same core as Google
- [ ] Useful claims (email, sub) are normalized into the internal user model

**Estimation:** S
**Epic:** EPIC-06

---

## EPIC-07 : Per-Application Profiled Images

### US-023 : Per-profile Docker build

**As a** developer,
**I want** to build an image per profile (`all`, `eve`, `kif`),
**so that** I deploy only the apps needed for a given environment.

**Acceptance criteria:**
- [ ] A build command accepts a profile (script or standardized argument)
- [ ] The `all` profile keeps the current behavior (all apps included)
- [ ] The `eve` profile includes only `eve-api` and the `eve` frontend
- [ ] The build/deploy documentation clearly describes the available profiles

**Estimation:** M
**Epic:** EPIC-07

---

### US-024 : Mono-front service at root `/`

**As a** visitor,
**I want** to access a mono-app frontend directly at `/`,
**so that** I don't have to deal with URL prefixes in a dedicated deployment.

**Acceptance criteria:**
- [ ] In mono-front profile, the active frontend is mounted at `/`
- [ ] Static assets and SPA/PWA routes work without a prefix
- [ ] Other frontends are not mounted in this profile

**Estimation:** M
**Epic:** EPIC-07

---

### US-025 : Secure the HTTPS scheme behind a reverse proxy

**As an** administrator,
**I want** the admin UI to serve all its resources over HTTPS,
**so that** we avoid browser warnings and mixed content.

**Acceptance criteria:**
- [ ] The application correctly interprets `X-Forwarded-Proto` behind the trusted proxy
- [ ] URLs generated for SQLAdmin use `https://` in production
- [ ] No admin asset is loaded over `http://` from the browser

**Estimation:** S
**Epic:** EPIC-07
