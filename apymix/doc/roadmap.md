# Roadmap — PAPI

## Plan de développement — Socle technique

> **Objectif :** Socle technique fonctionnel pour héberger des micro-APIs
> **Développeur :** Solo

---

## Phase 1 : Fondations

**Objectif :** Avoir un projet qui démarre et sert une sub-app vide.

| Tâche | Epic / Enabler | Estimation |
|-------|----------------|------------|
| Scaffolding projet (`pyproject.toml`, structure dossiers) | ENB-01 | 1h |
| Configuration Pydantic Settings | ENB-06, US-003 | 1h |
| App factory + montage sub-app | US-001, US-002 | 1h |
| Abstraction BDD (SQLAlchemy async + sessions) | ENB-02, US-004 | 2h |
| Setup Alembic | ENB-05 | 1h |

**Livrable :** `uvicorn papi.app:create_app --factory --reload` démarre, sub-app docs accessible.

---

## Phase 2 : Auth & Middleware

**Objectif :** L'authentification JWT est fonctionnelle, les middleware sont en place.

| Tâche | Epic / Enabler | Estimation |
|-------|----------------|------------|
| Modèle `User` + migration | ENB-03 | 1h |
| Endpoints auth (login, refresh) | US-005 | 2h |
| Dépendance `get_current_user` | US-005 | 1h |
| Middleware CORS, logging, errors | US-006, ENB-07 | 2h |
| Healthcheck endpoint | ENB-07 | 30min |

**Livrable :** On peut se connecter, obtenir un JWT, et accéder à un endpoint protégé.

---

## Phase 3 : Docker & Infrastructure

**Objectif :** L'application est déployable.

| Tâche | Epic / Enabler | Estimation |
|-------|----------------|------------|
| Dockerfile | ENB-04, US-017 | 1h |
| docker-compose.yml (app + PostgreSQL) | ENB-04, US-017 | 1h |
| Seed admin user (script) | ENB-03 | 30min |
| Documentation quickstart | US-016 | 30min |

**Livrable :** `docker-compose up` lance l'application complète en production.

---

## Post-MVP (backlog)

| Priorité | Fonctionnalité | Description |
|----------|----------------|-------------|
| 🔥 Haute | CI/CD GitHub Actions | Lint, tests, build Docker, push registry |
| 🔥 Haute | HTTPS (Let's Encrypt) | Via Traefik ou Caddy en reverse proxy |
| 🟡 Moyenne | Tests infra | pytest configuré, fixtures, couverture |
| 🟢 Basse | Observabilité avancée | Logging structuré JSON, métriques |

---

## Phase 4 : Opérations admin & qualité

**Objectif :** Outiller l'exploitation backend et fiabiliser le socle via des tests automatiques.

| Tâche | Epic / US | Estimation |
|-------|----------------|------------|
| Route admin de déclenchement seed par API | US-019 | ✅ |
| Tests pytest des routes de seed admin | US-020 | 1h |

**Livrable :** Un admin authentifié peut lancer un seed API et le comportement est couvert par des tests automatiques.
