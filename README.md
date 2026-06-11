# Apymix — API Python Mix

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)

**Apymix** est un framework FastAPI multi-apps conçu pour faire tourner plusieurs APIs et frontends derrière une seule application. Chaque projet (API ou frontend) se déclare via un simple fichier `amx.yaml` à sa racine : Apymix le découvre, le monte, et synchronise son état en base. Plus de copier-coller de boilerplate — vous écrivez votre métier, le framework s'occupe du reste.

> *API Python Mix* : un mix d'APIs, un mix de frontends, dans une seule app FastAPI.

---

## ✨ Fonctionnalités

- **🔌 Auto-discovery** — chaque sous-projet est détecté via `amx.yaml` au démarrage ; pas d'import statique.
- **🚀 FastAPI moderne** — Python 3.14+, async/await partout, SQLModel + Pydantic v2.
- **🔐 Auth JWT intégrée** — bcrypt, refresh tokens, endpoints `/auth/*` prêts à l'emploi.
- **🛠 SQLAdmin back-office** — UI CRUD auto-générée pour les modèles, extensible par projet.
- **🗃 Multi-DB** — SQLite en dev (zéro config), PostgreSQL en prod (asyncpg).
- **📦 Backup / Restore S3** — sauvegarde JSON+gzip vers tout bucket S3-compatible (Scaleway, AWS, MinIO…).
- **🎨 SPA-aware** — `SPAStaticFiles` avec fallback `index.html` automatique, `DevProxy` pour HMR Vite/Quasar en dev.
- **🌐 VHost routing** — un seul process, plusieurs domaines, routage par header `Host`.
- **↪️ Redirect middleware** — règles de redirection stockées en DB, rechargées toutes les 60s.
- **📨 Resend** — helper d'envoi d'emails transactionnels.

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/<votre-org>/apymix.git
cd apymix
uv sync
```

> Prérequis : [uv](https://github.com/astral-sh/uv) (≥ 0.5) et Python 3.14+.

### 2. Configuration

```bash
cp .env.example .env
# Éditer .env (au minimum JWT_SECRET en production)
```

### 3. Lancement en mode standalone

En standalone, Apymix sert sa home page (`/`) et l'admin (`/-/padmin`) :

```bash
uv run apymix --reload
```

- App : http://localhost:8000
- Docs OpenAPI : http://localhost:8000/-/docs
- Admin : http://localhost:8000/-/padmin

C'est utile pour développer le framework lui-même ou pour valider l'installation. Le seed admin se déclenche automatiquement si la DB est vide.

---

## 🧩 Mode workspace : la vraie valeur d'Apymix

Le mode workspace est l'usage principal d'Apymix. Placez le framework à côté d'un ou plusieurs projets `amx.yaml` :

```
my-workspace/
├── apymix/                 # ce repo (framework)
├── my-api/                 # votre API métier
│   ├── amx.yaml            # manifest Apymix
│   ├── pyproject.toml
│   └── my_api/
│       ├── __init__.py
│       ├── app.py          # FastAPI sub-app (exporte `app`)
│       ├── models.py
│       ├── routes.py
│       └── admin.py        # vues SQLAdmin (optionnel)
└── my-ui/                  # votre frontend Vue/Quasar
    ├── amx.yaml
    ├── package.json
    └── dist/spa/           # build Quasar
```

### Exemple d'`amx.yaml` pour une API

```yaml
# my-api/amx.yaml
name: My-API
route: /my
type: api
module: my_api
table_prefix: my_
version: 1.0.0
description: "Mon API métier"
enabled: true
```

### Exemple d'`amx.yaml` pour un frontend

```yaml
# my-ui/amx.yaml
name: My-UI
route: /my
type: static
dist_dir: dist/spa
version: 1.0.0
enabled: true
# dev_port: 9000          # décommenter pour proxy HMR en dev
```

### Lancement

```bash
cd my-workspace/apymix
uv run apymix --reload
```

Apymix scanne le répertoire parent, monte chaque `amx.yaml` actif, et synchronise le registre des apps en base. Au prochain démarrage, les apps sont reconnues automatiquement.

Pour plus de détails, voir [apymix/doc/architecture.md](apymix/doc/architecture.md).

---

## ⚙️ Configuration

Toute la config se fait via des variables d'environnement (ou `.env`). Voir [`.env.example`](.env.example) pour la liste complète. Variables principales :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `ENV` | `development` | `development` ou `production` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | URL SQLAlchemy async |
| `JWT_SECRET` | *(auto-généré en DB)* | Secret JWT — **obligatoire en prod** |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Origines autorisées (séparées par virgules) |
| `AMX_TABLE_PREFIX` | `amx_` | Préfixe des tables système Apymix |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `FORCE_SEED` | `false` | `true` pour reset BDD + seed au démarrage (dev/CI) |

---

## 📚 Documentation

Toute la documentation du framework est dans [`apymix/doc/`](apymix/doc/) :

- [Vision](apymix/doc/vision.md) — objectifs, personas, périmètre
- [Architecture](apymix/doc/architecture.md) — composants, flux, diagrammes
- [API Contract](apymix/doc/api-contract.md) — routes système `/-/*`, auth, health, apps
- [Data Model](apymix/doc/data-model.md) — tables partagées (AppEntry, User, TimestampMixin)
- [Epics](apymix/doc/epics.md) — epics de développement du framework
- [User Stories](apymix/doc/user-stories.md) — user stories détaillées
- [Enablers](apymix/doc/enablers.md) — enablers techniques (infra, CI/CD, sécurité, observabilité)
- [Roadmap](apymix/doc/roadmap.md) — plan de développement

---

## 🐳 Docker

```bash
docker build -t apymix .
docker run -p 8000:8000 --env-file .env apymix
```

Image basée sur `python:3.14-slim`, user non-root (uid 1000), healthcheck sur `/-/health`.

---

## 🧪 Tests

```bash
uv run pytest
```

---

## 🛠 Développement

```bash
# Lint
uv run ruff check apymix/

# Tests
uv run pytest -v

# Rebuild des deps
uv sync --all-packages

# Reset BDD (SQLite dev)
uv run python -m apymix.scripts.reset_db --seed
```

Le projet utilise `uv` pour la gestion des dépendances et `hatchling` comme backend de build.

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour trouver une tâche :

1. Lire [apymix/doc/epics.md](apymix/doc/epics.md) pour la vision produit
2. Lire [apymix/doc/user-stories.md](apymix/doc/user-stories.md) pour les user stories
3. Choisir une US, créer une branche, soumettre une PR

Pour les décisions structurantes, merci d'ouvrir une issue avec un ADR (Architecture Decision Record) avant d'implémenter.

---

## 📄 Licence

[Apache License 2.0](LICENSE) — Copyright 2026 Apymix Contributors.

---

## 🙏 Crédits

- [FastAPI](https://fastapi.tiangolo.com) — framework web
- [SQLModel](https://sqlmodel.tiangolo.com) — ORM + validation
- [SQLAdmin](https://sqladmin.readthedocs.io) — back-office auto-généré
- [Alembic](https://alembic.sqlalchemy.org) — migrations DB
- [Pydantic](https://docs.pydantic.dev) — validation de données
