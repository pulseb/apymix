# Enablers techniques — PAPI

---

## ENB-01 : Scaffolding projet & environnement de développement

**Type :** DevEx
**Objectif :** Mettre en place la structure de fichiers, les dépendances et l'outillage de développement.
**Dépendances :** Aucune

**Critères de done :**
- [x] `pyproject.toml` configuré avec les dépendances (FastAPI, SQLAlchemy, Alembic, Pydantic, uvicorn, etc.)
- [x] Groupe de dépendances `[dev]` (pytest, httpx, ruff, mypy)
- [x] Structure de dossiers créée (`papi/`, `apis/`, `fronts/`, `tests/`, `alembic/`)
- [ ] `.gitignore` configuré pour Python, Node.js, IDE, `.env`
- [ ] `.env.example` avec les variables documentées

---

## ENB-02 : Abstraction base de données multi-moteur

**Type :** Infrastructure
**Objectif :** Permettre l'utilisation de SQLite en développement et PostgreSQL en production avec le même code applicatif.
**Dépendances :** ENB-01

**Critères de done :**
- [x] SQLAlchemy 2.0 async configuré avec session factory
- [x] Moteur déterminé par la variable `DATABASE_URL`
- [x] Dépendance FastAPI `get_db` injectant une session par requête
- [x] Base model déclaratif avec `id`, `created_at`, `updated_at` automatiques
- [ ] Tests passent sur SQLite (in-memory)

---

## ENB-03 : Authentification & autorisation JWT

**Type :** Sécurité
**Objectif :** Sécuriser les endpoints d'administration avec une authentification JWT et/ou un token statique.
**Dépendances :** ENB-01, ENB-02

**Critères de done :**
- [x] Modèle `User` avec email et mot de passe hashé
- [x] Endpoints `/auth/login` et `/auth/refresh`
- [x] Dépendance FastAPI `get_current_user` pour protéger les routes
- [x] Hashage des mots de passe (bcrypt)
- [x] Configuration JWT (secret, durée de vie) via variables d'environnement
- [x] Gestion des rôles (au minimum : admin)
- [x] Token statique (`api_token`) comme alternative au JWT pour intégrations simples

---

## ENB-04 : Conteneurisation Docker

**Type :** Infrastructure
**Objectif :** Produire une image Docker optimisée pour le déploiement.
**Dépendances :** ENB-01

**Critères de done :**
- [x] Dockerfile (multi-stage, python:3.14, uv builder + runtime slim)
- [x] Image basée sur Python 3.14-slim
- [x] Utilisateur non-root dans le conteneur
- [ ] `docker-compose.yml` avec services `papi` + `db` (PostgreSQL)
- [ ] Healthcheck configuré
- [x] `.dockerignore` configuré

---

## ENB-05 : Migrations de schéma Alembic

**Type :** Infrastructure
**Objectif :** Gérer les évolutions de schéma de base de données de manière versionnée.
**Dépendances :** ENB-02

**Critères de done :**
- [ ] Alembic initialisé avec configuration async
- [ ] `alembic.ini` et `env.py` configurés
- [ ] Support SQLite et PostgreSQL
- [ ] Commande `alembic revision --autogenerate` fonctionnelle
- [ ] Migration initiale créée

---

## ENB-06 : Configuration centralisée

**Type :** DevEx
**Objectif :** Centraliser la configuration de l'application via Pydantic Settings.
**Dépendances :** ENB-01

**Critères de done :**
- [x] Classe `Settings` héritant de `BaseSettings` (Pydantic)
- [x] Support fichier `.env` via `env_file`
- [x] Variables : `ENV`, `DEBUG`, `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRATION`, `CORS_ORIGINS`
- [x] Validation des valeurs au démarrage
- [x] Singleton accessible dans toute l'application

---

## ENB-07 : Observabilité minimale

**Type :** Observabilité
**Objectif :** Mettre en place un logging structuré et un endpoint de healthcheck.
**Dépendances :** ENB-01

**Critères de done :**
- [ ] Logging structuré (JSON en prod, lisible en dev)
- [ ] Log de chaque requête (méthode, path, status, durée)
- [ ] Endpoint `GET /health` retournant le statut de l'app et de la BDD
- [ ] Niveau de log configurable via variable d'environnement

---

## ENB-08 : Tests & qualité de code

**Type :** DevEx
**Objectif :** Mettre en place l'infrastructure de tests et les outils de qualité de code.
**Dépendances :** ENB-01, ENB-02

**Critères de done :**
- [ ] pytest configuré avec `pytest.ini` ou `pyproject.toml`
- [ ] httpx `AsyncClient` configuré pour les tests d'API
- [ ] Fixtures de test (app, client, db session in-memory)
- [ ] Ruff configuré pour le linting
- [ ] Au moins un test par endpoint du MVP
