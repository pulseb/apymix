# ADR-001 : FastAPI as Dispatcher and API Framework

**Status:** Accepted
**Date:** 2026-02-24

## Context

Apymix must serve multiple APIs under a single server. Each API must have its own OpenAPI schema. Two main approaches are considered for dispatching requests to sub-applications.

## Considered options

### Option A : Starlette (main) + FastAPI (sub-apps)

Use pure Starlette for the main application (dispatch only) and FastAPI for each business sub-app.

- **Pros:** Lighter main app, clear separation of responsibilities
- **Cons:** No validation or OpenAPI docs on main routes (health, auth). Two frameworks to master. Middleware configuration differs.

### Option B : FastAPI everywhere (main + sub-apps)

Use FastAPI as the main application AND for each sub-app.

- **Pros:** Consistent API everywhere (validation, docs, dependency injection). A single framework. Global routes (auth, health) also benefit from OpenAPI. FastAPI is built ON Starlette, so there's no real overhead.
- **Cons:** Slightly more dependencies imported in the main app (negligible).

## Decision

**Option B: FastAPI everywhere.**

FastAPI is a thin layer over Starlette with no significant overhead. Using FastAPI as the main app allows us to:
- Have auth and health routes documented in OpenAPI
- Use the same dependency injection system everywhere
- Simplify maintenance (a single framework)

Mounting sub-apps via `app.mount("/prefix", sub_app)` automatically yields a separate OpenAPI schema per sub-app.

## Consequences

### Positive
- Technical consistency across the project
- Complete OpenAPI documentation (including auth and health)
- Reduced learning curve

### Negative
- If the `apymix` module is open-sourced, it ships FastAPI as a dependency (which is already de facto the case)

### Risks
- No risks identified. FastAPI is the de facto standard for modern Python APIs.
