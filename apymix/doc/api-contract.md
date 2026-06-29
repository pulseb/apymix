# API Contract — Apymix System Routes

## Global conventions

### Base URL

| Environment | URL |
|---------------|-----|
| Local dev | `http://localhost:8000` |
| Production | `https://<domain>/` |

### Prefixes

| Prefix | Role |
|---------|------|
| `/-/` | Apymix system routes (auth, health, admin, apps) |
| `/api/{name}` | Business APIs (e.g. `/api/eve`) |
| `/{name}` | Frontends (e.g. `/eve`) |
| `/` | Root — general information |

### Response format

All JSON responses follow this structure:

```json
{
  "data": ...,
  "message": "ok",
  "paging": {"page": 1, "size": 20, "total": 42},
  "metadata": { ... }
}
```

- `data`: object or list (always present)
- `message`: short description of the result
- `paging`: only for paginated lists
- `metadata`: additional contextual info (stats, event, etc.)

### Authentication

Two authentication modes via the `Authorization: Bearer <token>` header:

1. **JWT** (recommended): obtained via `POST /-/auth/login`, expires after N minutes, renewable via `POST /-/auth/refresh`
2. **api_token** (static): long-lived token generated via `POST /-/auth/me/token`, handy for scripts and integrations

Both are accepted wherever `Depends(get_current_user)` is used.

### Common HTTP codes

| Code | Meaning |
|------|---------------|
| `200` | Success |
| `201` | Resource created |
| `204` | Successful deletion (no body) |
| `400` | Invalid request / inactive event |
| `401` | Unauthenticated / invalid token |
| `403` | Forbidden (disabled account, no admin password) |
| `404` | Resource not found |
| `409` | Conflict (duplicate slug, duplicate email/event) |
| `422` | Pydantic validation error |

---

## Root

### `GET /`

General PulseApps information.

**Auth:** none

**Response 200:**

```json
{
  "app": "PulseApps",
  "version": "0.1.0",
  "docs": "/-/docs",
  "health": "/-/health"
}
```

---

## System routes (`/-/`)

### `GET /-/health`

Health check.

**Auth:** none

**Response 200:**

```json
{
  "status": "healthy",
  "database": "ok"
}
```

---

### `GET /-/apps`

List of registered applications (registry).

**Auth:** none

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | — | Filter by type: `api` or `front` |
| `status` | string | — | Filter by status: `active`, `disabled`, `unavailable` |

**Response 200:**

```json
{
  "data": [
    {
      "id": 1,
      "name": "eve",
      "app_type": "api",
      "prefix": "/eve",
      "status": "active",
      "docs_enabled": true,
      "description": "Eve API — events + RSVP",
      "version": "0.1.0",
      "last_seen_at": "2026-02-25T10:00:00Z",
      "created_at": "2026-02-25T10:00:00Z",
      "updated_at": "2026-02-25T10:00:00Z"
    }
  ],
  "message": "ok"
}
```

---

## Authentication (`/-/auth`)

### `POST /-/auth/login`

Obtain a JWT.

**Auth:** none

**Body:**

```json
{
  "email": "admin@pulseapps.dev",
  "password": "secret"
}
```

**Response 200:**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:** `401` invalid email/password, `403` disabled account.

---

### `POST /-/auth/refresh`

Renew a JWT using a refresh token.

**Auth:** none

**Body:**

```json
{
  "refresh_token": "eyJ..."
}
```

**Response 200:** same format as `/login`.

**Errors:** `401` invalid or expired refresh token.

---

### `GET /-/auth/me`

Information about the connected user.

**Auth:** JWT or api_token (Bearer)

**Response 200:**

```json
{
  "id": "uuid-...",
  "email": "admin@pulseapps.dev",
  "role": "admin",
  "is_active": true,
  "api_token": "xY3k..."
}
```

---

### `POST /-/auth/me/token`

Generate (or regenerate) a static api_token.

**Auth:** JWT or api_token (Bearer)

**Response 200:** same format as `GET /me`, with the new `api_token`.

---

### `DELETE /-/auth/me/token`

Revoke the api_token.

**Auth:** JWT or api_token (Bearer)

**Response 200:** same format as `GET /me`, with `api_token: null`.

---

## Admin API (`/-/api/*`)

> **Authentication:** All endpoints require a valid JWT Bearer with the `admin` role.
>
> **Header:** `Authorization: Bearer <access_token>`
>
> **Obtaining the token:** `POST /-/auth/login` with email + password
>
> **Rate limiting:** 200 requests per minute per IP (global).

### `GET /-/api`

Entry point and documentation for the admin API.

**Auth:** JWT Bearer, admin role

**Response 200:** See above.

---

### `GET /-/api/seeds`

List all APIs that have a seed available.

**Auth:** JWT Bearer, admin role

**Response 200:**

```json
{
  "data": {
    "available": ["eve", "kif"],
    "count": 2
  },
  "message": "ok"
}
```

---

### `POST /-/api/seeds/{api_name}`

Trigger the seed of a specific API.

**Auth:** JWT Bearer, admin role

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `api_name` | string | API name (e.g. `eve`) |

**Response 200 (seed executed):**

```json
{
  "data": {
    "api": "eve",
    "seeded": true,
    "message": "Seed executed successfully",
    "timestamp": "2026-03-03T12:00:00.000000"
  },
  "message": "ok"
}
```

**Response 200 (data already present):**

```json
{
  "data": {
    "api": "eve",
    "seeded": false,
    "message": "Data already present — no action taken",
    "timestamp": "2026-03-03T12:00:00.000000"
  },
  "message": "ok"
}
```

**Errors:**

| Code | Meaning |
|------|---------------|
| `401` | Invalid or missing token |
| `403` | Insufficient role (not admin) |
| `404` | API has no seed available |
| `429` | Rate limit exceeded |
| `500` | Error during seed |

---

## System endpoints summary

| Method | Path | Auth | Description |
|---------|--------|------|-------------|
| `GET` | `/` | — | PulseApps info |
| `GET` | `/-/health` | — | Health check |
| `GET` | `/-/apps` | — | Application registry |
| `POST` | `/-/auth/login` | — | JWT login |
| `POST` | `/-/auth/refresh` | — | Refresh JWT |
| `GET` | `/-/auth/me` | JWT/token | User info |
| `POST` | `/-/auth/me/token` | JWT/token | Generate api_token |
| `DELETE` | `/-/auth/me/token` | JWT/token | Revoke api_token |
| `GET` | `/-/api` | JWT admin | Admin API info |
| `GET` | `/-/api/seeds` | JWT admin | List seedable APIs |
| `POST` | `/-/api/seeds/{name}` | JWT admin | Trigger API seed |
