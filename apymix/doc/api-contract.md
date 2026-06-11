# Contrat d'API — Routes système PAPI

## Conventions globales

### Base URL

| Environnement | URL |
|---------------|-----|
| Dev local | `http://localhost:8000` |
| Production | `https://<domaine>/` |

### Préfixes

| Préfixe | Rôle |
|---------|------|
| `/-/` | Routes système PAPI (auth, health, admin, apps) |
| `/api/{nom}` | APIs métier (ex : `/api/eve`) |
| `/{nom}` | Frontends (ex : `/eve`) |
| `/` | Racine — informations générales |

### Format des réponses

Toutes les réponses JSON suivent la structure :

```json
{
  "data": ...,
  "message": "ok",
  "paging": {"page": 1, "size": 20, "total": 42},
  "metadata": { ... }
}
```

- `data` : objet ou liste (toujours présent)
- `message` : description courte du résultat
- `paging` : uniquement pour les listes paginées
- `metadata` : infos supplémentaires contextuelles (stats, event…)

### Authentification

Deux modes d'authentification via header `Authorization: Bearer <token>` :

1. **JWT** (recommandé) : obtenu via `POST /-/auth/login`, expire après N minutes, renouvelable via `POST /-/auth/refresh`
2. **api_token** (statique) : token longue durée généré via `POST /-/auth/me/token`, pratique pour scripts et intégrations

Les deux sont acceptés partout où `Depends(get_current_user)` est utilisé.

### Codes HTTP communs

| Code | Signification |
|------|---------------|
| `200` | Succès |
| `201` | Ressource créée |
| `204` | Suppression réussie (pas de body) |
| `400` | Requête invalide / événement inactif |
| `401` | Non authentifié / token invalide |
| `403` | Accès interdit (compte désactivé, pas de password admin) |
| `404` | Ressource introuvable |
| `409` | Conflit (doublon slug, doublon email/event) |
| `422` | Erreur de validation Pydantic |

---

## Racine

### `GET /`

Informations générales PulseApps.

**Auth :** aucune

**Réponse 200 :**

```json
{
  "app": "PulseApps",
  "version": "0.1.0",
  "docs": "/-/docs",
  "health": "/-/health"
}
```

---

## Routes système (`/-/`)

### `GET /-/health`

Health check.

**Auth :** aucune

**Réponse 200 :**

```json
{
  "status": "healthy",
  "database": "ok"
}
```

---

### `GET /-/apps`

Liste des applications enregistrées (registre).

**Auth :** aucune

**Query params :**

| Param | Type | Défaut | Description |
|-------|------|--------|-------------|
| `type` | string | — | Filtrer par type : `api` ou `front` |
| `status` | string | — | Filtrer par statut : `active`, `disabled`, `unavailable` |

**Réponse 200 :**

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
      "description": "API Eve — événements + RSVP",
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

## Authentification (`/-/auth`)

### `POST /-/auth/login`

Obtenir un JWT.

**Auth :** aucune

**Body :**

```json
{
  "email": "admin@pulseapps.dev",
  "password": "secret"
}
```

**Réponse 200 :**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Erreurs :** `401` email/password incorrect, `403` compte désactivé.

---

### `POST /-/auth/refresh`

Renouveler un JWT via refresh token.

**Auth :** aucune

**Body :**

```json
{
  "refresh_token": "eyJ..."
}
```

**Réponse 200 :** même format que `/login`.

**Erreurs :** `401` refresh token invalide ou expiré.

---

### `GET /-/auth/me`

Informations de l'utilisateur connecté.

**Auth :** JWT ou api_token (Bearer)

**Réponse 200 :**

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

Générer (ou régénérer) un api_token statique.

**Auth :** JWT ou api_token (Bearer)

**Réponse 200 :** même format que `GET /me`, avec le nouveau `api_token`.

---

### `DELETE /-/auth/me/token`

Révoquer l'api_token.

**Auth :** JWT ou api_token (Bearer)

**Réponse 200 :** même format que `GET /me`, avec `api_token: null`.

---

## API Admin (`/-/api/*`)

> **Authentification :** Tous les endpoints requièrent un JWT Bearer valide avec rôle `admin`.
> 
> **Header :** `Authorization: Bearer <access_token>`
> 
> **Obtention du token :** `POST /-/auth/login` avec email + password
> 
> **Rate limiting :** 200 requêtes par minute par IP (global).

### `GET /-/api`

Point d'entrée et documentation de l'API admin.

**Auth :** JWT Bearer, rôle admin

**Réponse 200 :** Voir ci-dessus.

---

### `GET /-/api/seeds`

Liste toutes les APIs qui ont un seed disponible.

**Auth :** JWT Bearer, rôle admin

**Réponse 200 :**

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

Déclenche le seed d'une API spécifique.

**Auth :** JWT Bearer, rôle admin

**Path params :**

| Param | Type | Description |
|-------|------|-------------|
| `api_name` | string | Nom de l'API (ex: `eve`) |

**Réponse 200 (seed exécuté) :**

```json
{
  "data": {
    "api": "eve",
    "seeded": true,
    "message": "Seed exécuté avec succès",
    "timestamp": "2026-03-03T12:00:00.000000"
  },
  "message": "ok"
}
```

**Réponse 200 (données déjà présentes) :**

```json
{
  "data": {
    "api": "eve",
    "seeded": false,
    "message": "Données déjà présentes — aucune action",
    "timestamp": "2026-03-03T12:00:00.000000"
  },
  "message": "ok"
}
```

**Erreurs :**

| Code | Signification |
|------|---------------|
| `401` | Token invalide ou absent |
| `403` | Rôle insuffisant (non admin) |
| `404` | API n'a pas de seed disponible |
| `429` | Rate limit dépassé |
| `500` | Erreur lors du seed |

---

## Récapitulatif des endpoints système

| Méthode | Chemin | Auth | Description |
|---------|--------|------|-------------|
| `GET` | `/` | — | Infos PulseApps |
| `GET` | `/-/health` | — | Health check |
| `GET` | `/-/apps` | — | Registre des applications |
| `POST` | `/-/auth/login` | — | Login JWT |
| `POST` | `/-/auth/refresh` | — | Refresh JWT |
| `GET` | `/-/auth/me` | JWT/token | User info |
| `POST` | `/-/auth/me/token` | JWT/token | Générer api_token |
| `DELETE` | `/-/auth/me/token` | JWT/token | Révoquer api_token |
| `GET` | `/-/api` | JWT admin | Info API admin |
| `GET` | `/-/api/seeds` | JWT admin | Lister les APIs seedables |
| `POST` | `/-/api/seeds/{name}` | JWT admin | Déclencher seed API |
