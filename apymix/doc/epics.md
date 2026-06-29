# Epics — Apymix

## EPIC-01 : Apymix Technical Core

**Objective:** Build the reusable technical module that lets us mount and serve several FastAPI sub-apps with shared authentication, database, and configuration.

**Personas:** Developer, Administrator

**Success criteria:**
- A developer can add a new API by creating a folder and registering it in the app factory
- Each sub-app has its own OpenAPI schema
- JWT authentication is functional and shared between APIs
- The database works on SQLite (dev) and PostgreSQL (prod) with no business code changes
- Middleware (CORS, logging, errors) is applied globally

**Related user stories:** US-001, US-002, US-003, US-004, US-005, US-006

---

## EPIC-04 : Deployment & Infrastructure

**Objective:** Set up the deployment infrastructure so that Apymix can be securely accessed in production.

**Personas:** Developer, Administrator

**Success criteria:**
- The app can be launched locally with a single command
- The app can be deployed via Docker / docker-compose
- Configuration is managed via environment variables
- HTTPS is in place in production

**Related user stories:** US-016, US-017, US-018

---

## EPIC-05 : Admin Operations & Quality

**Objective:** Streamline day-to-day backend operations and ensure a baseline of automated tests for the critical features.

**Personas:** Developer, Administrator

**Success criteria:**
- An authenticated admin can manually trigger the seed of an API from the backend
- Critical endpoints have `pytest` coverage
- Tests can be run locally via `uv run pytest`

**Related user stories:** US-019, US-020

---

## EPIC-06 : Federated Authentication (OIDC)

**Objective:** Add a standard OIDC SSO authentication to simplify admin access without managing additional local passwords.

**Personas:** Administrator, Developer

**Success criteria:**
- An administrator can sign in via Google OIDC
- The application retains an internal JWT mode after OIDC authentication
- OIDC accounts are linked to an internal user with a role (`admin`/`user`)
- Configuration is done via environment variables (`OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`)

**Related user stories:** US-021, US-022

---

## EPIC-07 : Per-Application Profiled Images

**Objective:** Produce targeted Docker images per application (e.g. `eve:latest`) while keeping an `all-in-one` image for test environments.

**Personas:** Developer, Administrator

**Success criteria:**
- A build can target a profile (`all`, `eve`, `kif`)
- The profile determines which APIs/fronts are included and enabled
- Mono-front mode can serve the application at `/` (no prefix)
- The build process stays KISS (one main command)

**Related user stories:** US-023, US-024, US-025
